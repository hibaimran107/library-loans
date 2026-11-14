"""Double lending must fail at the database, even with concurrent writers
and even when the application-level check is bypassed entirely."""
import os, sqlite3, tempfile, threading
os.environ["LIBRARY_DB"] = os.path.join(tempfile.mkdtemp(), "t.db")
import app as appmod

db = sqlite3.connect(os.environ["LIBRARY_DB"])
db.executescript(open("schema.sql").read())
db.execute("INSERT INTO books VALUES (1,'x','T','A')")
db.execute("INSERT INTO copies VALUES (1,1,'BC1')")
db.executemany("INSERT INTO members VALUES (?,?,?)", [(i, f"m{i}", f"m{i}@x") for i in range(1, 21)])
db.commit()

# 1) Raw SQL, no app code at all: second open loan of the same copy is rejected.
db.execute("INSERT INTO loans(copy_id,member_id,borrowed_at,due_at) VALUES (1,1,'2026-01-01','2026-01-29')")
try:
    db.execute("INSERT INTO loans(copy_id,member_id,borrowed_at,due_at) VALUES (1,2,'2026-01-02','2026-01-30')")
    raise SystemExit("FAIL: raw double insert succeeded")
except sqlite3.IntegrityError as e:
    print("raw SQL double insert rejected:", e)
db.execute("DELETE FROM loans"); db.commit()

# 2) 20 concurrent HTTP requests for the same copy: exactly one wins.
client = appmod.app.test_client()
codes = []
def go(m): codes.append(client.post("/loans", json={"copy_id": 1, "member_id": m}).status_code)
ts = [threading.Thread(target=go, args=(m,)) for m in range(1, 21)]
[t.start() for t in ts]; [t.join() for t in ts]
print("status codes:", sorted(codes))
assert codes.count(201) == 1 and codes.count(409) == 19, codes

# 3) After return, the copy can be lent again.
lid = db.execute("SELECT id FROM loans WHERE returned_at IS NULL").fetchone()[0]
assert client.post(f"/loans/{lid}/return").status_code == 200
assert client.post("/loans", json={"copy_id": 1, "member_id": 5}).status_code == 201
print("PASS")
