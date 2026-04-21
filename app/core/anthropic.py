

from anthropic import AsyncAnthropic

from .config import settings

anthropic_client = AsyncAnthropic(
    api_key=settings.AI_API_KEY, 
    base_url=settings.AI_BASE_URL
)