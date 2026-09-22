import os
from flask import Flask, redirect, render_template, request, session, url_for
from authlib.integrations.flask_client import OAuth
from dotenv import load_dotenv
import psycopg2
import psycopg2.extras
from api_routes import api_bp
from study_utils import StudySessionManager, StreakManager, StatisticsManager

# Load environment variables from .env
load_dotenv()

# Allow OAuth over plain HTTP for local development only.
# NEVER set this in production — real deployments must use HTTPS.
os.environ.setdefault("AUTHLIB_INSECURE_TRANSPORT", "1")


def get_db_connection():
    """Create a PostgreSQL connection using values from the .env file."""
    return psycopg2.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=os.getenv("DB_PORT", "5432"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD", ""),
        dbname=os.getenv("DB_NAME", "studyzen"),
    )


def initialize_database():
    """Initialize database tables for Discord-like features."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Create channels table if it doesn't exist
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS channels (
                id SERIAL PRIMARY KEY,
                group_id INT NOT NULL,
                channel_name VARCHAR(255) NOT NULL,
                description TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (group_id) REFERENCES study_groups(id) ON DELETE CASCADE
            )
        """)

        # Create messages table if it doesn't exist
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id SERIAL PRIMARY KEY,
                channel_id INT NOT NULL,
                user_id INT NOT NULL,
                content TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (channel_id) REFERENCES channels(id) ON DELETE CASCADE,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)

        # Add role column to group_members if it doesn't exist
        cursor.execute("""
            ALTER TABLE group_members
            ADD COLUMN IF NOT EXISTS role VARCHAR(20) DEFAULT 'member'
        """)

        # Insert default channels for existing groups if they don't exist
        # Requires a UNIQUE constraint on (group_id, channel_name) for ON CONFLICT to work.
        cursor.execute("""
            INSERT INTO channels (group_id, channel_name, description) VALUES
            (1, 'general', 'General discussion for software development'),
            (1, 'projects', 'Share and review programming projects'),
            (1, 'resources', 'Useful tutorials, documentation and tools'),
            (2, 'general', 'Math homework and concept discussions'),
            (2, 'problems', 'Problem solving and exercises'),
            (3, 'general', 'Science discussions and experiments'),
            (3, 'research', 'Share research papers and findings'),
            (4, 'general', 'Geography discussions and map sharing'),
            (5, 'general', 'English literature and writing discussions'),
            (5, 'writing', 'Share your writing and get feedback'),
            (6, 'general', 'Creative ideas and inspiration sharing'),
            (6, 'artwork', 'Share and critique artwork and designs')
            ON CONFLICT (group_id, channel_name) DO NOTHING
        """)

        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"Database initialization: {str(e)}")


app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "replace-with-a-secure-secret")
app.config["SERVER_NAME"] = "localhost:5001"

oauth = OAuth(app)
oauth.register(
    name="google",
    client_id=os.getenv("GOOGLE_CLIENT_ID"),
    client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={"scope": "openid email profile"},
)


# Register API Blueprint
app.register_blueprint(api_bp)

# Initialize database tables
initialize_database()


def get_current_user():
    """Fetch the currently logged in user from session and PostgreSQL."""
    user_id = session.get("user_id")
    if not user_id:
        return None

    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
    user = cursor.fetchone()
    cursor.close()
    conn.close()
    return user


def create_or_get_user(user_info):
    """Create a new user record or return an existing one from Google data."""
    google_id = user_info.get("sub")
    name = user_info.get("name") or "Student"
    email = user_info.get("email")
    profile_picture = user_info.get("picture") or ""

    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cursor.execute(
        "SELECT * FROM users WHERE google_id = %s OR email = %s LIMIT 1",
        (google_id, email),
    )
    user = cursor.fetchone()

    if user is None:
        cursor.execute(
            """
            INSERT INTO users (google_id, name, email, profile_picture, created_at)
            VALUES (%s, %s, %s, %s, NOW())
            """,
            (google_id, name, email, profile_picture),
        )
        conn.commit()
        cursor.execute(
            "SELECT * FROM users WHERE google_id = %s OR email = %s LIMIT 1",
            (google_id, email),
        )
        user = cursor.fetchone()

    cursor.close()
    conn.close()
    return user


def get_joined_group_ids(user_id):
    """Return all group IDs a user has already joined."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT group_id FROM group_members WHERE user_id = %s",
        (user_id,),
    )
    joined = {row[0] for row in cursor.fetchall()}
    cursor.close()
    conn.close()
    return joined


@app.route("/")
def index():
    return render_template("index.html", user=get_current_user())


@app.route("/dashboard")
def dashboard():
    """Personal dashboard for logged-in users"""
    user = get_current_user()
    if not user:
        return redirect(url_for("login"))

    return render_template("dashboard.html", user=user)


@app.route("/community")
def community():
    user = get_current_user()
    if not user:
        return render_template("community.html", user=None, logged_in=False, groups=[])

    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cursor.execute("SELECT * FROM study_groups ORDER BY id ASC")
    groups = cursor.fetchall()
    cursor.close()
    conn.close()

    joined_group_ids = get_joined_group_ids(user["id"])
    return render_template(
        "community.html",
        user=user,
        logged_in=True,
        groups=groups,
        joined_group_ids=joined_group_ids,
    )


@app.route("/about")
def about():
    return render_template("about.html", user=get_current_user())


@app.route("/profile")
def profile():
    user = get_current_user()
    if not user:
        return render_template("profile.html", user=None, logged_in=False, joined_groups=[])

    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cursor.execute(
        """
        SELECT sg.id, sg.group_name, sg.description, sg.category, sg.member_count
        FROM group_members gm
        JOIN study_groups sg ON sg.id = gm.group_id
        WHERE gm.user_id = %s
        ORDER BY gm.joined_at DESC
        """,
        (user["id"],),
    )
    joined_groups = cursor.fetchall()

    cursor.execute(
        "SELECT COUNT(*) AS total FROM group_members WHERE user_id = %s",
        (user["id"],),
    )
    total_groups = cursor.fetchone()["total"]
    cursor.close()
    conn.close()

    return render_template(
        "profile.html",
        user=user,
        logged_in=True,
        joined_groups=joined_groups,
        total_groups=total_groups,
    )


@app.route("/login")
def login():
    redirect_uri = url_for("auth_google_callback", _external=True)
    return oauth.google.authorize_redirect(redirect_uri)


@app.route("/auth/google/callback")
def auth_google_callback():
    token = oauth.google.authorize_access_token()
    user_info = oauth.google.userinfo()
    user = create_or_get_user(user_info)

    if user is None:
        return redirect(url_for("index"))

    session["user_id"] = user["id"]
    session["user_name"] = user["name"]
    session["user_email"] = user["email"]
    return redirect(url_for("community"))


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))


@app.route("/group/<int:group_id>")
def view_group(group_id):
    """View a specific group with its channels"""
    user = get_current_user()
    if not user:
        return redirect(url_for("login"))

    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    # Get group info
    cursor.execute("SELECT * FROM study_groups WHERE id = %s", (group_id,))
    group = cursor.fetchone()

    if not group:
        cursor.close()
        conn.close()
        return redirect(url_for("community"))

    # Check if user is a member
    cursor.execute(
        "SELECT role FROM group_members WHERE user_id = %s AND group_id = %s",
        (user["id"], group_id),
    )
    member = cursor.fetchone()

    if not member:
        cursor.close()
        conn.close()
        return redirect(url_for("community"))

    # Get all channels for this group
    cursor.execute(
        "SELECT * FROM channels WHERE group_id = %s ORDER BY created_at ASC",
        (group_id,),
    )
    channels = cursor.fetchall()

    # Get members count
    cursor.execute(
        "SELECT COUNT(*) as count FROM group_members WHERE group_id = %s",
        (group_id,),
    )
    member_count = cursor.fetchone()["count"]

    cursor.close()
    conn.close()

    return render_template(
        "group.html",
        user=user,
        group=group,
        channels=channels,
        member_count=member_count,
        user_role=member["role"],
    )


@app.route("/channel/<int:channel_id>")
def view_channel(channel_id):
    """View a specific channel with messages"""
    user = get_current_user()
    if not user:
        return redirect(url_for("login"))

    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    # Get channel and group info
    cursor.execute(
        """
        SELECT c.*, sg.id as group_id, sg.group_name
        FROM channels c
        JOIN study_groups sg ON c.group_id = sg.id
        WHERE c.id = %s
        """,
        (channel_id,),
    )
    channel = cursor.fetchone()

    if not channel:
        cursor.close()
        conn.close()
        return redirect(url_for("community"))

    # Check if user is a member of the group
    cursor.execute(
        "SELECT role FROM group_members WHERE user_id = %s AND group_id = %s",
        (user["id"], channel["group_id"]),
    )
    member = cursor.fetchone()

    if not member:
        cursor.close()
        conn.close()
        return redirect(url_for("community"))

    # Get all messages in this channel
    cursor.execute(
        """
        SELECT m.id, m.content, m.created_at, u.name, u.profile_picture
        FROM messages m
        JOIN users u ON m.user_id = u.id
        WHERE m.channel_id = %s
        ORDER BY m.created_at ASC
        """,
        (channel_id,),
    )
    messages = cursor.fetchall()

    # Get all channels for the sidebar
    cursor.execute(
        "SELECT * FROM channels WHERE group_id = %s ORDER BY created_at ASC",
        (channel["group_id"],),
    )
    channels = cursor.fetchall()

    # Get group members
    cursor.execute(
        """
        SELECT u.id, u.name, u.profile_picture, gm.role
        FROM group_members gm
        JOIN users u ON gm.user_id = u.id
        WHERE gm.group_id = %s
        ORDER BY gm.role DESC, u.name ASC
        """,
        (channel["group_id"],),
    )
    members = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template(
        "channel.html",
        user=user,
        channel=channel,
        messages=messages,
        channels=channels,
        members=members,
        user_role=member["role"],
    )


@app.route("/channel/<int:channel_id>/message", methods=["POST"])
def post_message(channel_id):
    """Post a message to a channel"""
    user = get_current_user()
    if not user:
        return redirect(url_for("login"))

    content = request.form.get("content", "").strip()
    if not content:
        return redirect(url_for("view_channel", channel_id=channel_id))

    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    # Verify user is in the channel's group
    cursor.execute(
        """
        SELECT c.group_id FROM channels c WHERE c.id = %s
        """,
        (channel_id,),
    )
    channel_data = cursor.fetchone()

    if not channel_data:
        cursor.close()
        conn.close()
        return redirect(url_for("community"))

    cursor.execute(
        "SELECT id FROM group_members WHERE user_id = %s AND group_id = %s",
        (user["id"], channel_data["group_id"]),
    )
    if not cursor.fetchone():
        cursor.close()
        conn.close()
        return redirect(url_for("community"))

    # Insert message
    cursor.execute(
        "INSERT INTO messages (channel_id, user_id, content, created_at) VALUES (%s, %s, %s, NOW())",
        (channel_id, user["id"], content),
    )
    conn.commit()
    cursor.close()
    conn.close()

    return redirect(url_for("view_channel", channel_id=channel_id))


@app.route("/join-group/<int:group_id>", methods=["POST"])
def join_group(group_id):
    user = get_current_user()
    if not user:
        return redirect(url_for("community"))

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT id FROM group_members WHERE user_id = %s AND group_id = %s",
        (user["id"], group_id),
    )
    existing = cursor.fetchone()

    if not existing:
        cursor.execute(
            "INSERT INTO group_members (user_id, group_id, joined_at) VALUES (%s, %s, NOW())",
            (user["id"], group_id),
        )
        cursor.execute(
            "UPDATE study_groups SET member_count = member_count + 1 WHERE id = %s",
            (group_id,),
        )
        conn.commit()

    cursor.close()
    conn.close()
    return redirect(url_for("view_group", group_id=group_id))


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5001)