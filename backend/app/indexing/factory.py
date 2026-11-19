"""Builds the IndexingService from settings."""

from app.core.config import Settings
from app.db.session import Database
from app.embeddings.factory import build_embedding_client
from app.indexing.service import IndexingService


def build_indexing_service(settings: Settings, database: Database) -> IndexingService:
    return IndexingService(database, build_embedding_client(settings))
