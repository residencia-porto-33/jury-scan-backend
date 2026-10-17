"""Schemas públicos da API (entrada e saída)."""
import uuid

from pydantic import BaseModel, Field, field_validator, model_validator

from app.core.config import get_settings
from app.schemas.common import Origem, RiscoAgregado, Severidade, StatusAnalise

AVISO_REVISAO_HUMANA = (
    "Ferramenta de apoio à triagem. O resultado não substitui a análise de "
    "profissional habilitado nem constitui parecer jurídico; confira as "
    "evidências antes de qualquer decisão."
)


class AnalysisRequestBody(BaseModel):
    texto_input: str = Field(description="Texto do CNIS extraído (localmente) ou colado pelo usuário.")
    origem: Origem = Field(description="Como o texto foi obtido.")

    @field_validator("texto_input")
    @classmethod
    def validar_texto(cls, v: str) -> str:
        settings = get_settings()
        texto = v.strip()
        if not texto:
            raise ValueError("O texto do CNIS não pode estar vazio.")
        if len(texto) < settings.min_text_chars:
            raise ValueError(
                f"O texto é curto demais para análise (mínimo de {settings.min_text_chars} caracteres)."
            )
        if len(v) > settings.max_text_chars:
            raise ValueError(f"O texto excede o limite de {settings.max_text_chars} caracteres.")
        return v


class DocumentSummary(BaseModel):
    cpf: str
    nit_pis_pasep: str
    periodo: str
    vinculos: list[str]
    contexto_beneficio: str


class Issue(BaseModel):
    identificador_exibicao: str = Field(examples=["CNIS-001"])
    severidade: Severidade
    categoria: str
    descricao: str
    evidencia: str = Field(description="Trecho do texto original que sustenta o achado.")
    sugestao: str
    impacto: str
    confianca: float = Field(
        ge=0, le=1, description="Confiança do modelo (0 a 1). Não representa certeza jurídica."
    )


class SeverityTotals(BaseModel):
    alta: int
    media: int
    baixa: int
    info: int


class AnalysisResult(BaseModel):
    analysis_request_id: uuid.UUID
    status: StatusAnalise = "concluido"
    documento_parece_cnis: bool
    document_summary: DocumentSummary
    risco_agregado: RiscoAgregado
    acoes_prioritarias: list[str]
    issues: list[Issue]
    severity_totals: SeverityTotals
    achados_descartados: int = Field(
        description="Achados da IA descartados por não terem evidência localizável no texto."
    )
    prompt_version: str
    modelo_versao: str
    aviso_revisao_humana: str = AVISO_REVISAO_HUMANA

    @model_validator(mode="after")
    def totais_consistentes(self) -> "AnalysisResult":
        if sum(self.severity_totals.model_dump().values()) != len(self.issues):
            raise ValueError("A soma dos totais por severidade difere do total de achados.")
        return self


class AnalysisStatus(BaseModel):
    analysis_request_id: uuid.UUID
    status: StatusAnalise
    resultado: AnalysisResult | None = Field(
        default=None, description="Presente apenas quando o status é 'concluido'."
    )


class ErrorDetail(BaseModel):
    campo: str
    motivo: str


class ErrorResponse(BaseModel):
    detail: str = Field(description="Mensagem amigável, sem detalhes internos.")
    code: str | None = None
    erros: list[ErrorDetail] | None = None
