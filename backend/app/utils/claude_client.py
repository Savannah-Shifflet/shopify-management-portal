import anthropic
from app.config import settings

_MODEL = "claude-haiku-4-5-20251001"


class ClaudeClient:
    """Synchronous client — used by single-product enrichment and non-batch tasks."""

    def __init__(self):
        self.client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        self.model = _MODEL

    def message(self, system: str, content: list, max_tokens: int = 2000):
        return self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": content}],
        )


class AsyncClaudeClient:
    """
    Async client for concurrent batch enrichment.
    Uses anthropic.AsyncAnthropic which manages an httpx.AsyncClient connection
    pool internally — safe to share across many concurrent coroutines.
    """

    def __init__(self):
        self.client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        self.model = _MODEL

    async def message(self, system: str, content: list, max_tokens: int = 2000):
        return await self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": content}],
        )
