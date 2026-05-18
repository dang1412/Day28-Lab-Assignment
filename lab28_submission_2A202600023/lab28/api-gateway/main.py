# api-gateway/main.py
from fastapi import FastAPI
from pydantic import BaseModel
from prometheus_fastapi_instrumentator import Instrumentator
import httpx, os, time

app = FastAPI(title="AI Platform API Gateway")
Instrumentator().instrument(app).expose(app)  # Integration 9: Prometheus

VLLM_URL = os.environ["VLLM_URL"]
VLLM_MODEL = os.environ.get("VLLM_MODEL", "Qwen/Qwen2.5-1.5B-Instruct")
QDRANT_URL = os.environ.get("QDRANT_URL", "http://qdrant:6333")


class ChatRequest(BaseModel):
    query: str
    embedding: list[float] | None = None


@app.post("/api/v1/chat")
async def chat(body: ChatRequest):
    query = body.query
    start = time.time()

    # 1. Vector search
    async with httpx.AsyncClient() as client:
        search_resp = await client.post(f"{QDRANT_URL}/collections/documents/points/search", json={
            "vector": body.embedding or [0.0] * 384,
            "limit": 3
        })
        context = search_resp.json().get("result", [])

    # 2. LLM inference
    prompt = f"Context: {context}\n\nQuery: {query}"
    async with httpx.AsyncClient(timeout=30) as client:
        llm_resp = await client.post(f"{VLLM_URL}/v1/chat/completions", json={
            "model": VLLM_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 80
        })

    latency = (time.time() - start) * 1000
    result = llm_resp.json()

    return {
        "answer": result["choices"][0]["message"]["content"],
        "latency_ms": round(latency, 2),
        "model": result["model"]
    }

@app.get("/health")
def health():
    return {"status": "ok"}
