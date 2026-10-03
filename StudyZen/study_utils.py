"""
StudyZen Utility Functions
- Study session tracking
- Streak calculation
- Statistics aggregation
- Notification helpers

"""

from datetime import date, timedelta


class StudySessionManager:
    """Manage study sessions and focus timer"""

    @staticmethod
    def create_session(cursor, user_id, group_id, subject_id, task_id,
                        duration_minutes, planned_duration, session_type='focus'):
        """Create a new study session. Returns the new session's id."""
        now = date.today()
        from datetime import datetime, timedelta as _td
        started_at = datetime.now()
        ended_at = started_at + _td(minutes=duration_minutes)

        cursor.execute("""
            INSERT INTO study_sessions
            (user_id, group_id, subject_id, task_id, session_type,
             duration_minutes, planned_duration_minutes, started_at, ended_at, completed)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (user_id, group_id, subject_id, task_id, session_type,
              duration_minutes, planned_duration, started_at, ended_at, True))

        return cursor.fetchone()['id']

    @staticmethod
    def get_user_study_time_today(cursor, user_id):
        """Get total study time (minutes) for user today."""
        today = date.today()
        cursor.execute("""
            SELECT COALESCE(SUM(duration_minutes), 0) AS total_time
            FROM study_sessions
            WHERE user_id = %s AND started_at::date = %s AND session_type = 'focus'
        """, (user_id, today))

        result = cursor.fetchone()
        return result['total_time'] if result else 0

    @staticmethod
    def get_group_study_time_this_week(cursor, group_id):
        """Get total study time (minutes) for group this week."""
        start_date = date.today() - timedelta(days=date.today().weekday())

        cursor.execute("""
            SELECT COALESCE(SUM(duration_minutes), 0) AS total_time
            FROM study_sessions
            WHERE group_id = %s AND started_at::date >= %s AND session_type = 'focus'
        """, (group_id, start_date))

        result = cursor.fetchone()
        return result['total_time'] if result else 0


class StreakManager:
    """Manage study streaks"""

    @staticmethod
    def update_streak(cursor, user_id, group_id=None):
        """Update user streak if they had a study session today."""
        today = date.today()

        cursor.execute("""
            SELECT COUNT(*) AS count
            FROM study_sessions
            WHERE user_id = %s AND started_at::date = %s
            AND session_type = 'focus'
        """, (user_id, today))

        if cursor.fetchone()['count'] == 0:
            return False  # No study today

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
            current_streak = streak_record['current_streak']
            last_study_date = streak_record['last_study_date']

            if last_study_date == today:
                return True  # Already counted for today
            elif last_study_date == today - timedelta(days=1):
                current_streak += 1
            else:
                current_streak = 1

            # FIXED: group_id condition is now built safely instead of
            # splicing a raw string fragment into the query as a parameter.
            if group_id:
                cursor.execute("""
                    UPDATE study_streaks
                    SET current_streak = %s,
                        last_study_date = %s,
                        max_streak = GREATEST(max_streak, %s)
                    WHERE user_id = %s AND group_id = %s
                """, (current_streak, today, current_streak, user_id, group_id))
            else:
                cursor.execute("""
                    UPDATE study_streaks
                    SET current_streak = %s,
                        last_study_date = %s,
                        max_streak = GREATEST(max_streak, %s)
                    WHERE user_id = %s AND group_id IS NULL
                """, (current_streak, today, current_streak, user_id))
        else:
            cursor.execute("""
                INSERT INTO study_streaks
                (user_id, group_id, current_streak, max_streak, last_study_date)
                VALUES (%s, %s, %s, %s, %s)
            """, (user_id, group_id, 1, 1, today))

        return True

    @staticmethod
    def get_streak(cursor, user_id, group_id=None):
        """Get current streak for user."""
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
                'current': result['current_streak'],
                'max': result['max_streak'],
                'last_date': str(result['last_study_date']) if result['last_study_date'] else None
            }
        return {'current': 0, 'max': 0, 'last_date': None}


class StatisticsManager:
    """Manage user and group statistics"""

    @staticmethod
    def update_daily_stats(cursor, user_id, group_id=None):
        """Update or create today's daily statistics row for this user (+ group)."""
        today = date.today()

        cursor.execute("""
            SELECT COALESCE(SUM(duration_minutes), 0) AS total_study_time
            FROM study_sessions
            WHERE user_id = %s AND started_at::date = %s
            AND session_type = 'focus'
        """, (user_id, today))
        total_study_time = cursor.fetchone()['total_study_time']

        cursor.execute("""
            SELECT COUNT(*) AS tasks_completed FROM group_tasks
            WHERE status = 'completed' AND assigned_to = %s
            AND completed_at::date = %s
        """, (user_id, today))
        tasks_completed = cursor.fetchone()['tasks_completed']

        cursor.execute("""
            SELECT COUNT(*) AS tasks_pending FROM group_tasks
            WHERE status IN ('pending', 'in_progress') AND assigned_to = %s
        """, (user_id,))
        tasks_pending = cursor.fetchone()['tasks_pending']

        had_session = total_study_time > 0

        # FIXED: MySQL's "ON DUPLICATE KEY UPDATE" replaced with Postgres'
        # "ON CONFLICT ... DO UPDATE". Note: Postgres treats NULL group_id
        # values as distinct from each other, so this only dedupes rows
        # where group_id is an actual group. If you also track a
        # group_id-less (personal) daily stat per user, that case needs
        # a partial unique index to dedupe correctly — ask if you want
        # that added.
        if group_id is not None:
            cursor.execute("""
                INSERT INTO daily_statistics
                (user_id, group_id, date, total_study_time, tasks_completed,
                 tasks_pending, had_study_session)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (user_id, group_id, date) DO UPDATE SET
                    total_study_time = EXCLUDED.total_study_time,
                    tasks_completed = EXCLUDED.tasks_completed,
                    tasks_pending = EXCLUDED.tasks_pending,
                    had_study_session = EXCLUDED.had_study_session
            """, (user_id, group_id, today, total_study_time, tasks_completed,
                  tasks_pending, had_session))
        else:
            cursor.execute("""
                SELECT id FROM daily_statistics
                WHERE user_id = %s AND group_id IS NULL AND date = %s
            """, (user_id, today))
            existing = cursor.fetchone()
            if existing:
                cursor.execute("""
                    UPDATE daily_statistics
                    SET total_study_time = %s,
                        tasks_completed = %s,
                        tasks_pending = %s,
                        had_study_session = %s
                    WHERE id = %s
                """, (total_study_time, tasks_completed, tasks_pending,
                      had_session, existing['id']))
            else:
                cursor.execute("""
                    INSERT INTO daily_statistics
                    (user_id, group_id, date, total_study_time, tasks_completed,
                     tasks_pending, had_study_session)
                    VALUES (%s, NULL, %s, %s, %s, %s, %s)
                """, (user_id, today, total_study_time, tasks_completed,
                      tasks_pending, had_session))

    @staticmethod
    def get_weekly_stats(cursor, user_id, group_id=None):
        """Get statistics for the past 7 days."""
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
                'date': str(row['date']),
                'study_time': row['total_study_time'],
                'tasks_completed': row['tasks_completed']
            })

        return stats


class NotificationManager:
    """Manage notifications"""

    @staticmethod
    def create_notification(cursor, user_id, group_id, notification_type,
                             title, message, related_id=None, action_url=None):
        """Create a notification."""
        cursor.execute("""
            INSERT INTO notifications
            (user_id, group_id, notification_type, title, message, related_id, action_url)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (user_id, group_id, notification_type, title, message, related_id, action_url))

    @staticmethod
    def get_unread_notifications(cursor, user_id, limit=10):
        """Get unread notifications."""
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
                'id': row['id'],
                'group_id': row['group_id'],
                'type': row['notification_type'],
                'title': row['title'],
                'message': row['message'],
                'created_at': str(row['created_at']),
                'action_url': row['action_url']
            })

        return notifications

    @staticmethod
    def mark_as_read(cursor, notification_id):
        """Mark notification as read."""
        cursor.execute("""
            UPDATE notifications SET is_read = TRUE WHERE id = %s
        """, (notification_id,))