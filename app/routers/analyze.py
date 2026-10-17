import uuid

from fastapi import APIRouter, Depends

from app.core.security import enforce_rate_limit, require_api_key
from app.routers.deps import get_analysis_service
from app.schemas.api import AnalysisRequestBody, AnalysisResult, AnalysisStatus, ErrorResponse
from app.services.analysis_service import AnalysisService

router = APIRouter(prefix="/api", tags=["Analysis"], dependencies=[Depends(require_api_key)])

_ERRORS = {
    400: {"model": ErrorResponse, "description": "Entrada inválida (texto vazio, curto ou grande demais)."},
    401: {"model": ErrorResponse, "description": "X-API-Key ausente ou inválida."},
    429: {"model": ErrorResponse, "description": "Limite de requisições excedido."},
    500: {"model": ErrorResponse, "description": "Erro interno inesperado."},
    502: {"model": ErrorResponse, "description": "A IA não devolveu uma resposta válida."},
    503: {"model": ErrorResponse, "description": "Serviço de IA indisponível ou sem cota."},
    504: {"model": ErrorResponse, "description": "Timeout ao aguardar o serviço de IA."},
}


@router.post(
    "/analyze",
    response_model=AnalysisResult,
    operation_id="analyzeCnis",
    summary="Solicita a análise de um extrato de CNIS",
    description=(
        "Recebe o texto já extraído do CNIS (a extração do PDF é feita no navegador; "
        "o binário nunca chega ao backend) e devolve a análise estruturada, validada "
        "e com evidências conferidas contra o texto enviado."
    ),
    responses=_ERRORS,
    dependencies=[Depends(enforce_rate_limit)],
)
def analyze(
    body: AnalysisRequestBody, service: AnalysisService = Depends(get_analysis_service)
) -> AnalysisResult:
    return service.analyze(body)


@router.get(
    "/analyze/{analysis_request_id}",
    response_model=AnalysisStatus,
    operation_id="getAnalysisStatus",
    summary="Consulta o status (e o resultado) de uma análise",
    responses={404: {"model": ErrorResponse, "description": "Análise não encontrada."}, **_ERRORS},
)
def get_analysis_status(
    analysis_request_id: uuid.UUID, service: AnalysisService = Depends(get_analysis_service)
) -> AnalysisStatus:
    return service.get_status(analysis_request_id)
