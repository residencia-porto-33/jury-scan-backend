"""Checagem de evidência: o trecho citado pela IA precisa existir no texto analisado."""
import re
import unicodedata

_ELLIPSIS = re.compile(r"\.{3,}|…")
_EDGE_CHARS = " \t\r\n\"'“”‘’«»"
MIN_EVIDENCE_CHARS = 4


def normalize(text: str) -> str:
    """Minúsculas, sem acentos e com espaços/quebras de linha colapsados."""
    decomposed = unicodedata.normalize("NFKD", text)
    without_marks = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", without_marks.casefold()).strip()


def evidence_in_text(evidencia: str, normalized_source: str) -> bool:
    """True se a evidência (ou cada fragmento dela, quando há reticências) está no texto.

    `normalized_source` deve vir de `normalize(texto_original)`, calculado uma vez por análise.
    """
    fragments = [f.strip(_EDGE_CHARS) for f in _ELLIPSIS.split(normalize(evidencia))]
    fragments = [f for f in fragments if f]
    if not fragments or sum(len(f) for f in fragments) < MIN_EVIDENCE_CHARS:
        return False
    return all(f in normalized_source for f in fragments)
