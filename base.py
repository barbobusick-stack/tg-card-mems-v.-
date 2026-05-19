import aiosqlite
import time
import config

DB = config.DB_PATH

# Seed карточек при инициализации
SEED_CARDS = [
    ("кот на арбузе", "Common",    10,  60, "кот на арбузе.png"),
    ("кот в шоке",    "Rare",    228,  30, "кот в шоке.png"),
    ("кот художник",  "Common",      120,  5, "кот художник.png"),
    ("кот алон",      "Epic",      424,  4, "кот алон.png"),
    ("ъуъ",           "Legendary",      1343,  1, "ъуъ.png"),
]


def get_cooldown_remaining(last_claim_time: int | None, now: int | None = None) -> int:
    """Секунд до следующего получения карты (0 — можно получать)."""
    if not last_claim_time:
        return 0
    now = int(time.time()) if now is None else now
    return max(0, config.COOLDOWN_SECONDS - (now - int(last_claim_time)))


async def get_claim_cooldown_remaining(user_id: int) -> int:
    async with aiosqlite.connect(DB) as db:
        cursor = await db.execute(
            "SELECT last_claim_time FROM users WHERE id = ?", (user_id,)
        )
        row = await cursor.fetchone()
        return get_cooldown_remaining(row[0] if row else None)


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
                image_file TEXT,
                created_at INTEGER
            )
        """)
        try:
            await db.execute("ALTER TABLE cards ADD COLUMN image_file TEXT")
            await db.commit()
        except aiosqlite.OperationalError:
            pass  # колонка уже есть
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
                "INSERT INTO cards (name, rarity, points, weight, image_file, created_at) VALUES (?,?,?,?,?,?)",
                [
                    (name, rarity, points, weight, image_file, now)
                    for name, rarity, points, weight, image_file in SEED_CARDS
                ],
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


async def add_card_to_user(user_id: int, card_id: int, points: int) -> tuple[bool, int]:
    """
    Выдаёт карту, если прошёл кулдаун (config.COOLDOWN_SECONDS).
    Возвращает (успех, секунд_до_следующей_попытки).
    """
    now = int(time.time())
    async with aiosqlite.connect(DB) as db:
        cursor = await db.execute(
            "SELECT last_claim_time FROM users WHERE id = ?", (user_id,)
        )
        row = await cursor.fetchone()
        if not row:
            return False, 0

        remaining = get_cooldown_remaining(row[0], now)
        if remaining > 0:
            return False, remaining

        await db.execute("""
            INSERT INTO user_cards (user_id, card_id, quantity)
            VALUES (?, ?, 1)
            ON CONFLICT(user_id, card_id) DO UPDATE SET quantity = quantity + 1
        """, (user_id, card_id))
        await db.execute("""
            UPDATE users
            SET total_points = total_points + ?,
                last_claim_time = ?
            WHERE id = ?
        """, (points, now, user_id))
        await db.commit()
        return True, 0


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
