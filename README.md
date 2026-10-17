# JuryScan — Backend

API em **FastAPI** que recebe o texto de um extrato do **CNIS** (Cadastro Nacional de Informações Sociais), pede uma análise ao **Gemini**, valida a resposta com **Pydantic**, confere as evidências contra o texto original e grava o resultado no **Postgres**.

> **Ferramenta de apoio à triagem.** O resultado não concede ou indefere benefícios, não substitui profissional habilitado e não é parecer jurídico.

## Como funciona

1. O frontend extrai o texto do PDF no navegador (o PDF nunca chega ao backend) ou recebe o texto colado, e envia só o texto para `POST /api/analyze`.
2. A API valida a entrada e registra a requisição no banco.
3. O Gemini devolve uma análise estruturada (JSON), validada contra um contrato Pydantic.
4. O backend descarta achados cuja evidência não existe no texto, ordena por severidade, gera os identificadores `CNIS-001…` e recalcula os totais.
5. O resultado é gravado e devolvido. Se o documento não parece um CNIS, a resposta traz apenas uma pendência documental.

## Pré-requisitos

| O quê | Para quê |
|---|---|
| [Git](https://git-scm.com/downloads) | Clonar o repositório |
| [Docker Desktop](https://www.docker.com/products/docker-desktop/) (já inclui o Compose) | Subir a API e o Postgres |
| Uma chave da API do Gemini ([Google AI Studio](https://aistudio.google.com/apikey)) | Fazer as análises |
| Python 3.12+ *(opcional)* | Rodar os testes automatizados ou a API sem Docker |

## Passo a passo (com Docker)

### 1. Clonar o repositório

```bash
git clone <URL-DO-REPOSITORIO>
cd <PASTA-DO-BACKEND>
```

### 2. Criar o arquivo `.env`

O `.env` guarda as suas chaves e **nunca deve ser versionado** (já está no `.gitignore`).

```powershell
# Windows (PowerShell)
Copy-Item .env.example .env
```
```bash
# Linux / macOS
cp .env.example .env
```

### 3. Preencher o `.env`

Abra o `.env` e ajuste, sem aspas e sem espaços:

- **`GEMINI_API_KEY`**: a chave gerada no Google AI Studio.
- **`API_KEYS`**: uma chave de acesso à *sua* API (qualquer texto, sem vírgulas). Ela vai no cabeçalho `X-API-Key`. Para gerar uma aleatória:
  ```bash
  python -c "import secrets; print(secrets.token_urlsafe(32))"
  ```
- **`GEMINI_MODEL`**: o Google desativa modelos com frequência. Liste os disponíveis para a sua chave e escolha um da família *flash*:
  ```powershell
  (curl.exe -s "https://generativelanguage.googleapis.com/v1beta/models?key=SUA_CHAVE_GEMINI&pageSize=100" | ConvertFrom-Json).models | Where-Object { $_.supportedGenerationMethods -contains "generateContent" -and $_.name -like "*flash*" } | Select-Object -ExpandProperty name
  ```
  Os nomes saem como `models/gemini-...`; no `.env`, use só o que vem depois de `models/`.

### 4. Subir os containers

```bash
docker compose up --build
```

O Docker Desktop precisa estar aberto. Na primeira vez, o build leva alguns minutos. A API cria as tabelas sozinha (migrações Alembic) ao iniciar.

### 5. Conferir

```bash
curl http://localhost:8000/health
```

Deve responder `{"status":"ok"}`. No Windows PowerShell, use `curl.exe` (o `curl` puro é um alias de outro comando).

A documentação interativa (Swagger) fica em **http://localhost:8000/docs** e o contrato OpenAPI em `/openapi.json`.

> O Postgres do compose é publicado na porta **5433** do seu computador (para não conflitar com um Postgres local na 5432). A API o acessa pela rede interna do Docker, então isso não afeta o funcionamento. Se não precisar abrir o banco por fora, pode remover o bloco `ports` do serviço `db`.

## Testando pelo Swagger

1. Abra http://localhost:8000/docs.
2. Clique em **Authorize**, cole o valor de `API_KEYS` e confirme.
3. Em `POST /api/analyze`, clique em **Try it out**, cole o corpo abaixo e **Execute**.

```json
{"texto_input": "CNIS - Cadastro Nacional de Informações Sociais\nEXTRATO PREVIDENCIÁRIO (DOCUMENTO FICTÍCIO PARA TESTE)\n\nDados do Cidadão\nNIT: 000.00000.00-0\nCPF: 000.000.000-00\nNome: MARIA EXEMPLO DA SILVA\n\nRelações Previdenciárias\nSeq.: 1\nOrigem do Vínculo: COMERCIAL EXEMPLO LTDA\nData Início: 01/03/2015\nData Fim: (vazio)\nIndicadores: IREC-INDPEND", "origem": "texto_colado"}
```

Use **apenas documentos fictícios ou anonimizados**. Nunca cole um CNIS real.

Para consultar uma análise já feita, use `GET /api/analyze/{analysis_request_id}` com o `analysis_request_id` devolvido no POST.

## Endpoints

| Método | Rota | Descrição |
|---|---|---|
| POST | `/api/analyze` | Analisa o texto de um CNIS (síncrono). |
| GET | `/api/analyze/{analysis_request_id}` | Status e, se concluída, o resultado gravado. |
| GET | `/health` | Verificação de saúde (pública). |

As rotas `/api/*` exigem o cabeçalho `X-API-Key`. Corpo do POST: `texto_input` (string de 100 a 200.000 caracteres) e `origem` (`upload_pdf` ou `texto_colado`).

### Códigos de resposta

| Status | `code` | Quando |
|---|---|---|
| 200 | — | Análise concluída. |
| 400 | `entrada_invalida` | Texto vazio, curto ou grande demais, ou `origem` inválida. |
| 401 | `nao_autorizado` | `X-API-Key` ausente ou inválida. |
| 404 | `nao_encontrado` | Análise inexistente (GET). |
| 429 | `limite_de_requisicoes` | Mais de `RATE_LIMIT_PER_MINUTE` por cliente (cabeçalho `Retry-After`). |
| 502 | `ia_resposta_invalida` / `ia_erro` | A IA não devolveu uma resposta válida ou o provedor recusou a chamada. |
| 503 | `ia_indisponivel` | IA fora do ar, sem cota, ou sem `GEMINI_API_KEY`. |
| 504 | `ia_timeout` | A IA não respondeu dentro de `AI_TIMEOUT_SECONDS`. |
| 500 | `erro_interno` / `erro_processamento` | Falha inesperada (sem detalhes internos na resposta). |

## Testes automatizados

Não precisam de Postgres, internet nem chave do Gemini (usam SQLite em memória e uma IA falsa).

```bash
python -m venv .venv
# Windows (PowerShell):  .venv\Scripts\Activate.ps1
# Linux / macOS:         source .venv/bin/activate
pip install -r requirements-dev.txt
pytest
```

## Rodando sem Docker (opcional)

Requer um Postgres acessível.

```bash
python -m venv .venv && source .venv/bin/activate     # ou o equivalente do seu SO
pip install -r requirements.txt
cp .env.example .env                                   # ajuste DATABASE_URL, GEMINI_API_KEY, API_KEYS
alembic upgrade head                                   # cria as tabelas
uvicorn app.main:app --reload
```

## Variáveis de ambiente

| Variável | Padrão | Descrição |
|---|---|---|
| `APP_ENV` | `development` | Em `production`, `API_KEYS` é obrigatória. |
| `DATABASE_URL` | Postgres local | Com Docker Compose, é sobrescrita para apontar ao container `db`. |
| `API_KEYS` | vazio | Chaves aceitas em `X-API-Key`, separadas por vírgula. Vazia em `development` = autenticação desligada. |
| `CORS_ORIGINS` | `http://localhost:5173` | Origens do frontend, separadas por vírgula. |
| `GEMINI_API_KEY` | vazio | Chave do Gemini (fica só no servidor). Vazia = respostas `503`. |
| `GEMINI_MODEL` | ver `.env.example` | Modelo do Gemini. Confira a lista da sua chave (passo 3). |
| `AI_TIMEOUT_SECONDS` | `60` | Timeout da chamada à IA. |
| `AI_MAX_RETRIES` | `1` | Tentativas extras em timeout, 5xx ou resposta inválida. |
| `MIN_TEXT_CHARS` / `MAX_TEXT_CHARS` | `100` / `200000` | Limites do texto de entrada. |
| `RATE_LIMIT_PER_MINUTE` | `5` | Requisições por minuto por cliente em `POST /api/analyze`. |
| `STORE_INPUT_TEXT` | `false` | Se `true`, grava o texto integral do CNIS no banco (contém dados pessoais). |

## Estrutura

```
app/
  main.py              # cria a app, CORS, handlers e rotas
  core/                # config (env), erros, segurança (API key) e rate limit
  db/                  # engine/sessão e Base do SQLAlchemy
  models/              # tabelas (AnalysisRequest/Response, DocumentSummary, Issue)
  schemas/             # api.py (entrada/saída) e ai_contract.py (o que a IA devolve)
  repositories/        # acesso ao banco
  services/
    analysis_service.py  # orquestra o fluxo
    postprocess.py       # evidência, ordenação, totais, pendência documental
    evidence.py          # normalização e checagem de evidência
    ai/                  # provedor de IA isolado (base, prompts, gemini)
  routers/             # rotas HTTP
alembic/               # migrações
tests/
```

Para trocar de provedor de IA, implemente `AIProvider` (`app/services/ai/base.py`) e ajuste `build_ai_provider` em `app/services/ai/__init__.py`.


## Limitações do MVP

- **Rate limit em memória:** vale por processo. Com várias instâncias, use um limitador compartilhado (ex.: Redis) ou o do proxy.
- **Sem usuários ainda:** `usuario_id` existe em `analysis_requests`, sem chave estrangeira, reservado para a v2.
- **A IA pode errar:** o backend garante evidência real e totais consistentes, mas não que a análise esteja juridicamente correta. A revisão por profissional habilitado é obrigatória.
- Em produção, limite também o tamanho do corpo das requisições no proxy ou servidor.
