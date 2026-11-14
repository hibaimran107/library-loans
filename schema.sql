PRAGMA foreign_keys = ON;

CREATE TABLE books (
    id      INTEGER PRIMARY KEY,
    isbn    TEXT NOT NULL UNIQUE,
    title   TEXT NOT NULL,
    author  TEXT NOT NULL
);

-- A physical copy of a book.
CREATE TABLE copies (
    id       INTEGER PRIMARY KEY,
    book_id  INTEGER NOT NULL REFERENCES books(id),
    barcode  TEXT NOT NULL UNIQUE
);

CREATE TABLE members (
    id     INTEGER PRIMARY KEY,
    name   TEXT NOT NULL,
    email  TEXT NOT NULL UNIQUE
);

CREATE TABLE loans (
    id           INTEGER PRIMARY KEY,
    copy_id      INTEGER NOT NULL REFERENCES copies(id),
    member_id    INTEGER NOT NULL REFERENCES members(id),
    borrowed_at  TEXT NOT NULL,            -- ISO-8601 UTC
    due_at       TEXT NOT NULL,
    returned_at  TEXT,                     -- NULL = still out
    CHECK (due_at > borrowed_at),
    CHECK (returned_at IS NULL OR returned_at >= borrowed_at)
);

-- The rule "a copy that is on loan cannot be lent again", enforced by the
-- database: at most ONE open loan (returned_at IS NULL) per copy.
CREATE UNIQUE INDEX one_open_loan_per_copy
    ON loans(copy_id) WHERE returned_at IS NULL;

-- Lookup index for copies -> books joins.
CREATE INDEX copies_book_id ON copies(book_id);
