"""
SQLite persistence for Political Arena.
Tables: users, fight_history, daily_claims, referrals.
"""
from __future__ import annotations

import sqlite3
import time
from pathlib import Path

DB_PATH = Path(__file__).parent / "arena.db"

# ── Connection ───────────────────────────────────────────

def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            sid             TEXT UNIQUE NOT NULL,
            telegram_id     INTEGER UNIQUE,
            telegram_name   TEXT,
            telegram_user   TEXT,
            telegram_photo  TEXT,
            balance         INTEGER DEFAULT 100,
            total_wins      INTEGER DEFAULT 0,
            total_losses    INTEGER DEFAULT 0,
            streak          INTEGER DEFAULT 0,
            best_streak     INTEGER DEFAULT 0,
            fights_today    INTEGER DEFAULT 0,
            last_fight_date TEXT DEFAULT '',
            last_daily_date TEXT DEFAULT '',
            daily_streak    INTEGER DEFAULT 0,
            referred_by     INTEGER,
            referral_count  INTEGER DEFAULT 0,
            created_at      INTEGER,
            updated_at      INTEGER
        );
        CREATE TABLE IF NOT EXISTS fight_history (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER NOT NULL,
            fight_id    TEXT NOT NULL,
            fighter_a   TEXT NOT NULL,
            fighter_b   TEXT NOT NULL,
            winner_id   TEXT NOT NULL,
            bet_fighter TEXT NOT NULL,
            bet_amount  INTEGER DEFAULT 0,
            payout      INTEGER DEFAULT 0,
            bet_won     INTEGER DEFAULT 0,
            created_at  INTEGER,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
        CREATE TABLE IF NOT EXISTS daily_claims (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER NOT NULL,
            amount      INTEGER NOT NULL,
            day_streak  INTEGER DEFAULT 1,
            claimed_at  TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
        CREATE TABLE IF NOT EXISTS referrals (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            referrer_id   INTEGER NOT NULL,
            referred_id   INTEGER NOT NULL,
            bonus_amount  INTEGER DEFAULT 200,
            created_at    INTEGER,
            FOREIGN KEY (referrer_id) REFERENCES users(id),
            FOREIGN KEY (referred_id) REFERENCES users(id)
        );
        CREATE INDEX IF NOT EXISTS idx_users_sid ON users(sid);
        CREATE INDEX IF NOT EXISTS idx_users_tg  ON users(telegram_id);
        CREATE INDEX IF NOT EXISTS idx_hist_user ON fight_history(user_id);
    """)
    conn.commit()
    conn.close()


# ── User CRUD ────────────────────────────────────────────

def get_or_create_user(sid: str) -> dict:
    conn = get_db()
    row = conn.execute("SELECT * FROM users WHERE sid = ?", (sid,)).fetchone()
    if row:
        d = dict(row)
        today = time.strftime("%Y-%m-%d")
        if d["last_fight_date"] != today:
            conn.execute(
                "UPDATE users SET fights_today=0, last_fight_date=? WHERE id=?",
                (today, d["id"]),
            )
            conn.commit()
            d["fights_today"] = 0
            d["last_fight_date"] = today
        conn.close()
        return d
    now = int(time.time())
    conn.execute(
        "INSERT INTO users (sid, balance, created_at, updated_at) VALUES (?,100,?,?)",
        (sid, now, now),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM users WHERE sid = ?", (sid,)).fetchone()
    conn.close()
    return dict(row)


def get_user_by_tg(tg_id: int) -> dict | None:
    conn = get_db()
    row = conn.execute("SELECT * FROM users WHERE telegram_id=?", (tg_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def link_telegram(user_id: int, tg_id: int, name: str, username: str, photo: str) -> dict:
    conn = get_db()
    existing = conn.execute("SELECT * FROM users WHERE telegram_id=?", (tg_id,)).fetchone()
    if existing:
        conn.close()
        return dict(existing)
    now = int(time.time())
    conn.execute(
        "UPDATE users SET telegram_id=?, telegram_name=?, telegram_user=?, telegram_photo=?, updated_at=? WHERE id=?",
        (tg_id, name, username, photo, now, user_id),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
    conn.close()
    return dict(row)


def update_balance(user_id: int, delta: int) -> int:
    conn = get_db()
    conn.execute(
        "UPDATE users SET balance=balance+?, updated_at=? WHERE id=?",
        (delta, int(time.time()), user_id),
    )
    conn.commit()
    row = conn.execute("SELECT balance FROM users WHERE id=?", (user_id,)).fetchone()
    conn.close()
    return row["balance"]


def set_field(user_id: int, field: str, value) -> None:
    allowed = {
        "balance", "streak", "best_streak", "fights_today",
        "total_wins", "total_losses", "last_fight_date",
    }
    if field not in allowed:
        raise ValueError(f"Field {field} not allowed")
    conn = get_db()
    conn.execute(f"UPDATE users SET {field}=?, updated_at=? WHERE id=?",
                 (value, int(time.time()), user_id))
    conn.commit()
    conn.close()


# ── Daily Bonus ──────────────────────────────────────────

def claim_daily(user_id: int) -> dict:
    conn = get_db()
    today = time.strftime("%Y-%m-%d")
    user = dict(conn.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone())

    if user["last_daily_date"] == today:
        conn.close()
        return {"ok": False, "reason": "already_claimed"}

    yesterday = time.strftime(
        "%Y-%m-%d", time.gmtime(time.time() - 86400)
    )
    if user["last_daily_date"] == yesterday:
        day_streak = user["daily_streak"] + 1
    else:
        day_streak = 1

    base = 50
    bonus = min(base + (day_streak - 1) * 10, 200)  # 50→200 cap

    now = int(time.time())
    conn.execute(
        "INSERT INTO daily_claims (user_id,amount,day_streak,claimed_at) VALUES (?,?,?,?)",
        (user_id, bonus, day_streak, today),
    )
    conn.execute(
        "UPDATE users SET balance=balance+?, last_daily_date=?, daily_streak=?, updated_at=? WHERE id=?",
        (bonus, today, day_streak, now, user_id),
    )
    conn.commit()
    new_bal = conn.execute("SELECT balance FROM users WHERE id=?", (user_id,)).fetchone()["balance"]
    conn.close()
    return {"ok": True, "amount": bonus, "day_streak": day_streak, "balance": new_bal}


# ── Referral ─────────────────────────────────────────────

def process_referral(referrer_id: int, new_user_id: int) -> dict:
    if referrer_id == new_user_id:
        return {"ok": False, "reason": "self_referral"}
    conn = get_db()
    existing = conn.execute(
        "SELECT 1 FROM referrals WHERE referred_id=?", (new_user_id,)
    ).fetchone()
    if existing:
        conn.close()
        return {"ok": False, "reason": "already_referred"}
    now = int(time.time())
    conn.execute(
        "INSERT INTO referrals (referrer_id,referred_id,bonus_amount,created_at) VALUES (?,?,200,?)",
        (referrer_id, new_user_id, now),
    )
    conn.execute(
        "UPDATE users SET balance=balance+200, referral_count=referral_count+1, updated_at=? WHERE id=?",
        (now, referrer_id),
    )
    conn.execute(
        "UPDATE users SET balance=balance+100, referred_by=?, updated_at=? WHERE id=?",
        (referrer_id, now, new_user_id),
    )
    conn.commit()
    conn.close()
    return {"ok": True, "referrer_bonus": 200, "referred_bonus": 100}


# ── Fight History ────────────────────────────────────────

def record_fight(user_id: int, fight_id: str, fighter_a: str, fighter_b: str,
                 winner_id: str, bet_fighter: str, bet_amount: int,
                 payout: int, bet_won: bool):
    conn = get_db()
    now = int(time.time())
    conn.execute(
        """INSERT INTO fight_history
           (user_id,fight_id,fighter_a,fighter_b,winner_id,bet_fighter,bet_amount,payout,bet_won,created_at)
           VALUES (?,?,?,?,?,?,?,?,?,?)""",
        (user_id, fight_id, fighter_a, fighter_b, winner_id, bet_fighter,
         bet_amount, payout, int(bet_won), now),
    )
    if bet_won:
        conn.execute(
            "UPDATE users SET total_wins=total_wins+1, streak=streak+1, best_streak=MAX(best_streak,streak+1), updated_at=? WHERE id=?",
            (now, user_id),
        )
    else:
        conn.execute(
            "UPDATE users SET total_losses=total_losses+1, streak=0, updated_at=? WHERE id=?",
            (now, user_id),
        )
    conn.execute(
        "UPDATE users SET fights_today=fights_today+1, updated_at=? WHERE id=?",
        (now, user_id),
    )
    conn.commit()
    conn.close()


def get_history(user_id: int, limit: int = 20) -> list:
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM fight_history WHERE user_id=? ORDER BY id DESC LIMIT ?",
        (user_id, limit),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_leaderboard(limit: int = 20) -> list:
    conn = get_db()
    rows = conn.execute(
        """SELECT id, telegram_name, telegram_user, telegram_photo,
                  total_wins, total_losses, best_streak, balance
           FROM users WHERE total_wins > 0
           ORDER BY total_wins DESC, best_streak DESC LIMIT ?""",
        (limit,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# Auto-init on import
init_db()
