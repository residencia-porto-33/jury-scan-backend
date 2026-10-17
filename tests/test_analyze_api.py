import uuid

from app.core.config import Settings, get_settings
from app.main import app
from app.models import AnalysisRequest
from app.services.ai.base import AIInvalidResponseError, AITimeoutError, AIUnavailableError
from tests.helpers import SAMPLE_TEXT, make_issue, make_output


def test_success_orders_by_severity_and_recomputes_totals(client, ai, body):
    ai.output = make_output(
        issues=[
            make_issue(severidade="media", evidencia="Data Fim: (vazio)"),
            make_issue(severidade="alta", evidencia="Remuneração: 0,00", categoria="remuneracao"),
        ]
    )
    response = client.post("/api/analyze", json=body)

    assert response.status_code == 200
    data = response.json()
    assert [i["identificador_exibicao"] for i in data["issues"]] == ["CNIS-001", "CNIS-002"]
    assert [i["severidade"] for i in data["issues"]] == ["alta", "media"]
    assert data["severity_totals"] == {"alta": 1, "media": 1, "baixa": 0, "info": 0}
    assert sum(data["severity_totals"].values()) == len(data["issues"])
    assert data["modelo_versao"] == "fake-model" and data["prompt_version"] == "test"
    assert data["aviso_revisao_humana"]


def test_issue_with_invented_evidence_is_discarded(client, ai, body):
    ai.output = make_output(
        issues=[make_issue(), make_issue(evidencia="Salário de R$ 9.999,00 em 2021")]
    )
    data = client.post("/api/analyze", json=body).json()

    assert len(data["issues"]) == 1
    assert data["achados_descartados"] == 1
    assert data["severity_totals"]["media"] == 1


def test_all_evidence_invalid_gives_low_risk(client, ai, body):
    ai.output = make_output(issues=[make_issue(evidencia="texto que não existe no documento")], risco="alto")
    data = client.post("/api/analyze", json=body).json()

    assert data["issues"] == []
    assert data["risco_agregado"] == "baixo"


def test_non_cnis_document_returns_only_documental_pendency(client, ai, body):
    ai.output = make_output(parece_cnis=False, issues=[make_issue()])
    data = client.post("/api/analyze", json=body).json()

    assert data["documento_parece_cnis"] is False
    assert len(data["issues"]) == 1
    assert data["issues"][0]["categoria"] == "pendencia_documental"
    assert data["document_summary"]["cpf"] == "não identificado"


def test_empty_text_is_rejected_without_echoing_input(client, ai):
    response = client.post("/api/analyze", json={"texto_input": "    ", "origem": "texto_colado"})

    assert response.status_code == 400
    assert response.json()["code"] == "entrada_invalida"
    assert '"input"' not in response.text
    assert ai.calls == 0


def test_too_short_text_and_invalid_origin_are_rejected(client, ai):
    assert client.post("/api/analyze", json={"texto_input": "curto", "origem": "texto_colado"}).status_code == 400
    assert client.post("/api/analyze", json={"texto_input": SAMPLE_TEXT, "origem": "outra"}).status_code == 400
    assert ai.calls == 0


def test_requires_valid_api_key(client, body):
    assert client.post("/api/analyze", json=body, headers={"X-API-Key": "errada"}).status_code == 401
    assert client.post("/api/analyze", json=body, headers={"X-API-Key": ""}).status_code == 401


def test_ai_failures_map_to_safe_http_errors(client, ai, body):
    cases = [
        (AITimeoutError("x"), 504, "ia_timeout"),
        (AIInvalidResponseError("x"), 502, "ia_resposta_invalida"),
        (AIUnavailableError("x"), 503, "ia_indisponivel"),
    ]
    for error, status, code in cases:
        ai.error = error
        response = client.post("/api/analyze", json=body)
        assert response.status_code == status
        assert response.json()["code"] == code
        assert "Traceback" not in response.text


def test_status_endpoint_returns_result_after_completion(client, body):
    created = client.post("/api/analyze", json=body).json()
    status = client.get(f"/api/analyze/{created['analysis_request_id']}")

    assert status.status_code == 200
    payload = status.json()
    assert payload["status"] == "concluido"
    assert payload["resultado"]["issues"] == created["issues"]
    assert payload["resultado"]["severity_totals"] == created["severity_totals"]


def test_failed_request_is_recorded_with_error_status(client, ai, body, session_factory):
    ai.error = AITimeoutError("x")
    client.post("/api/analyze", json=body)

    with session_factory() as db:
        requests = db.query(AnalysisRequest).all()
    assert len(requests) == 1
    assert requests[0].status == "erro" and requests[0].erro_codigo == "ia_timeout"


def test_input_text_is_not_stored_by_default(client, body, session_factory):
    created = client.post("/api/analyze", json=body).json()

    with session_factory() as db:
        row = db.get(AnalysisRequest, uuid.UUID(created["analysis_request_id"]))
    assert row.texto_input is None


def test_unknown_and_malformed_ids(client):
    assert client.get(f"/api/analyze/{uuid.uuid4()}").status_code == 404
    assert client.get("/api/analyze/nao-e-uuid").status_code == 400


def test_rate_limit_returns_429_with_retry_after(client, ai, body):
    app.dependency_overrides[get_settings] = lambda: Settings(api_keys="test-key", rate_limit_per_minute=2)
    try:
        assert client.post("/api/analyze", json=body).status_code == 200
        assert client.post("/api/analyze", json=body).status_code == 200
        blocked = client.post("/api/analyze", json=body)
    finally:
        app.dependency_overrides.pop(get_settings, None)

    assert blocked.status_code == 429
    assert int(blocked.headers["Retry-After"]) >= 1


def test_health_is_public(client):
    assert client.get("/health", headers={"X-API-Key": ""}).json() == {"status": "ok"}
