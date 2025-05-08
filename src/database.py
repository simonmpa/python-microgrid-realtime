import sqlite3

conn = sqlite3.connect("database.db")
cursor = conn.cursor()
print("Created / Opened database successfully")

cursor.execute(
    """CREATE TABLE IF NOT EXISTS microgrids
             (ID INTEGER PRIMARY KEY AUTOINCREMENT,
                Timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                Node text,
                CPU real,
                Completed_at DATETIME)"""
)

cursor.execute(
    """CREATE TABLE IF NOT EXISTS state_of_charge
             (ID INTEGER PRIMARY KEY AUTOINCREMENT,
                Timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                Node text,
                SOC real)"""
)

print("Table(s) created successfully")

cursor.close()

conn.commit()
conn.close()
print("Connection closed")
