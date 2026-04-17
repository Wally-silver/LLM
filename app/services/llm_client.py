from __future__ import annotations

import json
from collections.abc import AsyncGenerator

import httpx


class VLLMOpenAIClient:
    """Generic local LLM client.

    保留原类名以兼容旧调用，但支持：
    - provider=openai_compatible（vLLM/OpenAI兼容接口）
    - provider=ollama（Windows 本地可直接跑）
    """

    def __init__(
        self,
        base_url: str,
        api_key: str,
        model_name: str,
        http_client: httpx.AsyncClient,
        max_retries: int = 3,
        provider: str = "openai_compatible",
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model_name = model_name
        self.http_client = http_client
        self.max_retries = max_retries
        self.provider = provider

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

    async def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        stream: bool = False,
        max_tokens: int = 1024,
        response_format: dict | None = None,
    ):
        if self.provider == "ollama":
            return await self._complete_ollama(system_prompt, user_prompt, stream, max_tokens)
        return await self._complete_openai_compatible(system_prompt, user_prompt, stream, max_tokens, response_format)

    async def _complete_openai_compatible(
        self,
        system_prompt: str,
        user_prompt: str,
        stream: bool,
        max_tokens: int,
        response_format: dict | None,
    ):
        payload = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.2,
            "max_tokens": max_tokens,
            "stream": stream,
        }
        if response_format is not None:
            payload["response_format"] = response_format

        if not stream:
            last_error = None
            for _ in range(self.max_retries):
                try:
                    resp = await self.http_client.post(
                        f"{self.base_url}/chat/completions", headers=self._headers(), json=payload
                    )
                    resp.raise_for_status()
                    data = resp.json()
                    return data["choices"][0]["message"]["content"]
                except Exception as exc:
                    last_error = exc
            raise RuntimeError(f"LLM request failed after retries: {last_error}")

        async def streamer() -> AsyncGenerator[str, None]:
            async with self.http_client.stream(
                "POST", f"{self.base_url}/chat/completions", headers=self._headers(), json=payload
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line or not line.startswith("data:"):
                        continue
                    chunk = line.removeprefix("data:").strip()
                    if chunk == "[DONE]":
                        break
                    data = json.loads(chunk)
                    delta = data.get("choices", [{}])[0].get("delta", {})
                    content = delta.get("content")
                    if content:
                        yield content

        return streamer()

    async def _complete_ollama(self, system_prompt: str, user_prompt: str, stream: bool, max_tokens: int):
        payload = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "stream": stream,
            "options": {"num_predict": max_tokens, "temperature": 0.2},
        }

        if not stream:
            resp = await self.http_client.post(f"{self.base_url}/api/chat", json=payload)
            resp.raise_for_status()
            data = resp.json()
            return data.get("message", {}).get("content", "")

        async def streamer() -> AsyncGenerator[str, None]:
            async with self.http_client.stream("POST", f"{self.base_url}/api/chat", json=payload) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line:
                        continue
                    data = json.loads(line)
                    token = data.get("message", {}).get("content", "")
                    if token:
                        yield token
                    if data.get("done"):
                        break

        return streamer()
