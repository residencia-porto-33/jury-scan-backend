import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.errors import register_exception_handlers
from app.routers import analyze, health

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings = get_settings()
    if settings.is_production and not settings.api_key_list:
        raise RuntimeError("API_KEYS precisa estar configurada em produção.")
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="JuryScan API",
        description=(
            "API de triagem inicial de extratos do CNIS. Ferramenta de apoio: o resultado "
            "não concede ou indefere benefícios, não substitui profissional habilitado e "
            "não deve ser apresentado como parecer jurídico."
        ),
        version="1.0.0",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type", "X-API-Key"],
    )
    register_exception_handlers(app)
    app.include_router(health.router)
    app.include_router(analyze.router)
    return app


app = create_app()
