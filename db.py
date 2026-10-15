import aiosqlite
from config import config


async def init_db() -> None:
    """Создает таблицу транзакций при старте бота."""
    async with aiosqlite.connect(config.db_path) as db:
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS transactions (
                charge_id TEXT PRIMARY KEY,
                payload TEXT NOT NULL,
                user_id INTEGER NOT NULL,
                amount INTEGER NOT NULL,
                status TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        await db.commit()


async def is_duplicate_charge(charge_id: str) -> bool:
    """Проверяет, обрабатывался ли уже данный платеж."""
    async with aiosqlite.connect(config.db_path) as db:
        cursor = await db.execute(
            "SELECT 1 FROM transactions WHERE charge_id = ?",
            (charge_id,),
        )
        row = await cursor.fetchone()
        return row is not None


async def log_transaction(
    charge_id: str,
    payload: str,
    user_id: int,
    amount: int,
    status: str,
) -> None:
    """Сохраняет или обновляет статус платежной транзакции."""
    async with aiosqlite.connect(config.db_path) as db:
        await db.execute(
            """
            INSERT INTO transactions (charge_id, payload, user_id, amount, status)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(charge_id) DO UPDATE SET status = excluded.status
            """,
            (charge_id, payload, user_id, amount, status),
        )
        await db.commit()