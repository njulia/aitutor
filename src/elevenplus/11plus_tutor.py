import os
from pathlib import Path

from langchain_community.document_loaders import DirectoryLoader, PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter

from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_chroma import Chroma

from langchain.chains import RetrievalQA

from src.homework_rag import ElevenPlusRAGStore
from src.agent_workflow import init_llm


# =========================
# CONFIG
# =========================

DATA_DIR = "data"
DB_DIR = "vectordb"

os.environ["OPENAI_API_KEY"] = "YOUR_API_KEY_HERE"


# =========================
# LOAD + SPLIT DOCUMENTS
# =========================

def load_documents():
    loader = DirectoryLoader(
        DATA_DIR,
        glob="**/*.pdf",
        loader_cls=PyPDFLoader,
    )
    return loader.load()


def split_documents(docs):
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=800,
        chunk_overlap=150,
    )
    return splitter.split_documents(docs)


# =========================
# CREATE / LOAD VECTOR DB
# =========================

def get_vectorstore(chunks=None):

    rag = ElevenPlusRAGStore()

    print("Creating new vector DB...")
    return Chroma.from_documents(
        documents=chunks,
        embedding=rag.embeddings,
        persist_directory=rag.persist_dir,
    )


# =========================
# BUILD RAG TUTOR
# =========================

def build_tutor(db):
    # llm = ChatOpenAI(model="gpt-4.1")
    llm, _, _ = init_llm()

    qa = RetrievalQA.from_chain_type(
        llm=llm,
        retriever=db.as_retriever(search_kwargs={"k": 5}),
        chain_type="stuff",
    )

    return qa


# =========================
# MAIN
# =========================

def main():

    print("Loading documents...")
    docs = load_documents()

    print("Splitting documents...")
    chunks = split_documents(docs)

    print("Building / loading vector database...")
    db = get_vectorstore(chunks)

    print("Starting AI Tutor... (type 'quit' to exit)")
    tutor = build_tutor(db)

    while True:
        query = input("\nStudent: ")

        if query.lower() in ["quit", "exit"]:
            break

        result = tutor.invoke(query)

        print("\nTutor:\n")
        print(result["result"])


if __name__ == "__main__":
    main()