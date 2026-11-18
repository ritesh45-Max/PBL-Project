"""SQLite database setup for TruthGuard AI.

Two tables:
- users     : registered accounts (passwords stored as hashes only)
- analyses  : every saved detection result, linked to a user
"""
import os
import sqlite3

from flask import current_app, g

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT UNIQUE NOT NULL,
    full_name     TEXT NOT NULL,
    email         TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    created_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS analyses (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    content_type    TEXT NOT NULL,
    title           TEXT NOT NULL,
    score           INTEGER NOT NULL,
    prediction      TEXT NOT NULL,
    confidence      TEXT NOT NULL,
    mode            TEXT NOT NULL,
    explanation     TEXT NOT NULL,
    indicators      TEXT NOT NULL,
    recommendations TEXT NOT NULL,
    signals         TEXT NOT NULL,
    created_at      TEXT NOT NULL
);
"""


def get_db():
    """Return a database connection for the current request."""
    if "db" not in g:
        g.db = sqlite3.connect(current_app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(_exc=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_app_db(app):
    """Create the database file and tables the first time the app starts."""
    os.makedirs(os.path.dirname(app.config["DATABASE"]), exist_ok=True)
    app.teardown_appcontext(close_db)
    with app.app_context():
        db = get_db()
        db.executescript(SCHEMA)
        db.commit()
