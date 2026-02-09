# app/ai/embedding_model.py

import os
from typing import List
import httpx

HF_API_TOKEN = os.getenv("HF_API_TOKEN")
HF_EMBEDDING_MODEL = os.getenv(
    "HF_EMBEDDING_MODEL",
    "sentence-transformers/all-MiniLM-L6-v2",
)

HF_URL = (
    f"https://router.huggingface.co/hf-inference/models/{HF_EMBEDDING_MODEL}"
    f"/pipeline/feature-extraction"
)


class HFEmbeddingClient:
    def __init__(self, timeout: float = 30.0):
        if not HF_API_TOKEN:
            raise RuntimeError("HF_API_TOKEN (or HF_TOKEN) missing in env")

        self._headers = {
            "Authorization": f"Bearer {HF_API_TOKEN}",
            "Content-Type": "application/json",
        }
        self._timeout = timeout

    @staticmethod
    def _mean_pool(token_vecs: List[List[float]]) -> List[float]:
        dim = len(token_vecs[0])
        out = [0.0] * dim
        for tv in token_vecs:
            for i, v in enumerate(tv):
                out[i] += float(v)
        n = float(len(token_vecs)) if token_vecs else 1.0
        return [v / n for v in out]

    def _normalize(self, data) -> List[float]:
        """
        HF feature-extraction usually returns token embeddings:
          [[...], [...], ...]
        Sometimes it returns a pooled vector:
          [...]
        We always output one vector (dim=384 for MiniLM).
        """
        if not data:
            return []

        # already pooled: [dim]
        if isinstance(data[0], (int, float)):
            return [float(x) for x in data]

        # token vectors: [tokens][dim]
        return self._mean_pool(data)

    async def embed(self, text: str) -> List[float]:
        text = (text or "").strip()
        if not text:
            return []

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            r = await client.post(HF_URL, headers=self._headers, json={"inputs": text})
            if r.status_code >= 400:
                raise RuntimeError(f"HF error {r.status_code}: {r.text}")
            data = r.json()

        return self._normalize(data)

    async def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """
        Batch embedding. Returns one vector per input text.
        """
        if not texts:
            return []

        cleaned = [(t or "").strip() for t in texts]

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            r = await client.post(HF_URL, headers=self._headers, json={"inputs": cleaned})
            if r.status_code >= 400:
                raise RuntimeError(f"HF error {r.status_code}: {r.text}")
            data = r.json()

        # data is list per input
        return [self._normalize(item) for item in data]

_client = HFEmbeddingClient()

async def embed_texts(texts: List[str]) -> List[List[float]]:
    return await _client.embed_texts(texts)

async def embed_text(text: str) -> List[float]:
    return await _client.embed(text)
