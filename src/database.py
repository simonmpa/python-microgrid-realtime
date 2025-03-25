import sqlite3

conn = sqlite3.connect('database.db')
cursor = conn.cursor()
print("Created / Opened database successfully")

cursor.execute('''CREATE TABLE IF NOT EXISTS microgrids
             (ID INTEGER PRIMARY KEY AUTOINCREMENT,
                Timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                Gridname text,
                Load real)''')

print("Table created successfully")

cursor.execute("INSERT INTO microgrids (Gridname, Load) VALUES ('ES10', 7.5)")
cursor.execute("INSERT INTO microgrids (Gridname, Load) VALUES ('PT02', 5.0)")
cursor.execute("INSERT INTO microgrids (Gridname, Load) VALUES ('ES12', 2.5)")

cursor.close()

conn.commit()
conn.close()
print("Connection closed")
