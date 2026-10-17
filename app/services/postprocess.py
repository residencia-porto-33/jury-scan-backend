"""Pós-processamento determinístico da resposta da IA.

A IA sugere; o backend garante as regras do PRD: evidência real, identificadores
sequenciais, ordenação por severidade e totais recalculados dos achados validados.
"""
import re
import uuid

from app.schemas.ai_contract import AIOutput
from app.schemas.api import AnalysisResult, DocumentSummary, Issue, SeverityTotals
from app.schemas.common import NAO_IDENTIFICADO
from app.services.evidence import evidence_in_text, normalize
from app.services.severity import SEVERITY_ORDER, count_by_severity

CATEGORIA_PENDENCIA_DOCUMENTAL = "pendencia_documental"
# Confiança fixa da classificação "não parece CNIS" (a IA não informa um valor para ela).
NAO_CNIS_CONFIANCA = 0.8


def _pendencia_documental(
    texto: str, request_id: uuid.UUID, prompt_version: str, modelo_versao: str, descartados: int
) -> AnalysisResult:
    trecho = re.sub(r"\s+", " ", texto).strip()[:200]
    issue = Issue(
        identificador_exibicao="CNIS-001",
        severidade="media",
        categoria=CATEGORIA_PENDENCIA_DOCUMENTAL,
        descricao="O conteúdo enviado não parece ser um extrato do CNIS.",
        evidencia=trecho,
        sugestao="Envie um extrato CNIS válido (PDF com texto selecionável) ou cole o conteúdo completo do documento.",
        impacto="Sem um CNIS válido não é possível fazer a triagem previdenciária.",
        confianca=NAO_CNIS_CONFIANCA,
    )
    return AnalysisResult(
        analysis_request_id=request_id,
        documento_parece_cnis=False,
        document_summary=DocumentSummary(
            cpf=NAO_IDENTIFICADO,
            nit_pis_pasep=NAO_IDENTIFICADO,
            periodo=NAO_IDENTIFICADO,
            vinculos=[],
            contexto_beneficio=NAO_IDENTIFICADO,
        ),
        risco_agregado="baixo",
        acoes_prioritarias=["Solicitar um extrato CNIS válido antes de prosseguir com a triagem."],
        issues=[issue],
        severity_totals=SeverityTotals(**count_by_severity([issue.severidade])),
        achados_descartados=descartados,
        prompt_version=prompt_version,
        modelo_versao=modelo_versao,
    )


def build_result(
    output: AIOutput,
    texto: str,
    request_id: uuid.UUID,
    prompt_version: str,
    modelo_versao: str,
) -> AnalysisResult:
    if not output.documento_parece_cnis:
        # Sem conclusões previdenciárias: qualquer achado da IA é ignorado.
        return _pendencia_documental(
            texto, request_id, prompt_version, modelo_versao, descartados=len(output.achados)
        )

    normalized_source = normalize(texto)
    valid = [a for a in output.achados if evidence_in_text(a.evidencia, normalized_source)]
    descartados = len(output.achados) - len(valid)

    # Mais grave primeiro; a confiança desempata. O sort do Python é estável.
    valid.sort(key=lambda a: (SEVERITY_ORDER[a.severidade], -a.confianca))

    issues = [
        Issue(
            identificador_exibicao=f"CNIS-{n:03d}",
            severidade=a.severidade,
            categoria=a.categoria,
            descricao=a.descricao,
            evidencia=a.evidencia,
            sugestao=a.sugestao,
            impacto=a.impacto,
            confianca=a.confianca,
        )
        for n, a in enumerate(valid, start=1)
    ]

    resumo = output.resumo_documental
    return AnalysisResult(
        analysis_request_id=request_id,
        documento_parece_cnis=True,
        document_summary=DocumentSummary(
            cpf=resumo.cpf,
            nit_pis_pasep=resumo.nit_pis_pasep,
            periodo=resumo.periodo,
            vinculos=resumo.vinculos,
            contexto_beneficio=resumo.contexto_beneficio,
        ),
        # Se nenhum achado sobreviveu à checagem de evidência, não há risco sustentável.
        risco_agregado=output.risco_agregado if issues else "baixo",
        acoes_prioritarias=[a.strip() for a in output.acoes_prioritarias if a.strip()],
        issues=issues,
        severity_totals=SeverityTotals(**count_by_severity(i.severidade for i in issues)),
        achados_descartados=descartados,
        prompt_version=prompt_version,
        modelo_versao=modelo_versao,
    )
