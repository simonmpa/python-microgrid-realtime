import sqlite3

conn = sqlite3.connect("database.db")
cursor = conn.cursor()
print("Created / Opened database successfully")

cursor.execute(
    """CREATE TABLE IF NOT EXISTS microgrids
             (ID INTEGER PRIMARY KEY AUTOINCREMENT,
                Timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                Gridname text,
                Load real,
                Completed_at DATETIME)"""
)

cursor.execute(
    """CREATE TABLE IF NOT EXISTS state_of_charge
             (ID INTEGER PRIMARY KEY AUTOINCREMENT,
                Timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                Gridname text,
                SOC real)"""
)

print("Table(s) created successfully")

cursor.execute(
    "INSERT INTO microgrids (Gridname, Load, Completed_at) VALUES ('ES10', 7.5, '2025-04-03 09:05:47')"
)
cursor.execute(
    "INSERT INTO microgrids (Gridname, Load, Completed_at) VALUES ('PT02', 5.0, '2025-04-03 10:05:47')"
)
cursor.execute(
    "INSERT INTO microgrids (Gridname, Load, Completed_at) VALUES ('ES12', 2.5, '2025-04-03 10:35:47')"
)

cursor.close()

conn.commit()
conn.close()
print("Connection closed")
