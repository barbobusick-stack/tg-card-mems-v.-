import aiosqlite
import time
import config

DB = config.DB_PATH

# Seed карточек при инициализации
SEED_CARDS = [
    ("кот на арбузе", "Common",    10,  60, "кот на арбузе.png"),
    ("кот в шоке",    "Common",    15,  55, "кот в шоке.png"),
    ("кот художник",  "Rare",      40,  25, "кот художник.png"),
    ("ъуъ",           "Rare",      50,  20, "ъуъ.png"),
    ("кот алон",      "Epic",      204,  8, "кот алон.png"),
]


async def init_db():
    async with aiosqlite.connect(DB) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id            INTEGER PRIMARY KEY,
                username      TEXT,
                first_name    TEXT,
                last_name     TEXT,
                total_points  INTEGER DEFAULT 0,
                last_claim_time INTEGER DEFAULT 0,
                created_at    INTEGER
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS cards (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                name       TEXT,
                rarity     TEXT,
                points     INTEGER,
                weight     INTEGER,
                created_at INTEGER
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS user_cards (
                id       INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id  INTEGER,
                card_id  INTEGER,
                quantity INTEGER DEFAULT 1,
                UNIQUE(user_id, card_id)
            )
        """)
        await db.commit()

        # Заполняем карточки если таблица пустая
        cursor = await db.execute("SELECT COUNT(*) FROM cards")
        row = await cursor.fetchone()
        if row[0] == 0:
            now = int(time.time())
            await db.executemany(
                "INSERT INTO cards (name, rarity, points, weight, created_at) VALUES (?,?,?,?,?)",
                [(name, rarity, points, weight, now) for name, rarity, points, weight in SEED_CARDS]
            )
            await db.commit()


async def user_exists(user_id: int) -> bool:
    async with aiosqlite.connect(DB) as db:
        cursor = await db.execute("SELECT 1 FROM users WHERE id = ?", (user_id,))
        return await cursor.fetchone() is not None


async def add_user(user_id: int, username: str, first_name: str, last_name: str):
    async with aiosqlite.connect(DB) as db:
        await db.execute(
            "INSERT OR IGNORE INTO users (id, username, first_name, last_name, created_at) VALUES (?,?,?,?,?)",
            (user_id, username, first_name, last_name, int(time.time()))
        )
        await db.commit()


async def get_user(user_id: int) -> dict | None:
    async with aiosqlite.connect(DB) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None


async def get_all_cards() -> list[dict]:
    async with aiosqlite.connect(DB) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM cards")
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]


async def add_card_to_user(user_id: int, card_id: int, points: int):
    async with aiosqlite.connect(DB) as db:
        # Добавляем карту или увеличиваем количество
        await db.execute("""
            INSERT INTO user_cards (user_id, card_id, quantity)
            VALUES (?, ?, 1)
            ON CONFLICT(user_id, card_id) DO UPDATE SET quantity = quantity + 1
        """, (user_id, card_id))
        # Обновляем очки и время последнего получения
        await db.execute("""
            UPDATE users
            SET total_points = total_points + ?,
                last_claim_time = ?
            WHERE id = ?
        """, (points, int(time.time()), user_id))
        await db.commit()


async def get_user_cards(user_id: int) -> list[dict]:
    async with aiosqlite.connect(DB) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("""
            SELECT c.name, c.rarity, c.points, uc.quantity
            FROM user_cards uc
            JOIN cards c ON c.id = uc.card_id
            WHERE uc.user_id = ?
            ORDER BY c.points DESC
        """, (user_id,))
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]


async def get_top_users(limit: int = 10) -> list[dict]:
    async with aiosqlite.connect(DB) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("""
            SELECT first_name, username, total_points
            FROM users
            ORDER BY total_points DESC
            LIMIT ?
        """, (limit,))
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]
