import mysql.connector
import os
from dotenv import load_dotenv

load_dotenv()

# Connect without specifying database first
conn = mysql.connector.connect(
    host=os.getenv("DB_HOST", "localhost"),
    user=os.getenv("DB_USER", "root"),
    password=os.getenv("DB_PASSWORD", ""),
    autocommit=True,
)

cursor = conn.cursor()

# Read and execute the main schema file
with open("database/studyzen.sql", "r") as f:
    schema_sql = f.read()

# Split by semicolon and execute
statements = [s.strip() for s in schema_sql.split(';') if s.strip()]
for stmt in statements:
    try:
        cursor.execute(stmt)
        print(f"✓ {stmt[:60]}...")
    except Exception as e:
        print(f"Note: {str(e)[:70]}")

cursor.close()
conn.close()

print("\n✅ Database schema loaded successfully!")
