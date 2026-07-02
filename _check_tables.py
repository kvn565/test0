import sqlite3
conn = sqlite3.connect('db.sqlite3')
cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
for r in cur.fetchall():
    name = r[0]
    if 'devis' in name.lower():
        print(name)
conn.close()
