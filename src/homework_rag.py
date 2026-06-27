#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Homework RAG (Retrieval-Augmented Generation) System

Stores generated homework with metadata in a vector database for future search and retrieval.
Metadata includes: year_group, subject, homework_minutes, study_year_month, etc.
"""
import os
import json
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional

from langchain_openai import OpenAIEmbeddings
from langchain_chroma import Chroma
from langchain_core.documents import Document

logger = logging.getLogger(__name__)

# AGICTO API Key for embeddings
AGICTO_API_KEY = os.getenv("AGICTO_API_KEY")

# RAG storage directory
PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHROMA_DB_PATH = os.path.join(PROJECT_DIR, "data", "chroma_homework_db")


class HomeworkRAGStore:
    """RAG store for homework documents with metadata-based search"""

    def __init__(self, persist_directory: str = None):
        self.persist_dir = persist_directory or CHROMA_DB_PATH
        os.makedirs(self.persist_dir, exist_ok=True)

        # Initialize embeddings using AGICTO API
        self.embeddings = OpenAIEmbeddings(
            model="text-embedding-ada-002",
            openai_api_key=AGICTO_API_KEY,
            openai_api_base="https://api.agicto.cn/v1/",
        )

        # Initialize ChromaDB vector store
        self.db = Chroma(
            persist_directory=self.persist_dir,
            embedding_function=self.embeddings,
            collection_name="homework_collection",
        )

    def add_homework(
        self,
        homework_content: str,
        metadata: Dict[str, Any],
        doc_id: str = None,
    ) -> str:
        """Add a homework document to the RAG store

        Args:
            homework_content: The homework content text
            metadata: Dictionary with metadata fields:
                - year_group: int (1-6)
                - subject: str
                - homework_minutes: str (e.g., "10-15", "30")
                - study_year_month: str (e.g., "2026-09")
                - key_stage: str (e.g., "KS1", "KS2")
                - english_level: str
                - student_id: str
                - created_at: str (ISO datetime)
            doc_id: Optional document ID (auto-generated if not provided)

        Returns:
            The document ID
        """
        if not doc_id:
            doc_id = f"hw_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{metadata.get('subject', 'unknown')}"

        # Ensure metadata has required fields
        metadata.setdefault("created_at", datetime.now().isoformat())
        metadata.setdefault("study_year_month", datetime.now().strftime("%Y-%m"))

        document = Document(
            page_content=homework_content,
            metadata=metadata,
        )

        self.db.add_documents([document], ids=[doc_id])
        logger.info(f"[RAG] Added homework document: {doc_id}")
        return doc_id

    def add_batch_homework(
        self,
        homework_list: List[Dict[str, Any]],
    ) -> List[str]:
        """Add multiple homework documents in batch

        Args:
            homework_list: List of dicts with keys:
                - content: str (homework content)
                - metadata: Dict[str, Any]
                - doc_id: Optional[str]

        Returns:
            List of document IDs
        """
        documents = []
        doc_ids = []

        for item in homework_list:
            content = item["content"]
            metadata = item["metadata"]
            doc_id = item.get("doc_id")

            if not doc_id:
                doc_id = f"hw_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{metadata.get('subject', 'unknown')}"

            metadata.setdefault("created_at", datetime.now().isoformat())
            metadata.setdefault("study_year_month", datetime.now().strftime("%Y-%m"))

            documents.append(Document(page_content=content, metadata=metadata))
            doc_ids.append(doc_id)

        self.db.add_documents(documents, ids=doc_ids)
        logger.info(f"[RAG] Added {len(doc_ids)} homework documents in batch")
        return doc_ids

    def search(
        self,
        query: str,
        k: int = 5,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Search for homework documents

        Args:
            query: Search query text
            k: Number of results to return
            filters: Optional metadata filters, e.g.:
                {"year_group": 3, "subject": "Math"}

        Returns:
            List of dicts with 'content', 'metadata', and 'score'
        """
        if filters:
            # Build ChromaDB where clause
            where_clause = self._build_where_clause(filters)
            results = self.db.similarity_search_with_score(
                query,
                k=k,
                filter=where_clause,
            )
        else:
            results = self.db.similarity_search_with_score(query, k=k)

        return [
            {
                "content": doc.page_content,
                "metadata": doc.metadata,
                "score": score,
            }
            for doc, score in results
        ]

    def search_by_metadata(
        self,
        filters: Dict[str, Any],
        k: int = 10,
    ) -> List[Dict[str, Any]]:
        """Search homework documents by metadata only (no semantic search)

        Args:
            filters: Metadata filter dict, e.g.:
                {"year_group": 3, "subject": "Math", "study_year_month": "2026-09"}
            k: Max number of results

        Returns:
            List of dicts with 'content' and 'metadata'
        """
        where_clause = self._build_where_clause(filters)
        results = self.db.get(where=where_clause)

        if not results or not results.get("ids"):
            return []

        return [
            {
                "doc_id": results["ids"][i],
                "content": results["documents"][i],
                "metadata": results["metadatas"][i],
            }
            for i in range(len(results["ids"]))
        ][:k]

    def delete_homework(self, doc_id: str) -> bool:
        """Delete a homework document by ID

        Args:
            doc_id: Document ID to delete

        Returns:
            True if deleted, False otherwise
        """
        try:
            self.db.delete([doc_id])
            logger.info(f"[RAG] Deleted homework document: {doc_id}")
            return True
        except Exception as e:
            logger.error(f"[RAG] Failed to delete document {doc_id}: {e}")
            return False

    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about the RAG store

        Returns:
            Dictionary with collection stats
        """
        collection = self.db.get()
        total_docs = len(collection["ids"]) if collection.get("ids") else 0

        # Count by subject
        subject_counts = {}
        year_counts = {}
        if collection.get("metadatas"):
            for meta in collection["metadatas"]:
                subject = meta.get("subject", "Unknown")
                year_group = meta.get("year_group", "Unknown")
                subject_counts[subject] = subject_counts.get(subject, 0) + 1
                year_counts[year_group] = year_counts.get(year_group, 0) + 1

        return {
            "total_documents": total_docs,
            "by_subject": subject_counts,
            "by_year_group": year_counts,
        }

    def _build_where_clause(self, filters: Dict[str, Any]) -> Dict[str, Any]:
        """Build ChromaDB where clause from filter dict

        Args:
            filters: Filter dictionary

        Returns:
            ChromaDB where clause
        """
        if not filters:
            return {}

        # Simple equality filters
        where = {}
        for key, value in filters.items():
            if value is not None:
                where[key] = value

        return where


# Convenience functions for direct use
_homework_rag_store = None


def get_homework_rag_store() -> HomeworkRAGStore:
    """Get or create the singleton RAG store instance"""
    global _homework_rag_store
    if _homework_rag_store is None:
        _homework_rag_store = HomeworkRAGStore()
    return _homework_rag_store


def store_homework(
    homework_content: str,
    year_group: int,
    subject: str,
    homework_minutes: str,
    key_stage: str = None,
    english_level: str = None,
    student_id: str = None,
    doc_id: str = None,
) -> str:
    """Store a homework document in the RAG store

    Args:
        homework_content: The homework content
        year_group: UK year group (1-6)
        subject: Subject name
        homework_minutes: Recommended homework time (e.g., "10-15", "30")
        key_stage: UK Key Stage (KS1/KS2)
        english_level: Student English level
        student_id: Student ID
        doc_id: Optional document ID

    Returns:
        Document ID
    """
    store = get_homework_rag_store()

    metadata = {
        "year_group": year_group,
        "subject": subject,
        "homework_minutes": homework_minutes,
        "study_year_month": datetime.now().strftime("%Y-%m"),
    }

    if key_stage:
        metadata["key_stage"] = key_stage
    if english_level:
        metadata["english_level"] = english_level
    if student_id:
        metadata["student_id"] = student_id

    return store.add_homework(homework_content, metadata, doc_id)


def search_homework(
    query: str,
    year_group: int = None,
    subject: str = None,
    homework_minutes: str = None,
    study_year_month: str = None,
    k: int = 5,
) -> List[Dict[str, Any]]:
    """Search for homework documents

    Args:
        query: Semantic search query
        year_group: Filter by year group (1-6)
        subject: Filter by subject
        homework_minutes: Filter by homework time
        study_year_month: Filter by study year-month (e.g., "2026-09")
        k: Number of results

    Returns:
        List of search results
    """
    store = get_homework_rag_store()

    filters = {}
    if year_group is not None:
        filters["year_group"] = year_group
    if subject is not None:
        filters["subject"] = subject
    if homework_minutes is not None:
        filters["homework_minutes"] = homework_minutes
    if study_year_month is not None:
        filters["study_year_month"] = study_year_month

    return store.search(query, k=k, filters=filters if filters else None)
