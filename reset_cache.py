import sqlite3

conn = sqlite3.connect("data/tracer.db")
conn.execute("DROP TABLE IF EXISTS transactions")
conn.execute("DROP TABLE IF EXISTS addresses")
conn.commit()
conn.close()
print("Cache cleared. Your users are untouched.")