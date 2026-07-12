from __future__ import annotations

import json
import urllib.request
from pathlib import Path

# Load dynamic pricing from JSON
_PRICING_FILE = Path(__file__).parent / "models_pricing.json"
MODEL_PRICING_USD = {}
if _PRICING_FILE.exists():
    try:
        MODEL_PRICING_USD = json.loads(_PRICING_FILE.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"Failed to load models_pricing.json: {e}")

_USD_TO_JPY_CACHE = None

def get_usd_to_jpy() -> float:
    global _USD_TO_JPY_CACHE
    if _USD_TO_JPY_CACHE is not None:
        return _USD_TO_JPY_CACHE

    try:
        url = "https://open.er-api.com/v6/latest/USD"
        with urllib.request.urlopen(url, timeout=5) as response:
            data = json.loads(response.read().decode())
            rate = data.get("rates", {}).get("JPY", 150.0)
            _USD_TO_JPY_CACHE = rate
            return rate
    except Exception as e:
        print(f"Failed to fetch exchange rate ({e}). Falling back to 150.0 JPY/USD.")
        _USD_TO_JPY_CACHE = 150.0
        return 150.0

def estimate_tokens(text: str) -> int:
    """
    Count tokens strictly using tiktoken. Fallback to heuristic if unavailable.
    """
    try:
        import tiktoken
        # using o200k_base or cl100k_base, both are similar.
        enc = tiktoken.get_encoding("cl100k_base")
        return len(enc.encode(text))
    except ImportError:
        print("Strict token calculation library (tiktoken) not found. Falling back to heuristic calculation.")
        return max(1, len(text) // 4)
    except Exception as e:
        print(f"Token calculation failed ({e}). Falling back to heuristic calculation.")
        return max(1, len(text) // 4)

def estimate_cost_jpy(model_name: str, input_tokens: int, output_tokens: int) -> float:
    """
    Estimate the cost in JPY for the given model and token counts.
    """
    pricing = MODEL_PRICING_USD.get(model_name)
    if not pricing:
        return 0.0
    
    cost_usd = (input_tokens / 1_000_000) * pricing["input"] + (output_tokens / 1_000_000) * pricing["output"]
    return cost_usd * get_usd_to_jpy()

def select_urgent_models(input_tokens: int) -> dict[str, str]:
    """
    Select models dynamically based on estimated input tokens.
    Prioritizes Gemini 1.5 models.
    """
    if input_tokens > 100_000:
        base_model = "gemini-1.5-pro"
        return {
            "review": base_model,
            "autofix": base_model,
            "fallback": base_model,
            "audit": base_model,
            "report": "gemini-1.5-flash"
        }
    else:
        return {
            "review": "gemini-1.5-flash",       
            "autofix": "gemini-1.5-flash",      
            "fallback": "gemini-1.5-pro",          
            "audit": "gemini-1.5-pro",             
            "report": "gemini-1.5-flash"        
        }
