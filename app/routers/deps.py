from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.services.ai import build_ai_provider
from app.services.ai.base import AIProvider
from app.services.analysis_service import AnalysisService


def get_ai_provider(settings: Settings = Depends(get_settings)) -> AIProvider:
    return build_ai_provider(settings)


def get_analysis_service(
    db: Session = Depends(get_db), ai: AIProvider = Depends(get_ai_provider)
) -> AnalysisService:
    return AnalysisService(db, ai)
