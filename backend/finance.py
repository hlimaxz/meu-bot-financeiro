from collections import defaultdict
from datetime import datetime
from typing import Any, Optional

from backend.db import get_db, previous_period, row_to_dict, rows_to_list


def user_summary(user_id: int, start: str, end: str) -> dict[str, Any]:
    with get_db() as conn:
        income = conn.execute(
            """
            SELECT COALESCE(SUM(amount), 0) AS total
            FROM transactions
            WHERE user_id = ? AND type = 'income' AND date BETWEEN ? AND ?
            """,
            (user_id, start, end),
        ).fetchone()["total"]
        expense = conn.execute(
            """
            SELECT COALESCE(SUM(amount), 0) AS total
            FROM transactions
            WHERE user_id = ? AND type = 'expense' AND date BETWEEN ? AND ?
            """,
            (user_id, start, end),
        ).fetchone()["total"]
        accounts = conn.execute(
            "SELECT COALESCE(SUM(balance), 0) AS total FROM accounts WHERE user_id = ?",
            (user_id,),
        ).fetchone()["total"]

        p_start, p_end = previous_period(start, end)
        prev_income = conn.execute(
            """
            SELECT COALESCE(SUM(amount), 0) AS total
            FROM transactions
            WHERE user_id = ? AND type = 'income' AND date BETWEEN ? AND ?
            """,
            (user_id, p_start, p_end),
        ).fetchone()["total"]
        prev_expense = conn.execute(
            """
            SELECT COALESCE(SUM(amount), 0) AS total
            FROM transactions
            WHERE user_id = ? AND type = 'expense' AND date BETWEEN ? AND ?
            """,
            (user_id, p_start, p_end),
        ).fetchone()["total"]

    savings = income - expense
    prev_savings = prev_income - prev_expense
    return {
        "balance": round(float(accounts), 2),
        "income": round(float(income), 2),
        "expense": round(float(expense), 2),
        "savings": round(float(savings), 2),
        "previous": {
            "income": round(float(prev_income), 2),
            "expense": round(float(prev_expense), 2),
            "savings": round(float(prev_savings), 2),
        },
        "start": start,
        "end": end,
    }


def cashflow_series(user_id: int, start: str, end: str) -> list[dict[str, Any]]:
    with get_db() as conn:
        rows = conn.execute(
            """
            SELECT date, type, SUM(amount) AS total
            FROM transactions
            WHERE user_id = ? AND date BETWEEN ? AND ?
            GROUP BY date, type
            ORDER BY date
            """,
            (user_id, start, end),
        ).fetchall()
    by_day: dict[str, dict[str, float]] = defaultdict(lambda: {"income": 0.0, "expense": 0.0})
    for row in rows:
        by_day[row["date"]][row["type"]] = float(row["total"])
    series = []
    running = 0.0
    for day in sorted(by_day.keys()):
        inc = by_day[day]["income"]
        exp = by_day[day]["expense"]
        running += inc - exp
        series.append(
            {
                "date": day,
                "income": round(inc, 2),
                "expense": round(exp, 2),
                "balance": round(running, 2),
            }
        )
    return series


def spending_by_category(user_id: int, start: str, end: str) -> list[dict[str, Any]]:
    with get_db() as conn:
        rows = conn.execute(
            """
            SELECT category, SUM(amount) AS total
            FROM transactions
            WHERE user_id = ? AND type = 'expense' AND date BETWEEN ? AND ?
            GROUP BY category
            ORDER BY total DESC
            """,
            (user_id, start, end),
        ).fetchall()
    total = sum(float(r["total"]) for r in rows) or 1
    return [
        {
            "category": r["category"],
            "amount": round(float(r["total"]), 2),
            "percent": round(float(r["total"]) / total * 100, 1),
        }
        for r in rows
    ]


def list_transactions(
    user_id: int,
    start: Optional[str] = None,
    end: Optional[str] = None,
    category: Optional[str] = None,
    account_id: Optional[int] = None,
    card_id: Optional[int] = None,
    tx_type: Optional[str] = None,
    search: Optional[str] = None,
    min_amount: Optional[float] = None,
    max_amount: Optional[float] = None,
    limit: int = 50,
    offset: int = 0,
):
    sql = """
        SELECT t.*, a.name AS account_name, c.name AS card_name
        FROM transactions t
        LEFT JOIN accounts a ON a.id = t.account_id
        LEFT JOIN cards c ON c.id = t.card_id
        WHERE t.user_id = ?
    """
    params: list[Any] = [user_id]
    if start:
        sql += " AND t.date >= ?"
        params.append(start)
    if end:
        sql += " AND t.date <= ?"
        params.append(end)
    if category:
        sql += " AND t.category = ?"
        params.append(category)
    if account_id:
        sql += " AND t.account_id = ?"
        params.append(account_id)
    if card_id:
        sql += " AND t.card_id = ?"
        params.append(card_id)
    if tx_type in ("income", "expense"):
        sql += " AND t.type = ?"
        params.append(tx_type)
    if search:
        sql += " AND (t.description LIKE ? OR t.category LIKE ?)"
        like = f"%{search}%"
        params.extend([like, like])
    if min_amount is not None:
        sql += " AND t.amount >= ?"
        params.append(min_amount)
    if max_amount is not None:
        sql += " AND t.amount <= ?"
        params.append(max_amount)
    count_sql = f"SELECT COUNT(*) AS c FROM ({sql})"
    sql += " ORDER BY t.date DESC, t.id DESC LIMIT ? OFFSET ?"
    params_page = params + [limit, offset]
    with get_db() as conn:
        total = conn.execute(count_sql, params).fetchone()["c"]
        rows = conn.execute(sql, params_page).fetchall()
    return {"items": rows_to_list(rows), "total": total, "limit": limit, "offset": offset}


def get_transaction(user_id: int, tx_id: int):
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM transactions WHERE id = ? AND user_id = ?",
            (tx_id, user_id),
        ).fetchone()
        return row_to_dict(row)


def create_transaction(user_id: int, data: dict[str, Any]):
    amount = abs(float(data["amount"]))
    tx_type = data.get("type", "expense")
    if tx_type not in ("income", "expense"):
        tx_type = "expense"
    date = data.get("date") or datetime.now().strftime("%Y-%m-%d")
    with get_db() as conn:
        cur = conn.execute(
            """
            INSERT INTO transactions
            (user_id, description, category, amount, type, date, account_id, card_id, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                str(data.get("description") or data.get("categoria") or "Lançamento")[:200],
                str(data.get("category") or data.get("categoria") or "Outros")[:80],
                amount,
                tx_type,
                date,
                data.get("account_id"),
                data.get("card_id"),
                data.get("notes"),
            ),
        )
        tx_id = cur.lastrowid
        account_id = data.get("account_id")
        if account_id:
            delta = amount if tx_type == "income" else -amount
            conn.execute(
                "UPDATE accounts SET balance = balance + ? WHERE id = ? AND user_id = ?",
                (delta, account_id, user_id),
            )
        card_id = data.get("card_id")
        if card_id and tx_type == "expense":
            conn.execute(
                "UPDATE cards SET limit_used = limit_used + ? WHERE id = ? AND user_id = ?",
                (amount, card_id, user_id),
            )
    return get_transaction(user_id, tx_id)


def update_transaction(user_id: int, tx_id: int, data: dict[str, Any]):
    current = get_transaction(user_id, tx_id)
    if not current:
        return None
    fields = []
    params: list[Any] = []
    for key in ("description", "category", "amount", "type", "date", "account_id", "card_id", "notes"):
        if key in data:
            fields.append(f"{key} = ?")
            value = data[key]
            if key == "amount":
                value = abs(float(value))
            params.append(value)
    if not fields:
        return current
    params.extend([tx_id, user_id])
    with get_db() as conn:
        conn.execute(
            f"UPDATE transactions SET {', '.join(fields)} WHERE id = ? AND user_id = ?",
            params,
        )
    return get_transaction(user_id, tx_id)


def delete_transaction(user_id: int, tx_id: int) -> bool:
    with get_db() as conn:
        cur = conn.execute(
            "DELETE FROM transactions WHERE id = ? AND user_id = ?",
            (tx_id, user_id),
        )
        return cur.rowcount > 0


def list_accounts(user_id: int):
    with get_db() as conn:
        return rows_to_list(
            conn.execute(
                "SELECT * FROM accounts WHERE user_id = ? ORDER BY name", (user_id,)
            ).fetchall()
        )


def create_account(user_id: int, data: dict[str, Any]):
    with get_db() as conn:
        cur = conn.execute(
            """
            INSERT INTO accounts (user_id, name, bank, type, balance, last_sync)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                str(data.get("name", "Conta"))[:80],
                data.get("bank"),
                data.get("type", "corrente"),
                float(data.get("balance") or 0),
                datetime.now().isoformat(),
            ),
        )
        aid = cur.lastrowid
        row = conn.execute(
            "SELECT * FROM accounts WHERE id = ? AND user_id = ?", (aid, user_id)
        ).fetchone()
        return row_to_dict(row)


def update_account(user_id: int, account_id: int, data: dict[str, Any]):
    with get_db() as conn:
        existing = conn.execute(
            "SELECT id FROM accounts WHERE id = ? AND user_id = ?",
            (account_id, user_id),
        ).fetchone()
        if not existing:
            return None
        fields, params = [], []
        for key in ("name", "bank", "type", "balance"):
            if key in data:
                fields.append(f"{key} = ?")
                params.append(data[key])
        if fields:
            fields.append("last_sync = ?")
            params.append(datetime.now().isoformat())
            params.extend([account_id, user_id])
            conn.execute(
                f"UPDATE accounts SET {', '.join(fields)} WHERE id = ? AND user_id = ?",
                params,
            )
        row = conn.execute(
            "SELECT * FROM accounts WHERE id = ? AND user_id = ?",
            (account_id, user_id),
        ).fetchone()
        return row_to_dict(row)


def delete_account(user_id: int, account_id: int) -> bool:
    with get_db() as conn:
        cur = conn.execute(
            "DELETE FROM accounts WHERE id = ? AND user_id = ?",
            (account_id, user_id),
        )
        return cur.rowcount > 0


def list_cards(user_id: int):
    with get_db() as conn:
        rows = rows_to_list(
            conn.execute(
                "SELECT * FROM cards WHERE user_id = ? ORDER BY name", (user_id,)
            ).fetchall()
        )
    for card in rows:
        total = float(card["limit_total"] or 0)
        used = float(card["limit_used"] or 0)
        card["available"] = round(max(total - used, 0), 2)
        card["usage_percent"] = round((used / total * 100) if total else 0, 1)
    return rows


def create_card(user_id: int, data: dict[str, Any]):
    with get_db() as conn:
        cur = conn.execute(
            """
            INSERT INTO cards (user_id, name, brand, limit_total, limit_used, closing_day, due_day)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                str(data.get("name", "Cartão"))[:80],
                data.get("brand"),
                float(data.get("limit_total") or 0),
                float(data.get("limit_used") or 0),
                data.get("closing_day"),
                data.get("due_day"),
            ),
        )
        cid = cur.lastrowid
    cards = [c for c in list_cards(user_id) if c["id"] == cid]
    return cards[0] if cards else None


def update_card(user_id: int, card_id: int, data: dict[str, Any]):
    with get_db() as conn:
        existing = conn.execute(
            "SELECT id FROM cards WHERE id = ? AND user_id = ?",
            (card_id, user_id),
        ).fetchone()
        if not existing:
            return None
        fields, params = [], []
        for key in ("name", "brand", "limit_total", "limit_used", "closing_day", "due_day"):
            if key in data:
                fields.append(f"{key} = ?")
                params.append(data[key])
        if fields:
            params.extend([card_id, user_id])
            conn.execute(
                f"UPDATE cards SET {', '.join(fields)} WHERE id = ? AND user_id = ?",
                params,
            )
    cards = [c for c in list_cards(user_id) if c["id"] == card_id]
    return cards[0] if cards else None


def delete_card(user_id: int, card_id: int) -> bool:
    with get_db() as conn:
        cur = conn.execute(
            "DELETE FROM cards WHERE id = ? AND user_id = ?", (card_id, user_id)
        )
        return cur.rowcount > 0


def list_budgets(user_id: int, start: str, end: str):
    with get_db() as conn:
        budgets = rows_to_list(
            conn.execute(
                "SELECT * FROM budgets WHERE user_id = ? ORDER BY category", (user_id,)
            ).fetchall()
        )
        spent_rows = conn.execute(
            """
            SELECT category, SUM(amount) AS total
            FROM transactions
            WHERE user_id = ? AND type = 'expense' AND date BETWEEN ? AND ?
            GROUP BY category
            """,
            (user_id, start, end),
        ).fetchall()
    spent = {r["category"]: float(r["total"]) for r in spent_rows}
    result = []
    for b in budgets:
        current = spent.get(b["category"], 0)
        limit_amount = float(b["limit_amount"])
        percent = (current / limit_amount * 100) if limit_amount else 0
        result.append(
            {
                **b,
                "current": round(current, 2),
                "percent": round(percent, 1),
                "alert": percent >= 80,
            }
        )
    return result


def upsert_budget(user_id: int, category: str, limit_amount: float, period: str = "month"):
    with get_db() as conn:
        conn.execute(
            """
            INSERT INTO budgets (user_id, category, limit_amount, period)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(user_id, category, period)
            DO UPDATE SET limit_amount = excluded.limit_amount
            """,
            (user_id, category, float(limit_amount), period),
        )
    start = datetime.now().replace(day=1).strftime("%Y-%m-%d")
    end = datetime.now().strftime("%Y-%m-%d")
    items = list_budgets(user_id, start, end)
    return next((b for b in items if b["category"] == category), None)


def delete_budget(user_id: int, budget_id: int) -> bool:
    with get_db() as conn:
        cur = conn.execute(
            "DELETE FROM budgets WHERE id = ? AND user_id = ?",
            (budget_id, user_id),
        )
        return cur.rowcount > 0


def list_goals(user_id: int):
    with get_db() as conn:
        rows = rows_to_list(
            conn.execute(
                "SELECT * FROM goals WHERE user_id = ? ORDER BY deadline IS NULL, deadline",
                (user_id,),
            ).fetchall()
        )
    for g in rows:
        target = float(g["target_amount"] or 0)
        current = float(g["current_amount"] or 0)
        g["percent"] = round((current / target * 100) if target else 0, 1)
    return rows


def create_goal(user_id: int, data: dict[str, Any]):
    with get_db() as conn:
        cur = conn.execute(
            """
            INSERT INTO goals (user_id, name, target_amount, current_amount, deadline)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                user_id,
                str(data.get("name", "Meta"))[:80],
                float(data.get("target_amount") or 0),
                float(data.get("current_amount") or 0),
                data.get("deadline"),
            ),
        )
        gid = cur.lastrowid
    return next((g for g in list_goals(user_id) if g["id"] == gid), None)


def update_goal(user_id: int, goal_id: int, data: dict[str, Any]):
    with get_db() as conn:
        existing = conn.execute(
            "SELECT id FROM goals WHERE id = ? AND user_id = ?",
            (goal_id, user_id),
        ).fetchone()
        if not existing:
            return None
        fields, params = [], []
        for key in ("name", "target_amount", "current_amount", "deadline"):
            if key in data:
                fields.append(f"{key} = ?")
                params.append(data[key])
        if fields:
            params.extend([goal_id, user_id])
            conn.execute(
                f"UPDATE goals SET {', '.join(fields)} WHERE id = ? AND user_id = ?",
                params,
            )
    return next((g for g in list_goals(user_id) if g["id"] == goal_id), None)


def delete_goal(user_id: int, goal_id: int) -> bool:
    with get_db() as conn:
        cur = conn.execute(
            "DELETE FROM goals WHERE id = ? AND user_id = ?", (goal_id, user_id)
        )
        return cur.rowcount > 0


def list_notifications(user_id: int):
    with get_db() as conn:
        return rows_to_list(
            conn.execute(
                """
                SELECT * FROM notifications
                WHERE user_id = ?
                ORDER BY created_at DESC
                LIMIT 50
                """,
                (user_id,),
            ).fetchall()
        )


def mark_notification_read(user_id: int, notif_id: int):
    with get_db() as conn:
        conn.execute(
            "UPDATE notifications SET read = 1 WHERE id = ? AND user_id = ?",
            (notif_id, user_id),
        )


def add_notification(user_id: int, title: str, body: str, kind: str = "info"):
    with get_db() as conn:
        conn.execute(
            """
            INSERT INTO notifications (user_id, title, body, kind, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (user_id, title, body, kind, datetime.utcnow().isoformat()),
        )


def reports_payload(user_id: int, start: str, end: str):
    summary = user_summary(user_id, start, end)
    categories = spending_by_category(user_id, start, end)
    txs = list_transactions(user_id, start=start, end=end, limit=10, offset=0)
    top = [t for t in txs["items"] if t["type"] == "expense"][:8]
    return {
        "summary": summary,
        "categories": categories,
        "series": cashflow_series(user_id, start, end),
        "top_expenses": top,
    }
