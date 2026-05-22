import sqlite3

DB_NAME = "database.db"

with sqlite3.connect(DB_NAME) as conn:
    cursor = conn.cursor()
    
    # Add is_verified column
    cursor.execute("ALTER TABLE reports ADD COLUMN is_verified INTEGER DEFAULT 0")
    
    # Add is_collected column
    cursor.execute("ALTER TABLE reports ADD COLUMN is_collected INTEGER DEFAULT 0")
    
    conn.commit()

print("Columns 'is_verified' and 'is_collected' added successfully.")
