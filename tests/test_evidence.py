from app.services.evidence import evidence_in_text, normalize
from app.services.severity import count_by_severity

SOURCE = normalize("Seq. 1  Empregador: EMPRESA EXEMPLO LTDA\nData Início: 01/02/2015  Data Fim: (vazio)")


def test_normalize_collapses_spaces_and_accents():
    assert normalize("Vínculo   SEM\nData") == "vinculo sem data"


def test_evidence_matches_ignoring_case_accent_and_whitespace():
    assert evidence_in_text("data inicio: 01/02/2015", SOURCE)
    assert evidence_in_text("EMPRESA   exemplo\nltda", SOURCE)


def test_evidence_with_ellipsis_checks_each_fragment():
    assert evidence_in_text("Empregador: EMPRESA ... Data Fim: (vazio)", SOURCE)
    assert not evidence_in_text("Empregador: EMPRESA ... Data Fim: 31/12/2020", SOURCE)


def test_invented_or_empty_evidence_is_rejected():
    assert not evidence_in_text("Salário de R$ 9.999,00", SOURCE)
    assert not evidence_in_text("", SOURCE)
    assert not evidence_in_text("   ...   ", SOURCE)
    assert not evidence_in_text("ab", SOURCE)


def test_quotes_around_evidence_are_ignored():
    assert evidence_in_text("“Data Fim: (vazio)”", SOURCE)


def test_count_by_severity_always_has_four_keys():
    assert count_by_severity([]) == {"alta": 0, "media": 0, "baixa": 0, "info": 0}
    assert count_by_severity(["alta", "alta", "info"]) == {"alta": 2, "media": 0, "baixa": 0, "info": 1}
