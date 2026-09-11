import mysql.connector
import os
from dotenv import load_dotenv

load_dotenv()

conn = mysql.connector.connect(
    host=os.getenv("DB_HOST", "localhost"),
    port=int(os.getenv("DB_PORT", "3306")),
    user=os.getenv("DB_USER", "root"),
    password=os.getenv("DB_PASSWORD", ""),
    database=os.getenv("DB_NAME", "studyzen"),
    autocommit=True,
)

cursor = conn.cursor()

# Create a test user
cursor.execute("""
    INSERT IGNORE INTO users (google_id, name, email, profile_picture, created_at)
    VALUES ('test-user-123', 'Test Student', 'test@studyzen.com', '', NOW())
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
        INSERT IGNORE INTO group_members (user_id, group_id, role, joined_at)
        VALUES (%s, %s, 'member', NOW())
    """, (user_id, group_id))

print(f"✅ Test user created!")
print(f"User ID: {user_id}")
print(f"Email: test@studyzen.com")
print(f"User joined to all {len(groups)} groups!")

cursor.close()
conn.close()
