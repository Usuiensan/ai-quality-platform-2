import json
import urllib.request
import urllib.error
from typing import Any

from .base import Provider, AIResponse, TokenUsage

class GeminiProvider(Provider):
    def generate_review(self, system_prompt: str, user_prompt: str, schema: dict[str, Any] | None = None) -> AIResponse:
        if not self.api_key:
            raise ValueError("API Key is required for Gemini")

        url = self.base_url or f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.api_key}"
        headers = {
            "Content-Type": "application/json",
        }

        payload: dict[str, Any] = {
            "system_instruction": {
                "parts": [{"text": system_prompt}]
            },
            "contents": [{
                "parts": [{"text": user_prompt}]
            }],
            "generationConfig": {
                "temperature": 0.0,
            }
        }

        if schema:
            payload["generationConfig"]["response_mime_type"] = "application/json"
            # Note: Gemini supports response_schema in newer versions.
            payload["generationConfig"]["response_schema"] = schema

        req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_seconds) as response:
                response_data = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            error_body = e.read().decode("utf-8")
            raise RuntimeError(f"Gemini API Error {e.code}: {error_body}") from e

        content = response_data["candidates"][0]["content"]["parts"][0]["text"]
        usage_metadata = response_data.get("usageMetadata", {})
        
        prompt_tokens = usage_metadata.get("promptTokenCount", 0)
        completion_tokens = usage_metadata.get("candidatesTokenCount", 0)
        total_tokens = usage_metadata.get("totalTokenCount", 0)
        
        cost_jpy = (prompt_tokens * 0.0001) + (completion_tokens * 0.0003)
        
        usage = TokenUsage(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            estimated_cost_jpy=cost_jpy
        )

        return AIResponse(content=content, usage=usage, raw_response=response_data)
