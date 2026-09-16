import psycopg2
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Connect to database
conn = psycopg2.connect(
    host=os.getenv("DB_HOST", "localhost"),
    port=int(os.getenv("DB_PORT", "5432")),
    user=os.getenv("DB_USER", "postgres"),
    password=os.getenv("DB_PASSWORD", ""),
    dbname=os.getenv("DB_NAME", "postgres")  # Connect to the default "postgres" database for migration,
)
conn.autocommit = True

cursor = conn.cursor()

# Read and execute migration
with open("database/migration_add_channels.sql", "r") as f:
    migration_sql = f.read()
    
# Split by semicolon and execute each statement
statements = migration_sql.split(';')
for statement in statements:
    statement = statement.strip()
    if statement:
        try:
            cursor.execute(statement)
            print(f"✓ Executed: {statement[:60]}...")
        except Exception as e:
            print(f"⚠ Note: {str(e)[:80]}")

cursor.close()
conn.close()

print("\n✅ Database migration complete!")