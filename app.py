import os, sqlite3
from datetime import datetime, timedelta, timezone
from flask import Flask, g, jsonify, request

DB = os.environ.get("LIBRARY_DB", "library.db")
app = Flask(__name__)

CURRENT_LOANS_SQL = """
SELECT b.title, l.due_at, l.borrowed_at, l.id AS loan_id, l.copy_id
FROM loans l
JOIN copies c ON c.id = l.copy_id
JOIN books  b ON b.id = c.book_id
WHERE l.member_id = ? AND l.returned_at IS NULL
ORDER BY l.borrowed_at DESC
"""

def connect(path=DB):
    db = sqlite3.connect(path, timeout=5)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    return db

def get_db():
    if "db" not in g:
        g.db = connect()
    return g.db

@app.teardown_appcontext
def close_db(_):
    db = g.pop("db", None)
    if db:
        db.close()

now = lambda: datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

@app.get("/members/<int:member_id>/loans")
def current_loans(member_id):
    """Books the member currently has out, most recently borrowed first."""
    db = get_db()
    if not db.execute("SELECT 1 FROM members WHERE id=?", (member_id,)).fetchone():
        return jsonify(error="member not found"), 404
    rows = db.execute(CURRENT_LOANS_SQL, (member_id,)).fetchall()
    return jsonify([{"title": r["title"], "due_at": r["due_at"],
                     "borrowed_at": r["borrowed_at"], "loan_id": r["loan_id"]} for r in rows])

@app.post("/loans")
def lend():
    """Body: {"member_id": 1, "copy_id": 2}. No availability pre-check on purpose:
    the unique partial index is the arbiter, so there is no check-then-insert race."""
    body = request.get_json(force=True)
    t = datetime.now(timezone.utc)
    db = get_db()
    try:
        cur = db.execute(
            "INSERT INTO loans(copy_id, member_id, borrowed_at, due_at) VALUES (?,?,?,?)",
            (body["copy_id"], body["member_id"], t.strftime("%Y-%m-%dT%H:%M:%SZ"),
             (t + timedelta(days=28)).strftime("%Y-%m-%dT%H:%M:%SZ")))
        db.commit()
    except sqlite3.IntegrityError as e:
        db.rollback()
        if "loans.copy_id" in str(e):          # the one-open-loan-per-copy index
            return jsonify(error="copy is already on loan"), 409
        return jsonify(error="invalid copy or member"), 422
    return jsonify(loan_id=cur.lastrowid), 201

@app.post("/loans/<int:loan_id>/return")
def give_back(loan_id):
    db = get_db()
    cur = db.execute("UPDATE loans SET returned_at=? WHERE id=? AND returned_at IS NULL",
                     (now(), loan_id))
    db.commit()
    return (jsonify(ok=True), 200) if cur.rowcount else (jsonify(error="no open loan"), 404)

if __name__ == "__main__":
    app.run(port=5000)
