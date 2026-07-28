import logging

from src import homework_generator
from src.homework_rag import get_homework_rag_store, store_homework

# Mock LLM Client
class MockLLMClient:
    def complete(self, messages):
        return "Generated Year 2 Maths Homework Content"
    def complete_json(self, messages):
        return []

def reproduce_issue():
    logging.basicConfig(level=logging.INFO)
    llm = MockLLMClient()
    
    # 1. Add some Year 2 Maths homework to RAG
    year_group = 2
    subject = "Maths"
    content = "RAG Year 2 Maths Content"
    
    # Clear existing RAG for Year 2 Maths to ensure clean state (optional but good)
    store = get_homework_rag_store()
    # No easy way to clear just year 2 maths without deleting whole DB or adding complex delete logic
    
    doc_id = store_homework(
        homework_content=content,
        year_group=year_group,
        subject=subject,
        homework_minutes="20"
    )
    print(f"Stored RAG homework with doc_id: {doc_id}")
    
    student_profile = {
        "student_id": "test_student_y2",
        "year_group": year_group,
        "age": 7
    }
    
    # 2. Call generate_homework_for_subject
    print("\n--- Attempting generation (should hit RAG) ---")
    result_content, result_doc_id, from_rag = homework_generator.generate_homework_for_subject(
        student_profile=student_profile,
        subject=subject,
        llm=llm
    )
    
    print(f"Result from_rag: {from_rag}")
    print(f"Result doc_id: {result_doc_id}")
    
    # 3. Inspect what's in RAG
    print("\n--- Inspecting RAG store ---")
    session = store.store.Session()
    from src.pgvector_store import VectorDocument
    from sqlalchemy import select
    stmt = select(VectorDocument).where(VectorDocument.collection_name == store.store.collection_name)
    all_docs = session.execute(stmt).scalars().all()
    print(f"Total documents in database for collection {store.store.collection_name}: {len(all_docs)}")
    for doc in all_docs:
        print(f"doc_id={doc.id}, metadata={doc.metadata_json}, type(year_group)={type(doc.metadata_json.get('year_group'))}")
    session.close()

    # Search all for this subject to see year_group
    all_subject_results = store.search_by_metadata({"subject": subject}, k=100)
    print(f"Found {len(all_subject_results)} documents for subject {subject}")
    for i, res in enumerate(all_subject_results):
        print(f"Result {i}: doc_id={res['doc_id']}, metadata={res['metadata']}")
    
    results = store.search_by_metadata({"year_group": year_group, "subject": subject})
    print(f"Found {len(results)} documents for Year {year_group} {subject} (filtered)")
    
    if from_rag:
        print("\nSUCCESS: RAG was checked and hit.")
    else:
        print("\nFAILURE: RAG was NOT hit.")

if __name__ == "__main__":
    reproduce_issue()
