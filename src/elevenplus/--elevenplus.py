import os
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_core.output_parsers import JsonOutputParser, StrOutputParser
from langchain_core.prompts import ChatPromptTemplate

from src.homework_rag import ElevenPlusRAGStore
from src.agent_workflow import init_llm
from src.prompts import ELEVEN_PLUS_RAG_PROMPT
from src.models import ELEVEN_PLUS_SUBJECTS


# =========================
# HOMEWORK GENERATION PROMPT
# =========================

def generate_homework(subject: str, index: int, llm) -> str:
    """
    Generate homework for a given subject and index using the provided LLM.
    Args:
        subject:
        index:
        llm:

    Returns:

    """
    prompt = ChatPromptTemplate.from_template(ELEVEN_PLUS_RAG_PROMPT)
    chain = prompt | llm | StrOutputParser()

    result = chain.invoke({
        "subject": subject,
        "index": index
    })
    return result.content

    # prompt = ELEVEN_PLUS_RAG_PROMPT.format(subject=subject, index=index, context=result )
    # response = llm.invoke(prompt)
    # return response.content


# =========================
# CREATE VECTOR STORE
# =========================

def create_vectorstore():
    print("Creating new vector DB...")
    rag = ElevenPlusRAGStore()
    return rag.db


# =========================
# STORE HOMEWORK
# =========================

def store_homework(db, subject, index, content):
    doc_id = f"{subject.lower()}_{index:03d}"
    doc = Document(
        page_content=content,
        metadata={
            "subject": subject,
            "type": "11plus_homework",
            "duration_minutes": 30
        }
    )

    db.add_documents([doc], ids=[doc_id])


# =========================
# GENERATE ALL HOMEWORK
# =========================

def generate_all_homework(db, llm):
    subjects = ELEVEN_PLUS_SUBJECTS

    total = 300
    per_subject = total // len(subjects)

    count = 0

    for subject in subjects:
        for i in range(1, per_subject + 1):

            print(f"Generating {subject} homework {i}/{per_subject}")

            hw = generate_homework(subject, i, llm)

            store_homework(db, subject, i, hw)

            count += 1

    print(f"\nDONE: Generated {count} homework sets")


# =========================
# SEARCH FUNCTION (RAG)
# =========================

def search_homework(db, query):
    results = db.similarity_search(query, k=3)

    for i, doc in enumerate(results):
        print(f"\n--- Result {i+1} ---")
        print(doc.page_content[:1200])


# =========================
# MAIN
# =========================

def main():

    llm, _, _ = init_llm()
    db = create_vectorstore()

    # Check if empty DB (simple heuristic)
    existing = db._collection.count()

    if existing == 0:
        print("No homework found. Generating 300 sets...")
        generate_all_homework(db, llm)
    else:
        print(f"Loaded existing database ({existing} items)")

    print("\nAI Tutor ready. Type queries or 'quit'.")

    while True:
        q = input("\nStudent: ")

        if q.lower() in ["quit", "exit"]:
            break

        search_homework(db, q)


if __name__ == "__main__":
    main()