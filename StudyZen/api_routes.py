"""
StudyZen API Routes - PostgreSQL Edition
JSON endpoints used by the profile page:
- /api/dashboard          today's study time and daily goal
- /api/sessions/start     save a completed focus session
- /api/statistics/weekly  last seven days of study time
- /api/streak             current and best streak

All routes identify the user from the Flask session (set at Google login),
never from a user_id sent in the URL or request body.
"""

import os
from contextlib import contextmanager
from datetime import date
from functools import wraps

import psycopg2
from dotenv import load_dotenv
from flask import Blueprint, jsonify, request, session, current_app
from psycopg2.extras import RealDictCursor

from study_utils import (
    StudySessionManager,
    StreakManager,
    StatisticsManager,
)

load_dotenv()

# Create blueprint
api_bp = Blueprint('api', __name__, url_prefix='/api')



# HELPERS


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



# DASHBOARD ROUTE (used by the profile page)

@api_bp.route('/dashboard', methods=['GET'])
@api_login_required
def get_dashboard():
    """Today's study time and the daily study goal of the logged-in user."""
    user_id = current_user_id()

    try:
        with db_cursor() as cursor:
            today_study_time = StudySessionManager.get_user_study_time_today(cursor, user_id)

            cursor.execute(
                "SELECT study_goal_minutes FROM user_settings WHERE user_id = %s",
                (user_id,),
            )
            row = cursor.fetchone()
            study_goal = row['study_goal_minutes'] if row else 120

        return jsonify({
            'success': True,
            'today_date': str(date.today()),
            'study_goal': study_goal,
            'today_study_time': today_study_time,
        })
    except Exception as e:
        return server_error(e)



# FOCUS TIMER ROUTES


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
        
        with db_cursor() as cursor:
            if group_id and not is_group_member(cursor, user_id, group_id):
                return jsonify({'error': 'not a member of this group'}), 403

            session_id = StudySessionManager.create_session(
                cursor, user_id, group_id, subject_id, task_id,
                duration, duration, 'focus'
            )

            StreakManager.update_streak(cursor, user_id, group_id)
            StatisticsManager.update_daily_stats(cursor, user_id, group_id)

        return jsonify({'success': True, 'session_id': session_id}), 201

    except Exception as e:
        return server_error(e)

# STATISTICS ROUTES

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


# STREAK ROUTES

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