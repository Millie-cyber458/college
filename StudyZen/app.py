import os
from flask import Flask, g, redirect, render_template, request, session, url_for
from authlib.integrations.flask_client import OAuth
from dotenv import load_dotenv
import psycopg2
import psycopg2.extras
from api_routes import api_bp
import uuid
import requests
from werkzeug.utils import secure_filename
# Load environment variables from .env
load_dotenv()

# Allow OAuth over plain HTTP for local development only.
# NEVER set this in production — real deployments must use HTTPS.
os.environ.setdefault("AUTHLIB_INSECURE_TRANSPORT", "1")


def _create_db_connection():
    """Open a brand new PostgreSQL connection (autocommit, so every
    statement is committed immediately without needing conn.commit())."""
    conn = psycopg2.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=os.getenv("DB_PORT", "5432"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD", ""),
        dbname=os.getenv("DB_NAME", "studyzen"),
    )
    conn.autocommit = True
    return conn


def get_db_connection():
    """Reuse ONE PostgreSQL connection per request, cached on flask.g,
    instead of opening a new network connection every time this is called."""
    if "db_conn" not in g:
        g.db_conn = _create_db_connection()
    return g.db_conn


app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "replace-with-a-secure-secret")


@app.teardown_appcontext
def close_db_connection(exception=None):
    """Close the request's shared connection exactly once, when the
    request is fully done (whether it succeeded or raised an error)."""
    db_conn = g.pop("db_conn", None)
    if db_conn is not None:
        db_conn.close()


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
        cursor.execute(
            "SELECT * FROM users WHERE google_id = %s OR email = %s LIMIT 1",
            (google_id, email),
        )
        user = cursor.fetchone()

    cursor.close()
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
    return joined

@app.route("/")
def index():
    user = get_current_user()
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM users")
    student_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM study_groups")
    group_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM shared_files")
    file_count = cursor.fetchone()[0]

    cursor.close()

    return render_template(
        'index.html',
        user=user,
        student_count=student_count,
        group_count=group_count,
        file_count=file_count
    )


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

    cursor.execute("SELECT * FROM study_groups WHERE id = %s", (group_id,))
    group = cursor.fetchone()

    if not group:
        cursor.close()
        return redirect(url_for("community"))

    cursor.execute(
        "SELECT role FROM group_members WHERE user_id = %s AND group_id = %s",
        (user["id"], group_id),
    )
    member = cursor.fetchone()

    if not member:
        cursor.close()
        return redirect(url_for("community"))

    cursor.execute(
        "SELECT * FROM channels WHERE group_id = %s ORDER BY created_at ASC",
        (group_id,),
    )
    channels = cursor.fetchall()

    cursor.execute(
        "SELECT COUNT(*) as count FROM group_members WHERE group_id = %s",
        (group_id,),
    )
    member_count = cursor.fetchone()["count"]

    cursor.close()

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
        return redirect(url_for("community"))

    cursor.execute(
        "SELECT role FROM group_members WHERE user_id = %s AND group_id = %s",
        (user["id"], channel["group_id"]),
    )
    member = cursor.fetchone()

    if not member:
        cursor.close()
        return redirect(url_for("community"))

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

    cursor.execute(
        "SELECT * FROM channels WHERE group_id = %s ORDER BY created_at ASC",
        (channel["group_id"],),
    )
    channels = cursor.fetchall()

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

    cursor.execute(
        """
        SELECT c.group_id FROM channels c WHERE c.id = %s
        """,
        (channel_id,),
    )
    channel_data = cursor.fetchone()

    if not channel_data:
        cursor.close()
        return redirect(url_for("community"))

    cursor.execute(
        "SELECT id FROM group_members WHERE user_id = %s AND group_id = %s",
        (user["id"], channel_data["group_id"]),
    )
    if not cursor.fetchone():
        cursor.close()
        return redirect(url_for("community"))

    cursor.execute(
        "INSERT INTO messages (channel_id, user_id, content, created_at) VALUES (%s, %s, %s, NOW())",
        (channel_id, user["id"], content),
    )
    cursor.close()

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

    cursor.close()
    return redirect(url_for("view_group", group_id=group_id))

@app.route("/create-group", methods=["POST"])
def create_group():
    user = get_current_user()
    if not user:
        return redirect(url_for("login"))

    name = request.form.get("group_name", "").strip()
    description = request.form.get("description", "").strip()
    icon = request.form.get("category", "").strip() or "📚"

    if not name or not description:
        return redirect(url_for("community"))

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO study_groups (group_name, description, category, member_count)
        VALUES (%s, %s, %s, 1) RETURNING id
        """,
        (name, description, icon),
    )
    group_id = cursor.fetchone()[0]
    cursor.execute(
        "INSERT INTO group_members (user_id, group_id, role) VALUES (%s, %s, 'admin')",
        (user["id"], group_id),
    )
    cursor.execute(
        "INSERT INTO channels (group_id, channel_name, description) VALUES (%s, 'general', 'General discussion')",
        (group_id,),
    )
    cursor.close()
    return redirect(url_for("view_group", group_id=group_id))

@app.route("/leave-group/<int:group_id>", methods=["POST"])
def leave_group(group_id):
    user = get_current_user()
    if not user:
        return redirect(url_for("community"))

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "DELETE FROM group_members WHERE user_id = %s AND group_id = %s",
        (user["id"], group_id),
    )
    cursor.execute(
        "UPDATE study_groups SET member_count = GREATEST(member_count - 1, 0) WHERE id = %s",
        (group_id,),
    )
    cursor.close()
    return redirect(url_for("community"))

@app.route("/api/channels/<int:channel_id>/messages")
def get_channel_messages(channel_id):
    user = get_current_user()
    if not user:
        return {"success": False, "error": "Not logged in"}, 401

    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cursor.execute("SELECT group_id FROM channels WHERE id = %s", (channel_id,))
    channel_data = cursor.fetchone()
    if not channel_data:
        cursor.close()
        return {"success": False, "error": "Channel not found"}, 404

    cursor.execute(
        "SELECT id FROM group_members WHERE user_id = %s AND group_id = %s",
        (user["id"], channel_data["group_id"]),
    )
    if not cursor.fetchone():
        cursor.close()
        return {"success": False, "error": "Not a member"}, 403

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
    cursor.close()

    return {
        "success": True,
        "messages": [
            {
                "id": m["id"],
                "name": m["name"],
                "profile_picture": m["profile_picture"],
                "content": m["content"],
                "created_at": m["created_at"].strftime('%b %d, %I:%M %p'),
            }
            for m in messages
        ],
    }


@app.route("/group/<int:group_id>/files", methods=["GET", "POST"])
def group_files(group_id):
    user = get_current_user()
    if not user:
        return redirect(url_for("login"))

    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cursor.execute(
        "SELECT role FROM group_members WHERE user_id = %s AND group_id = %s",
        (user["id"], group_id),
    )
    member = cursor.fetchone()
    if not member:
        cursor.close()
        return redirect(url_for("community"))

    cursor.execute("SELECT * FROM study_groups WHERE id = %s", (group_id,))
    group = cursor.fetchone()
    if not group:
        cursor.close()
        return redirect(url_for("community"))

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        uploaded_file = request.files.get("file")

        if not title or not uploaded_file or uploaded_file.filename == "":
            cursor.close()
            return redirect(url_for("group_files", group_id=group_id))

        original_name = secure_filename(uploaded_file.filename)
        unique_name = f"{uuid.uuid4().hex}_{original_name}"
        file_bytes = uploaded_file.read()
        content_type = uploaded_file.content_type or "application/octet-stream"

        supabase_url = os.getenv("SUPABASE_URL")
        service_role_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        bucket = os.getenv("SUPABASE_BUCKET", "shared-files")

        upload_url = f"{supabase_url}/storage/v1/object/{bucket}/{unique_name}"
        response = requests.post(
            upload_url,
            headers={
                "Authorization": f"Bearer {service_role_key}",
                "apikey": service_role_key,
                "Content-Type": content_type,
            },
            data=file_bytes,
        )

        if response.status_code not in (200, 201):
            cursor.close()
            return f"Upload failed: {response.text}", 500

        public_url = f"{supabase_url}/storage/v1/object/public/{bucket}/{unique_name}"

        cursor.execute(
            """
            INSERT INTO shared_files
                (user_id, group_id, title, description, file_name, storage_path, file_size, content_type)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (user["id"], group_id, title, description, original_name, public_url,
             len(file_bytes), content_type),
        )

        cursor.close()

        return redirect(url_for("group_files", group_id=group_id))

    cursor.execute(
        """
        SELECT sf.id, sf.title, sf.description, sf.file_name, sf.storage_path,
               sf.created_at, u.name AS uploaded_by
        FROM shared_files sf
        JOIN users u ON u.id = sf.user_id
        WHERE sf.group_id = %s
        ORDER BY sf.created_at DESC
        """,
        (group_id,),
    )
    files = cursor.fetchall()
    cursor.close()

    return render_template(
        "group_files.html", user=user, group=group, files=files, user_role=member["role"]
    )


if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=5001)