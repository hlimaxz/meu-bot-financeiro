import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta
from typing import Any, Iterator, Optional

from backend.config import DB_PATH


@contextmanager
def get_db() -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def row_to_dict(row: Optional[sqlite3.Row]) -> Optional[dict[str, Any]]:
    if row is None:
        return None
    return dict(row)


def rows_to_list(rows) -> list[dict[str, Any]]:
    return [dict(r) for r in rows]


def init_db() -> None:
    with get_db() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT UNIQUE,
                phone TEXT UNIQUE,
                password_hash TEXT,
                plan TEXT NOT NULL DEFAULT 'livre',
                theme TEXT NOT NULL DEFAULT 'system',
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS password_resets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                token_hash TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS accounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                bank TEXT,
                type TEXT NOT NULL DEFAULT 'corrente',
                balance REAL NOT NULL DEFAULT 0,
                last_sync TEXT,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS cards (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                brand TEXT,
                limit_total REAL NOT NULL DEFAULT 0,
                limit_used REAL NOT NULL DEFAULT 0,
                closing_day INTEGER,
                due_day INTEGER,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                name TEXT NOT NULL,
                icon TEXT,
                UNIQUE(user_id, name)
            );

            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                description TEXT NOT NULL,
                category TEXT NOT NULL,
                amount REAL NOT NULL,
                type TEXT NOT NULL,
                date TEXT NOT NULL,
                account_id INTEGER,
                card_id INTEGER,
                notes TEXT,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (account_id) REFERENCES accounts(id) ON DELETE SET NULL,
                FOREIGN KEY (card_id) REFERENCES cards(id) ON DELETE SET NULL
            );

            CREATE TABLE IF NOT EXISTS budgets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                category TEXT NOT NULL,
                limit_amount REAL NOT NULL,
                period TEXT NOT NULL DEFAULT 'month',
                UNIQUE(user_id, category, period),
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS goals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                target_amount REAL NOT NULL,
                current_amount REAL NOT NULL DEFAULT 0,
                deadline TEXT,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                title TEXT NOT NULL DEFAULT 'Nova conversa',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                body TEXT NOT NULL,
                kind TEXT NOT NULL DEFAULT 'info',
                read INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS settings (
                user_id INTEGER PRIMARY KEY,
                notify_budget INTEGER NOT NULL DEFAULT 1,
                notify_goals INTEGER NOT NULL DEFAULT 1,
                notify_recurring INTEGER NOT NULL DEFAULT 1,
                ai_style TEXT NOT NULL DEFAULT 'clara',
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );
            """
        )
        _migrate_legacy(conn)
        _ensure_default_categories(conn)


def _table_exists(conn: sqlite3.Connection, name: str) -> bool:
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone()
    return row is not None


def _migrate_legacy(conn: sqlite3.Connection) -> None:
    """Move dados do bot WhatsApp (gastos/historico) para o schema multi-usuário."""
    if not _table_exists(conn, "gastos"):
        return
    existing = conn.execute("SELECT COUNT(*) AS c FROM transactions").fetchone()["c"]
    if existing:
        return
    user = conn.execute("SELECT id FROM users ORDER BY id LIMIT 1").fetchone()
    if not user:
        now = datetime.utcnow().isoformat()
        cur = conn.execute(
            "INSERT INTO users (name, email, plan, theme, created_at) VALUES (?, ?, ?, ?, ?)",
            ("Hector", "hector@kaliba.local", "livre", "system", now),
        )
        user_id = cur.lastrowid
    else:
        user_id = user["id"]

    for row in conn.execute("SELECT data, categoria, valor FROM gastos").fetchall():
        valor = float(row["valor"] or 0)
        tipo = "income" if valor < 0 else "expense"
        conn.execute(
            """
            INSERT INTO transactions (user_id, description, category, amount, type, date)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                row["categoria"] or "Geral",
                row["categoria"] or "Geral",
                abs(valor),
                tipo,
                row["data"] or datetime.now().strftime("%Y-%m-%d"),
            ),
        )

    if _table_exists(conn, "historico"):
        hist = conn.execute(
            "SELECT role, content FROM historico ORDER BY id ASC"
        ).fetchall()
        if hist:
            now = datetime.utcnow().isoformat()
            cur = conn.execute(
                """
                INSERT INTO conversations (user_id, title, created_at, updated_at)
                VALUES (?, ?, ?, ?)
                """,
                (user_id, "WhatsApp", now, now),
            )
            cid = cur.lastrowid
            for item in hist:
                conn.execute(
                    """
                    INSERT INTO messages (conversation_id, user_id, role, content, created_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (cid, user_id, item["role"], item["content"], now),
                )


DEFAULT_CATEGORIES = [
    "Alimentação",
    "Transporte",
    "Moradia",
    "Lazer",
    "Saúde",
    "Educação",
    "Assinaturas",
    "Compras",
    "Salário",
    "Outros",
]


def _ensure_default_categories(conn: sqlite3.Connection) -> None:
    for name in DEFAULT_CATEGORIES:
        conn.execute(
            "INSERT OR IGNORE INTO categories (user_id, name) VALUES (NULL, ?)",
            (name,),
        )


def period_range(period: str, start: Optional[str] = None, end: Optional[str] = None):
    today = datetime.now().date()
    if period == "today":
        return today.isoformat(), today.isoformat()
    if period == "week":
        begin = today - timedelta(days=today.weekday())
        return begin.isoformat(), today.isoformat()
    if period == "quarter":
        begin = today - timedelta(days=90)
        return begin.isoformat(), today.isoformat()
    if period == "custom" and start and end:
        return start, end
    begin = today.replace(day=1)
    return begin.isoformat(), today.isoformat()


def previous_period(start: str, end: str):
    s = datetime.fromisoformat(start).date()
    e = datetime.fromisoformat(end).date()
    delta = (e - s).days + 1
    prev_end = s - timedelta(days=1)
    prev_start = prev_end - timedelta(days=delta - 1)
    return prev_start.isoformat(), prev_end.isoformat()
