from functools import lru_cache

from langchain.chat_models import init_chat_model
from langchain_core.language_models import BaseChatModel

from app.config import get_settings

_API_KEY_FIELD = {
    "anthropic": "anthropic_api_key",
    "openai": "openai_api_key",
    "google_genai": "google_api_key",
}


@lru_cache
def get_llm() -> BaseChatModel:
    """Return the configured chat model, provider selected via LLM_PROVIDER."""
    settings = get_settings()
    api_key = getattr(settings, _API_KEY_FIELD[settings.llm_provider])
    return init_chat_model(
        model=settings.llm_model,
        model_provider=settings.llm_provider,
        api_key=api_key,
    )
