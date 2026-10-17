import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.schemas import api as schemas
from app.services.severity import count_by_severity


class AnalysisRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create_request(self, origem: str, texto_input: str | None) -> models.AnalysisRequest:
        """Registra a requisição (status 'processando') antes de chamar a IA."""
        request = models.AnalysisRequest(origem=origem, status="processando", texto_input=texto_input)
        self.db.add(request)
        self.db.commit()
        return request

    def mark_error(self, request_id: uuid.UUID, codigo: str) -> None:
        self.db.rollback()
        request = self.db.get(models.AnalysisRequest, request_id)
        if request is not None:
            request.status = "erro"
            request.erro_codigo = codigo
            self.db.commit()

    def save_result(self, result: schemas.AnalysisResult) -> None:
        """Grava resposta, resumo e achados numa única transação (tudo ou nada)."""
        request = self.db.get(models.AnalysisRequest, result.analysis_request_id)
        if request is None:
            raise LookupError("requisição inexistente")

        resumo = result.document_summary
        response = models.AnalysisResponse(
            analysis_request_id=result.analysis_request_id,
            risco_agregado=result.risco_agregado,
            prompt_version=result.prompt_version,
            modelo_versao=result.modelo_versao,
            acoes_prioritarias=list(result.acoes_prioritarias),
            documento_parece_cnis=result.documento_parece_cnis,
            achados_descartados=result.achados_descartados,
        )
        response.summary = models.DocumentSummary(
            cpf=resumo.cpf,
            nit_pis_pasep=resumo.nit_pis_pasep,
            periodo=resumo.periodo,
            vinculos=list(resumo.vinculos),
            contexto_beneficio=resumo.contexto_beneficio,
        )
        response.issues = [
            models.Issue(
                ordem=ordem,
                identificador_exibicao=issue.identificador_exibicao,
                categoria=issue.categoria,
                severidade=issue.severidade,
                descricao=issue.descricao,
                evidencia=issue.evidencia,
                sugestao=issue.sugestao,
                impacto=issue.impacto,
                confianca=issue.confianca,
            )
            for ordem, issue in enumerate(result.issues)
        ]
        self.db.add(response)
        request.status = "concluido"
        self.db.commit()

    def get_request(self, request_id: uuid.UUID) -> models.AnalysisRequest | None:
        return self.db.get(models.AnalysisRequest, request_id)

    def load_result(self, request_id: uuid.UUID) -> schemas.AnalysisResult | None:
        response = self.db.scalars(
            select(models.AnalysisResponse).where(models.AnalysisResponse.analysis_request_id == request_id)
        ).first()
        if response is None or response.summary is None:
            return None

        issues = [
            schemas.Issue(
                identificador_exibicao=i.identificador_exibicao,
                severidade=i.severidade,
                categoria=i.categoria,
                descricao=i.descricao,
                evidencia=i.evidencia,
                sugestao=i.sugestao,
                impacto=i.impacto,
                confianca=i.confianca,
            )
            for i in sorted(response.issues, key=lambda item: item.ordem)
        ]
        resumo = response.summary
        return schemas.AnalysisResult(
            analysis_request_id=request_id,
            documento_parece_cnis=response.documento_parece_cnis,
            document_summary=schemas.DocumentSummary(
                cpf=resumo.cpf,
                nit_pis_pasep=resumo.nit_pis_pasep,
                periodo=resumo.periodo,
                vinculos=list(resumo.vinculos),
                contexto_beneficio=resumo.contexto_beneficio,
            ),
            risco_agregado=response.risco_agregado,
            acoes_prioritarias=list(response.acoes_prioritarias),
            issues=issues,
            # Totais sempre derivados da lista de achados (nunca armazenados).
            severity_totals=schemas.SeverityTotals(**count_by_severity(i.severidade for i in issues)),
            achados_descartados=response.achados_descartados,
            prompt_version=response.prompt_version,
            modelo_versao=response.modelo_versao,
        )
