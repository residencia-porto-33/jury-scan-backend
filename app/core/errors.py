import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

logger = logging.getLogger("juryscan")


class AppError(Exception):
    """Erro controlado: vira uma resposta HTTP com mensagem segura."""

    def __init__(
        self,
        status_code: int,
        code: str,
        detail: str,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.code = code
        self.detail = detail
        self.headers = headers


_MOTIVOS = {
    "missing": "Campo obrigatório.",
    "string_type": "Deve ser um texto.",
    "json_invalid": "O corpo da requisição não é um JSON válido.",
    "model_attributes_type": "O corpo da requisição deve ser um objeto JSON.",
    "uuid_parsing": "Identificador inválido (esperado um UUID).",
}


def _motivo(err: dict) -> str:
    tipo = str(err.get("type", ""))
    if tipo in ("literal_error", "enum"):
        esperado = str((err.get("ctx") or {}).get("expected", "")).replace(" or ", " ou ")
        return f"Valor inválido. Valores aceitos: {esperado}." if esperado else "Valor inválido."
    if tipo in _MOTIVOS:
        return _MOTIVOS[tipo]
    return str(err.get("msg", "valor inválido")).removeprefix("Value error, ")


def _campo(err: dict) -> str:
    if err.get("type") in ("json_invalid", "model_attributes_type"):
        return "corpo"
    return ".".join(str(p) for p in err.get("loc", ()) if p != "body")


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def handle_app_error(_: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail, "code": exc.code},
            headers=exc.headers,
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        # Nunca devolve o "input" do erro: ele conteria o texto do CNIS (dados pessoais).
        erros = [{"campo": _campo(err), "motivo": _motivo(err)} for err in exc.errors()]
        return JSONResponse(
            status_code=400,
            content={
                "detail": "A entrada é inválida. Revise os campos informados.",
                "code": "entrada_invalida",
                "erros": erros,
            },
        )

    @app.exception_handler(Exception)
    async def handle_unexpected(_: Request, exc: Exception) -> JSONResponse:
        logger.error("unhandled_error type=%s", type(exc).__name__)
        return JSONResponse(
            status_code=500,
            content={
                "detail": "Erro interno. Tente novamente em instantes.",
                "code": "erro_interno",
            },
        )
