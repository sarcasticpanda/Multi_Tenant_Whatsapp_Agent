from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from app.config import settings

_client: AsyncIOMotorClient | None = None


async def connect_mongodb() -> None:
    global _client
    _client = AsyncIOMotorClient(settings.mongo_uri)
    # Ping to confirm connection
    await _client.admin.command("ping")
    print("Connected to MongoDB Atlas")


async def close_mongodb() -> None:
    global _client
    if _client:
        _client.close()


def get_db() -> AsyncIOMotorDatabase:
    if _client is None:
        raise RuntimeError("MongoDB not connected. Call connect_mongodb() first.")
    return _client[settings.mongo_db_name]
