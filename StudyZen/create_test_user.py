import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()

# Create a PostgreSQL connection
conn = psycopg2.connect(
    host=os.getenv("DB_HOST", "localhost"),
    port=int(os.getenv("DB_PORT", "5432")),
    user=os.getenv("DB_USER", "postgres"),
    password=os.getenv("DB_PASSWORD", ""),
    dbname=os.getenv("DB_NAME", "studyzen"),
)
conn.autocommit = True

cursor = conn.cursor()

# Create a test user (ON CONFLICT handles unique constraints in Postgres)
cursor.execute("""
    INSERT INTO users (google_id, name, email, profile_picture, created_at)
    VALUES ('test-user-123', 'Test Student', 'test@studyzen.com', '', NOW())
    ON CONFLICT (email) DO NOTHING
""")

# Get the user ID
cursor.execute("SELECT id FROM users WHERE email = 'test@studyzen.com'")
user_id = cursor.fetchone()[0]

# Join this user to all groups
cursor.execute("SELECT id FROM study_groups")
groups = cursor.fetchall()

for group in groups:
    group_id = group[0]
    cursor.execute("""
        INSERT INTO group_members (user_id, group_id, role, joined_at)
        VALUES (%s, %s, 'member', NOW())
        ON CONFLICT (user_id, group_id) DO NOTHING
    """, (user_id, group_id))

print(f"✅ Test user created!")
print(f"User ID: {user_id}")
print(f"Email: test@studyzen.com")
print(f"User joined to all {len(groups)} groups!")

cursor.close()
conn.close()