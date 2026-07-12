import sys
import os
import random
import json

# 添加项目根目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from src.homework_rag import get_homework_rag_store


RAG_WRITE_BATCH_SIZE = 250
os.environ["TOKENIZERS_PARALLELISM"] = "false"


def count_year_homework(year_group: int, subject) -> int:
    """Count every stored subject document for one year."""
    store = get_homework_rag_store()

    where = {
        "$and": [
            {"year_group": year_group},
            {"subject": subject},
        ]
    }

    count = 0
    offset = 0
    page_size = 500

    while True:
        page = store.collection.get(
            where=where,
            limit=page_size,
            offset=offset,
        )

        ids = page.get("ids") or []
        count += len(ids)

        if len(ids) < page_size:
            break

        offset += len(ids)

    return count


def clean_year_homeworks(year_group: int, subject: str) -> int:
    """清理指定年级的指定科目作业"""
    store = get_homework_rag_store()
    results = store.search_by_metadata({"year_group": year_group, "subject": subject})

    if not results:
        print(f"  Year {year_group}: 没有找到需要清理的作业")
        return 0

    deleted = 0
    for item in results:
        doc_id = item.get("doc_id")
        if doc_id and store.delete_homework(doc_id):
            deleted += 1

    print(f"  Year {year_group}: 已清理 {deleted} 份作业")
    return deleted


def clean_subject_homeworks(subject: str) -> int:
    """清理指定科目作业"""
    store = get_homework_rag_store()
    results = store.search_by_metadata({"subject": subject})

    if not results:
        print(f"  Subject {subject}: 没有找到需要清理的作业")
        return 0

    deleted = 0
    for item in results:
        doc_id = item.get("doc_id")
        if doc_id and store.delete_homework(doc_id):
            deleted += 1

    print(f"  Subject {subject}: 已清理 {deleted} 份作业")
    return deleted


def check_year_homework_exists(year_group: int, subject: str) -> bool:
    """检查指定年级是否已有指定科目的作业"""
    store = get_homework_rag_store()
    results = store.search(query="maths", k=1, filters={"year_group": year_group, "subject": subject})
    return len(results) > 0


def add_homework_in_batches(store, homework_items: list) -> int:
    """Store homework safely in small, restartable batches."""
    added_total = 0

    for start in range(0, len(homework_items), RAG_WRITE_BATCH_SIZE):
        batch = homework_items[start:start + RAG_WRITE_BATCH_SIZE]

        # Make reruns safe when an earlier run stopped halfway.
        requested_ids = [item["doc_id"] for item in batch]
        existing_result = store.collection.get(ids=requested_ids)
        existing_ids = set(existing_result.get("ids") or [])

        new_items = [
            item for item in batch
            if item["doc_id"] not in existing_ids
        ]

        if new_items:
            store.add_batch_homework(new_items)
            added_total += len(new_items)

        completed = min(start + len(batch), len(homework_items))
        print(
            f"  Stored {completed}/{len(homework_items)} "
            f"({len(new_items)} new, {len(batch) - len(new_items)} already existed)"
        )

    return added_total
