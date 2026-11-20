"""LLM factory. Switch providers by editing .env only."""
from functools import lru_cache

from langchain.chat_models import init_chat_model

from app import config


@lru_cache(maxsize=4)
def get_llm(fast: bool = False, temperature: float = 0.2):
    model = config.LLM_FAST_MODEL if fast else config.LLM_MODEL
    return init_chat_model(
        model,
        model_provider=config.LLM_PROVIDER,
        temperature=temperature,
        max_retries=3,
    )


def structured(schema, fast: bool = False, temperature: float = 0.0):
    """LLM that returns a validated Pydantic object.
    Set STRUCTURED_METHOD in .env (function_calling | json_schema | json_mode) if your provider needs it."""
    llm = get_llm(fast=fast, temperature=temperature)
    method = config.env("STRUCTURED_METHOD")
    kwargs = {"method": method} if method else {}
    # STRUCTURED_STRICT=true -> provider-side constrained decoding (e.g. Groq gpt-oss + json_schema)
    if config.env("STRUCTURED_STRICT").lower() == "true":
        kwargs["strict"] = True
    runnable = llm.with_structured_output(schema, **kwargs)
    # Some providers (e.g. Groq json_schema) intermittently return an empty/invalid generation (HTTP 400).
    # Retrying the same request usually succeeds; this does not relax any validation.
    return runnable.with_retry(stop_after_attempt=3)
