import os # Added this line
import logging
import time
import json
import re
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

_YEAR_ROUND_BLOCK_RE = re.compile(
    r"Homework Question\s+(?P<number>\d+)\s*:\s*\n"
    r"(?P<question>.*?)\n"
    r"Options:\s*(?P<options>.*?)\n"
    r"Correct Answer:\s*(?:Option\s*)?(?P<letter>[A-H])\s*\((?P<answer>.*?)\)\s*\n"
    r"Explanation:\s*(?P<explanation>.*?)\n"
    r"(?:Coaching Strategy|Coach(?:ing)? Tip):\s*(?P<tip>.*?)"
    r"(?=\n\nHomework Question\s+\d+\s*:|\Z)",
    re.IGNORECASE | re.DOTALL,
)


def _split_legacy_options(value: str) -> List[str]:
    """Split the old comma-joined option format without breaking 1,000 or quotes."""
    text = str(value or "").strip()
    if not text:
        return []

    parts: List[str] = []
    buffer: List[str] = []
    quote: Optional[str] = None
    index = 0
    while index < len(text):
        char = text[index]
        if char in {'"', "'"}:
            previous = text[index - 1] if index else ""
            following = text[index + 1] if index + 1 < len(text) else ""
            is_apostrophe = char == "'" and previous.isalnum() and following.isalnum()
            if not is_apostrophe:
                if quote is None:
                    quote = char
                elif quote == char:
                    quote = None
            buffer.append(char)
            index += 1
            continue

        if char == "," and index + 1 < len(text) and text[index + 1] == " ":
            if quote is None:
                candidate = "".join(buffer).strip()
                if candidate:
                    parts.append(candidate)
                buffer = []
                index += 2
                continue

        buffer.append(char)
        index += 1

    candidate = "".join(buffer).strip()
    if candidate:
        parts.append(candidate)
    return parts


def _normalise_answer_records(raw_answers: Any) -> List[Dict[str, Any]]:
    if not raw_answers:
        return []
    if isinstance(raw_answers, str):
        try:
            raw_answers = json.loads(raw_answers)
        except (TypeError, json.JSONDecodeError):
            return []
    if not isinstance(raw_answers, list):
        return []

    records: List[Dict[str, Any]] = []
    for index, item in enumerate(raw_answers, start=1):
        if not isinstance(item, dict):
            continue
        question = str(item.get("question") or item.get("questionText") or "").strip()
        answer = str(
            item.get("answer")
            or item.get("correctValue")
            or item.get("correct_answer")
            or ""
        ).strip()
        options = item.get("options") if isinstance(item.get("options"), list) else []
        options = [str(option).strip() for option in options if str(option).strip()]
        if not question or not answer:
            continue
        if not re.match(r"^\s*\d+[.)]\s*", question):
            question = f"{index}. {question}"
        records.append(
            {
                "question": question,
                "answer": answer,
                "options": options,
                "correct_letter": str(
                    item.get("correct_letter")
                    or item.get("correctLetter")
                    or item.get("letter")
                    or ""
                ).strip().upper(),
                "explanation": str(item.get("explanation") or "").strip(),
                "tip": str(item.get("tip") or item.get("coaching_strategy") or "").strip(),
            }
        )
    return records


def extract_year_round_answer_records(content: str) -> List[Dict[str, Any]]:
    """Recover structured answers from legacy year-round documents.

    Older generators stored answers and explanations inside the document rather
    than metadata. This parser supports those records so existing RAG databases
    continue to work after the safer question-only format is introduced.
    """
    records: List[Dict[str, Any]] = []
    for match in _YEAR_ROUND_BLOCK_RE.finditer(str(content or "").strip()):
        number = int(match.group("number"))
        records.append(
            {
                "question": f"{number}. {match.group('question').strip()}",
                "answer": match.group("answer").strip(),
                "options": _split_legacy_options(match.group("options")),
                "correct_letter": match.group("letter").strip().upper(),
                "explanation": match.group("explanation").strip(),
                "tip": match.group("tip").strip(),
            }
        )
    return records


def extract_multiple_choice_questions(content: str) -> List[Dict[str, Any]]:
    """Extract question stems and options without returning answer material."""
    text = str(content or "").replace("\r\n", "\n").replace("\r", "\n")
    legacy = extract_year_round_answer_records(text)
    if legacy:
        return questions_from_answer_records(legacy)

    # LLM fallback and new RAG records use one option per line. Ignore every
    # answer/explanation section before parsing so answer keys never reach UI.
    questions_only = re.split(
        r"(?im)^\s*#{0,6}\s*(?:answers?|answer key|explanations?|worked solutions?|bonus)\b.*$",
        text,
        maxsplit=1,
    )[0]
    question_re = re.compile(r"^\s*(?:Question\s*)?(\d+)[.)]\s+(.+?)\s*$", re.I)
    option_re = re.compile(r"^\s*(?:[-*]\s*)?\(?([A-H])\)?[.)]\s+(.+?)\s*$", re.I)
    questions: List[Dict[str, Any]] = []
    current: Optional[Dict[str, Any]] = None
    for raw_line in questions_only.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        question_match = question_re.match(line)
        if question_match:
            if current and len(current["options"]) >= 2:
                questions.append(current)
            current = {
                "number": int(question_match.group(1)),
                "question": question_match.group(2).strip(),
                "options": [],
            }
            continue
        option_match = option_re.match(line)
        if option_match and current is not None:
            current["options"].append(
                {"label": option_match.group(1).upper(), "text": option_match.group(2).strip()}
            )
    if current and len(current["options"]) >= 2:
        questions.append(current)
    return questions


def questions_from_answer_records(records: Any) -> List[Dict[str, Any]]:
    """Return the public, answer-free shape consumed by the browser."""
    normalised = _normalise_answer_records(records)
    questions: List[Dict[str, Any]] = []
    for index, record in enumerate(normalised, start=1):
        match = re.match(r"^\s*(\d+)[.)]\s*(.*)$", record["question"], re.DOTALL)
        number = int(match.group(1)) if match else index
        question = match.group(2).strip() if match else record["question"]
        options = [
            {"label": chr(65 + option_index), "text": option}
            for option_index, option in enumerate(record.get("options") or [])
        ]
        if question and len(options) >= 2:
            questions.append({"number": number, "question": question, "options": options})
    return questions


def format_questions_only(questions: List[Dict[str, Any]]) -> str:
    """Create a readable question-only fallback string for API clients."""
    lines = ["QUESTIONS"]
    for index, item in enumerate(questions, start=1):
        number = int(item.get("number") or index)
        lines.append(f"{number}. {str(item.get('question') or '').strip()}")
        for option_index, option in enumerate(item.get("options") or []):
            if isinstance(option, dict):
                label = str(option.get("label") or chr(65 + option_index)).strip().upper()
                text = str(option.get("text") or "").strip()
            else:
                label = chr(65 + option_index)
                text = str(option).strip()
            if text:
                lines.append(f"{label}) {text}")
        lines.append("")
    return "\n".join(lines).strip()

# RAG storage directory
PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
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

        # Deterministic year-round document IDs must be safely regeneratable.
        # Upsert keeps ingestion idempotent and avoids deleting the collection first.
        self.collection.upsert(documents=texts, metadatas=metadatas, ids=doc_ids)
        logger.info(f"[RAG] Upserted {len(doc_ids)} homework documents in batch")
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

    def delete_student_homework(self, student_id: str) -> int:
        """Delete legacy 11+ documents that directly reference one learner."""
        learner = str(student_id or "").strip()
        if not learner or self.collection is None:
            return 0
        try:
            result = self.collection.get(where={"student_id": learner}, include=[])
            ids = list(result.get("ids") or [])
            if ids:
                self.collection.delete(ids=ids)
            return len(ids)
        except Exception:
            logger.exception("[RAG] Failed to erase legacy 11+ homework for learner %s", learner)
            return 0

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
            raw_correct_answers = metadata.get("correct_answers")
            decoded_answers: Any = raw_correct_answers
            if isinstance(raw_correct_answers, str):
                try:
                    decoded_answers = json.loads(raw_correct_answers)
                except (TypeError, json.JSONDecodeError):
                    decoded_answers = raw_correct_answers

            correct_answers = _normalise_answer_records(decoded_answers)
            if correct_answers:
                logger.info("[RAG] Found structured answers for doc_id=%s", doc_id)
                return correct_answers
            if isinstance(decoded_answers, list) and decoded_answers:
                # Preserve older answer-only lists for the generic 11+ review path.
                return decoded_answers

            documents = result.get("documents") or []
            legacy_records = extract_year_round_answer_records(documents[0] if documents else "")
            if legacy_records:
                logger.info("[RAG] Recovered legacy year-round answers for doc_id=%s", doc_id)
                return legacy_records
            return None
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
        age: Optional[int] = None,
        week_num: Optional[int] = None,
        content_type: Optional[str] = None,
        topic: Optional[str] = None,
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
        age: Student age

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
    if age is not None:
        metadata["age"] = int(age)
    if week_num is not None:
        metadata["week_num"] = int(week_num)
    if content_type:
        metadata["content_type"] = str(content_type)
    if topic:
        metadata["topic"] = str(topic)

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



def _subject_aliases(subject: str) -> List[str]:
    """Return exact new keys first, followed by safe legacy aliases."""
    canonical = str(subject or "").strip()
    has_year_suffix = canonical.casefold().endswith("-1year")
    base = canonical[:-6] if has_year_suffix else canonical
    folded = re.sub(r"[\s_-]+", "", base).casefold()

    if folded in {"maths", "mathematics"}:
        aliases = ["Maths-1year", "Maths"] if has_year_suffix else ["Maths"]
    elif folded == "english":
        aliases = ["English-1year", "English"] if has_year_suffix else ["English"]
    elif folded == "verbalreasoning":
        aliases = (
            ["VerbalReasoning-1year", "Verbal Reasoning-1year", "Verbal Reasoning", "VerbalReasoning"]
            if has_year_suffix
            else ["Verbal Reasoning", "VerbalReasoning"]
        )
    elif folded == "nonverbalreasoning":
        aliases = (
            [
                "NonVerbalReasoning-1year",
                "Non-Verbal Reasoning-1year",
                "Non Verbal Reasoning-1year",
                "Non-Verbal Reasoning",
                "NonVerbalReasoning",
                "Non Verbal Reasoning",
            ]
            if has_year_suffix
            else ["Non-Verbal Reasoning", "NonVerbalReasoning", "Non Verbal Reasoning"]
        )
    else:
        aliases = [canonical]

    # Preserve order while avoiding duplicate metadata queries.
    return list(dict.fromkeys(alias for alias in aliases if alias))


def search_homework_by_metadata(
    year_group: int,
    subject: str,
    k: int = 50,
    week_num: Optional[int] = None,
    content_type: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Return exact metadata candidates without creating a query embedding.

    ``week_num`` is a hard filter for the 52-week plan. Subject aliases keep
    older RAG databases compatible with the canonical spaced subject names.
    """
    store = get_elevenplus_rag_store()
    merged: List[Dict[str, Any]] = []
    seen: set[str] = set()
    aliases = _subject_aliases(subject)
    prefer_exact_year_round = str(subject or "").strip().casefold().endswith("-1year")
    for alias_index, alias in enumerate(aliases):
        filters: Dict[str, Any] = {"year_group": int(year_group), "subject": alias}
        if week_num is not None:
            filters["week_num"] = int(week_num)
        if content_type:
            filters["content_type"] = str(content_type)
        alias_results = store.search_by_metadata(filters, k=k)
        for item in alias_results:
            doc_id = str(item.get("doc_id") or "")
            if doc_id and doc_id not in seen:
                seen.add(doc_id)
                merged.append(item)
            if len(merged) >= k:
                return merged
        # New 52-week records are authoritative. Query legacy aliases only
        # when the exact new key has no records, reducing database work.
        if prefer_exact_year_round and alias_index == 0 and alias_results:
            return merged
    return merged


def get_homework_questions(doc_id: Optional[str], content: str = "") -> List[Dict[str, Any]]:
    """Return answer-free structured questions for the year-round browser UI."""
    records = search_homework_answers(doc_id) if doc_id else None
    questions = questions_from_answer_records(records)
    if questions:
        return questions
    return extract_multiple_choice_questions(content)

def get_student_homework_history(student_id: str, subject: str = None) -> List[Dict[str, Any]]:
    """Get homework history for a student"""
    store = get_elevenplus_rag_store()
    return store.get_student_homework_history(student_id, subject)


def delete_student_homework(student_id: str) -> int:
    """Erase legacy learner-owned documents from the 11+ RAG."""
    return get_elevenplus_rag_store().delete_student_homework(student_id)


def get_student_previous_topics(student_id: str, subject: str) -> List[str]:
    """Get previous topics covered for a student in a subject"""
    store = get_elevenplus_rag_store()
    return store.get_student_previous_topics(student_id, subject)


def search_homework_answers(doc_id: str) -> Optional[list]:
    """通过 doc_id 获取正确答案

    Args:
        doc_id: 作业文档 ID

    Returns:
        正确答案字符串，未找到则返回 None
    """
    store = get_elevenplus_rag_store()
    return store.search_homework_answers(doc_id)
