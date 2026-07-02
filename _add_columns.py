import sqlite3
conn = sqlite3.connect('db.sqlite3')
cur = conn.cursor()
try:
    cur.execute('ALTER TABLE facturer_devis ADD COLUMN uuid_public varchar(64) NOT NULL DEFAULT \'\'')
    print('Added uuid_public')
except Exception as e:
    print(f'uuid_public: {e}')
try:
    cur.execute('ALTER TABLE facturer_devis ADD COLUMN email_envoye bool NOT NULL DEFAULT 0')
    print('Added email_envoye')
except Exception as e:
    print(f'email_envoye: {e}')
try:
    cur.execute('ALTER TABLE facturer_devis ADD COLUMN date_envoi_email datetime NULL')
    print('Added date_envoi_email')
except Exception as e:
    print(f'date_envoi_email: {e}')
conn.commit()
cur.execute('PRAGMA table_info(facturer_devis)')
cols = [r[1] for r in cur.fetchall()]
print('Final columns:', cols)
conn.close()
