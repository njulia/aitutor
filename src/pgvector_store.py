"""Small PostgreSQL/pgvector store with a SQLite test fallback.

PostgreSQL is the production backend. SQLite support exists only so unit tests
and lightweight development commands can import and exercise the RAG layer
without installing the pgvector Python package or running PostgreSQL.
"""
from __future__ import annotations

import logging
import math
import os
from datetime import UTC, datetime
from typing import Any, Dict, Iterable, List, Optional

from sqlalchemy import JSON, Column, DateTime, String, delete, func, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import declarative_base, sessionmaker

from src.webapp.db import get_engine, normalise_database_url

logger = logging.getLogger(__name__)

_DEFAULT_DATABASE_URL = (
    os.getenv("PGVECTOR_DATABASE_URL")
    or os.getenv("DATABASE_URL")
    or "sqlite:///./test_vector.db"
)
_NORMALISED_DEFAULT_URL = normalise_database_url(_DEFAULT_DATABASE_URL)
_DEFAULT_IS_POSTGRES = _NORMALISED_DEFAULT_URL.startswith("postgresql")
EMBEDDING_DIMENSION = max(8, int(os.getenv("EMBEDDING_DIMENSION", "384")))
SQLITE_VECTOR_SCAN_LIMIT = max(100, min(int(os.getenv("SQLITE_VECTOR_SCAN_LIMIT", "5000")), 50_000))

try:  # Production dependency; intentionally optional for SQLite-only tests.
    from pgvector.sqlalchemy import Vector as _PGVector
except ImportError:  # pragma: no cover - exercised by environments without pgvector
    _PGVector = None

if _DEFAULT_IS_POSTGRES and _PGVector is None:
    raise RuntimeError(
        "PostgreSQL RAG requires the 'pgvector' Python package. Install requirements.txt."
    )

Base = declarative_base()
_EMBEDDING_COLUMN_TYPE = _PGVector(EMBEDDING_DIMENSION) if _DEFAULT_IS_POSTGRES else JSON


class VectorDocument(Base):
    __tablename__ = "vector_documents"

    id = Column(String(120), primary_key=True)
    collection_name = Column(String(80), nullable=False, index=True)
    content = Column(String, nullable=False)
    metadata_json = Column(JSON, nullable=False, default=dict)
    embedding = Column(_EMBEDDING_COLUMN_TYPE, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False)


def _cosine_distance(left: Iterable[float], right: Iterable[float]) -> float:
    a = [float(value) for value in left]
    b = [float(value) for value in right]
    if len(a) != len(b) or not a:
        return 1.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 1.0
    similarity = max(-1.0, min(1.0, dot / (norm_a * norm_b)))
    return 1.0 - similarity


class PGVectorStore:
    def __init__(self, collection_name: str, embedding_dimension: int = EMBEDDING_DIMENSION):
        self.collection_name = str(collection_name).strip()
        if not self.collection_name:
            raise ValueError("collection_name is required")
        self.embedding_dimension = int(embedding_dimension)
        if self.embedding_dimension != EMBEDDING_DIMENSION:
            raise ValueError(
                f"Configured embedding dimension is {EMBEDDING_DIMENSION}; "
                f"received {self.embedding_dimension}. Set EMBEDDING_DIMENSION before startup."
            )

        db_url = (
            os.getenv("PGVECTOR_DATABASE_URL")
            or os.getenv("DATABASE_URL")
            or "sqlite:///./test_vector.db"
        )
        if not (os.getenv("PGVECTOR_DATABASE_URL") or os.getenv("DATABASE_URL")) and os.getenv("DEV_MODE", "").lower() not in ("1", "true", "yes"):
            logger.warning(
                "PGVECTOR_DATABASE_URL and DATABASE_URL are not set; falling back to %s",
                db_url,
            )
        self.db_url = normalise_database_url(db_url)
        self.is_postgres = self.db_url.startswith("postgresql")
        if self.is_postgres and _PGVector is None:
            raise RuntimeError("PostgreSQL RAG requires the 'pgvector' Python package")

        self.engine = get_engine(self.db_url)
        self.Session = sessionmaker(bind=self.engine, expire_on_commit=False)
        self._prepare_db()
        logger.info(
            "[PGVector] collection=%s database=%s",
            self.collection_name,
            self.database_target,
        )


    @property
    def database_target(self) -> str:
        """Return a password-free database identifier for logs and diagnostics."""
        url = make_url(self.db_url)
        if url.get_backend_name() == "sqlite":
            return f"sqlite:///{url.database}"
        host = url.host or "localhost"
        port = f":{url.port}" if url.port else ""
        database = url.database or ""
        return f"{url.get_backend_name()}://{host}{port}/{database}"

    def _prepare_db(self) -> None:
        if self.is_postgres:
            with self.engine.begin() as conn:
                conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        Base.metadata.create_all(self.engine)
        if self.is_postgres:
            # Metadata lookup is the hot path for homework generation. This
            # expression index avoids an embedding call and a full-table scan.
            with self.engine.begin() as conn:
                conn.execute(text(
                    "CREATE INDEX IF NOT EXISTS ix_vector_docs_collection_year_subject "
                    "ON vector_documents "
                    "(collection_name, (metadata_json->>'year_group'), (metadata_json->>'subject'))"
                ))
                conn.execute(text(
                    "CREATE INDEX IF NOT EXISTS ix_vector_docs_elevenplus_lookup "
                    "ON vector_documents "
                    "(collection_name, (metadata_json->>'year_group'), "
                    "(metadata_json->>'subject'), (metadata_json->>'week_num'), "
                    "(metadata_json->>'content_type'))"
                ))
            # HNSW is available on modern pgvector installations. Keep startup
            # working on older servers and fall back to exact vector search.
            try:
                with self.engine.begin() as conn:
                    conn.execute(text(
                        "CREATE INDEX IF NOT EXISTS ix_vector_docs_embedding_hnsw "
                        "ON vector_documents USING hnsw (embedding vector_cosine_ops)"
                    ))
            except Exception:
                logger.warning("Could not create the optional pgvector HNSW index", exc_info=True)

    @staticmethod
    def _validate_lengths(
        texts: List[str], metadatas: List[Dict[str, Any]], ids: List[str], embeddings: List[List[float]]
    ) -> None:
        lengths = {len(texts), len(metadatas), len(ids), len(embeddings)}
        if len(lengths) != 1:
            raise ValueError("texts, metadatas, ids and embeddings must have equal lengths")
        if len(set(ids)) != len(ids):
            raise ValueError("ids must be unique within a batch")

    def _validate_embedding(self, embedding: Iterable[float]) -> List[float]:
        vector = [float(value) for value in embedding]
        if len(vector) != self.embedding_dimension:
            raise ValueError(
                f"Embedding has {len(vector)} dimensions; expected {self.embedding_dimension}. "
                "Use the same embedding model and EMBEDDING_DIMENSION for ingestion and search."
            )
        return vector

    def _metadata_expression(self, key: str, value: Any):
        node = VectorDocument.metadata_json[str(key)]
        # PostgreSQL compares the extracted text so the composite expression
        # index on year_group/subject can be used. SQLite needs typed JSON
        # accessors for numeric values.
        if self.is_postgres:
            return node.as_string() == str(value)
        if isinstance(value, bool):
            return node.as_boolean() == value
        if isinstance(value, int) and not isinstance(value, bool):
            return node.as_integer() == value
        if isinstance(value, float):
            return node.as_float() == value
        return node.as_string() == str(value)

    def _apply_filters(self, statement, filters: Optional[Dict[str, Any]]):
        for key, value in (filters or {}).items():
            if value is not None:
                statement = statement.where(self._metadata_expression(str(key), value))
        return statement

    def add_documents(
        self,
        texts: List[str],
        metadatas: List[Dict[str, Any]],
        ids: List[str],
        embeddings: List[List[float]],
    ) -> None:
        self._validate_lengths(texts, metadatas, ids, embeddings)
        if not texts:
            return
        rows = [
            {
                "id": str(ids[index]),
                "collection_name": self.collection_name,
                "content": str(texts[index]),
                "metadata_json": dict(metadatas[index] or {}),
                "embedding": self._validate_embedding(embeddings[index]),
                "created_at": datetime.now(UTC),
            }
            for index in range(len(texts))
        ]

        if self.is_postgres:
            from sqlalchemy.dialects.postgresql import insert as dialect_insert
        else:
            from sqlalchemy.dialects.sqlite import insert as dialect_insert

        statement = dialect_insert(VectorDocument).values(rows)
        statement = statement.on_conflict_do_update(
            index_elements=[VectorDocument.id],
            set_={
                "collection_name": statement.excluded.collection_name,
                "content": statement.excluded.content,
                "metadata_json": statement.excluded.metadata_json,
                "embedding": statement.excluded.embedding,
            },
        )
        with self.Session.begin() as session:
            session.execute(statement)

    def add_documents_if_absent(
        self,
        texts: List[str],
        metadatas: List[Dict[str, Any]],
        ids: List[str],
        embeddings: List[List[float]],
    ) -> None:
        """Insert immutable records without replacing an earlier value."""
        self._validate_lengths(texts, metadatas, ids, embeddings)
        if not texts:
            return
        rows = [
            {
                "id": str(ids[index]),
                "collection_name": self.collection_name,
                "content": str(texts[index]),
                "metadata_json": dict(metadatas[index] or {}),
                "embedding": self._validate_embedding(embeddings[index]),
                "created_at": datetime.now(UTC),
            }
            for index in range(len(texts))
        ]
        if self.is_postgres:
            from sqlalchemy.dialects.postgresql import insert as dialect_insert
        else:
            from sqlalchemy.dialects.sqlite import insert as dialect_insert
        statement = dialect_insert(VectorDocument).values(rows)
        statement = statement.on_conflict_do_nothing(
            index_elements=[VectorDocument.id]
        )
        with self.Session.begin() as session:
            session.execute(statement)

    def search(
        self,
        query_embedding: List[float],
        k: int = 5,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        vector = self._validate_embedding(query_embedding)
        limit = max(1, int(k))
        with self.Session() as session:
            if self.is_postgres:
                distance = VectorDocument.embedding.cosine_distance(vector).label("distance")
                statement = select(
                    VectorDocument.id,
                    VectorDocument.content,
                    VectorDocument.metadata_json,
                    distance,
                ).where(VectorDocument.collection_name == self.collection_name)
                statement = self._apply_filters(statement, filters).order_by(distance).limit(limit)
                rows = session.execute(statement).all()
                return [
                    {
                        "doc_id": row.id,
                        "content": row.content,
                        "metadata": row.metadata_json or {},
                        "distance": float(row.distance) if row.distance is not None else None,
                        "similarity": 1.0 - float(row.distance) if row.distance is not None else None,
                    }
                    for row in rows
                ]

            # SQLite fallback: bounded in-process cosine scan for tests/dev.
            statement = select(VectorDocument).where(
                VectorDocument.collection_name == self.collection_name
            )
            statement = self._apply_filters(statement, filters).limit(SQLITE_VECTOR_SCAN_LIMIT)
            documents = session.execute(statement).scalars().all()
            ranked = []
            for document in documents:
                distance_value = _cosine_distance(document.embedding or [], vector)
                ranked.append((distance_value, document))
            ranked.sort(key=lambda item: item[0])
            return [
                {
                    "doc_id": document.id,
                    "content": document.content,
                    "metadata": document.metadata_json or {},
                    "distance": float(distance_value),
                    "similarity": 1.0 - float(distance_value),
                }
                for distance_value, document in ranked[:limit]
            ]

    def get_by_ids(self, ids: List[str]) -> List[Dict[str, Any]]:
        clean_ids = [str(value) for value in ids if value]
        if not clean_ids:
            return []
        with self.Session() as session:
            rows = session.execute(
                select(VectorDocument).where(
                    VectorDocument.collection_name == self.collection_name,
                    VectorDocument.id.in_(clean_ids),
                )
            ).scalars().all()
        by_id = {row.id: row for row in rows}
        return [
            {
                "doc_id": by_id[doc_id].id,
                "content": by_id[doc_id].content,
                "metadata": by_id[doc_id].metadata_json or {},
            }
            for doc_id in clean_ids
            if doc_id in by_id
        ]

    def get_by_metadata(
        self,
        filters: Dict[str, Any],
        k: int = 10,
        *,
        offset: int = 0,
        exclude_ids: Optional[Iterable[str]] = None,
    ) -> List[Dict[str, Any]]:
        """Return newest metadata matches, optionally excluding already assigned IDs."""
        statement = select(VectorDocument).where(
            VectorDocument.collection_name == self.collection_name
        )
        statement = self._apply_filters(statement, filters)
        clean_exclude_ids = list(dict.fromkeys(str(value) for value in (exclude_ids or []) if value))
        if clean_exclude_ids:
            statement = statement.where(~VectorDocument.id.in_(clean_exclude_ids))
        statement = (
            statement.order_by(VectorDocument.created_at.desc(), VectorDocument.id.asc())
            .offset(max(0, int(offset)))
            .limit(max(1, int(k)))
        )
        with self.Session() as session:
            rows = session.execute(statement).scalars().all()
        return [
            {"doc_id": row.id, "content": row.content, "metadata": row.metadata_json or {}}
            for row in rows
        ]

    def delete(self, ids: List[str]) -> None:
        clean_ids = [str(value) for value in ids if value]
        if not clean_ids:
            return
        with self.Session.begin() as session:
            session.execute(
                delete(VectorDocument).where(
                    VectorDocument.collection_name == self.collection_name,
                    VectorDocument.id.in_(clean_ids),
                )
            )

    def delete_by_metadata(self, filters: Dict[str, Any]) -> int:
        statement = delete(VectorDocument).where(
            VectorDocument.collection_name == self.collection_name
        )
        statement = self._apply_filters(statement, filters)
        with self.Session.begin() as session:
            result = session.execute(statement)
        return int(result.rowcount or 0)

    def count(self) -> int:
        with self.Session() as session:
            value = session.execute(
                select(func.count()).select_from(VectorDocument).where(
                    VectorDocument.collection_name == self.collection_name
                )
            ).scalar_one()
        return int(value)

    def count_by_metadata(self, filters: Dict[str, Any]) -> int:
        statement = select(func.count()).select_from(VectorDocument).where(
            VectorDocument.collection_name == self.collection_name
        )
        statement = self._apply_filters(statement, filters)
        with self.Session() as session:
            return int(session.execute(statement).scalar_one())

    def get_stats_metadata(self, limit: int, offset: int) -> List[Dict[str, Any]]:
        statement = select(VectorDocument.metadata_json).where(
            VectorDocument.collection_name == self.collection_name
        ).limit(max(1, int(limit))).offset(max(0, int(offset)))
        with self.Session() as session:
            return [row[0] or {} for row in session.execute(statement).all()]
