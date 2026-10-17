import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class AnalysisRequest(Base):
    __tablename__ = "analysis_requests"

    analysis_request_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    origem: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20), default="processando")
    data_criacao: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    # Só é preenchido se STORE_INPUT_TEXT=true (o texto contém dados pessoais).
    texto_input: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # Reservado para a v2 (autenticação). Sem FK até a tabela de usuários existir.
    usuario_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid, nullable=True)
    erro_codigo: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    response: Mapped[Optional["AnalysisResponse"]] = relationship(
        back_populates="request", uselist=False, cascade="all, delete-orphan"
    )


class AnalysisResponse(Base):
    __tablename__ = "analysis_responses"

    analysis_response_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    analysis_request_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("analysis_requests.analysis_request_id", ondelete="CASCADE"),
        unique=True,
    )
    risco_agregado: Mapped[str] = mapped_column(String(10))
    prompt_version: Mapped[str] = mapped_column(String(20))
    modelo_versao: Mapped[str] = mapped_column(String(100))
    acoes_prioritarias: Mapped[list] = mapped_column(JSON)
    documento_parece_cnis: Mapped[bool] = mapped_column(Boolean, default=True)
    achados_descartados: Mapped[int] = mapped_column(Integer, default=0)
    data_criacao: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    request: Mapped["AnalysisRequest"] = relationship(back_populates="response")
    summary: Mapped[Optional["DocumentSummary"]] = relationship(
        back_populates="response", uselist=False, cascade="all, delete-orphan"
    )
    issues: Mapped[list["Issue"]] = relationship(
        back_populates="response", cascade="all, delete-orphan"
    )


class DocumentSummary(Base):
    __tablename__ = "document_summaries"

    document_summary_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    analysis_response_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("analysis_responses.analysis_response_id", ondelete="CASCADE"),
        unique=True,
    )
    cpf: Mapped[str] = mapped_column(Text)
    nit_pis_pasep: Mapped[str] = mapped_column(Text)
    periodo: Mapped[str] = mapped_column(Text)
    vinculos: Mapped[list] = mapped_column(JSON)
    contexto_beneficio: Mapped[str] = mapped_column(Text)

    response: Mapped["AnalysisResponse"] = relationship(back_populates="summary")


class Issue(Base):
    __tablename__ = "issues"

    issue_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    analysis_response_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("analysis_responses.analysis_response_id", ondelete="CASCADE"),
        index=True,
    )
    ordem: Mapped[int] = mapped_column(Integer)
    identificador_exibicao: Mapped[str] = mapped_column(String(20))
    categoria: Mapped[str] = mapped_column(Text)
    severidade: Mapped[str] = mapped_column(String(10))
    descricao: Mapped[str] = mapped_column(Text)
    evidencia: Mapped[str] = mapped_column(Text)
    sugestao: Mapped[str] = mapped_column(Text)
    impacto: Mapped[str] = mapped_column(Text)
    confianca: Mapped[float] = mapped_column(Float)

    response: Mapped["AnalysisResponse"] = relationship(back_populates="issues")
