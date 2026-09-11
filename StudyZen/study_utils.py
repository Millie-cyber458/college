"""
StudyZen Utility Functions
- Study session tracking
- Streak calculation
- Statistics aggregation
- Notification helpers
"""

from datetime import datetime, timedelta, date
import json

class StudySessionManager:
    """Manage study sessions and focus timer"""
    
    @staticmethod
    def create_session(cursor, user_id, group_id, subject_id, task_id, 
                       duration_minutes, planned_duration, session_type='focus'):
        """Create a new study session"""
        now = datetime.now()
        end_time = now + timedelta(minutes=duration_minutes)
        
        cursor.execute("""
            INSERT INTO study_sessions 
            (user_id, group_id, subject_id, task_id, session_type, 
             duration_minutes, planned_duration_minutes, started_at, ended_at, completed)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (user_id, group_id, subject_id, task_id, session_type, 
              duration_minutes, planned_duration, now, end_time, True))
        
        return cursor.lastrowid
    
    @staticmethod
    def get_user_study_time_today(cursor, user_id):
        """Get total study time for user today"""
        today = date.today()
        cursor.execute("""
            SELECT SUM(duration_minutes) as total_time
            FROM study_sessions
            WHERE user_id = %s AND DATE(started_at) = %s AND session_type = 'focus'
        """, (user_id, today))
        
        result = cursor.fetchone()
        return result[0] if result[0] else 0
    
    @staticmethod
    def get_group_study_time_this_week(cursor, group_id):
        """Get total study time for group this week"""
        start_date = date.today() - timedelta(days=date.today().weekday())
        
        cursor.execute("""
            SELECT SUM(duration_minutes) as total_time
            FROM study_sessions
            WHERE group_id = %s AND DATE(started_at) >= %s AND session_type = 'focus'
        """, (group_id, start_date))
        
        result = cursor.fetchone()
        return result[0] if result[0] else 0


class StreakManager:
    """Manage study streaks"""
    
    @staticmethod
    def update_streak(cursor, user_id, group_id=None):
        """Update user streak if they had a study session today"""
        today = date.today()
        
        # Check if user had study session today
        cursor.execute("""
            SELECT COUNT(*) as count
            FROM study_sessions
            WHERE user_id = %s AND DATE(started_at) = %s 
            AND session_type = 'focus'
        """, (user_id, today))
        
        if cursor.fetchone()[0] == 0:
            return False  # No study today
        
        # Determine streak key
        if group_id:
            cursor.execute("""
                SELECT id, current_streak, last_study_date
                FROM study_streaks
                WHERE user_id = %s AND group_id = %s
            """, (user_id, group_id))
        else:
            cursor.execute("""
                SELECT id, current_streak, last_study_date
                FROM study_streaks
                WHERE user_id = %s AND group_id IS NULL
            """, (user_id,))
        
        streak_record = cursor.fetchone()
        
        if streak_record:
            current_streak = streak_record[1]
            last_study_date = streak_record[2]
            
            if last_study_date == today:
                return True  # Already counted for today
            elif last_study_date == today - timedelta(days=1):
                # Continue streak
                current_streak += 1
            else:
                # Streak broken, restart
                current_streak = 1
            
            # Update streak
            cursor.execute("""
                UPDATE study_streaks
                SET current_streak = %s, 
                    last_study_date = %s,
                    max_streak = GREATEST(max_streak, %s)
                WHERE user_id = %s AND group_id %s
            """, (current_streak, today, current_streak, user_id, 
                  f"= {group_id}" if group_id else "IS NULL"))
        else:
            # Create new streak
            cursor.execute("""
                INSERT INTO study_streaks 
                (user_id, group_id, current_streak, max_streak, last_study_date)
                VALUES (%s, %s, %s, %s, %s)
            """, (user_id, group_id, 1, 1, today))
        
        return True
    
    @staticmethod
    def get_streak(cursor, user_id, group_id=None):
        """Get current streak for user"""
        if group_id:
            cursor.execute("""
                SELECT current_streak, max_streak, last_study_date
                FROM study_streaks
                WHERE user_id = %s AND group_id = %s
            """, (user_id, group_id))
        else:
            cursor.execute("""
                SELECT current_streak, max_streak, last_study_date
                FROM study_streaks
                WHERE user_id = %s AND group_id IS NULL
            """, (user_id,))
        
        result = cursor.fetchone()
        if result:
            return {
                'current': result[0],
                'max': result[1],
                'last_date': str(result[2]) if result[2] else None
            }
        return {'current': 0, 'max': 0, 'last_date': None}


class StatisticsManager:
    """Manage user and group statistics"""
    
    @staticmethod
    def update_daily_stats(cursor, user_id, group_id=None):
        """Update or create daily statistics"""
        today = date.today()
        
        # Get study time for today
        cursor.execute("""
            SELECT SUM(duration_minutes)
            FROM study_sessions
            WHERE user_id = %s AND DATE(started_at) = %s 
            AND session_type = 'focus'
        """, (user_id, today))
        
        total_study_time = cursor.fetchone()[0] or 0
        
        # Get completed tasks
        cursor.execute("""
            SELECT COUNT(*) FROM group_tasks
            WHERE status = 'completed' AND assigned_to = %s 
            AND DATE(completed_at) = %s
        """, (user_id, today))
        
        tasks_completed = cursor.fetchone()[0]
        
        # Get pending tasks
        cursor.execute("""
            SELECT COUNT(*) FROM group_tasks
            WHERE status IN ('pending', 'in_progress') AND assigned_to = %s
        """, (user_id,))
        
        tasks_pending = cursor.fetchone()[0]
        
        # Check if had study session
        had_session = total_study_time > 0
        
        # Insert or update
        cursor.execute("""
            INSERT INTO daily_statistics 
            (user_id, group_id, date, total_study_time, tasks_completed, 
             tasks_pending, had_study_session)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                total_study_time = %s,
                tasks_completed = %s,
                tasks_pending = %s,
                had_study_session = %s
        """, (user_id, group_id, today, total_study_time, tasks_completed,
              tasks_pending, had_session, total_study_time, tasks_completed,
              tasks_pending, had_session))
    
    @staticmethod
    def get_weekly_stats(cursor, user_id, group_id=None):
        """Get statistics for the past 7 days"""
        start_date = date.today() - timedelta(days=6)
        
        if group_id:
            cursor.execute("""
                SELECT date, total_study_time, tasks_completed
                FROM daily_statistics
                WHERE user_id = %s AND group_id = %s 
                AND date >= %s
                ORDER BY date ASC
            """, (user_id, group_id, start_date))
        else:
            cursor.execute("""
                SELECT date, total_study_time, tasks_completed
                FROM daily_statistics
                WHERE user_id = %s AND date >= %s
                ORDER BY date ASC
            """, (user_id, start_date))
        
        stats = []
        for row in cursor.fetchall():
            stats.append({
                'date': str(row[0]),
                'study_time': row[1],
                'tasks_completed': row[2]
            })
        
        return stats


class NotificationManager:
    """Manage notifications"""
    
    @staticmethod
    def create_notification(cursor, user_id, group_id, notification_type, 
                           title, message, related_id=None, action_url=None):
        """Create a notification"""
        cursor.execute("""
            INSERT INTO notifications
            (user_id, group_id, notification_type, title, message, related_id, action_url)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (user_id, group_id, notification_type, title, message, related_id, action_url))
    
    @staticmethod
    def get_unread_notifications(cursor, user_id, limit=10):
        """Get unread notifications"""
        cursor.execute("""
            SELECT id, group_id, notification_type, title, message, created_at, action_url
            FROM notifications
            WHERE user_id = %s AND is_read = FALSE
            ORDER BY created_at DESC
            LIMIT %s
        """, (user_id, limit))
        
        notifications = []
        for row in cursor.fetchall():
            notifications.append({
                'id': row[0],
                'group_id': row[1],
                'type': row[2],
                'title': row[3],
                'message': row[4],
                'created_at': str(row[5]),
                'action_url': row[6]
            })
        
        return notifications
    
    @staticmethod
    def mark_as_read(cursor, notification_id):
        """Mark notification as read"""
        cursor.execute("""
            UPDATE notifications SET is_read = TRUE WHERE id = %s
        """, (notification_id,))
