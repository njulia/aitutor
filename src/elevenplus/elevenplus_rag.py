import os # Added this line
import logging
import time
from datetime import datetime
from typing import Dict, List, Any, Optional

try:
    import chromadb
except ImportError:
    chromadb = None

logger = logging.getLogger(__name__)

# RAG 存储重试配置
RAG_MAX_RETRIES = 3
RAG_RETRY_DELAY = 2  # 秒

# RAG storage directory
PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CHROMA_DB_PATH = os.getenv("CHROMA_DB_PATH") or os.path.join(PROJECT_DIR, "data", "chroma_11plus_db")
# If data was moved to data_archive, fall back to that path
if not os.path.exists(CHROMA_DB_PATH):
    alt = os.path.join(PROJECT_DIR, "data_archive", "chroma_11plus_db")
    if os.path.exists(alt):
        CHROMA_DB_PATH = alt

class ElevenPlusRAGStore:
    def __init__(self, persist_directory: str = None):
        self.persist_dir = persist_directory or CHROMA_DB_PATH

        if chromadb is None:
            logger.warning("[RAG] chromadb is not installed. ChromaDB capabilities will be disabled.")
            self.client = None
            self.embedding_function = None
            self.collection = None

            return

        os.makedirs(self.persist_dir, exist_ok=True)

        # 初始化 ChromaDB 客户端
        self.client = chromadb.PersistentClient(path=self.persist_dir)

        # 复用 homework_rag 的嵌入函数创建逻辑
        try:
            from src.homework_rag import _create_embedding_function
            self.embedding_function = _create_embedding_function()
        except ImportError:
            # Fallback if homework_rag is not present in the same workspace yet
            self.embedding_function = None

        # 作业集合
        self.collection = self.client.get_or_create_collection(
            name="elevenplus_collection",
            embedding_function=self.embedding_function,
            metadata={"hnsw:space": "cosine"},
        )


    def _sanitize_metadata(self, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Sanitize metadata to comply with ChromaDB's strict type requirements.
        ChromaDB only supports str, int, float, or bool values for metadata.
        Any None, list, dict, or other unsupported types must be converted to strings or removed.
        """
        sanitized = {}
        for k, v in metadata.items():
            if v is None:
                continue  # Drop None values to avoid ChromaDB conversion errors
            if isinstance(v, (str, int, float, bool)):
                sanitized[k] = v
            elif isinstance(v, (list, dict)):
                import json
                sanitized[k] = json.dumps(v, ensure_ascii=False)
            else:
                sanitized[k] = str(v)
        return sanitized

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
        if self.collection is None:
            logger.warning("[RAG] ChromaDB disabled. add_homework bypassed.")
            return str(int(datetime.now().timestamp() * 1000))

        now = datetime.now()
        # 用毫秒时间戳生成唯一 ID
        doc_id = str(int(now.timestamp() * 1000))

        # Ensure metadata has required fields and complies with ChromaDB rules
        metadata_copy = metadata.copy()
        metadata_copy.setdefault("created_at", now.isoformat())
        sanitized_metadata = self._sanitize_metadata(metadata_copy)

        for attempt in range(1, RAG_MAX_RETRIES + 1):
            try:
                self.collection.add(
                    documents=[homework_content],
                    metadatas=[sanitized_metadata],
                    ids=[doc_id],
                )
                logger.info(f"[RAG] Added homework document: {doc_id}")
                return doc_id
            except Exception as e:
                if attempt < RAG_MAX_RETRIES:
                    logger.warning(
                        f"[RAG] Store attempt {attempt} failed for {doc_id}: {e}, retrying in {RAG_RETRY_DELAY}s...")
                    time.sleep(RAG_RETRY_DELAY)
                else:
                    raise

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
        if self.collection is None:
            logger.warning("[RAG] ChromaDB disabled. add_batch_homework bypassed.")
            return [item.get("doc_id") or str(int(datetime.now().timestamp() * 1000) + i) for i, item in
                    enumerate(homework_list)]

        texts = []
        metadatas = []
        doc_ids = []

        for item in homework_list:
            content = item["content"]
            metadata = item["metadata"].copy()
            doc_id = item.get("doc_id")

            now = datetime.now()
            if not doc_id:
                # 用毫秒时间戳生成唯一 ID
                doc_id = str(int(now.timestamp() * 1000))

            metadata.setdefault("created_at", now.isoformat())
            metadata.setdefault("study_year_month", now.strftime("%Y-%m"))

            texts.append(content)
            metadatas.append(self._sanitize_metadata(metadata))
            doc_ids.append(doc_id)

        self.collection.add(documents=texts, metadatas=metadatas, ids=doc_ids)
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
        if self.collection is None:
            logger.warning("[RAG] ChromaDB disabled. search bypassed.")
            return []

        where_clause = self._build_where_clause(filters) if filters else None

        # 直接使用 collection 的 query 方法，嵌入由 embedding_function 自动处理
        query_kwargs = {
            "query_texts": [query],
            "n_results": k,
            "include": ["documents", "metadatas", "distances"],
        }
        if where_clause:
            query_kwargs["where"] = where_clause

        raw = self.collection.query(**query_kwargs)

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
        if self.collection is None:
            logger.warning("[RAG] ChromaDB disabled. search_by_metadata bypassed.")
            return []

        where_clause = self._build_where_clause(filters)
        results = self.collection.get(where=where_clause)

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
        if self.collection is None:
            logger.warning("[RAG] ChromaDB disabled. delete_homework bypassed.")
            return False

        try:
            self.collection.delete(ids=[doc_id])
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
        if self.collection is None:
            logger.warning("[RAG] ChromaDB disabled. get_stats bypassed.")
            return {
                "total_documents": 0,
                "by_subject": {},
                "by_year_group": {},
            }

        all_docs = self.collection.get()
        total_docs = len(all_docs["ids"]) if all_docs.get("ids") else 0

        # Count by subject
        subject_counts = {}
        year_counts = {}
        if all_docs.get("metadatas"):
            for meta in all_docs["metadatas"]:
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
        if self.collection is None:
            logger.warning("[RAG] ChromaDB disabled. get_student_homework_history bypassed.")
            return []

        filters = {"student_id": student_id}
        if subject:
            filters["subject"] = subject

        results = self.collection.get(where=self._build_where_clause(filters))

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


    def search_homework_answers(
            self,
            doc_id: str,
    ) -> Optional[list]:
        """通过 doc_id 直接获取正确答案

        Args:
            doc_id: 作业文档 ID

        Returns:
            正确答案列表，未找到则返回 None
        """
        if not doc_id:
            logger.warning("[RAG] doc_id 为空")
            return None

        if self.collection is None:
            logger.warning("[RAG] ChromaDB disabled. search_homework_answers bypassed.")
            return None

        try:
            result = self.collection.get(ids=[doc_id])
            if not result or not result.get("ids"):
                logger.warning(f"[RAG] 未找到 doc_id={doc_id} 对应的文档")
                return None

            metadata = result["metadatas"][0]
            correct_answers = metadata.get("correct_answers")
            if correct_answers:
                # Parse JSON string back to list
                try:
                    import json
                    correct_answers = json.loads(correct_answers)
                    logger.info(f"[RAG] 找到 doc_id={doc_id} 的正确答案")
                except (json.JSONDecodeError, TypeError):
                    logger.warning(f"[RAG] doc_id={doc_id} 的正确答案格式错误，返回原始字符串")
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


def search_homework_answers(doc_id: str) -> Optional[str]:
    """通过 doc_id 获取正确答案

    Args:
        doc_id: 作业文档 ID

    Returns:
        正确答案字符串，未找到则返回 None
    """
    store = get_elevenplus_rag_store()
    return store.search_homework_answers(doc_id)
