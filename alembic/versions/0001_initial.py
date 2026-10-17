"""tabelas iniciais: requisições, respostas, resumos e achados

Revision ID: 0001
Revises:
Create Date: 2026-10-17
"""
import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "analysis_requests",
        sa.Column("analysis_request_id", sa.Uuid(), primary_key=True),
        sa.Column("origem", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("data_criacao", sa.DateTime(timezone=True), nullable=False),
        sa.Column("texto_input", sa.Text(), nullable=True),
        sa.Column("usuario_id", sa.Uuid(), nullable=True),
        sa.Column("erro_codigo", sa.String(50), nullable=True),
    )
    op.create_table(
        "analysis_responses",
        sa.Column("analysis_response_id", sa.Uuid(), primary_key=True),
        sa.Column(
            "analysis_request_id",
            sa.Uuid(),
            sa.ForeignKey("analysis_requests.analysis_request_id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("risco_agregado", sa.String(10), nullable=False),
        sa.Column("prompt_version", sa.String(20), nullable=False),
        sa.Column("modelo_versao", sa.String(100), nullable=False),
        sa.Column("acoes_prioritarias", sa.JSON(), nullable=False),
        sa.Column("documento_parece_cnis", sa.Boolean(), nullable=False),
        sa.Column("achados_descartados", sa.Integer(), nullable=False),
        sa.Column("data_criacao", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "document_summaries",
        sa.Column("document_summary_id", sa.Uuid(), primary_key=True),
        sa.Column(
            "analysis_response_id",
            sa.Uuid(),
            sa.ForeignKey("analysis_responses.analysis_response_id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("cpf", sa.Text(), nullable=False),
        sa.Column("nit_pis_pasep", sa.Text(), nullable=False),
        sa.Column("periodo", sa.Text(), nullable=False),
        sa.Column("vinculos", sa.JSON(), nullable=False),
        sa.Column("contexto_beneficio", sa.Text(), nullable=False),
    )
    op.create_table(
        "issues",
        sa.Column("issue_id", sa.Uuid(), primary_key=True),
        sa.Column(
            "analysis_response_id",
            sa.Uuid(),
            sa.ForeignKey("analysis_responses.analysis_response_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("ordem", sa.Integer(), nullable=False),
        sa.Column("identificador_exibicao", sa.String(20), nullable=False),
        sa.Column("categoria", sa.Text(), nullable=False),
        sa.Column("severidade", sa.String(10), nullable=False),
        sa.Column("descricao", sa.Text(), nullable=False),
        sa.Column("evidencia", sa.Text(), nullable=False),
        sa.Column("sugestao", sa.Text(), nullable=False),
        sa.Column("impacto", sa.Text(), nullable=False),
        sa.Column("confianca", sa.Float(), nullable=False),
    )
    op.create_index("ix_issues_analysis_response_id", "issues", ["analysis_response_id"])


def downgrade() -> None:
    op.drop_index("ix_issues_analysis_response_id", table_name="issues")
    op.drop_table("issues")
    op.drop_table("document_summaries")
    op.drop_table("analysis_responses")
    op.drop_table("analysis_requests")
