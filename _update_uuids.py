import sqlite3, uuid
conn = sqlite3.connect('db.sqlite3')
cur = conn.cursor()
cur.execute("SELECT id, uuid_public FROM facturer_devis WHERE uuid_public IS NULL OR uuid_public = ''")
rows = cur.fetchall()
for row in rows:
    cur.execute('UPDATE facturer_devis SET uuid_public = ? WHERE id = ?', (uuid.uuid4().hex, row[0]))
conn.commit()
print(f'Updated {len(rows)} devis records with UUIDs')
conn.close()
