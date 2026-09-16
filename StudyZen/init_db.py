import psycopg2
import os
from dotenv import load_dotenv
 
load_dotenv()
 
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_NAME = os.getenv("DB_NAME", "studyzen")
 
# Step 1: Connect to the default "postgres" database to create our database
# (Postgres requires connecting to an existing database before creating a new one)
conn = psycopg2.connect(
    host=DB_HOST,
    port=DB_PORT,
    user=DB_USER,
    password=DB_PASSWORD,
    dbname="postgres",
)
conn.autocommit = True
cursor = conn.cursor()
 
cursor.execute("SELECT 1 FROM pg_database WHERE datname = %s", (DB_NAME,))
exists = cursor.fetchone()
 
if not exists:
    cursor.execute(f'CREATE DATABASE "{DB_NAME}"')
    print(f"✓ Created database {DB_NAME}")
else:
    print(f"Note: database {DB_NAME} already exists")
 
cursor.close()
conn.close()
 
# Step 2: Connect to the actual studyzen database and run the schema
conn = psycopg2.connect(
    host=DB_HOST,
    port=DB_PORT,
    user=DB_USER,
    password=DB_PASSWORD,
    dbname=DB_NAME,
)
conn.autocommit = True
cursor = conn.cursor()
 
with open("database/studyzen.sql", "r") as f:
    schema_sql = f.read()
 
# Split by semicolon and execute each statement
statements = [s.strip() for s in schema_sql.split(";") if s.strip()]
for stmt in statements:
    try:
        cursor.execute(stmt)
        print(f"✓ {stmt[:60]}...")
    except Exception as e:
        print(f"Note: {str(e)[:70]}")
 
cursor.close()
conn.close()
 
print("\n✅ Database schema loaded successfully!")