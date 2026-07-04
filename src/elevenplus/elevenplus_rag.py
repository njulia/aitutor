#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Homework RAG (Retrieval-Augmented Generation) System

Stores generated homework with metadata in a vector database for future search and retrieval.
Metadata includes: year_group, subject, homework_minutes, study_year_month, etc.
"""
import os
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
PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CHROMA_DB_PATH = os.path.join(PROJECT_DIR, "data", "chroma_11plus_db")


class ElevenPlusRAGStore:
    def __init__(self, persist_directory: str = None):
        self.persist_dir = persist_directory or CHROMA_DB_PATH
        os.makedirs(self.persist_dir, exist_ok=True)

        # Initialize embeddings using AGICTO API
        self.embeddings = OpenAIEmbeddings(
            model="text-embedding-3-small",
            openai_api_key=AGICTO_API_KEY,
            openai_api_base="https://api.agicto.cn/v1/",
        )

        # Initialize ChromaDB vector store for homework
        self.db = Chroma(
            persist_directory=self.persist_dir,
            embedding_function=self.embeddings,
            collection_name="elevenplus_collection",
        )
        # self.retriever = self.db.as_retriever(
        #     search_type="mmr",
        #     search_kwargs={
        #     "k":5
        #    }
        # )

    def add_homework(
            self,
            homework_content: str,
            metadata: Dict[str, Any]
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
                - correct_answers: Optional correct answers for homework with unique answers
            doc_id: Optional document ID (auto-generated if not provided)

        Returns:
            The document ID
        """
        now = datetime.now()
        # 用毫秒时间戳生成唯一 ID
        doc_id = str(int(now.timestamp() * 1000))

        # Ensure metadata has required fields
        metadata.setdefault("created_at", now.isoformat())

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

            now = datetime.now()
            if not doc_id:
                # 用毫秒时间戳生成唯一 ID
                doc_id = str(int(now.timestamp() * 1000))

            metadata.setdefault("created_at", now.isoformat())
            metadata.setdefault("study_year_month", now.strftime("%Y-%m"))

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
        """搜索作业文档

        Args:
            query: 语义搜索关键词
            k: 返回结果数量
            filters: 可选的 metadata 过滤条件, 如:
                {"year_group": 3, "subject": "Maths"}

        Returns:
            包含 'doc_id', 'content', 'metadata', 'score' 的字典列表
        """
        where_clause = self._build_where_clause(filters) if filters else None

        # 使用我们自己的嵌入模型来嵌入查询，避免维度不匹配问题
        query_embedding = self.embeddings.embed_query(query)

        # 使用底层 ChromaDB collection 查询，可以同时获取 ID
        query_kwargs = {
            "query_embeddings": [query_embedding],
            "n_results": k,
            "include": ["documents", "metadatas", "distances"],
        }
        if where_clause:
            query_kwargs["where"] = where_clause

        raw = self.db._collection.query(**query_kwargs)

        results = []
        if raw and raw.get("ids") and raw["ids"][0]:
            ids = raw["ids"][0]
            docs = raw["documents"][0]
            metas = raw["metadatas"][0]
            dists = raw["distances"][0]
            for i in range(len(ids)):
                results.append({
                    "doc_id": ids[i],
                    "content": docs[i],
                    "metadata": metas[i],
                    "score": dists[i],
                })

        return results

    def search_by_metadata(
            self,
            filters: Dict[str, Any],
            k: int = 10,
    ) -> List[Dict[str, Any]]:
        """Search homework documents by metadata only (no semantic search)

        Args:
            filters: Metadata filter dict, e.g.:
                {"year_group": 3, "subject": "Maths", "study_year_month": "2026-09"}
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

        # ChromaDB requires $and for multiple conditions
        conditions = []
        for key, value in filters.items():
            if value is not None:
                conditions.append({key: value})

        if len(conditions) == 1:
            return conditions[0]
        elif len(conditions) > 1:
            return {"$and": conditions}

        return {}

    def get_student_homework_history(
            self,
            student_id: str,
            subject: str = None,
    ) -> List[Dict[str, Any]]:
        """Get all homework previously generated for a student

        Args:
            student_id: Student ID
            subject: Optional subject filter

        Returns:
            List of homework documents with metadata
        """
        filters = {"student_id": student_id}
        if subject:
            filters["subject"] = subject

        results = self.db.get(where=self._build_where_clause(filters))

        if not results or not results.get("ids"):
            return []

        return [
            {
                "doc_id": results["ids"][i],
                "content": results["documents"][i],
                "metadata": results["metadatas"][i],
            }
            for i in range(len(results["ids"]))
        ]

    def get_student_previous_topics(
            self,
            student_id: str,
            subject: str,
    ) -> List[str]:
        """Extract list of topics/areas previously covered for a student in a subject

        Args:
            student_id: Student ID
            subject: Subject name

        Returns:
            List of topic keywords/descriptions from previous homework
        """
        history = self.get_student_homework_history(student_id, subject)
        if not history:
            return []

        # Extract content previews (first 200 chars) as topic indicators
        topics = []
        for hw in history:
            content = hw["content"][:200]
            topics.append(content)
        return topics

    def ingest_chinese_textbooks(self, chinese_dir: str = None) -> int:
        """Ingest Chinese textbooks into RAG store

        Textbook mapping:
        - 第一册 -> Year 1
        - 第二册 -> Year 2
        - ... up to 第九册 -> Year 9

        Args:
            chinese_dir: Path to Chinese textbooks directory

        Returns:
            Number of documents ingested
        """
        if chinese_dir is None:
            chinese_dir = os.path.join(PROJECT_DIR, "data", "chinese")

        if not os.path.exists(chinese_dir):
            logger.warning(f"[RAG] Chinese textbooks directory not found: {chinese_dir}")
            return 0

        # Map Chinese numeral to year group
        chinese_num_to_year = {
            "第一册": 1,
            "第二册": 2,
            "第三册": 3,
            "第四册": 4,
            "第五册": 5,
            "第六册": 6,
            "第七册": 7,
            "第八册": 8,
            "第九册": 9,
        }

        documents = []
        doc_ids = []

        # Iterate through each volume folder
        for volume_folder in os.listdir(chinese_dir):
            volume_path = os.path.join(chinese_dir, volume_folder)
            if not os.path.isdir(volume_path):
                continue

            # Match volume name to year group
            year_group = None
            for chinese_num, year in chinese_num_to_year.items():
                if chinese_num in volume_folder:
                    year_group = year
                    break

            if year_group is None:
                logger.warning(f"[RAG] Could not determine year group for: {volume_folder}")
                continue

            # Find PDF files in subfolders
            for root, _dirs, files in os.walk(volume_path):
                for filename in files:
                    if not filename.endswith(".pdf"):
                        continue

                    filepath = os.path.join(root, filename)
                    doc_id = f"chinese_y{year_group}_{filename.replace('.pdf', '')}"

                    # Skip if already ingested
                    try:
                        existing = self.chinese_db.get(ids=[doc_id])
                        if existing and existing.get("ids"):
                            logger.debug(f"[RAG] Already ingested: {doc_id}")
                            continue
                    except Exception:
                        pass

                    metadata = {
                        "subject": "Chinese",
                        "year_group": year_group,
                        "volume": volume_folder,
                        "filename": filename,
                        "filepath": filepath,
                        "source": "chinese_textbook",
                        "ingested_at": datetime.now().isoformat(),
                    }

                    # Use filename and path as content (PDF parsing would need additional library)
                    content = f"Chinese Textbook - Year {year_group}\nVolume: {volume_folder}\nFile: {filename}\nPath: {filepath}"

                    documents.append(Document(page_content=content, metadata=metadata))
                    doc_ids.append(doc_id)

        if documents:
            self.chinese_db.add_documents(documents, ids=doc_ids)
            logger.info(f"[RAG] Ingested {len(doc_ids)} Chinese textbook documents")

        return len(doc_ids)

    def search_chinese_textbooks(
            self,
            query: str,
            year_group: int = None,
            k: int = 5,
    ) -> List[Dict[str, Any]]:
        """Search Chinese textbooks

        Args:
            query: Search query
            year_group: Optional year group filter
            k: Number of results

        Returns:
            List of search results
        """
        filters = {}
        if year_group is not None:
            filters["year_group"] = year_group

        where_clause = self._build_where_clause(filters) if filters else None

        if where_clause:
            results = self.chinese_db.similarity_search_with_score(query, k=k, filter=where_clause)
        else:
            results = self.chinese_db.similarity_search_with_score(query, k=k)

        return [
            {
                "content": doc.page_content,
                "metadata": doc.metadata,
                "score": score,
            }
            for doc, score in results
        ]

    def search_homework_answers(
            self,
            doc_id: str,
    ) -> Optional[str]:
        """通过 doc_id 直接获取正确答案

        Args:
            doc_id: 作业文档 ID

        Returns:
            正确答案字符串，未找到则返回 None
        """
        if not doc_id:
            logger.warning("[RAG] doc_id 为空")
            return None

        try:
            result = self.db.get(ids=[doc_id])
            if not result or not result.get("ids"):
                logger.warning(f"[RAG] 未找到 doc_id={doc_id} 对应的文档")
                return None

            metadata = result["metadatas"][0]
            correct_answers = metadata.get("correct_answers")
            if correct_answers:
                logger.info(f"[RAG] 找到 doc_id={doc_id} 的正确答案")
            return correct_answers
        except Exception as e:
            logger.error(f"[RAG] 获取正确答案失败: {e}")
            return None


# Convenience functions for direct use
_elevenplus_rag_store = None


def get_elevenplus_rag_store():
    """Get or create the singleton RAG store instance"""
    global _elevenplus_rag_store
    if _elevenplus_rag_store is None:
        _elevenplus_rag_store = ElevenPlusRAGStore()
    return _elevenplus_rag_store


def store_homework(
        homework_content: str,
        year_group: int,
        subject: str,
        homework_minutes: str,
        key_stage: str = None,
        english_level: str = None,
        student_id: str = None,
        correct_answers: str = None,
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
        correct_answers: Optional correct answers for homework with unique answers

    Returns:
        Document ID
    """
    store = get_elevenplus_rag_store()

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
    if correct_answers:
        metadata["correct_answers"] = correct_answers

    return store.add_homework(homework_content, metadata)


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
    store = get_elevenplus_rag_store()

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


def get_student_homework_history(student_id: str, subject: str = None) -> List[Dict[str, Any]]:
    """Get homework history for a student"""
    store = get_elevenplus_rag_store()
    return store.get_student_homework_history(student_id, subject)


def get_student_previous_topics(student_id: str, subject: str) -> List[str]:
    """Get previous topics covered for a student in a subject"""
    store = get_elevenplus_rag_store()
    return store.get_student_previous_topics(student_id, subject)


def ingest_chinese_textbooks(chinese_dir: str = None) -> int:
    """Ingest Chinese textbooks into RAG"""
    store = get_elevenplus_rag_store()
    return store.ingest_chinese_textbooks(chinese_dir)


def search_chinese_textbooks(query: str, year_group: int = None, k: int = 5) -> List[Dict[str, Any]]:
    """Search Chinese textbooks"""
    store = get_elevenplus_rag_store()
    return store.search_chinese_textbooks(query, year_group, k)


def search_homework_answers(doc_id: str) -> Optional[str]:
    """通过 doc_id 获取正确答案

    Args:
        doc_id: 作业文档 ID

    Returns:
        正确答案字符串，未找到则返回 None
    """
    store = get_elevenplus_rag_store()
    return store.search_homework_answers(doc_id)
