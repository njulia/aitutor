import logging
import os
import json
import uuid
from datetime import datetime, UTC
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import Column, String, Integer, JSON, DateTime, create_engine, text, select
from sqlalchemy.orm import declarative_base, sessionmaker
from pgvector.sqlalchemy import Vector
from src.webapp.db import normalise_database_url, engine_options

logger = logging.getLogger(__name__)

Base = declarative_base()

class VectorDocument(Base):
    __tablename__ = "vector_documents"

    id = Column(String, primary_key=True)
    collection_name = Column(String, index=True)
    content = Column(String, nullable=False)
    metadata_json = Column(JSON, nullable=False)
    embedding = Column(Vector(384)) # Default for all-MiniLM-L6-v2
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))

class PGVectorStore:
    def __init__(self, collection_name: str, embedding_dimension: int = 384):
        self.collection_name = collection_name
        self.embedding_dimension = embedding_dimension
        
        db_url = os.getenv("DATABASE_URL")
        if not db_url:
            # Fallback to local sqlite for testing if DATABASE_URL is not set, 
            # though pgvector won't work there. In production, DATABASE_URL is mandatory.
            db_url = "sqlite:///./test_vector.db"
            if os.getenv("DEV_MODE", "").lower() not in ("1", "true", "yes"):
                logger.warning("DATABASE_URL not set, falling back to %s", db_url)
        
        self.db_url = normalise_database_url(db_url)
        self.engine = create_engine(self.db_url, **engine_options(self.db_url))
        self.Session = sessionmaker(bind=self.engine)
        
        self._prepare_db()

    def _prepare_db(self):
        if "postgresql" in self.db_url:
            with self.engine.connect() as conn:
                conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
                conn.commit()
        
        # Adjust VectorDocument embedding dimension if needed
        # In a real dynamic scenario we might need different tables or dynamic column types,
        # but for this project, 384 seems to be the standard.
        Base.metadata.create_all(self.engine)

    def add_documents(
        self, 
        texts: List[str], 
        metadatas: List[Dict[str, Any]], 
        ids: List[str], 
        embeddings: List[List[float]]
    ):
        session = self.Session()
        try:
            for i in range(len(texts)):
                doc = VectorDocument(
                    id=ids[i],
                    collection_name=self.collection_name,
                    content=texts[i],
                    metadata_json=metadatas[i],
                    embedding=embeddings[i]
                )
                session.merge(doc) # use merge to handle potential duplicates like Chroma's add/update
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def search(
        self, 
        query_embedding: List[float], 
        k: int = 5, 
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        session = self.Session()
        try:
            # We use cosine distance <=> 1 - cosine similarity
            # pgvector cosine distance operator is <=>
            stmt = select(
                VectorDocument.id,
                VectorDocument.content,
                VectorDocument.metadata_json,
                VectorDocument.embedding.cosine_distance(query_embedding).label("distance")
            ).where(VectorDocument.collection_name == self.collection_name)
            
            params = {}
            if filters:
                for key, value in filters.items():
                    # Check metadata_json for matching key/value
                    stmt = stmt.where(text(f"metadata_json->>'{key}' = :f_{key}"))
                    params[f"f_{key}"] = str(value)
            
            stmt = stmt.order_by("distance").limit(k)
            
            results = session.execute(stmt, params).all()
            
            return [
                {
                    "doc_id": r.id,
                    "content": r.content,
                    "metadata": r.metadata_json,
                    "distance": float(r.distance) if r.distance is not None else None,
                    "similarity": 1.0 - float(r.distance) if r.distance is not None else None
                }
                for r in results
            ]
        finally:
            session.close()

    def get_by_ids(self, ids: List[str]) -> List[Dict[str, Any]]:
        session = self.Session()
        try:
            stmt = select(VectorDocument).where(
                VectorDocument.collection_name == self.collection_name,
                VectorDocument.id.in_(ids)
            )
            results = session.execute(stmt).scalars().all()
            return [
                {
                    "doc_id": r.id,
                    "content": r.content,
                    "metadata": r.metadata_json
                }
                for r in results
            ]
        finally:
            session.close()

    def get_by_metadata(self, filters: Dict[str, Any], k: int = 10) -> List[Dict[str, Any]]:
        session = self.Session()
        try:
            stmt = select(VectorDocument).where(VectorDocument.collection_name == self.collection_name)
            params = {"coll": self.collection_name}
            for i, (key, value) in enumerate(filters.items()):
                param_name = f"val_{i}"
                stmt = stmt.where(text(f"metadata_json->>'{key}' = :{param_name}"))
                params[param_name] = str(value)
            stmt = stmt.limit(k)
            results = session.execute(stmt, params).scalars().all()
            return [
                {
                    "doc_id": r.id,
                    "content": r.content,
                    "metadata": r.metadata_json
                }
                for r in results
            ]
        finally:
            session.close()

    def delete(self, ids: List[str]):
        session = self.Session()
        try:
            session.execute(
                text("DELETE FROM vector_documents WHERE collection_name = :coll AND id = ANY(:ids)"),
                {"coll": self.collection_name, "ids": ids}
            )
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def delete_by_metadata(self, filters: Dict[str, Any]) -> int:
        session = self.Session()
        try:
            params = {"coll": self.collection_name}
            where_clauses = ["collection_name = :coll"]
            for i, (key, value) in enumerate(filters.items()):
                param_name = f"val_{i}"
                where_clauses.append(f"metadata_json->>'{key}' = :{param_name}")
                params[param_name] = str(value)
            
            full_stmt = text(f"DELETE FROM vector_documents WHERE {' AND '.join(where_clauses)}")
            result = session.execute(full_stmt, params)
            session.commit()
            return result.rowcount
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def count(self) -> int:
        session = self.Session()
        try:
            stmt = select(text("count(*)")).select_from(text("vector_documents")).where(text("collection_name = :coll"))
            return session.execute(stmt, {"coll": self.collection_name}).scalar()
        finally:
            session.close()

    def count_by_metadata(self, filters: Dict[str, Any]) -> int:
        session = self.Session()
        try:
            stmt = select(text("count(*)")).select_from(text("vector_documents")).where(text("collection_name = :coll"))
            params = {"coll": self.collection_name}
            for i, (key, value) in enumerate(filters.items()):
                param_name = f"val_{i}"
                stmt = stmt.where(text(f"metadata_json->>'{key}' = :{param_name}"))
                params[param_name] = str(value)
            return session.execute(stmt, params).scalar()
        finally:
            session.close()

    def get_stats_metadata(self, limit: int, offset: int) -> List[Dict[str, Any]]:
        session = self.Session()
        try:
            stmt = select(VectorDocument.metadata_json).where(
                VectorDocument.collection_name == self.collection_name
            ).limit(limit).offset(offset)
            return [r.metadata_json for r in session.execute(stmt).all()]
        finally:
            session.close()
