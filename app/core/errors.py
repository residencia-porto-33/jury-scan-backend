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
        erros = [
            {
                "campo": ".".join(str(p) for p in err.get("loc", ()) if p != "body"),
                "motivo": str(err.get("msg", "valor inválido")).removeprefix("Value error, "),
            }
            for err in exc.errors()
        ]
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
