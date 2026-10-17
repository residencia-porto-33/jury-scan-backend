"""Contrato do que a IA deve devolver.

Estes modelos são enviados ao Gemini como `response_schema`, por isso:
- não usam valores default (o Gemini rejeita `default` no schema);
- as regras finas (faixa de confiança, campos em branco) ficam em validators,
  que não entram no schema enviado, mas valem na validação da resposta.
"""
import math

from pydantic import BaseModel, field_validator

from app.schemas.common import NAO_IDENTIFICADO, RiscoAgregado, Severidade


class AIDocumentSummary(BaseModel):
    cpf: str
    nit_pis_pasep: str
    periodo: str
    vinculos: list[str]
    contexto_beneficio: str

    @field_validator("cpf", "nit_pis_pasep", "periodo", "contexto_beneficio")
    @classmethod
    def blank_means_not_identified(cls, v: str) -> str:
        v = v.strip()
        return v or NAO_IDENTIFICADO

    @field_validator("vinculos")
    @classmethod
    def clean_vinculos(cls, v: list[str]) -> list[str]:
        return [item.strip() for item in v if item.strip()]


class AIIssue(BaseModel):
    categoria: str
    severidade: Severidade
    descricao: str
    evidencia: str
    sugestao: str
    impacto: str
    confianca: float

    @field_validator("categoria", "descricao", "sugestao", "impacto")
    @classmethod
    def required_text(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("campo obrigatório vazio")
        return v

    @field_validator("evidencia")
    @classmethod
    def strip_evidence(cls, v: str) -> str:
        # Evidência vazia não invalida a resposta inteira: o achado é descartado
        # depois, na checagem de evidência contra o texto original.
        return v.strip()

    @field_validator("confianca")
    @classmethod
    def confidence_range(cls, v: float) -> float:
        if not math.isfinite(v) or not 0.0 <= v <= 1.0:
            raise ValueError("confianca deve estar entre 0 e 1")
        return v


class AIOutput(BaseModel):
    documento_parece_cnis: bool
    resumo_documental: AIDocumentSummary
    risco_agregado: RiscoAgregado
    acoes_prioritarias: list[str]
    achados: list[AIIssue]
