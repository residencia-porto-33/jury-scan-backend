from collections.abc import Iterable

SEVERITY_ORDER: dict[str, int] = {"alta": 0, "media": 1, "baixa": 2, "info": 3}


def count_by_severity(severities: Iterable[str]) -> dict[str, int]:
    """Conta achados por severidade. Sempre devolve as 4 chaves."""
    totals = {key: 0 for key in SEVERITY_ORDER}
    for severity in severities:
        totals[severity] += 1
    return totals
