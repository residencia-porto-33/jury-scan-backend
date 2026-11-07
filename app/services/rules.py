"""Regras determinísticas (sem IA) sobre períodos e sobre instruções embutidas no texto.

A IA apenas *extrai* vínculos e benefícios; o cálculo de sobreposição é feito aqui,
com datas conferidas contra o texto original. Este módulo só usa a biblioteca padrão.
"""
import calendar
import re
from dataclasses import dataclass
from datetime import date

from app.services.evidence import normalize, shorten

MAX_FINDINGS_PER_RULE = 10


@dataclass(frozen=True)
class Periodo:
    rotulo: str  # empregador (vínculo) ou espécie (benefício)
    inicio: date | None
    fim: date | None  # None = sem data de fim
    trecho: str  # trecho literal do documento


@dataclass(frozen=True)
class Finding:
    severidade: str
    categoria: str
    descricao: str
    evidencia: str
    sugestao: str
    impacto: str
    confianca: float


_DATE_RE = re.compile(r"^\s*(?:(\d{1,2})/)?(\d{1,2})/(\d{4})\s*$")


def parse_br_date(value: str, end: bool = False) -> date | None:
    """Aceita dd/mm/aaaa ou mm/aaaa. Em mm/aaaa, usa o 1º dia (início) ou o último (fim)."""
    match = _DATE_RE.match(value or "")
    if not match:
        return None
    day_txt, month_txt, year_txt = match.groups()
    month, year = int(month_txt), int(year_txt)
    if not 1 <= month <= 12 or year < 1900:
        return None
    if day_txt is None:
        day = calendar.monthrange(year, month)[1] if end else 1
    else:
        day = int(day_txt)
    try:
        return date(year, month, day)
    except ValueError:
        return None


def format_date(value: date) -> str:
    return value.strftime("%d/%m/%Y")


def _overlap(a: Periodo, b: Periodo) -> tuple[date, date | None, bool] | None:
    """(início da sobreposição, fim ou None se ambos abertos, algum aberto?) ou None."""
    if a.inicio is None or b.inicio is None:
        return None
    start = max(a.inicio, b.inicio)
    end = min(a.fim or date.max, b.fim or date.max)
    if start > end:
        return None
    return start, (None if end == date.max else end), (a.fim is None or b.fim is None)


def find_overlapping_vinculos(vinculos: list[Periodo]) -> list[Finding]:
    unique = {(v.rotulo, v.inicio, v.fim): v for v in vinculos if v.inicio is not None}
    ordered = sorted(unique.values(), key=lambda v: v.inicio)  # type: ignore[arg-type, return-value]

    findings: list[Finding] = []
    total = 0
    for i, a in enumerate(ordered):
        for b in ordered[i + 1 :]:
            overlap = _overlap(a, b)
            if overlap is None:
                continue
            total += 1
            if len(findings) < MAX_FINDINGS_PER_RULE:
                findings.append(_overlap_finding(a, b, overlap))

    if total > len(findings):
        findings.append(
            Finding(
                severidade="info",
                categoria="vinculo",
                descricao=f"Há outros {total - len(findings)} períodos concomitantes entre vínculos além dos listados.",
                evidencia=findings[0].evidencia,
                sugestao="Revise a lista completa de vínculos do documento.",
                impacto="A quantidade de concomitâncias pode exigir conferência detalhada.",
                confianca=0.9,
            )
        )
    return findings


def _overlap_finding(a: Periodo, b: Periodo, overlap: tuple[date, date | None, bool]) -> Finding:
    start, end, open_ended = overlap
    evidencia = f"{a.trecho} … {b.trecho}"
    if open_ended:
        return Finding(
            severidade="media",
            categoria="vinculo",
            descricao=(
                f"Os vínculos com {a.rotulo} e {b.rotulo} coincidem a partir de {format_date(start)}, "
                "e ao menos um deles está sem data de fim."
            ),
            evidencia=evidencia,
            sugestao=(
                "Comprovar a data de encerramento do vínculo em aberto (CTPS, TRCT ou documentos do "
                "empregador) e conferir se houve atividade simultânea."
            ),
            impacto="Sem a data de fim, não é possível saber se os períodos realmente se sobrepõem.",
            confianca=0.75,
        )
    return Finding(
        severidade="baixa",
        categoria="vinculo",
        descricao=(
            f"Os vínculos com {a.rotulo} e {b.rotulo} têm períodos concomitantes, "
            f"de {format_date(start)} a {format_date(end)}."  # type: ignore[arg-type]
        ),
        evidencia=evidencia,
        sugestao=(
            "Conferir se são atividades simultâneas legítimas e se as remunerações de cada vínculo "
            "estão registradas corretamente."
        ),
        impacto=(
            "Períodos concomitantes podem exigir conferência de como as remunerações são consideradas "
            "na análise; a conclusão depende de profissional habilitado."
        ),
        confianca=0.9,
    )


_INCAPACITY_MARKERS = ("incapacidade", "doenca")


def is_incapacity_benefit(especie: str) -> bool:
    normalized = normalize(especie)
    return any(marker in normalized for marker in _INCAPACITY_MARKERS)


def find_benefit_vinculo_conflicts(beneficios: list[Periodo], vinculos: list[Periodo]) -> list[Finding]:
    findings: list[Finding] = []
    for beneficio in beneficios:
        if beneficio.inicio is None or not is_incapacity_benefit(beneficio.rotulo):
            continue
        fim_txt = format_date(beneficio.fim) if beneficio.fim else "sem data de cessação"
        for vinculo in vinculos:
            if _overlap(beneficio, vinculo) is None:
                continue
            findings.append(
                Finding(
                    severidade="media",
                    categoria="beneficio",
                    descricao=(
                        f'O benefício "{beneficio.rotulo}" ({format_date(beneficio.inicio)} a {fim_txt}) '
                        f"coincide com o vínculo com {vinculo.rotulo}."
                    ),
                    evidencia=f"{beneficio.trecho} … {vinculo.trecho}",
                    sugestao=(
                        "Conferir se houve remuneração ou atividade durante o período do benefício "
                        "(holerites, GFIP/eSocial) e a situação do vínculo no período."
                    ),
                    impacto=(
                        "Atividade remunerada durante benefício por incapacidade costuma exigir "
                        "esclarecimento; a conclusão depende de profissional habilitado."
                    ),
                    confianca=0.8,
                )
            )
            if len(findings) >= MAX_FINDINGS_PER_RULE:
                return findings
    return findings


_INJECTION_PATTERNS = [
    re.compile(r"\b(ignore|ignorar|desconsidere|desconsiderar|esqueca|esquecer)\b.{0,40}\b(instruco\w*|regras|orientaco\w*|comandos?)\b"),
    re.compile(r"\b(ignore|disregard|forget)\b.{0,40}\b(instructions?|prompts?|rules)\b"),
    re.compile(r"\b(responda|diga|afirme|escreva|conclua)\s+que\b"),
    re.compile(r"\b(prompt do sistema|system prompt)\b"),
    re.compile(r"\bclassifique\b.{0,20}\brisco\b"),
    re.compile(r"\bnao liste\b"),
]
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+|\n+")


def find_embedded_instructions(texto: str, limit: int = 3) -> list[str]:
    """Frases do documento que parecem ordens dirigidas a um sistema automatizado."""
    found: list[str] = []
    for sentence in _SENTENCE_SPLIT.split(texto):
        sentence = sentence.strip()
        if not sentence:
            continue
        normalized = normalize(sentence)
        if any(pattern.search(normalized) for pattern in _INJECTION_PATTERNS):
            found.append(shorten(sentence, 150))
            if len(found) >= limit:
                break
    return found
