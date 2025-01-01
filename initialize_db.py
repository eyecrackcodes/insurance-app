import sqlite3

# Connect to the database (it will create 'app.db' if it doesn't exist)
conn = sqlite3.connect('app.db')

# Create a cursor to execute SQL commands
cursor = conn.cursor()

# Create the `agents` table
cursor.execute('''
CREATE TABLE IF NOT EXISTS agents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL,
    commission_level TEXT NOT NULL
)
''')

# Commit changes and close the connection
conn.commit()
conn.close()

print("Table `agents` created successfully.")
