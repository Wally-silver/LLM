from collections.abc import AsyncGenerator

import httpx


class VLLMOpenAIClient:
    """OpenAI-compatible caller for vLLM server."""

    def __init__(self, base_url: str, api_key: str, model_name: str):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model_name = model_name

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

    async def complete(self, system_prompt: str, user_prompt: str, stream: bool = False):
        payload = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.2,
            "stream": stream,
        }
        async with httpx.AsyncClient(timeout=90) as client:
            if not stream:
                resp = await client.post(f"{self.base_url}/chat/completions", headers=self._headers(), json=payload)
                resp.raise_for_status()
                data = resp.json()
                return data["choices"][0]["message"]["content"]

            async def streamer() -> AsyncGenerator[str, None]:
                async with client.stream(
                    "POST", f"{self.base_url}/chat/completions", headers=self._headers(), json=payload
                ) as resp:
                    resp.raise_for_status()
                    async for line in resp.aiter_lines():
                        if not line or not line.startswith("data:"):
                            continue
                        chunk = line.removeprefix("data:").strip()
                        if chunk == "[DONE]":
                            break
                        yield chunk

            return streamer()
