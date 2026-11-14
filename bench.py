"""Measure the endpoint query before/after the index; print plans and timings."""
import random, sqlite3, statistics, time
from app import CURRENT_LOANS_SQL, connect

db = connect()
db.execute("DROP INDEX IF EXISTS loans_open_by_member")
db.execute("ANALYZE"); db.commit()

# Pick members with a realistic number of open loans (median-ish) and a spread.
members = [r[0] for r in db.execute("SELECT id FROM members")]
random.seed(1)
sample = random.sample(members, 200)

def plan():
    mid = sample[0]
    return "\n".join(r[3] for r in db.execute("EXPLAIN QUERY PLAN " + CURRENT_LOANS_SQL, (mid,)))

def timings():
    ts = []
    for _ in range(3):                      # 3 passes x 200 members
        for m in sample:
            t = time.perf_counter()
            db.execute(CURRENT_LOANS_SQL, (m,)).fetchall()
            ts.append((time.perf_counter() - t) * 1000)
    ts.sort()
    return f"median {statistics.median(ts):.3f} ms | p95 {ts[int(len(ts)*.95)]:.3f} ms | max {ts[-1]:.3f} ms"

print("=== BEFORE INDEX ==="); print(plan()); print(timings())
db.executescript(open("indexes.sql").read()); db.execute("ANALYZE"); db.commit()
print("\n=== AFTER INDEX ==="); print(plan()); print(timings())
