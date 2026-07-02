import sqlite3
conn = sqlite3.connect('db.sqlite3')
conn.text_factory = str
cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
tables = [r[0] for r in cur.fetchall() if not r[0].startswith('sqlite_')]
for t in tables:
    cur = conn.execute('PRAGMA table_info("{}")'.format(t))
    cols = cur.fetchall()
    text_cols = [c[1] for c in cols if 'char' in c[2].lower() or 'text' in c[2].lower()]
    if not text_cols:
        continue
    for sample_col in text_cols[:3]:
        cur = conn.execute('SELECT "{}" FROM "{}" WHERE "{}" IS NOT NULL LIMIT 5'.format(sample_col, t, sample_col))
        for row in cur:
            val = row[0]
            if val and any(ord(c) > 127 for c in val):
                print('{}: "{}"'.format(t, val[:100]))
                break
conn.close()
print("Done")
