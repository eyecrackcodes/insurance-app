import sqlite3

# Connect to the SQLite database
conn = sqlite3.connect('app.db')  # Make sure 'app.db' is the correct database file
cursor = conn.cursor()

# Add the `username` column to the `clients` table
try:
    cursor.execute('''
    ALTER TABLE clients ADD COLUMN username TEXT;
    ''')
    print("Column 'username' added successfully to 'clients' table.")
except sqlite3.OperationalError as e:
    print(f"Error: {e}. This might mean the column already exists.")

# Commit the changes and close the connection
conn.commit()
conn.close()
