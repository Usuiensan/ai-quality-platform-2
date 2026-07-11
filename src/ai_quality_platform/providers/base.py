import abc
from dataclasses import dataclass
from typing import Any

@dataclass
class TokenUsage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    estimated_cost_jpy: float = 0.0

@dataclass
class AIResponse:
    content: str
    usage: TokenUsage
    raw_response: dict[str, Any] | None = None

class Provider(abc.ABC):
    def __init__(self, model: str, api_key: str | None = None, base_url: str | None = None, timeout_seconds: int = 300):
        self.model = model
        self.api_key = api_key
        self.base_url = base_url
        self.timeout_seconds = timeout_seconds

    @abc.abstractmethod
    def generate_review(self, system_prompt: str, user_prompt: str, schema: dict[str, Any] | None = None) -> AIResponse:
        """Generate a review based on the prompts. Optionally use JSON schema."""
        pass

def create_provider(provider_name: str, model: str, api_key: str | None = None, base_url: str | None = None, timeout_seconds: int = 300) -> Provider:
    if provider_name == "openai" or provider_name == "openai-compatible":
        from .openai import OpenAIProvider
        return OpenAIProvider(model, api_key, base_url, timeout_seconds)
    elif provider_name == "gemini":
        from .gemini import GeminiProvider
        return GeminiProvider(model, api_key, base_url, timeout_seconds)
    elif provider_name == "ollama":
        from .ollama import OllamaProvider
        return OllamaProvider(model, api_key, base_url, timeout_seconds)
    else:
        raise ValueError(f"Unknown provider: {provider_name}")
