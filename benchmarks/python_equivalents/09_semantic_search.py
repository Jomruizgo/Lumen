import os
from pathlib import Path
from typing import Any

import numpy as np
import openai

client = openai.OpenAI()

def _embed(text: str) -> list[float]:
    resp = client.embeddings.create(model="text-embedding-3-small", input=text)
    return resp.data[0].embedding

def _cosine_sim(a: list[float], b: list[float]) -> float:
    va = np.array(a)
    vb = np.array(b)
    return float(np.dot(va, vb) / (np.linalg.norm(va) * np.linalg.norm(vb) + 1e-9))

def semantic_search(query: str, corpus_path: str, top_k: int = 5) -> list[dict[str, Any]]:
    corpus = Path(corpus_path).expanduser()
    query_emb = _embed(query)
    results = []
    for doc_path in corpus.rglob("*"):
        if not doc_path.is_file():
            continue
        try:
            text = doc_path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        doc_emb = _embed(text[:2000])
        relevance = _cosine_sim(query_emb, doc_emb)
        results.append({"path": str(doc_path), "relevance": relevance})
    results.sort(key=lambda x: x["relevance"], reverse=True)
    return results[:top_k]

if __name__ == "__main__":
    results = semantic_search(
        query="documentos sobre el proyecto Mars",
        corpus_path="~/Documents/",
    )
    for r in results:
        print(f"{r['path']} ({r['relevance']:.3f})")
