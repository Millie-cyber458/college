"""
StudyZen API Routes - PostgreSQL Edition
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

All routes identify the user from the Flask session (set at Google login),
never from a user_id sent in the URL or request body.
"""

import os
from contextlib import contextmanager
from datetime import datetime, date
from functools import wraps

import psycopg2
from dotenv import load_dotenv
from flask import Blueprint, jsonify, request, session, current_app
from psycopg2.extras import RealDictCursor

from study_utils import (
    StudySessionManager,
    StreakManager,
    StatisticsManager,
    NotificationManager,
)

load_dotenv()

# Create blueprint
api_bp = Blueprint('api', __name__, url_prefix='/api')


# =====================================================
# HELPERS
# =====================================================

def get_db_connection():
    """Create a PostgreSQL connection"""
    conn = psycopg2.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", "5432")),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD", ""),
        dbname=os.getenv("DB_NAME", "studyzen"),
    )
    conn.autocommit = True
    return conn


@contextmanager
def db_cursor(dict_rows=True):
    """Open a cursor and always close the cursor and connection afterwards."""
    conn = get_db_connection()
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor) if dict_rows else conn.cursor()
        try:
            yield cursor
        finally:
            cursor.close()
    finally:
        conn.close()


def api_login_required(view):
    """Return 401 JSON if nobody is logged in."""
    @wraps(view)
    def wrapper(*args, **kwargs):
        if not session.get("user_id"):
            return jsonify({'error': 'login required'}), 401
        return view(*args, **kwargs)
    return wrapper


def current_user_id():
    return session.get("user_id")


def is_group_member(cursor, user_id, group_id):
    cursor.execute(
        "SELECT 1 FROM group_members WHERE user_id = %s AND group_id = %s",
        (user_id, group_id),
    )
    return cursor.fetchone() is not None


def server_error(exc):
    current_app.logger.exception("API error: %s", exc)
    return jsonify({'error': 'Something went wrong'}), 500


# =====================================================
# DASHBOARD ROUTES
# =====================================================

@api_bp.route('/dashboard', methods=['GET'])
@api_login_required
def get_dashboard():
    """Get personalized dashboard data"""
    user_id = current_user_id()

    try:
        with db_cursor() as cursor:
            # Get user info
            cursor.execute("SELECT name, email FROM users WHERE id = %s", (user_id,))
            user = cursor.fetchone()
            if not user:
                return jsonify({'error': 'user not found'}), 404

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
                AND gt.due_date >= CURRENT_DATE
                ORDER BY gt.due_date ASC
                LIMIT 10
            """, (user_id,))
            upcoming_tasks = cursor.fetchall()

            # Get upcoming exams (joins members on the exam's own group)
            cursor.execute("""
                SELECT e.id, e.title, e.exam_date, e.exam_type,
                       sg.group_name, s.subject_name
                FROM exams e
                JOIN study_groups sg ON e.group_id = sg.id
                JOIN group_members gm ON gm.group_id = e.group_id
                LEFT JOIN subjects s ON e.subject_id = s.id
                WHERE gm.user_id = %s AND e.status = 'upcoming'
                AND e.exam_date >= CURRENT_DATE
                ORDER BY e.exam_date ASC
                LIMIT 5
            """, (user_id,))
            upcoming_exams = cursor.fetchall()

            # Get today's study time
            today_study_time = StudySessionManager.get_user_study_time_today(cursor, user_id)

            # Get study goal (column is study_goal_minutes)
            cursor.execute(
                "SELECT study_goal_minutes FROM user_settings WHERE user_id = %s",
                (user_id,),
            )
            study_goal_result = cursor.fetchone()
            study_goal = study_goal_result['study_goal_minutes'] if study_goal_result else 120

        hour = datetime.now().hour
        part_of_day = 'morning' if hour < 12 else 'afternoon' if hour < 18 else 'evening'

        return jsonify({
            'success': True,
            'user': {
                'name': user['name'],
                'email': user['email']
            },
            'greeting': f"Good {part_of_day}, {user['name']}! 🌱",
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
        return server_error(e)


# =====================================================
# TASKS ROUTES
# =====================================================

@api_bp.route('/groups/<int:group_id>/tasks', methods=['GET', 'POST'])
@api_login_required
def manage_group_tasks(group_id):
    """Get or create tasks for a group"""
    user_id = current_user_id()

    try:
        with db_cursor() as cursor:
            if not is_group_member(cursor, user_id, group_id):
                return jsonify({'error': 'not a member of this group'}), 403

            if request.method == 'GET':
                status_filter = request.args.get('status')
                subject_id = request.args.get('subject_id')
                priority_filter = request.args.get('priority')

                # due_time cast to text so it can be turned into JSON
                query = """
                    SELECT gt.id, gt.title, gt.description, gt.priority,
                           gt.due_date, gt.due_time::text AS due_time, gt.status,
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

                # sort priority by meaning (high first), not alphabetically
                query += """
                    ORDER BY gt.due_date ASC,
                             CASE gt.priority WHEN 'high' THEN 1 WHEN 'medium' THEN 2 ELSE 3 END
                """

                cursor.execute(query, params)
                tasks = cursor.fetchall()

                cursor.execute("""
                    SELECT status, COUNT(*) as count
                    FROM group_tasks
                    WHERE group_id = %s
                    GROUP BY status
                """, (group_id,))
                counts = {row['status']: row['count'] for row in cursor.fetchall()}

                return jsonify({
                    'success': True,
                    'tasks': tasks,
                    'counts': counts
                })

            # POST
            data = request.get_json(silent=True) or {}
            title = (data.get('title') or '').strip()
            if not title:
                return jsonify({'error': 'title required'}), 400

            cursor.execute("""
                INSERT INTO group_tasks
                (group_id, subject_id, title, description, assigned_by,
                 assigned_to, priority, due_date, due_time, status)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (group_id, data.get('subject_id'), title,
                  data.get('description'), user_id, data.get('assigned_to'),
                  data.get('priority', 'medium'), data.get('due_date'),
                  data.get('due_time'), 'pending'))

            task_id = cursor.fetchone()['id']
            return jsonify({'success': True, 'task_id': task_id}), 201

    except Exception as e:
        return server_error(e)


@api_bp.route('/tasks/<int:task_id>', methods=['PUT', 'DELETE'])
@api_login_required
def update_task(task_id):
    """Update or delete a task"""
    user_id = current_user_id()

    try:
        with db_cursor() as cursor:
            cursor.execute("SELECT group_id FROM group_tasks WHERE id = %s", (task_id,))
            row = cursor.fetchone()
            if not row:
                return jsonify({'error': 'task not found'}), 404
            if not is_group_member(cursor, user_id, row['group_id']):
                return jsonify({'error': 'not a member of this group'}), 403

            if request.method == 'PUT':
                data = request.get_json(silent=True) or {}

                # fields not sent are left unchanged instead of set to NULL
                cursor.execute("""
                    UPDATE group_tasks
                    SET title = COALESCE(%s, title),
                        description = COALESCE(%s, description),
                        status = COALESCE(%s, status),
                        priority = COALESCE(%s, priority),
                        due_date = COALESCE(%s, due_date),
                        due_time = COALESCE(%s, due_time),
                        completed_at = CASE
                            WHEN COALESCE(%s, status) = 'completed'
                            THEN COALESCE(completed_at, NOW())
                            ELSE NULL
                        END,
                        updated_at = NOW()
                    WHERE id = %s
                """, (data.get('title'), data.get('description'), data.get('status'),
                      data.get('priority'), data.get('due_date'), data.get('due_time'),
                      data.get('status'), task_id))
                return jsonify({'success': True})

            # DELETE
            cursor.execute("DELETE FROM group_tasks WHERE id = %s", (task_id,))
            return jsonify({'success': True})

    except Exception as e:
        return server_error(e)


# =====================================================
# FOCUS TIMER ROUTES
# =====================================================

@api_bp.route('/sessions/start', methods=['POST'])
@api_login_required
def start_study_session():
    """Start a new study session"""
    user_id = current_user_id()
    data = request.get_json(silent=True) or {}
    group_id = data.get('group_id')
    subject_id = data.get('subject_id')
    task_id = data.get('task_id')

    try:
        duration = int(data.get('duration', 25))
    except (TypeError, ValueError):
        return jsonify({'error': 'duration must be a number'}), 400
    if not 1 <= duration <= 240:
        return jsonify({'error': 'duration must be between 1 and 240 minutes'}), 400

    try:
        # CHANGED: dict_rows=False -> default (dict cursor), since
        # StudySessionManager.create_session reads cursor.fetchone()['id']
        with db_cursor() as cursor:
            if group_id and not is_group_member(cursor, user_id, group_id):
                return jsonify({'error': 'not a member of this group'}), 403

            session_id = StudySessionManager.create_session(
                cursor, user_id, group_id, subject_id, task_id,
                duration, duration, 'focus'
            )

            StreakManager.update_streak(cursor, user_id, group_id)
            # ADDED: without this, daily_statistics never gets populated,
            # so the dashboard's streak/tasks-completed cards and weekly
            # chart would always show empty data.
            StatisticsManager.update_daily_stats(cursor, user_id, group_id)

        return jsonify({'success': True, 'session_id': session_id}), 201

    except Exception as e:
        return server_error(e)


@api_bp.route('/sessions/today', methods=['GET'])
@api_login_required
def get_today_sessions():
    """Get all study sessions for user today"""
    user_id = current_user_id()

    try:
        with db_cursor() as cursor:
            today_time = StudySessionManager.get_user_study_time_today(cursor, user_id)

            cursor.execute("""
                SELECT duration_minutes, session_type, started_at
                FROM study_sessions
                WHERE user_id = %s AND started_at::date = CURRENT_DATE
                ORDER BY started_at DESC
            """, (user_id,))
            sessions = cursor.fetchall()

        return jsonify({
            'success': True,
            'total_study_time': today_time,
            'sessions': sessions
        })

    except Exception as e:
        return server_error(e)


# =====================================================
# NOTES ROUTES
# =====================================================

@api_bp.route('/groups/<int:group_id>/notes', methods=['GET', 'POST'])
@api_login_required
def manage_group_notes(group_id):
    """Get or create notes for a group"""
    user_id = current_user_id()

    try:
        with db_cursor() as cursor:
            if not is_group_member(cursor, user_id, group_id):
                return jsonify({'error': 'not a member of this group'}), 403

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
                return jsonify({'success': True, 'notes': notes})

            # POST
            data = request.get_json(silent=True) or {}
            title = (data.get('title') or '').strip()
            content = (data.get('content') or '').strip()
            if not title or not content:
                return jsonify({'error': 'title and content required'}), 400

            cursor.execute("""
                INSERT INTO group_notes
                (group_id, subject_id, channel_id, created_by, title, content)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (group_id, data.get('subject_id'), data.get('channel_id'),
                  user_id, title, content))

            note_id = cursor.fetchone()['id']
            return jsonify({'success': True, 'note_id': note_id}), 201

    except Exception as e:
        return server_error(e)


# =====================================================
# EXAMS ROUTES
# =====================================================

@api_bp.route('/groups/<int:group_id>/exams', methods=['GET', 'POST'])
@api_login_required
def manage_exams(group_id):
    """Get or create exams for a group"""
    user_id = current_user_id()

    try:
        with db_cursor() as cursor:
            if not is_group_member(cursor, user_id, group_id):
                return jsonify({'error': 'not a member of this group'}), 403

            if request.method == 'GET':
                # exam_time cast to text so it can be turned into JSON
                cursor.execute("""
                    SELECT e.id, e.title, e.exam_date, e.exam_time::text AS exam_time,
                           e.exam_type, e.location, e.description, s.subject_name,
                           (e.exam_date - CURRENT_DATE) as days_left
                    FROM exams e
                    LEFT JOIN subjects s ON e.subject_id = s.id
                    WHERE e.group_id = %s AND e.status = 'upcoming'
                    ORDER BY e.exam_date ASC
                """, (group_id,))
                exams = cursor.fetchall()
                return jsonify({'success': True, 'exams': exams})

            # POST
            data = request.get_json(silent=True) or {}
            title = (data.get('title') or '').strip()
            if not title or not data.get('exam_date'):
                return jsonify({'error': 'title and exam_date required'}), 400

            cursor.execute("""
                INSERT INTO exams
                (group_id, subject_id, title, exam_type, exam_date,
                 exam_time, location, description, created_by, status)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (group_id, data.get('subject_id'), title,
                  data.get('exam_type', 'exam'), data['exam_date'],
                  data.get('exam_time'), data.get('location'),
                  data.get('description'), user_id, 'upcoming'))

            exam_id = cursor.fetchone()['id']
            return jsonify({'success': True, 'exam_id': exam_id}), 201

    except Exception as e:
        return server_error(e)


# =====================================================
# STATISTICS ROUTES
# =====================================================

@api_bp.route('/statistics/weekly', methods=['GET'])
@api_login_required
def get_weekly_statistics():
    """Get weekly study statistics"""
    user_id = current_user_id()
    group_id = request.args.get('group_id')

    try:
        with db_cursor() as cursor:
            stats = StatisticsManager.get_weekly_stats(cursor, user_id, group_id)
        return jsonify({'success': True, 'stats': stats})

    except Exception as e:
        return server_error(e)


# =====================================================
# STREAK ROUTES
# =====================================================

@api_bp.route('/streak', methods=['GET'])
@api_login_required
def get_streak():
    """Get user streak"""
    user_id = current_user_id()
    group_id = request.args.get('group_id')

    try:
        with db_cursor() as cursor:
            streak = StreakManager.get_streak(cursor, user_id, group_id)
        return jsonify({'success': True, 'streak': streak})

    except Exception as e:
        return server_error(e)


# =====================================================
# NOTIFICATIONS ROUTES
# =====================================================

@api_bp.route('/notifications', methods=['GET', 'POST'])
@api_login_required
def manage_notifications():
    """Get or mark notifications"""
    user_id = current_user_id()

    try:
        with db_cursor() as cursor:
            if request.method == 'GET':
                notifications = NotificationManager.get_unread_notifications(cursor, user_id)
                return jsonify({'success': True, 'notifications': notifications})

            # POST: mark one of the user's own notifications as read
            data = request.get_json(silent=True) or {}
            notif_id = data.get('notification_id')
            if not notif_id:
                return jsonify({'error': 'notification_id required'}), 400

            cursor.execute(
                "UPDATE notifications SET is_read = TRUE WHERE id = %s AND user_id = %s",
                (notif_id, user_id),
            )
            return jsonify({'success': True})

    except Exception as e:
        return server_error(e)


# =====================================================
# SETTINGS ROUTES
# =====================================================

DEFAULT_SETTINGS = {
    'theme': 'light',
    'notifications_enabled': True,
    'study_goal_minutes': 120,
    'pomodoro_duration': 25,
    'break_duration': 5,
}


@api_bp.route('/settings', methods=['GET', 'PUT'])
@api_login_required
def manage_settings():
    """Get or update user settings"""
    user_id = current_user_id()

    try:
        with db_cursor() as cursor:
            if request.method == 'GET':
                cursor.execute("""
                    SELECT theme, notifications_enabled, study_goal_minutes,
                           pomodoro_duration, break_duration
                    FROM user_settings
                    WHERE user_id = %s
                """, (user_id,))
                settings = cursor.fetchone() or DEFAULT_SETTINGS
                return jsonify({'success': True, 'settings': settings})

            # PUT: create the settings row if it doesn't exist yet, otherwise update it
            data = request.get_json(silent=True) or {}
            theme = data.get('theme')
            notif = data.get('notifications_enabled')
            goal = data.get('study_goal_minutes')
            pomodoro = data.get('pomodoro_duration')

            cursor.execute("""
                INSERT INTO user_settings
                    (user_id, theme, notifications_enabled, study_goal_minutes, pomodoro_duration)
                VALUES (%s, COALESCE(%s, 'light'), COALESCE(%s, TRUE),
                        COALESCE(%s, 120), COALESCE(%s, 25))
                ON CONFLICT (user_id) DO UPDATE SET
                    theme = COALESCE(%s, user_settings.theme),
                    notifications_enabled = COALESCE(%s, user_settings.notifications_enabled),
                    study_goal_minutes = COALESCE(%s, user_settings.study_goal_minutes),
                    pomodoro_duration = COALESCE(%s, user_settings.pomodoro_duration),
                    updated_at = NOW()
            """, (user_id, theme, notif, goal, pomodoro,
                  theme, notif, goal, pomodoro))

            return jsonify({'success': True})

    except Exception as e:
        return server_error(e)