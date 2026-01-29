import os
import json
from typing import List, Dict, Optional

from groq import Groq


class LLMClient:
    def __init__(self):
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise RuntimeError("GROQ_API_KEY missing in environment")

        self.client = Groq(api_key=api_key)
        self.model = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

    def complete(
        self,
        system_prompt: str,
        messages: List[Dict[str, str]],
        *,
        json_mode: bool = False,
        temperature: float = 0.2,
    ) -> str:
        chat_messages = [{"role": "system", "content": system_prompt}]
        chat_messages.extend(messages)

        kwargs = {
            "model": self.model,
            "messages": chat_messages,
            "temperature": temperature,
        }

        # ✅ only force JSON when needed (planner)
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}

            # Groq requirement: the word "json" must appear in messages somewhere
            has_json_word = any("json" in (m.get("content") or "").lower() for m in chat_messages)
            if not has_json_word:
                chat_messages[0]["content"] += "\n\nReturn valid JSON."

        resp = self.client.chat.completions.create(**kwargs)
        return resp.choices[0].message.content


llm_client = LLMClient()
