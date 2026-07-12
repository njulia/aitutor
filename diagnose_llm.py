import os
from dotenv import load_dotenv

# Load .env first
project_root = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(project_root, ".env"))

from src.llm_client import LLMClient, get_llm_provider

def diagnose():
    provider = get_llm_provider()
    print(f"LLM_PROVIDER: {provider}")
    
    client = LLMClient()
    print(f"Client Provider: {client.provider}")
    print(f"Client Model: {client.model}")
    print(f"Client API Base: {client.api_base}")
    print(f"Client API Key: {'Set' if client.api_key else 'Not Set'}")
    
    if client.is_ollama():
        print("DIAGNOSIS: Client is using OLLAMA")
    else:
        print("DIAGNOSIS: Client is using API")

if __name__ == "__main__":
    diagnose()
