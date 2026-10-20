import motor.motor_asyncio
from config import MONGO_URI, DB_NAME

_client = motor.motor_asyncio.AsyncIOMotorClient(MONGO_URI)
db = _client[DB_NAME]

users_col = db["users"]
sessions_col = db["sessions"]
targets_col = db["targets"]


async def init_db():
    await users_col.create_index("user_id", unique=True)
    await sessions_col.create_index("session_name", unique=True)
    await targets_col.create_index("chat_id", unique=True)


async def is_allowed(user_id: int) -> bool:
    doc = await users_col.find_one({"user_id": user_id})
    return bool(doc)


async def add_user(user_id: int) -> bool:
    try:
        await users_col.insert_one({"user_id": user_id})
        return True
    except Exception:
        return False


async def remove_user(user_id: int) -> bool:
    res = await users_col.delete_one({"user_id": user_id})
    return res.deleted_count > 0


async def list_users():
    cursor = users_col.find({}, {"_id": 0})
    return [u["user_id"] async for u in cursor]


async def add_session(session_name: str, phone: str, session_string: str = "") -> bool:
    try:
        await sessions_col.insert_one(
            {
                "session_name": session_name,
                "phone": phone,
                "session_string": session_string,
            }
        )
        return True
    except Exception:
        await sessions_col.update_one(
            {"session_name": session_name},
            {"$set": {"phone": phone, "session_string": session_string}},
        )
        return True


async def update_session_string(session_name: str, session_string: str) -> bool:
    res = await sessions_col.update_one(
        {"session_name": session_name},
        {"$set": {"session_string": session_string}},
    )
    return res.modified_count > 0


async def remove_session(session_name: str) -> bool:
    res = await sessions_col.delete_one({"session_name": session_name})
    return res.deleted_count > 0


async def list_sessions():
    cursor = sessions_col.find({}, {"_id": 0})
    return [s async for s in cursor]


async def get_session(session_name: str):
    return await sessions_col.find_one({"session_name": session_name}, {"_id": 0})


async def add_target(chat_id, title: str, link: str) -> bool:
    try:
        await targets_col.insert_one(
            {"chat_id": chat_id, "title": title, "link": link}
        )
        return True
    except Exception:
        await targets_col.update_one(
            {"chat_id": chat_id}, {"$set": {"title": title, "link": link}}
        )
        return True


async def remove_target(chat_id) -> bool:
    res = await targets_col.delete_one({"chat_id": chat_id})
    return res.deleted_count > 0


async def list_targets():
    cursor = targets_col.find({}, {"_id": 0})
    return [t async for t in cursor]
