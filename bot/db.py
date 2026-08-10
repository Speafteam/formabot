"""Хранилище на SQLite. Вся долгая память бота живёт здесь.

Важно: таймеры отдыха тоже пишутся в базу. Если бот перезапустится посреди
тренировки, при старте он поднимет незакрытые таймеры и досчитает их —
иначе человек так и останется стоять у штанги.
"""

import json
from datetime import datetime, date

import aiosqlite

from .config import DB_PATH, TZ, DEFAULT_TIMES

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    tg_id         INTEGER PRIMARY KEY,
    username      TEXT,
    sex           TEXT,
    age           INTEGER,
    height_cm     REAL,
    weight_kg     REAL,
    start_kg      REAL,
    activity      TEXT,
    goal          TEXT,
    target_kg     REAL,
    target_date   TEXT,
    kcal          INTEGER,
    protein       INTEGER,
    fat           INTEGER,
    carbs         INTEGER,
    water_ml      INTEGER,
    times_json    TEXT,
    weigh_in      TEXT,
    pref_place    TEXT,
    pref_kind     TEXT,
    nicknames_json TEXT,
    created_at    TEXT
);

CREATE TABLE IF NOT EXISTS meals (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    tg_id    INTEGER NOT NULL,
    day      TEXT NOT NULL,
    name     TEXT,
    grams    REAL,
    kcal     REAL,
    protein  REAL,
    fat      REAL,
    carbs    REAL,
    added_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_meals_day ON meals(tg_id, day);

CREATE TABLE IF NOT EXISTS water (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    tg_id    INTEGER NOT NULL,
    day      TEXT NOT NULL,
    ml       INTEGER,
    added_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_water_day ON water(tg_id, day);

CREATE TABLE IF NOT EXISTS weights (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    tg_id    INTEGER NOT NULL,
    day      TEXT NOT NULL,
    kg       REAL,
    added_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_weights ON weights(tg_id, day);

-- Незавершённые таймеры отдыха. Переживают перезапуск бота.
CREATE TABLE IF NOT EXISTS timers (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    tg_id     INTEGER NOT NULL,
    fire_at   TEXT NOT NULL,
    warn_at   TEXT NOT NULL,
    payload   TEXT,
    done      INTEGER DEFAULT 0
);

-- Текущая тренировка: где остановились по упражнениям и подходам.
CREATE TABLE IF NOT EXISTS sessions (
    tg_id       INTEGER PRIMARY KEY,
    place       TEXT,
    kind        TEXT,
    slot        TEXT,
    program     TEXT,
    ex_index    INTEGER DEFAULT 0,
    set_index   INTEGER DEFAULT 0,
    started_at  TEXT
);

-- Заявки на работу с живым тренером.
CREATE TABLE IF NOT EXISTS leads (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    tg_id      INTEGER NOT NULL,
    username   TEXT,
    tariff     TEXT,
    contact    TEXT,
    status     TEXT DEFAULT 'new',
    created_at TEXT
);
"""


def now() -> datetime:
    return datetime.now(TZ)


def today() -> str:
    return now().date().isoformat()


async def connect() -> aiosqlite.Connection:
    conn = await aiosqlite.connect(DB_PATH)
    conn.row_factory = aiosqlite.Row
    await conn.execute("PRAGMA journal_mode=WAL")
    return conn


async def init(conn: aiosqlite.Connection) -> None:
    await conn.executescript(SCHEMA)
    await _migrate(conn)
    await conn.commit()


async def _migrate(conn: aiosqlite.Connection) -> None:
    """Догоняет схему у баз, созданных прошлыми версиями бота."""
    cur = await conn.execute("PRAGMA table_info(users)")
    present = {row["name"] for row in await cur.fetchall()}
    for column, decl in (("pref_place", "TEXT"), ("pref_kind", "TEXT"),
                         ("nicknames_json", "TEXT")):
        if column not in present:
            await conn.execute(f"ALTER TABLE users ADD COLUMN {column} {decl}")


# ---------- пользователи ----------

async def get_user(conn, tg_id: int) -> aiosqlite.Row | None:
    cur = await conn.execute("SELECT * FROM users WHERE tg_id = ?", (tg_id,))
    return await cur.fetchone()


async def save_user(conn, tg_id: int, **fields) -> None:
    """Создаёт пользователя или обновляет переданные поля."""
    existing = await get_user(conn, tg_id)
    if existing is None:
        fields.setdefault("times_json", json.dumps(DEFAULT_TIMES))
        fields.setdefault("created_at", now().isoformat())
        cols = ", ".join(["tg_id"] + list(fields))
        marks = ", ".join("?" * (len(fields) + 1))
        await conn.execute(
            f"INSERT INTO users ({cols}) VALUES ({marks})",
            [tg_id, *fields.values()],
        )
    elif fields:
        sets = ", ".join(f"{k} = ?" for k in fields)
        await conn.execute(
            f"UPDATE users SET {sets} WHERE tg_id = ?", [*fields.values(), tg_id]
        )
    await conn.commit()


async def all_users(conn) -> list[aiosqlite.Row]:
    cur = await conn.execute("SELECT * FROM users WHERE kcal IS NOT NULL")
    return list(await cur.fetchall())


def user_times(row) -> dict:
    """Время напоминаний пользователя, с подстановкой значений по умолчанию."""
    times = dict(DEFAULT_TIMES)
    raw = row["times_json"] if row is not None else None
    if raw:
        try:
            times.update(json.loads(raw))
        except json.JSONDecodeError:
            pass
    return times


async def set_time(conn, tg_id: int, key: str, value: str) -> dict:
    row = await get_user(conn, tg_id)
    times = user_times(row)
    times[key] = value
    await conn.execute(
        "UPDATE users SET times_json = ? WHERE tg_id = ?", (json.dumps(times), tg_id)
    )
    await conn.commit()
    return times


# ---------- прозвища ----------

def user_nicknames(row) -> dict:
    """Правки пользователя к набору обращений.

    Храним не готовый список, а разницу с набором по умолчанию: какие
    стандартные прозвища выкинуты и какие свои добавлены. Так набор сам
    обновится, если человек сменит цель — «здоровяк» уйдёт вместе с массой.
    """
    prefs = {"banned": [], "custom": []}
    raw = row["nicknames_json"] if row is not None else None
    if raw:
        try:
            saved = json.loads(raw)
            prefs["banned"] = list(saved.get("banned") or [])
            prefs["custom"] = list(saved.get("custom") or [])
        except (json.JSONDecodeError, AttributeError):
            pass
    return prefs


async def save_nicknames(conn, tg_id: int, prefs: dict) -> None:
    await conn.execute(
        "UPDATE users SET nicknames_json = ? WHERE tg_id = ?",
        (json.dumps(prefs, ensure_ascii=False), tg_id),
    )
    await conn.commit()


async def ban_nickname(conn, tg_id: int, name: str) -> dict:
    """Убирает прозвище: своё удаляет насовсем, стандартное прячет."""
    row = await get_user(conn, tg_id)
    prefs = user_nicknames(row)
    if name in prefs["custom"]:
        prefs["custom"].remove(name)
    elif name not in prefs["banned"]:
        prefs["banned"].append(name)
    await save_nicknames(conn, tg_id, prefs)
    return prefs


async def add_nickname(conn, tg_id: int, name: str) -> dict:
    row = await get_user(conn, tg_id)
    prefs = user_nicknames(row)
    # Если прозвище раньше выкинули, а теперь вписали снова — просто вернём.
    if name in prefs["banned"]:
        prefs["banned"].remove(name)
    elif name not in prefs["custom"]:
        prefs["custom"].append(name)
    await save_nicknames(conn, tg_id, prefs)
    return prefs


async def reset_nicknames(conn, tg_id: int) -> dict:
    prefs = {"banned": [], "custom": []}
    await save_nicknames(conn, tg_id, prefs)
    return prefs


# ---------- еда ----------

async def add_meal(conn, tg_id: int, name, grams, kcal, p, f, c) -> None:
    await conn.execute(
        "INSERT INTO meals (tg_id, day, name, grams, kcal, protein, fat, carbs, added_at)"
        " VALUES (?,?,?,?,?,?,?,?,?)",
        (tg_id, today(), name, grams, kcal, p, f, c, now().isoformat()),
    )
    await conn.commit()


async def day_totals(conn, tg_id: int) -> dict:
    cur = await conn.execute(
        "SELECT COALESCE(SUM(kcal),0) k, COALESCE(SUM(protein),0) p,"
        " COALESCE(SUM(fat),0) f, COALESCE(SUM(carbs),0) c"
        " FROM meals WHERE tg_id = ? AND day = ?",
        (tg_id, today()),
    )
    r = await cur.fetchone()
    return {"kcal": r["k"], "protein": r["p"], "fat": r["f"], "carbs": r["c"]}


async def day_meals(conn, tg_id: int) -> list[aiosqlite.Row]:
    cur = await conn.execute(
        "SELECT * FROM meals WHERE tg_id = ? AND day = ? ORDER BY id",
        (tg_id, today()),
    )
    return list(await cur.fetchall())


async def undo_last_meal(conn, tg_id: int) -> aiosqlite.Row | None:
    cur = await conn.execute(
        "SELECT * FROM meals WHERE tg_id = ? AND day = ? ORDER BY id DESC LIMIT 1",
        (tg_id, today()),
    )
    row = await cur.fetchone()
    if row:
        await conn.execute("DELETE FROM meals WHERE id = ?", (row["id"],))
        await conn.commit()
    return row


# ---------- вода ----------

async def add_water(conn, tg_id: int, ml: int) -> int:
    await conn.execute(
        "INSERT INTO water (tg_id, day, ml, added_at) VALUES (?,?,?,?)",
        (tg_id, today(), ml, now().isoformat()),
    )
    await conn.commit()
    return await water_total(conn, tg_id)


async def water_total(conn, tg_id: int) -> int:
    cur = await conn.execute(
        "SELECT COALESCE(SUM(ml),0) t FROM water WHERE tg_id = ? AND day = ?",
        (tg_id, today()),
    )
    return int((await cur.fetchone())["t"])


# ---------- вес ----------

async def add_weight(conn, tg_id: int, kg: float) -> None:
    await conn.execute(
        "DELETE FROM weights WHERE tg_id = ? AND day = ?", (tg_id, today())
    )
    await conn.execute(
        "INSERT INTO weights (tg_id, day, kg, added_at) VALUES (?,?,?,?)",
        (tg_id, today(), kg, now().isoformat()),
    )
    await conn.execute("UPDATE users SET weight_kg = ? WHERE tg_id = ?", (kg, tg_id))
    await conn.commit()


async def weight_history(conn, tg_id: int, limit: int = 12) -> list[aiosqlite.Row]:
    cur = await conn.execute(
        "SELECT * FROM weights WHERE tg_id = ? ORDER BY day DESC LIMIT ?",
        (tg_id, limit),
    )
    return list(reversed(await cur.fetchall()))


# ---------- тренировочная сессия ----------

async def start_session(conn, tg_id, place, kind, slot, program) -> None:
    await conn.execute(
        "INSERT INTO sessions (tg_id, place, kind, slot, program, ex_index, set_index,"
        " started_at) VALUES (?,?,?,?,?,0,0,?)"
        " ON CONFLICT(tg_id) DO UPDATE SET place=excluded.place, kind=excluded.kind,"
        " slot=excluded.slot, program=excluded.program, ex_index=0, set_index=0,"
        " started_at=excluded.started_at",
        (tg_id, place, kind, slot, json.dumps(program, ensure_ascii=False),
         now().isoformat()),
    )
    await conn.commit()


async def get_session(conn, tg_id: int) -> dict | None:
    cur = await conn.execute("SELECT * FROM sessions WHERE tg_id = ?", (tg_id,))
    row = await cur.fetchone()
    if not row:
        return None
    data = dict(row)
    data["program"] = json.loads(data["program"]) if data["program"] else []
    return data


async def update_session(conn, tg_id: int, ex_index: int, set_index: int) -> None:
    await conn.execute(
        "UPDATE sessions SET ex_index = ?, set_index = ? WHERE tg_id = ?",
        (ex_index, set_index, tg_id),
    )
    await conn.commit()


async def end_session(conn, tg_id: int) -> None:
    await conn.execute("DELETE FROM sessions WHERE tg_id = ?", (tg_id,))
    await conn.commit()


# ---------- таймеры отдыха ----------

async def add_timer(conn, tg_id, fire_at: datetime, warn_at: datetime, payload: dict) -> int:
    cur = await conn.execute(
        "INSERT INTO timers (tg_id, fire_at, warn_at, payload) VALUES (?,?,?,?)",
        (tg_id, fire_at.isoformat(), warn_at.isoformat(),
         json.dumps(payload, ensure_ascii=False)),
    )
    await conn.commit()
    return cur.lastrowid


async def close_timer(conn, timer_id: int) -> None:
    await conn.execute("UPDATE timers SET done = 1 WHERE id = ?", (timer_id,))
    await conn.commit()


async def cancel_timers(conn, tg_id: int) -> None:
    await conn.execute("UPDATE timers SET done = 1 WHERE tg_id = ? AND done = 0", (tg_id,))
    await conn.commit()


async def pending_timers(conn) -> list[dict]:
    cur = await conn.execute("SELECT * FROM timers WHERE done = 0")
    out = []
    for row in await cur.fetchall():
        item = dict(row)
        item["payload"] = json.loads(item["payload"]) if item["payload"] else {}
        out.append(item)
    return out


# ---------- заявки на тренера ----------

async def add_lead(conn, tg_id, username, tariff, contact) -> int:
    cur = await conn.execute(
        "INSERT INTO leads (tg_id, username, tariff, contact, created_at)"
        " VALUES (?,?,?,?,?)",
        (tg_id, username, tariff, contact, now().isoformat()),
    )
    await conn.commit()
    return cur.lastrowid
