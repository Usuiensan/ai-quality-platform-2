from __future__ import annotations

# Pricing per 1M tokens in USD
MODEL_PRICING_USD = {
    "gpt-4o": {"input": 5.00, "output": 15.00, "max_tokens": 128000},
    "gpt-4o-mini": {"input": 0.15, "output": 0.60, "max_tokens": 128000},
    "gemini-1.5-pro": {"input": 3.50, "output": 10.50, "max_tokens": 2000000},
    "gemini-1.5-flash": {"input": 0.075, "output": 0.30, "max_tokens": 1000000},
}

USD_TO_JPY = 150.0  # Fixed exchange rate for estimation

def estimate_tokens(text: str) -> int:
    """
    Roughly estimate token count using a heuristic (1 token approx 4 characters for code/English).
    """
    return max(1, len(text) // 4)

def estimate_cost_jpy(model_name: str, input_tokens: int, output_tokens: int) -> float:
    """
    Estimate the cost in JPY for the given model and token counts.
    """
    pricing = MODEL_PRICING_USD.get(model_name)
    if not pricing:
        return 0.0
    
    cost_usd = (input_tokens / 1_000_000) * pricing["input"] + (output_tokens / 1_000_000) * pricing["output"]
    return cost_usd * USD_TO_JPY

def select_urgent_models(input_tokens: int) -> dict[str, str]:
    """
    Select models dynamically based on estimated input tokens.
    """
    # If the context is huge (> 100k tokens), we must use Gemini 1.5 Pro
    if input_tokens > 100_000:
        base_model = "gemini-1.5-pro"
        return {
            "review": base_model,
            "autofix": base_model,
            "fallback": base_model,
            "audit": base_model,
            "report": "gemini-1.5-flash"  # Cheaper model for formatting
        }
    else:
        # For typical sizes, use OpenAI for high quality
        return {
            "review": "gpt-4o-mini",       # Fast initial review
            "autofix": "gpt-4o-mini",      # Fast fix attempt
            "fallback": "gpt-4o",          # Strong fallback for fixes
            "audit": "gpt-4o",             # Strong audit
            "report": "gpt-4o-mini"        # Cheap report generation
        }
