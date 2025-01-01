import sqlite3

# Connect to the database
conn = sqlite3.connect('app.db')  # Adjust the path if needed
cursor = conn.cursor()

# List all tables in the database
cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
tables = cursor.fetchall()

# Print the list of tables
print("Tables in the database:")
for table in tables:
    print(table[0])

# Close the connection
conn.close()
