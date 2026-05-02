import sqlite3
conn = sqlite3.connect('/root/Trans_Guide_AI/data/users.db')
conn.row_factory = sqlite3.Row
c = conn.cursor()
c.execute("SELECT id, username, role, last_login, refresh_token FROM users ORDER BY id")
for r in c.fetchall():
    rt = r['refresh_token']
    print(f"  id={r['id']} username={r['username']} role={r['role']} last_login={r['last_login']} refresh_token={rt[:24] if rt else 'NULL'}")
conn.close()
