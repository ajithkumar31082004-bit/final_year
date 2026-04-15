from pathlib import Path
import sqlite3
text = Path('models/database.py').read_text(encoding='utf-8')
start = text.index('CREATE TABLE IF NOT EXISTS users')
end = text.index('"""', start)
# find the next closing triple quote after the start of the SQL block
end = text.index('"""', start)
sql = text[start:end]
print('SQL snippet:')
print(sql)
conn = sqlite3.connect(':memory:')
try:
    conn.execute(sql)
    print('OK')
except Exception as exc:
    print(type(exc).__name__, exc)
