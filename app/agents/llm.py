from functools import lru_cache

from langchain.chat_models import init_chat_model
from langchain_core.language_models import BaseChatModel

from app.config import get_settings


@lru_cache
def get_llm() -> BaseChatModel:
    """Return the configured chat model, provider selected via LLM_PROVIDER."""
    settings = get_settings()
    return init_chat_model(
        model=settings.llm_model,
        model_provider=settings.llm_provider,
    )
