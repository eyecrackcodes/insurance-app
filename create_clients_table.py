import sqlite3

# Connect to the database
conn = sqlite3.connect('app.db')  # Ensure this matches the path of your app's database
cursor = conn.cursor()

# Create the `clients` table
cursor.execute('''
CREATE TABLE IF NOT EXISTS clients (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_name TEXT NOT NULL,
    date_of_birth TEXT,
    carrier TEXT,
    product TEXT,
    annual_premium REAL,
    total_commission REAL,
    commission_paid REAL,
    status TEXT,
    policy_date TEXT,
    state TEXT,
    lead_source TEXT,
    username TEXT
);
''')

# Commit and close the connection
conn.commit()
conn.close()

print("Table `clients` created successfully.")
