import json
import urllib.request
import urllib.error
from typing import Any

from .base import Provider, AIResponse, TokenUsage

class OllamaProvider(Provider):
    def generate_review(self, system_prompt: str, user_prompt: str, schema: dict[str, Any] | None = None) -> AIResponse:
        url = self.base_url or "http://localhost:11434/api/generate"
        headers = {
            "Content-Type": "application/json",
        }

        payload: dict[str, Any] = {
            "model": self.model,
            "system": system_prompt,
            "prompt": user_prompt,
            "stream": False,
            "options": {
                "temperature": 0.0,
            }
        }

        if schema:
            payload["format"] = "json"

        req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_seconds) as response:
                response_data = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            error_body = e.read().decode("utf-8")
            raise RuntimeError(f"Ollama API Error {e.code}: {error_body}") from e

        content = response_data.get("response", "")
        
        prompt_tokens = response_data.get("prompt_eval_count", 0)
        completion_tokens = response_data.get("eval_count", 0)
        total_tokens = prompt_tokens + completion_tokens
        
        # Local LLMs typically have no API cost
        cost_jpy = 0.0
        
        usage = TokenUsage(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            estimated_cost_jpy=cost_jpy
        )

        return AIResponse(content=content, usage=usage, raw_response=response_data)
