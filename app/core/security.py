import hashlib
import secrets

from fastapi import Depends, Request, Security
from fastapi.security import APIKeyHeader

from app.core.config import Settings, get_settings
from app.core.errors import AppError
from app.core.rate_limit import get_limiter

api_key_header = APIKeyHeader(
    name="X-API-Key",
    auto_error=False,
    description="Chave de acesso à API.",
)

ANONYMOUS_DEV = "anonymous-dev"


def require_api_key(
    api_key: str | None = Security(api_key_header),
    settings: Settings = Depends(get_settings),
) -> str:
    """Valida a X-API-Key e devolve um identificador do cliente (hash, nunca a chave)."""
    keys = settings.api_key_list
    if not keys:
        if settings.is_production:
            raise AppError(500, "erro_interno", "Erro interno. Tente novamente em instantes.")
        return ANONYMOUS_DEV  # desenvolvimento sem chaves configuradas

    provided = (api_key or "").encode()
    if not provided or not any(secrets.compare_digest(provided, k.encode()) for k in keys):
        raise AppError(
            401,
            "nao_autorizado",
            "Credenciais ausentes ou inválidas.",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    return hashlib.sha256(provided).hexdigest()[:16]


def enforce_rate_limit(
    request: Request,
    client_id: str = Depends(require_api_key),
    settings: Settings = Depends(get_settings),
) -> None:
    key = client_id
    if client_id == ANONYMOUS_DEV:
        key = request.client.host if request.client else "unknown"
    retry_after = get_limiter().hit(key, settings.rate_limit_per_minute)
    if retry_after is not None:
        raise AppError(
            429,
            "limite_de_requisicoes",
            "Muitas requisições. Aguarde um instante e tente novamente.",
            headers={"Retry-After": str(retry_after)},
        )
