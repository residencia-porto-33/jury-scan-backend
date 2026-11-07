"""Pós-processamento determinístico da resposta da IA.

A IA sugere achados e *extrai* vínculos/benefícios; o backend garante as regras do PRD:
evidência real, datas conferidas, coincidência de períodos calculada em Python, ordenação
por severidade, identificadores sequenciais, risco e ações derivados dos achados validados
e totais recalculados.
"""
import uuid

from app.schemas.ai_contract import AIOutput
from app.schemas.api import AnalysisResult, DocumentSummary, Issue, SeverityTotals
from app.schemas.common import NAO_IDENTIFICADO
from app.services import rules
from app.services.evidence import evidence_in_text, normalize, shorten
from app.services.rules import Finding, Periodo
from app.services.severity import SEVERITY_ORDER, count_by_severity, risco_from_severities

CATEGORIA_PENDENCIA_DOCUMENTAL = "pendencia_documental"
# Confiança fixa da classificação "não parece CNIS" (a IA não informa um valor para ela).
NAO_CNIS_CONFIANCA = 0.8
MAX_ACOES = 5


def _pendencia_documental(
    texto: str, request_id: uuid.UUID, prompt_version: str, modelo_versao: str, descartados: int
) -> AnalysisResult:
    issue = Issue(
        identificador_exibicao="CNIS-001",
        severidade="media",
        categoria=CATEGORIA_PENDENCIA_DOCUMENTAL,
        descricao="O conteúdo enviado não parece ser um extrato do CNIS.",
        evidencia=shorten(texto, 200),
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


def _to_periodo(
    rotulo: str, inicio_txt: str, fim_txt: str, trecho: str, normalized_source: str
) -> Periodo | None:
    """Converte um item extraído pela IA em período, só se o trecho e as datas existem no texto."""
    if not evidence_in_text(trecho, normalized_source):
        return None
    inicio = rules.parse_br_date(inicio_txt)
    if inicio is None or normalize(inicio_txt) not in normalized_source:
        return None
    fim = None
    if fim_txt.strip():
        fim = rules.parse_br_date(fim_txt, end=True)
        if fim is not None:
            # Data inventada ou fim anterior ao início: descarta o item inteiro.
            if normalize(fim_txt) not in normalized_source or fim < inicio:
                return None
        # Texto que não é data (ex.: "em aberto") conta como sem data de fim.
    return Periodo(rotulo.strip() or NAO_IDENTIFICADO, inicio, fim, shorten(trecho, 160))


def _instruction_finding(texto: str) -> Finding | None:
    sentences = rules.find_embedded_instructions(texto)
    if not sentences:
        return None
    return Finding(
        severidade="media",
        categoria="outros",
        descricao=(
            "O documento contém um trecho que parece uma instrução dirigida a sistemas automatizados, "
            "o que não é esperado em um extrato do CNIS."
        ),
        evidencia=" … ".join(sentences),
        sugestao="Verifique a origem do documento e desconsidere o trecho. A análise não seguiu essa instrução.",
        impacto="Conteúdo estranho a um extrato do CNIS pode indicar adulteração do arquivo.",
        confianca=0.7,
    )


def _acoes(issues: list[Issue]) -> list[str]:
    if not issues:
        return ["Nenhuma providência prioritária identificada. Mantenha a conferência humana do documento."]
    prioritarios = [i for i in issues if i.severidade in ("alta", "media")] or issues
    return [f"{i.identificador_exibicao}: {i.sugestao}" for i in prioritarios[:MAX_ACOES]]


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

    # 1) Achados da IA, só com evidência localizável no texto.
    findings: list[Finding] = []
    descartados = 0
    for achado in output.achados:
        if evidence_in_text(achado.evidencia, normalized_source):
            findings.append(
                Finding(
                    achado.severidade, achado.categoria, achado.descricao,
                    achado.evidencia, achado.sugestao, achado.impacto, achado.confianca,
                )
            )
        else:
            descartados += 1

    # 2) Regras determinísticas sobre vínculos e benefícios extraídos (datas conferidas no texto).
    vinculos = [
        p
        for v in output.vinculos_extraidos
        if (p := _to_periodo(v.empregador, v.data_inicio, v.data_fim, v.trecho, normalized_source))
    ]
    beneficios = [
        p
        for b in output.beneficios_extraidos
        if (p := _to_periodo(b.especie, b.dib, b.dcb, b.trecho, normalized_source))
    ]
    findings += rules.find_overlapping_vinculos(vinculos)
    findings += rules.find_benefit_vinculo_conflicts(beneficios, vinculos)

    # 3) Instruções embutidas no documento (possível adulteração).
    instruction = _instruction_finding(texto)
    if instruction:
        findings.append(instruction)

    # Mais grave primeiro; a confiança desempata. O sort do Python é estável.
    findings.sort(key=lambda f: (SEVERITY_ORDER[f.severidade], -f.confianca))
    issues = [
        Issue(
            identificador_exibicao=f"CNIS-{n:03d}",
            severidade=f.severidade,
            categoria=f.categoria,
            descricao=f.descricao,
            evidencia=f.evidencia,
            sugestao=f.sugestao,
            impacto=f.impacto,
            confianca=f.confianca,
        )
        for n, f in enumerate(findings, start=1)
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
        risco_agregado=risco_from_severities(i.severidade for i in issues),
        acoes_prioritarias=_acoes(issues),
        issues=issues,
        severity_totals=SeverityTotals(**count_by_severity(i.severidade for i in issues)),
        achados_descartados=descartados,
        prompt_version=prompt_version,
        modelo_versao=modelo_versao,
    )
