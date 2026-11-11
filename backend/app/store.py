"""SQLite storage for bills and each person's share."""
import json
import secrets
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone

from .config import get_settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS bills (
    id TEXT PRIMARY KEY, created_at TEXT NOT NULL, receipt_json TEXT NOT NULL, currency TEXT NOT NULL,
    people_json TEXT NOT NULL DEFAULT '[]', payer TEXT, payee_email TEXT, story_json TEXT NOT NULL DEFAULT '[]', plan_json TEXT
);
CREATE TABLE IF NOT EXISTS shares (
    id TEXT PRIMARY KEY, bill_id TEXT NOT NULL REFERENCES bills(id), person TEXT NOT NULL, amount REAL NOT NULL,
    detail_json TEXT NOT NULL, status TEXT NOT NULL, order_id TEXT, capture_id TEXT, paid_at TEXT
);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@contextmanager
def connect():
    connection = sqlite3.connect(get_settings().database_path)
    connection.row_factory = sqlite3.Row
    try:
        yield connection
        connection.commit()
    finally:
        connection.close()


def init() -> None:
    with connect() as db:
        db.executescript(SCHEMA)


def create_bill(receipt: dict, currency: str) -> str:
    bill_id = secrets.token_urlsafe(8)
    with connect() as db:
        db.execute("INSERT INTO bills (id, created_at, receipt_json, currency) VALUES (?, ?, ?, ?)", (bill_id, _now(), json.dumps(receipt), currency))
    return bill_id


def get_bill(bill_id: str) -> dict | None:
    with connect() as db:
        row = db.execute("SELECT * FROM bills WHERE id = ?", (bill_id,)).fetchone()
        if not row:
            return None
        shares = db.execute("SELECT * FROM shares WHERE bill_id = ? ORDER BY rowid", (bill_id,)).fetchall()
    return {
        "id": row["id"], "created_at": row["created_at"], "currency": row["currency"],
        "receipt": json.loads(row["receipt_json"]), "people": json.loads(row["people_json"]),
        "payer": row["payer"], "payee_email": row["payee_email"], "story": json.loads(row["story_json"]),
        "plan": json.loads(row["plan_json"]) if row["plan_json"] else None,
        "shares": [_share(share) for share in shares],
    }


def save_split(bill_id: str, people: list[str], payer: str, payee_email: str | None, story: list[str], plan: dict, shares: list[dict]) -> None:
    """Store a (re)worked split; earlier unpaid shares are replaced."""
    with connect() as db:
        db.execute("UPDATE bills SET people_json = ?, payer = ?, payee_email = ?, story_json = ?, plan_json = ? WHERE id = ?",
                   (json.dumps(people), payer, payee_email, json.dumps(story), json.dumps(plan), bill_id))
        db.execute("DELETE FROM shares WHERE bill_id = ?", (bill_id,))
        for share in shares:
            status = "payer" if share["person"] == payer else "pending"
            db.execute("INSERT INTO shares (id, bill_id, person, amount, detail_json, status) VALUES (?, ?, ?, ?, ?, ?)",
                       (secrets.token_urlsafe(8), bill_id, share["person"], share["amount"], json.dumps(share), status))


def get_share(share_id: str) -> dict | None:
    with connect() as db:
        row = db.execute("SELECT * FROM shares WHERE id = ?", (share_id,)).fetchone()
    return _share(row) if row else None


def set_order(share_id: str, order_id: str) -> None:
    with connect() as db:
        db.execute("UPDATE shares SET order_id = ? WHERE id = ?", (order_id, share_id))


def mark_paid(share_id: str, capture_id: str) -> None:
    with connect() as db:
        db.execute("UPDATE shares SET status = 'paid', capture_id = ?, paid_at = ? WHERE id = ?", (capture_id, _now(), share_id))


def _share(row: sqlite3.Row) -> dict:
    return {"id": row["id"], "bill_id": row["bill_id"], "person": row["person"], "amount": row["amount"], "status": row["status"],
            "order_id": row["order_id"], "capture_id": row["capture_id"], "paid_at": row["paid_at"], **_detail(row["detail_json"])}


def _detail(detail_json: str) -> dict:
    detail = json.loads(detail_json)
    return {key: detail[key] for key in ("items", "items_total", "extras", "note")}
