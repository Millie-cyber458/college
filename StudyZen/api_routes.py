"""
StudyZen API Routes
Extended features for community study platform
- Dashboard
- Tasks
- Focus Timer
- Notes
- Exams
- Statistics
- Streak
- Notifications
- Settings
"""

from flask import Blueprint, jsonify, request
from datetime import datetime, date
from study_utils import StudySessionManager, StreakManager, StatisticsManager, NotificationManager
import os
from dotenv import load_dotenv
import mysql.connector

load_dotenv()

# Create blueprint
api_bp = Blueprint('api', __name__, url_prefix='/api')


def get_db_connection():
    """Create a MySQL connection"""
    return mysql.connector.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", "3306")),
        user=os.getenv("DB_USER", "root"),
        password=os.getenv("DB_PASSWORD", ""),
        database=os.getenv("DB_NAME", "studyzen"),
        autocommit=True,
        charset="utf8mb4",
    )


# =====================================================
# DASHBOARD ROUTES
# =====================================================

@api_bp.route('/dashboard', methods=['GET'])
def get_dashboard():
    """Get personalized dashboard data"""
    user_id = request.args.get('user_id')
    if not user_id:
        return jsonify({'error': 'user_id required'}), 400
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Get user info
        cursor.execute("SELECT name, email FROM users WHERE id = %s", (user_id,))
        user = cursor.fetchone()
        
        # Get user's groups
        cursor.execute("""
            SELECT sg.id, sg.group_name
            FROM study_groups sg
            JOIN group_members gm ON sg.id = gm.group_id
            WHERE gm.user_id = %s
        """, (user_id,))
        groups = cursor.fetchall()
        
        # Get upcoming tasks (across all user's groups)
        cursor.execute("""
            SELECT gt.id, gt.title, gt.priority, gt.due_date, 
                   sg.group_name, s.subject_name
            FROM group_tasks gt
            JOIN study_groups sg ON gt.group_id = sg.id
            JOIN group_members gm ON sg.id = gm.group_id
            LEFT JOIN subjects s ON gt.subject_id = s.id
            WHERE gm.user_id = %s AND gt.status IN ('pending', 'in_progress')
            AND gt.due_date >= CURDATE()
            ORDER BY gt.due_date ASC
            LIMIT 10
        """, (user_id,))
        upcoming_tasks = cursor.fetchall()
        
        # Get upcoming exams
        cursor.execute("""
            SELECT e.id, e.title, e.exam_date, e.exam_type,
                   sg.group_name, s.subject_name
            FROM exams e
            JOIN study_groups sg ON e.group_id = sg.id
            JOIN group_members gm ON sg.id = gm.group_id
            LEFT JOIN subjects s ON e.subject_id = s.id
            WHERE gm.user_id = %s AND e.status = 'upcoming'
            AND e.exam_date >= CURDATE()
            ORDER BY e.exam_date ASC
            LIMIT 5
        """, (user_id,))
        upcoming_exams = cursor.fetchall()
        
        # Get today's study time
        today_study_time = StudySessionManager.get_user_study_time_today(cursor, user_id)
        
        # Get study goal
        cursor.execute("SELECT study_goal FROM user_settings WHERE user_id = %s", (user_id,))
        study_goal_result = cursor.fetchone()
        study_goal = study_goal_result[0] if study_goal_result else 120
        
        cursor.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'user': {
                'name': user['name'],
                'email': user['email']
            },
            'greeting': f"Good {'morning' if datetime.now().hour < 12 else 'afternoon'}, {user['name']}! 🌱",
            'today_date': str(date.today()),
            'study_goal': study_goal,
            'today_study_time': today_study_time,
            'groups': groups,
            'upcoming_tasks': upcoming_tasks,
            'upcoming_exams': upcoming_exams,
            'task_count': len(upcoming_tasks),
            'exam_count': len(upcoming_exams)
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# =====================================================
# TASKS ROUTES
# =====================================================

@api_bp.route('/groups/<int:group_id>/tasks', methods=['GET', 'POST'])
def manage_group_tasks(group_id):
    """Get or create tasks for a group"""
    user_id = request.args.get('user_id')
    
    if not user_id:
        return jsonify({'error': 'user_id required'}), 400
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        if request.method == 'GET':
            # Get tasks with optional filters
            status_filter = request.args.get('status')  # pending, in_progress, completed
            subject_id = request.args.get('subject_id')
            priority_filter = request.args.get('priority')
            
            query = """
                SELECT gt.id, gt.title, gt.description, gt.priority, 
                       gt.due_date, gt.due_time, gt.status,
                       s.subject_name, u.name as assigned_to
                FROM group_tasks gt
                LEFT JOIN subjects s ON gt.subject_id = s.id
                LEFT JOIN users u ON gt.assigned_to = u.id
                WHERE gt.group_id = %s
            """
            params = [group_id]
            
            if status_filter:
                query += " AND gt.status = %s"
                params.append(status_filter)
            
            if subject_id:
                query += " AND gt.subject_id = %s"
                params.append(subject_id)
            
            if priority_filter:
                query += " AND gt.priority = %s"
                params.append(priority_filter)
            
            query += " ORDER BY gt.due_date ASC, gt.priority DESC"
            
            cursor.execute(query, params)
            tasks = cursor.fetchall()
            
            # Count completed/pending
            cursor.execute("""
                SELECT status, COUNT(*) as count
                FROM group_tasks
                WHERE group_id = %s
                GROUP BY status
            """, (group_id,))
            
            counts = {}
            for row in cursor.fetchall():
                counts[row['status']] = row['count']
            
            cursor.close()
            conn.close()
            
            return jsonify({
                'success': True,
                'tasks': tasks,
                'counts': counts
            })
        
        elif request.method == 'POST':
            # Create new task
            data = request.json
            
            cursor.execute("""
                INSERT INTO group_tasks 
                (group_id, subject_id, title, description, assigned_by, 
                 assigned_to, priority, due_date, due_time, status)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (group_id, data.get('subject_id'), data['title'],
                  data.get('description'), user_id, data.get('assigned_to'),
                  data.get('priority', 'medium'), data.get('due_date'),
                  data.get('due_time'), 'pending'))
            
            task_id = cursor.lastrowid
            conn.commit()
            cursor.close()
            conn.close()
            
            return jsonify({'success': True, 'task_id': task_id}), 201
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@api_bp.route('/tasks/<int:task_id>', methods=['PUT', 'DELETE'])
def update_task(task_id):
    """Update or delete a task"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        if request.method == 'PUT':
            data = request.json
            
            cursor.execute("""
                UPDATE group_tasks
                SET title = %s, description = %s, status = %s, 
                    priority = %s, due_date = %s, due_time = %s,
                    completed_at = CASE WHEN %s = 'completed' THEN NOW() ELSE NULL END
                WHERE id = %s
            """, (data.get('title'), data.get('description'), data.get('status'),
                  data.get('priority'), data.get('due_date'), data.get('due_time'),
                  data.get('status'), task_id))
            
            conn.commit()
            
            return jsonify({'success': True})
        
        elif request.method == 'DELETE':
            cursor.execute("DELETE FROM group_tasks WHERE id = %s", (task_id,))
            conn.commit()
            
            return jsonify({'success': True})
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()
        conn.close()


# =====================================================
# FOCUS TIMER ROUTES
# =====================================================

@api_bp.route('/sessions/start', methods=['POST'])
def start_study_session():
    """Start a new study session"""
    data = request.json
    user_id = data.get('user_id')
    group_id = data.get('group_id')
    subject_id = data.get('subject_id')
    task_id = data.get('task_id')
    duration = int(data.get('duration', 25))  # Default 25 min Pomodoro
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        session_id = StudySessionManager.create_session(
            cursor, user_id, group_id, subject_id, task_id, 
            duration, duration, 'focus'
        )
        
        conn.commit()
        cursor.close()
        conn.close()
        
        # Update streak
        conn = get_db_connection()
        cursor = conn.cursor()
        StreakManager.update_streak(cursor, user_id, group_id)
        conn.commit()
        cursor.close()
        conn.close()
        
        return jsonify({'success': True, 'session_id': session_id}), 201
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@api_bp.route('/sessions/today', methods=['GET'])
def get_today_sessions():
    """Get all study sessions for user today"""
    user_id = request.args.get('user_id')
    
    if not user_id:
        return jsonify({'error': 'user_id required'}), 400
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        today_time = StudySessionManager.get_user_study_time_today(cursor, user_id)
        
        cursor.execute("""
            SELECT duration_minutes, session_type, started_at
            FROM study_sessions
            WHERE user_id = %s AND DATE(started_at) = CURDATE()
            ORDER BY started_at DESC
        """, (user_id,))
        
        sessions = cursor.fetchall()
        cursor.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'total_study_time': today_time,
            'sessions': sessions
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# =====================================================
# NOTES ROUTES
# =====================================================

@api_bp.route('/groups/<int:group_id>/notes', methods=['GET', 'POST'])
def manage_group_notes(group_id):
    """Get or create notes for a group"""
    user_id = request.args.get('user_id')
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        if request.method == 'GET':
            subject_id = request.args.get('subject_id')
            
            query = """
                SELECT gn.id, gn.title, gn.content, gn.is_pinned,
                       u.name as created_by, gn.created_at, s.subject_name
                FROM group_notes gn
                JOIN users u ON gn.created_by = u.id
                LEFT JOIN subjects s ON gn.subject_id = s.id
                WHERE gn.group_id = %s
            """
            params = [group_id]
            
            if subject_id:
                query += " AND gn.subject_id = %s"
                params.append(subject_id)
            
            query += " ORDER BY gn.is_pinned DESC, gn.created_at DESC"
            
            cursor.execute(query, params)
            notes = cursor.fetchall()
            
            cursor.close()
            conn.close()
            
            return jsonify({'success': True, 'notes': notes})
        
        elif request.method == 'POST':
            data = request.json
            
            cursor.execute("""
                INSERT INTO group_notes
                (group_id, subject_id, channel_id, created_by, title, content)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (group_id, data.get('subject_id'), data.get('channel_id'),
                  user_id, data['title'], data['content']))
            
            note_id = cursor.lastrowid
            conn.commit()
            cursor.close()
            conn.close()
            
            return jsonify({'success': True, 'note_id': note_id}), 201
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# =====================================================
# EXAMS ROUTES
# =====================================================

@api_bp.route('/groups/<int:group_id>/exams', methods=['GET', 'POST'])
def manage_exams(group_id):
    """Get or create exams for a group"""
    user_id = request.args.get('user_id')
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        if request.method == 'GET':
            cursor.execute("""
                SELECT e.id, e.title, e.exam_date, e.exam_time, e.exam_type,
                       e.location, e.description, s.subject_name,
                       DATEDIFF(e.exam_date, CURDATE()) as days_left
                FROM exams e
                LEFT JOIN subjects s ON e.subject_id = s.id
                WHERE e.group_id = %s AND e.status = 'upcoming'
                ORDER BY e.exam_date ASC
            """, (group_id,))
            
            exams = cursor.fetchall()
            
            cursor.close()
            conn.close()
            
            return jsonify({'success': True, 'exams': exams})
        
        elif request.method == 'POST':
            data = request.json
            
            cursor.execute("""
                INSERT INTO exams
                (group_id, subject_id, title, exam_type, exam_date, 
                 exam_time, location, description, created_by, status)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (group_id, data.get('subject_id'), data['title'],
                  data.get('exam_type', 'exam'), data['exam_date'],
                  data.get('exam_time'), data.get('location'),
                  data.get('description'), user_id, 'upcoming'))
            
            exam_id = cursor.lastrowid
            conn.commit()
            cursor.close()
            conn.close()
            
            return jsonify({'success': True, 'exam_id': exam_id}), 201
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# =====================================================
# STATISTICS ROUTES
# =====================================================

@api_bp.route('/statistics/weekly', methods=['GET'])
def get_weekly_statistics():
    """Get weekly study statistics"""
    user_id = request.args.get('user_id')
    group_id = request.args.get('group_id')
    
    if not user_id:
        return jsonify({'error': 'user_id required'}), 400
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        stats = StatisticsManager.get_weekly_stats(cursor, user_id, group_id)
        
        cursor.close()
        conn.close()
        
        return jsonify({'success': True, 'stats': stats})
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# =====================================================
# STREAK ROUTES
# =====================================================

@api_bp.route('/streak', methods=['GET'])
def get_streak():
    """Get user streak"""
    user_id = request.args.get('user_id')
    group_id = request.args.get('group_id')
    
    if not user_id:
        return jsonify({'error': 'user_id required'}), 400
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        streak = StreakManager.get_streak(cursor, user_id, group_id)
        
        cursor.close()
        conn.close()
        
        return jsonify({'success': True, 'streak': streak})
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# =====================================================
# NOTIFICATIONS ROUTES
# =====================================================

@api_bp.route('/notifications', methods=['GET', 'POST'])
def manage_notifications():
    """Get or mark notifications"""
    user_id = request.args.get('user_id')
    
    if not user_id:
        return jsonify({'error': 'user_id required'}), 400
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        if request.method == 'GET':
            notifications = NotificationManager.get_unread_notifications(cursor, user_id)
            
            cursor.close()
            conn.close()
            
            return jsonify({'success': True, 'notifications': notifications})
        
        elif request.method == 'POST':
            data = request.json
            notif_id = data.get('notification_id')
            
            NotificationManager.mark_as_read(cursor, notif_id)
            conn.commit()
            
            cursor.close()
            conn.close()
            
            return jsonify({'success': True})
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# =====================================================
# SETTINGS ROUTES
# =====================================================

@api_bp.route('/settings', methods=['GET', 'PUT'])
def manage_settings():
    """Get or update user settings"""
    user_id = request.args.get('user_id')
    
    if not user_id:
        return jsonify({'error': 'user_id required'}), 400
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        if request.method == 'GET':
            cursor.execute("""
                SELECT theme, notifications_enabled, study_goal_minutes,
                       pomodoro_duration, break_duration
                FROM user_settings
                WHERE user_id = %s
            """, (user_id,))
            
            settings = cursor.fetchone()
            
            cursor.close()
            conn.close()
            
            return jsonify({'success': True, 'settings': settings})
        
        elif request.method == 'PUT':
            data = request.json
            
            cursor.execute("""
                UPDATE user_settings
                SET theme = %s, notifications_enabled = %s,
                    study_goal_minutes = %s, pomodoro_duration = %s
                WHERE user_id = %s
            """, (data.get('theme'), data.get('notifications_enabled'),
                  data.get('study_goal_minutes'), data.get('pomodoro_duration'),
                  user_id))
            
            conn.commit()
            cursor.close()
            conn.close()
            
            return jsonify({'success': True})
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500
