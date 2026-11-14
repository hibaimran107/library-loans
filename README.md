# Library loans

Flask + SQLite. Four related tables, 100,000 seeded loans, one endpoint that matters.

```
pip install -r requirements.txt
python seed.py                 # builds library.db (100k loans)
python bench.py                # before/after index: plans + timings
python test_double_loan.py     # double-lending proof
python app.py                  # http://localhost:5000
curl localhost:5000/members/7/loans
```

## Model

| table | key columns |
|---|---|
| `books` | id, isbn (unique), title, author |
| `copies` | id, **book_id → books**, barcode (unique) |
| `members` | id, name, email (unique) |
| `loans` | id, **copy_id → copies**, **member_id → members**, borrowed_at, due_at, returned_at (NULL = still out) |

Seed: 3,000 books, 9,000 copies, 1,000 members, **100,000 loans** (2,500 currently open, the rest returned over the past three years).

## The endpoint

`GET /members/<id>/loans` → open loans for the member, newest first, with title and due date.

```sql
SELECT b.title, l.due_at, l.borrowed_at, l.id AS loan_id, l.copy_id
FROM loans l
JOIN copies c ON c.id = l.copy_id
JOIN books  b ON b.id = c.book_id
WHERE l.member_id = ? AND l.returned_at IS NULL
ORDER BY l.borrowed_at DESC
```

### Before the index

```
SCAN l USING INDEX one_open_loan_per_copy
SEARCH c USING INTEGER PRIMARY KEY (rowid=?)
SEARCH b USING INTEGER PRIMARY KEY (rowid=?)
USE TEMP B-TREE FOR ORDER BY
```
median 2.07 ms · p95 2.93 ms · max 8.69 ms (query only, 600 runs over 200 members)

Not a table scan of 100k rows, but only by luck: the partial unique index that enforces
the lending rule happens to contain exactly the open loans, so SQLite scans that (about 2,500 entries)
and filters by member. Cost still grows with the number of open loans library-wide, not with
the one member's loans, and it needs a temp B-tree sort.

### After the index

```sql
CREATE INDEX loans_open_by_member
    ON loans(member_id, borrowed_at DESC) WHERE returned_at IS NULL;
```
```
SEARCH l USING INDEX loans_open_by_member (member_id=?)
SEARCH c USING INTEGER PRIMARY KEY (rowid=?)
SEARCH b USING INTEGER PRIMARY KEY (rowid=?)
```
median 0.014 ms · p95 0.044 ms · max 0.115 ms

Roughly 125x faster. The scan became a seek on `member_id`, and the temp sort is gone because the
index is already ordered by `borrowed_at DESC`. It is partial, so it only holds open loans and
does not grow as history accumulates.

End to end through Flask (in-process test client, 500 random members, after index):
median 0.55 ms, p95 0.89 ms. The 200 ms target is met with a wide margin. A real network and
server add overhead, but nowhere near that. Absolute numbers will differ on your machine; the
plans are what to compare.

## Preventing double lending

```sql
CREATE UNIQUE INDEX one_open_loan_per_copy
    ON loans(copy_id) WHERE returned_at IS NULL;
```

A copy can have at most one loan with `returned_at IS NULL`. Returned loans are not indexed,
so history is unlimited and a returned copy can be lent again.

**Why the database, and why a constraint rather than a transaction.**

- **It can't be bypassed.** Every writer goes through the database: this API, a future
  admin script, a data fix in a SQL console, a second service. Application code covers only
  the paths that remember to call it.
- **No race window.** The naive approach (`SELECT` is the copy free? then `INSERT`) is a
  check-then-act race: two requests both see "free" and both insert. A unique index makes the
  check and the write one atomic step; the loser gets an `IntegrityError`. `POST /loans` therefore has no
  pre-check at all. It inserts and translates the violation to HTTP 409.
- **Simpler than locking.** A transaction would need serializable isolation or
  `SELECT ... FOR UPDATE` to be correct, and a mistake there fails silently. A constraint
  fails loudly and is declared once in the schema.

`test_double_loan.py` proves it: (1) a raw SQL second insert is rejected with no app code
involved; (2) 20 concurrent `POST /loans` for one copy yield exactly one 201 and nineteen 409s;
(3) after a return the copy can be lent again.

## Notes / limits

- SQLite serializes writers, which makes the concurrency test easy to pass. The guarantee does not
  rely on that: the same partial unique index works unchanged in PostgreSQL, where
  concurrent inserts are arbitrated by the index too.
- No auth, pagination, renewals or fines. The endpoint returns all open loans for a member, which is a
  naturally small set.
- Timestamps are ISO-8601 UTC strings, so they sort correctly as text.
