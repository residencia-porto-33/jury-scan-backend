from app.core.config import Settings, get_settings
from app.services.ai.base import AIProvider, AIProviderError, AIResult, AIUnavailableError


class UnconfiguredProvider:
    """Usado quando não há GEMINI_API_KEY: falha de forma controlada (503)."""

    def analyze(self, texto: str) -> AIResult:
        raise AIUnavailableError("provedor de IA não configurado")


def build_ai_provider(settings: Settings | None = None) -> AIProvider:
    settings = settings or get_settings()
    if not settings.gemini_api_key:
        return UnconfiguredProvider()
    from app.services.ai.gemini import GeminiProvider  # import tardio: SDK só quando usado

    return GeminiProvider(settings)


__all__ = ["AIProvider", "AIProviderError", "AIResult", "UnconfiguredProvider", "build_ai_provider"]
