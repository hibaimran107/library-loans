"""Create library.db and seed it. Usage: python seed.py [n_loans]"""
import os, random, sqlite3, sys
from datetime import datetime, timedelta, timezone

DB = os.environ.get("LIBRARY_DB", "library.db")
N_LOANS = int(sys.argv[1]) if len(sys.argv) > 1 else 100_000
N_BOOKS, COPIES_PER_BOOK, N_MEMBERS = 3_000, 3, 1_000
random.seed(42)

if os.path.exists(DB):
    os.remove(DB)
db = sqlite3.connect(DB)
db.executescript(open("schema.sql").read())

words = "river stone night garden silent winter paper glass iron salt ember harbor lantern orchard thread".split()
db.executemany("INSERT INTO books(id,isbn,title,author) VALUES (?,?,?,?)", [
    (i, f"978-{i:010d}", f"The {random.choice(words).title()} {random.choice(words).title()} {i}",
     f"Author {random.randint(1, 800)}") for i in range(1, N_BOOKS + 1)])
n_copies = N_BOOKS * COPIES_PER_BOOK
db.executemany("INSERT INTO copies(id,book_id,barcode) VALUES (?,?,?)",
    [(i, (i - 1) % N_BOOKS + 1, f"BC{i:07d}") for i in range(1, n_copies + 1)])
db.executemany("INSERT INTO members(id,name,email) VALUES (?,?,?)",
    [(i, f"Member {i}", f"member{i}@example.org") for i in range(1, N_MEMBERS + 1)])

now = datetime(2026, 11, 15, tzinfo=timezone.utc)
fmt = lambda d: d.strftime("%Y-%m-%dT%H:%M:%SZ")

# ~2,500 copies are out right now: distinct copies, so the unique index holds.
open_copies = set(random.sample(range(1, n_copies + 1), 2_500))
rows = []
for c in open_copies:
    b = now - timedelta(days=random.randint(0, 27), seconds=random.randint(0, 86399))
    rows.append((c, random.randint(1, N_MEMBERS), fmt(b), fmt(b + timedelta(days=28)), None))
# Historical, returned loans over the past 3 years.
while len(rows) < N_LOANS:
    b = now - timedelta(days=random.randint(30, 1100), seconds=random.randint(0, 86399))
    r = b + timedelta(days=random.randint(1, 27))
    rows.append((random.randint(1, n_copies), random.randint(1, N_MEMBERS),
                 fmt(b), fmt(b + timedelta(days=28)), fmt(r)))
random.shuffle(rows)
db.executemany("INSERT INTO loans(copy_id,member_id,borrowed_at,due_at,returned_at) VALUES (?,?,?,?,?)", rows)
db.commit()
for t in ("books", "copies", "members", "loans"):
    print(t, db.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0])
print("open loans", db.execute("SELECT COUNT(*) FROM loans WHERE returned_at IS NULL").fetchone()[0])
