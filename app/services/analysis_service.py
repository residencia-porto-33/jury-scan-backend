import logging
import uuid

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import AppError
from app.repositories.analysis_repository import AnalysisRepository
from app.schemas.api import AnalysisRequestBody, AnalysisResult, AnalysisStatus
from app.services.ai.base import (
    AIInvalidResponseError,
    AIProvider,
    AIProviderError,
    AITimeoutError,
    AIUnavailableError,
)
from app.services.postprocess import build_result

logger = logging.getLogger("juryscan.analysis")


class AnalysisService:
    def __init__(self, db: Session, ai: AIProvider) -> None:
        self.repo = AnalysisRepository(db)
        self.ai = ai

    def analyze(self, body: AnalysisRequestBody) -> AnalysisResult:
        settings = get_settings()
        request = self.repo.create_request(
            body.origem, body.texto_input if settings.store_input_text else None
        )
        request_id = request.analysis_request_id

        try:
            ai_result = self.ai.analyze(body.texto_input)
        except AITimeoutError:
            self._fail(request_id, "ia_timeout", 504, "A análise demorou mais que o esperado. Tente novamente.")
        except AIInvalidResponseError:
            self._fail(
                request_id, "ia_resposta_invalida", 502,
                "Não foi possível gerar uma análise válida. Tente novamente.",
            )
        except AIUnavailableError:
            self._fail(
                request_id, "ia_indisponivel", 503,
                "O serviço de análise está indisponível no momento. Tente novamente em instantes.",
            )
        except AIProviderError:
            self._fail(request_id, "ia_erro", 502, "Falha ao obter a análise. Tente novamente.")

        try:
            result = build_result(
                ai_result.output,
                body.texto_input,
                request_id,
                ai_result.prompt_version,
                ai_result.modelo_versao,
            )
            self.repo.save_result(result)
        except Exception as exc:
            logger.error("analysis_processing_failed type=%s", type(exc).__name__)
            self._fail(request_id, "erro_processamento", 500, "Erro interno. Tente novamente em instantes.")

        logger.info(
            "analysis_completed id=%s issues=%d discarded=%d",
            request_id, len(result.issues), result.achados_descartados,
        )
        return result

    def get_status(self, analysis_request_id: uuid.UUID) -> AnalysisStatus:
        request = self.repo.get_request(analysis_request_id)
        if request is None:
            raise AppError(404, "nao_encontrado", "Análise não encontrada.")
        resultado = self.repo.load_result(analysis_request_id) if request.status == "concluido" else None
        return AnalysisStatus(
            analysis_request_id=analysis_request_id, status=request.status, resultado=resultado
        )

    def _fail(self, request_id: uuid.UUID, codigo: str, status_code: int, detail: str) -> None:
        self.repo.mark_error(request_id, codigo)
        logger.warning("analysis_failed id=%s code=%s", request_id, codigo)
        raise AppError(status_code, codigo, detail)
