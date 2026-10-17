"""Dados e dublês compartilhados pelos testes."""
from app.schemas.ai_contract import AIDocumentSummary, AIIssue, AIOutput
from app.services.ai.base import AIResult

# Texto FICTÍCIO (não é um CNIS real).
SAMPLE_TEXT = """CNIS - Cadastro Nacional de Informações Sociais (documento de teste anonimizado)
NIT: 123.45678.90-1   CPF: 000.000.000-00   Nome: FULANO DE TAL
Seq. 1  Empregador: EMPRESA EXEMPLO LTDA  Data Início: 01/02/2015  Data Fim: (vazio)
Seq. 2  Empregador: OUTRA EMPRESA S/A  Data Início: 05/2019  Data Fim: 12/2020
Competência 03/2018  Remuneração: 0,00  Indicador: PEND-EXEMPLO
"""


def make_issue(**overrides) -> AIIssue:
    data = dict(
        categoria="vinculo",
        severidade="media",
        descricao="Vínculo sem data de fim.",
        evidencia="Data Fim: (vazio)",
        sugestao="Conferir a data de saída com a CTPS.",
        impacto="Pode afetar a contagem de tempo.",
        confianca=0.8,
    )
    data.update(overrides)
    return AIIssue(**data)


def make_output(issues=None, parece_cnis=True, risco="medio") -> AIOutput:
    return AIOutput(
        documento_parece_cnis=parece_cnis,
        resumo_documental=AIDocumentSummary(
            cpf="000.000.000-00",
            nit_pis_pasep="123.45678.90-1",
            periodo="02/2015 a 12/2020",
            vinculos=["EMPRESA EXEMPLO LTDA", "OUTRA EMPRESA S/A"],
            contexto_beneficio="não identificado",
        ),
        risco_agregado=risco,
        acoes_prioritarias=["Conferir o vínculo sem data de fim."],
        achados=issues if issues is not None else [make_issue()],
    )


class FakeAI:
    """Provedor de IA falso: devolve `output` ou levanta `error`."""

    def __init__(self) -> None:
        self.output = make_output()
        self.error: Exception | None = None
        self.calls = 0

    def analyze(self, texto: str) -> AIResult:
        self.calls += 1
        if self.error is not None:
            raise self.error
        return AIResult(output=self.output, modelo_versao="fake-model", prompt_version="test")
