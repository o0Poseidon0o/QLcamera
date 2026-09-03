from datetime import datetime, timezone, timedelta
from motor.motor_asyncio import AsyncIOMotorClient
from config import settings
import logging

# Múi giờ Việt Nam (UTC+7)
VN_TZ = timezone(timedelta(hours=7))

def get_vn_now() -> datetime:
    """Trả về thời gian hiện tại chuẩn múi giờ Việt Nam (UTC+7)."""
    return datetime.now(VN_TZ)

logger = logging.getLogger("camera_manager.db")

class Database:
    client: AsyncIOMotorClient = None
    db = None

db_instance = Database()

async def connect_to_mongo():
    try:
        logger.info(f"Connecting to MongoDB Atlas (Timezone: UTC+7 Asia/Ho_Chi_Minh)...")
        db_instance.client = AsyncIOMotorClient(settings.mongodb_uri, tz_aware=True, tzinfo=VN_TZ)
        db_instance.db = db_instance.client[settings.database_name]
        # Quick ping
        await db_instance.client.admin.command('ping')
        logger.info("Successfully connected to MongoDB Atlas!")
        
        # Create indexes
        await db_instance.db.devices.create_index("ip", unique=False)
        await db_instance.db.channels.create_index([("device_id", 1), ("channel_no", 1)])
        await db_instance.db.events.create_index([("device_id", 1), ("timestamp", -1)])
        await db_instance.db.events.create_index([("target_type", 1), ("timestamp", -1)])
    except Exception as e:
        logger.error(f"Failed to connect to MongoDB: {e}")
        raise e

async def close_mongo_connection():
    if db_instance.client:
        db_instance.client.close()
        logger.info("MongoDB connection closed.")

def get_db():
    return db_instance.db
