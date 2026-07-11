import json
import urllib.request
import urllib.error
from typing import Any

from .base import Provider, AIResponse, TokenUsage

class OpenAIProvider(Provider):
    def generate_review(self, system_prompt: str, user_prompt: str, schema: dict[str, Any] | None = None) -> AIResponse:
        if not self.api_key:
            raise ValueError("API Key is required for OpenAI")

        url = self.base_url or "https://api.openai.com/v1/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }

        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": 0.0,
        }

        if schema:
            payload["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": "review_result",
                    "strict": True,
                    "schema": schema
                }
            }

        req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_seconds) as response:
                response_data = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            error_body = e.read().decode("utf-8")
            raise RuntimeError(f"OpenAI API Error {e.code}: {error_body}") from e

        content = response_data["choices"][0]["message"]["content"]
        usage_data = response_data.get("usage", {})
        
        # Simple cost estimation (example for gpt-4o-mini as fallback, adjust as needed)
        prompt_tokens = usage_data.get("prompt_tokens", 0)
        completion_tokens = usage_data.get("completion_tokens", 0)
        total_tokens = usage_data.get("total_tokens", 0)
        
        # Cost mapping (dummy values, USD converted to JPY roughly)
        cost_jpy = (prompt_tokens * 0.00015) + (completion_tokens * 0.0006)
        
        usage = TokenUsage(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            estimated_cost_jpy=cost_jpy
        )

        return AIResponse(content=content, usage=usage, raw_response=response_data)
