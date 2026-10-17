from typing import Literal

Severidade = Literal["alta", "media", "baixa", "info"]
RiscoAgregado = Literal["alto", "medio", "baixo"]
Origem = Literal["upload_pdf", "texto_colado"]
StatusAnalise = Literal["processando", "concluido", "erro"]

NAO_IDENTIFICADO = "não identificado"
