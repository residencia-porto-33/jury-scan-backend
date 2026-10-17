from dataclasses import dataclass
from typing import Protocol

from app.schemas.ai_contract import AIOutput


@dataclass(frozen=True)
class AIResult:
    output: AIOutput
    modelo_versao: str
    prompt_version: str


class AIProviderError(Exception):
    """Falha ao obter a análise do provedor de IA."""

    retryable = False


class AITimeoutError(AIProviderError):
    retryable = True


class AIUnavailableError(AIProviderError):
    """Provedor fora do ar, sem cota (429) ou não configurado."""

    retryable = False


class AITransientError(AIUnavailableError):
    """Falha momentânea (rede, 5xx): vale tentar de novo."""

    retryable = True


class AIInvalidResponseError(AIProviderError):
    """Resposta vazia, não-JSON ou que não respeita o contrato."""

    retryable = True


class AIProvider(Protocol):
    def analyze(self, texto: str) -> AIResult: ...
