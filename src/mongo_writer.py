"""Thin MongoDB writer with dependency-aware lookups."""
from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Dict, Optional

from pymongo import MongoClient
from pymongo.collection import Collection
from pymongo.errors import DuplicateKeyError


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


class MongoWriter:
    def __init__(
        self,
        connection_string: Optional[str] = None,
        db_name: Optional[str] = None,
    ):
        uri = connection_string or os.environ.get(
            "MONGO_CONNECTION_STRING", "mongodb://localhost:27017"
        )
        db_name = db_name or os.environ.get("MONGO_DATABASE", "merchant")
        self.client = MongoClient(uri, serverSelectionTimeoutMS=5000)
        self.db = self.client[db_name]

    def get_collection(self, name: str) -> Collection:
        return self.db[name]

    def exists(self, collection: str, id_field: str, id_value: str) -> bool:
        return self.db[collection].find_one(
            {id_field: id_value}, projection={"_id": 1}
        ) is not None

    def upsert(
        self,
        collection: str,
        id_field: str,
        document: Dict,
    ) -> Dict:
        """Upsert by id_field and stamp create/update timestamps."""
        if id_field not in document:
            raise ValueError(
                f"Document missing id field {id_field!r} for collection {collection!r}"
            )
        now = _now_iso()
        update = {
            "$set": {**document, "updated_at": now},
            "$setOnInsert": {"created_at": now},
        }
        try:
            result = self.db[collection].update_one(
                {id_field: document[id_field]},
                update,
                upsert=True,
            )
            return {
                "matched": result.matched_count,
                "modified": result.modified_count,
                "upserted_id": str(result.upserted_id) if result.upserted_id else None,
            }
        except DuplicateKeyError as exc:
            raise ValueError(f"duplicate key while writing to {collection}: {exc}") from exc

    def close(self) -> None:
        self.client.close()
