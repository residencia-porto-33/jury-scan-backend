import logging
import time

import httpx
from google import genai
from google.genai import errors, types
from pydantic import ValidationError

from app.core.config import Settings
from app.schemas.ai_contract import AIOutput
from app.services.ai.base import (
    AIInvalidResponseError,
    AIProviderError,
    AIResult,
    AITimeoutError,
    AITransientError,
    AIUnavailableError,
)
from app.services.ai.prompts import PROMPT_VERSION, SYSTEM_PROMPT, build_user_prompt

logger = logging.getLogger("juryscan.ai")


class GeminiProvider:
    def __init__(self, settings: Settings) -> None:
        self._model = settings.gemini_model
        self._max_retries = max(0, settings.ai_max_retries)
        self._client = genai.Client(
            api_key=settings.gemini_api_key,
            http_options=types.HttpOptions(timeout=int(settings.ai_timeout_seconds * 1000)),
        )

    def analyze(self, texto: str) -> AIResult:
        attempt = 0
        while True:
            try:
                return self._call_once(texto)
            except AIProviderError as exc:
                if not exc.retryable or attempt >= self._max_retries:
                    raise
                attempt += 1
                logger.warning("ai_retry attempt=%d reason=%s", attempt, type(exc).__name__)
                time.sleep(min(2**attempt, 5))

    def _call_once(self, texto: str) -> AIResult:
        try:
            response = self._client.models.generate_content(
                model=self._model,
                contents=build_user_prompt(texto),
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT,
                    response_mime_type="application/json",
                    response_schema=AIOutput,
                    temperature=0.1,
                ),
            )
        except httpx.TimeoutException as exc:
            raise AITimeoutError("timeout") from exc
        except httpx.TransportError as exc:
            raise AITransientError("transporte") from exc
        except errors.APIError as exc:
            raise _classify_api_error(exc) from exc

        raw = getattr(response, "text", None)
        if not raw:
            raise AIInvalidResponseError("resposta vazia")
        try:
            output = AIOutput.model_validate_json(raw)
        except ValidationError as exc:
            # Não registra o conteúdo: pode conter trechos do CNIS.
            raise AIInvalidResponseError("fora do contrato") from exc
        return AIResult(output=output, modelo_versao=self._model, prompt_version=PROMPT_VERSION)


def _classify_api_error(exc: errors.APIError) -> AIProviderError:
    code = getattr(exc, "code", None)
    logger.error("ai_api_error code=%s", code)  # só o código HTTP, nunca a mensagem
    if code == 429:
        return AIUnavailableError("limite de uso do provedor")
    if code in (408, 504):
        return AITimeoutError("timeout no provedor")
    if isinstance(code, int) and code >= 500:
        return AITransientError("provedor indisponível")
    return AIProviderError("requisição recusada pelo provedor")
