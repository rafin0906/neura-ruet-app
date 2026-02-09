# app/ai/llm_client.py
import os
from typing import Dict, List, Optional, Any
import httpx

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
DEFAULT_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")


class GroqClient:
    def __init__(self, timeout: float = 60.0):
        if not GROQ_API_KEY:
            raise RuntimeError("GROQ_API_KEY missing in env")
        self.timeout = timeout

    async def complete(
        self,
        system_prompt: str,
        messages: List[Dict[str, str]],
        json_mode: bool,
        temperature: float = 0.2,
        model: Optional[str] = None,
        max_tokens: Optional[int] = 800,
    ) -> str:
        chat_messages = [{"role": "system", "content": system_prompt}]
        for m in messages:
            role = m.get("role", "user")
            content = m.get("content", "")
            if role not in ("user", "assistant", "system"):
                role = "user"
            chat_messages.append({"role": role, "content": str(content)})

        payload: Dict[str, Any] = {
            "model": model or DEFAULT_MODEL,
            "messages": chat_messages,
            "temperature": temperature,
        }
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        headers = {
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            r = await client.post(GROQ_URL, headers=headers, json=payload)
            if r.status_code >= 400:
                raise RuntimeError(f"Groq {r.status_code}: {r.text}")
            data = r.json()

        return data["choices"][0]["message"]["content"]
