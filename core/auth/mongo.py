from __future__ import annotations

import os
from functools import lru_cache

from pymongo import MongoClient
from pymongo.collection import Collection
from pymongo.database import Database


@lru_cache(maxsize=1)
def _client() -> MongoClient:
    uri = os.environ.get("MONGODB_URI")
    if not uri:
        raise RuntimeError("MONGODB_URI environment variable is not set")
    return MongoClient(uri)


def get_db() -> Database:
    db_name = os.environ.get("MONGODB_DB", "ai_agents")
    return _client()[db_name]


def users_collection() -> Collection:
    col = get_db()["users"]
    col.create_index("email", unique=True)
    return col
