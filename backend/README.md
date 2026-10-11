##

---

| Area                       | Choice                          |
| -------------------------- | ------------------------------- |
| Language                   | Python 3.12.10                  |
| API framework              | FastAPI                         |
| ASGI server                | Uvicorn                         |
| Validation/settings        | Pydantic v2 + pydantic-settings |
| ORM                        | SQLAlchemy 2.x                  |
| Migrations                 | Alembic                         |
| PostgreSQL driver          | psycopg                         |
| Vector support             | pgvector                        |
| Storage/backend config     | Supabase                        |
| LLM integration            | Ollama locally first            |
| AI integration abstraction | LangChain-compatible providers  |
| Testing                    | pytest + pytest-asyncio         |
| Linting/formatting         | Ruff                            |
| IDE                        | VS Code on Windows              |

---

## Fresh PostgreSQL database

The application schema is managed by Alembic. For a **new, empty PostgreSQL
database**, set `DATABASE_URL` to that database and run this once from the
`backend` directory before starting the API:

```bash
python -m alembic -c alembic.ini upgrade head
```

The initial revision creates the eight relational tables, enables the
`vector` extension, and creates `document_chunks` with a 1024-dimensional
embedding column plus cosine HNSW and full-text indexes. The PostgreSQL
provider must support pgvector and allow `CREATE EXTENSION vector`. Keep
`VECTOR_STORE_TABLE_NAME=document_chunks` and `VECTOR_STORE_DIMENSION=1024`
aligned with this initial revision; changing either requires a deliberate
follow-up migration.

For Render, configure the same command as the backend service's **Pre-Deploy
Command**. Do not run migrations on every worker startup. Verify with
`python -m alembic -c alembic.ini current`.

This initial revision is for an empty database only. It does not copy data from
Supabase and must not be run against an existing database that already has
these tables. The older SQL files in `migrations/` are legacy repair scripts,
not the fresh-database bootstrap path.

## Optional LangSmith tracing

LangSmith tracing is disabled by default. The QA pipeline is recorded as a
parent `chain` run and its LLM provider call as a nested `llm` run. Both carry
the HTTP `X-Request-ID` value as trace metadata. Provider runs include the
normalized model, token usage, and latency values returned by OpenRouter or
Ollama.

Enable tracing by setting these backend environment variables:

```dotenv
LANGSMITH_TRACING=true
LANGSMITH_API_KEY=...
LANGSMITH_PROJECT=your-project-name
# Optional for a custom/self-hosted API:
LANGSMITH_ENDPOINT=
```

When tracing is disabled, no LangSmith client is created and credentials are
not required. The SDK client is created once during application startup and
flushed during shutdown.

Tracing includes the customer query and LLM prompts/answer, which can contain
conversation history and retrieved business documents. Enable it only when
that data is approved for transfer to the configured LangSmith workspace.

## Render CORS configuration

Set these environment variables on the **backend Render service**:

```env
FRONTEND_URL=https://chatbot3-proj-1.onrender.com
ALLOWED_ORIGINS=https://chatbot3-proj-1.onrender.com
CORS_ALLOW_LOCAL_ORIGINS=false
INGESTION_STALE_AFTER_MINUTES=15
DOCUMENT_INGESTION_CONCURRENCY=1
INGESTION_TIMEOUT_SECONDS=900
INGESTION_LEASE_SECONDS=120
INGESTION_MAX_ATTEMPTS=3
MAX_UPLOAD_FILE_SIZE_BYTES=20971520
MAX_PDF_PAGES=50
```

`FRONTEND_URL` is automatically merged into the backend global CORS allow-list,
so the deployed admin frontend can call the API. `ALLOWED_ORIGINS` may also
contain additional first-party origins separated by commas.

Set `CHAT_HISTORY_RETENTION_DAYS` on the backend service to choose the default
message-history retention for newly created applications (defaults to `30`).
Each application's `retention_days` setting overrides that default. Expired
conversations and their messages are removed at startup and hourly; a visitor's
history is also cleaned against its application's exact retention cutoff when
the widget session is opened.

Document uploads and website sources are persisted as `pending` jobs. Workers
start with the FastAPI ASGI lifespan and claim jobs from PostgreSQL using
`FOR UPDATE SKIP LOCKED`; keep ASGI lifespan enabled in the Render start
command. `DOCUMENT_INGESTION_CONCURRENCY` controls the worker count per service
instance and defaults to `1`. Active jobs heartbeat while parsing, embedding,
and indexing. A renewable database lease (`INGESTION_LEASE_SECONDS`, default
`120`; heartbeat every 30 seconds) governs ownership. Jobs with expired leases
are eligible for automatic worker reclamation. Attempts are bounded by
`INGESTION_MAX_ATTEMPTS` (default `3`); only provider failures explicitly
classified as transient are retried, using capped exponential backoff with
jitter (`INGESTION_RETRY_BASE_SECONDS=30`,
`INGESTION_RETRY_MAX_SECONDS=300`). Billing failures such as HTTP 402 are not
automatically retried. Timeouts and permanent failures remain failed until an
admin explicitly retries them. Check
`/api/system/ingestion-workers` for worker health and Render logs for
document-scoped ingestion stage progress. Apply
`0004_ingestion_leases` before deployment.

PDF uploads are bounded by `MAX_UPLOAD_FILE_SIZE_BYTES` (default 20 MiB) and
`MAX_PDF_PAGES` (default 50); the page limit is checked before the object is
stored and again before Docling conversion. Docling OCR/layout/table processing
can be CPU- and memory-intensive. `INGESTION_TIMEOUT_SECONDS` defaults to 900;
choose values that leave headroom for model initialization and processing.
Keep concurrency at one until representative Render CPU/memory and OCR
measurements justify increasing it. The subprocess-per-document design is
retained to isolate jobs; it repeats model startup and no persistent-worker
performance gain is assumed.

PDF and DOCX parsing is selected independently with
`DOCUMENT_PARSER_PROVIDER=docling` (the default) or `native`. Docling processes
PDF/DOCX uploads directly and conversion errors fail that ingestion attempt;
the application does not silently retry with another parser. Docling PDF
processing uses layout and table structure analysis with OCR explicitly
disabled. It extracts text available in the PDF; scanned/image-only pages are
not OCR'd. No selectable-text precheck is performed, but a document that
produces no usable text chunks cannot be published as ready. Docling exports
heading-aware sections and tables as Markdown; section headings are carried
into generated chunks. Text, Markdown, JSON, CSV, website, and image sources
keep their dedicated parsers.

Docling's PDF layout and table analysis are more compute-intensive than plain
text extraction and may download model artifacts on first use. OCR model
artifacts are not needed while OCR is disabled. The ingestion worker runs each
document in a fresh subprocess and enforces `INGESTION_TIMEOUT_SECONDS`
(default `900`), so first-use downloads and conversion must fit the configured
timeout and service CPU/memory limits. Prewarm
Docling model artifacts during deployment and set `DOCLING_ARTIFACTS_PATH` to
that directory when running offline; a configured path must contain all
required Docling layout/table artifacts. Otherwise, leave
`DOCLING_ARTIFACTS_PATH` unset/blank so Docling can use its default cache and
model download behavior. Monitor the `parse_document` stage duration and
Docling conversion logs. The parser logs byte count, elapsed time, page count,
extracted character count, and section count, but never document text. Use
`DOCUMENT_PARSER_PROVIDER=native` only when choosing the legacy PDF/DOCX
parsers intentionally; native PDF parsing rejects scanned/image-only files.

Uploaded source objects must live in a **private** Supabase Storage bucket
(the default bucket name is `data_files`). The backend accesses it with the
service-role key; do not expose source files through public object URLs. Each
job increments `documents.ingestion_version`. Successful vector writes,
`ready_version`, and the document's `ready` status publish in one PostgreSQL
transaction. The pipeline verifies the exact indexed chunk set before
publication. Each vector row carries its immutable per-document
`ingestion_version`; semantic and keyword retrieval only return the active
`ready_version` and require the document and knowledge base to belong to the
same application. Failed or superseded attempts do not replace the last
published version, so a previously indexed version remains searchable while a
replacement is processing or has failed. Archived documents are excluded.
Apply migrations `0002_document_ingestion_versions`,
`0003_version_document_chunks`, `0004_ingestion_leases`, and
`0005_storage_upload_intents` before deploying this version of the backend.
Uploads first commit a durable storage intent and remove it atomically with the
document row after successful upload. The lifespan recovery task checks stale
intents every minute; intents older than 30 minutes with no matching document
are deleted from Supabase Storage. The delete operation is idempotent for
already-missing objects, so crashes between deletion and database commit are
safe to retry. For databases managed with
`supabase_schema_fix.sql`, apply that script as well; it switches the default
`data_files` bucket to private. If `SUPABASE_BUCKET_NAME` is customized, make
that bucket private in Supabase Storage settings.

For OpenRouter embeddings, `OPENROUTER_EMBEDDING_BATCH_SIZE` controls how many
chunks are sent per request (default `64`, maximum `64`). Lower it if the
selected embedding model has stricter request limits. Vector writes are sent
to PostgreSQL in batches of 100 chunks. Raising worker concurrency can reduce
queue wait, but increases peak memory and provider/database load per service
instance; start conservatively and monitor Render memory and provider limits.

Embeddings can use Hugging Face independently from the LLM provider. To use
Hugging Face Inference Providers, set `EMBEDDING_PROVIDER=huggingface`,
`HF_TOKEN` to a Hugging Face token with Inference Providers permission, and
leave `LLM_PROVIDER` unchanged. The default model is
`BAAI/bge-large-en-v1.5` through `hf-inference`; it returns 1024-dimensional
vectors for the current pgvector schema. `HF_EMBEDDING_BATCH_SIZE` defaults to
`32` (maximum `64`) and `HF_INFERENCE_TIMEOUT_SECONDS` defaults to `60`.
Confirm the selected model is available through the configured provider.

Changing embedding model/provider changes the vector space. Re-ingest all
documents before relying on retrieval after a switch; never mix vectors
generated by different embedding models in one searchable knowledge base.
The Hugging Face key is used only for embeddings; LLM calls continue to use
the configured `LLM_PROVIDER` and its credentials.

OpenAI embeddings can also be selected with `EMBEDDING_PROVIDER=openai`,
`OPENAI_API_KEY`, and `OPENAI_EMBEDDING_MODEL` (default
`text-embedding-3-small`). Its default output dimension is 1024, matching the
current vector schema; keep `OPENAI_EMBEDDING_DIMENSIONS` equal to
`VECTOR_STORE_DIMENSION`. OpenAI embedding settings affect only embeddings,
not the separately configured chat LLM.

`EMBEDDING_PROVIDER` is the single selector used by ingestion and chat query
embedding; model, provider endpoint, credentials, dimensions, and batching are
configured separately for each backend. Adding a future embeddings backend
requires implementing the common `EmbeddingProvider` interface and registering
it in the embeddings provider factory. It does not require changing LLM
selection. Set the desired provider/model in Render environment variables and
keep vector dimensions at 1024 unless deliberately migrating the pgvector
column and re-indexing every document.

Embedded customer sites are configured separately in the application's
`allowed_origins` field in the admin UI. Add the complete origin, for example
`https://customer.example.com`, without a trailing slash or path. Do not add
only the frontend Render URL unless the widget is actually embedded there.

Set these variables on the **frontend Render service**:

```env
VITE_BACKEND_URL=https://chatbot3-proj.onrender.com
VITE_FRONTEND_URL=https://chatbot3-proj-1.onrender.com
```

mkdir D:\AI-Projects
cd D:\AI-Projects

mkdir rag-system
cd rag-system

mkdir backend
cd backend
code .

1. Create virtual environment;

- cd backend

python -m venv .venv

2. Activate the environment;

.venv\Scripts\Activate.ps1 

- (If PowerShell blocks activation, run this once in the same terminal session:)

Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass

3. Install Python Packages & base dependencies;
   python -m pip freeze > requirements.txt
   (or) already have file;

pip install -r requirements.txt
- and check if unmatched...
.\.venv\Scripts\python.exe -m pip check

4. Upgrade pip/tooling:

python -m pip install --upgrade pip setuptools wheel

    (Verify:

python -c "import sys; print(sys.executable)"
Expected:
...\backend\.venv\Scripts\python.exe)


5. Project Skeleton


6. Initialize Git;
   git init
   .gitignore
   (
   .venv/
   **pycache**/
   .pytest_cache/
   .mypy_cache/
   .ruff_cache/
   .env
   .vscode/
   storage/
   data_resources/
   \*.pyc
   )

# finall check up

where python
py -0p
Get-Command python

### Run application

- cd /project/backend

run by setup runner file(run.py)
(or)
.\.venv\Scripts\python.exe -m uvicorn app.main:app
or
uvicorn app.main:app --reload


## Restart Steps
- Stop all Uvicorn processes:
Get-Process python -ErrorAction SilentlyContinue | Stop-Process -Force


.\.venv\Scripts\python.exe -m compileall app 
uvicorn app.main:app

- clear cache and py files by;
Get-ChildItem -Path .\app -Recurse -Directory -Filter __pycache__ |
    Remove-Item -Recurse -Force
---

finalized application structure:
/app/
├── main.py
├── composition.py
│
├── api/
│   ├── router.py
│   ├── middleware.py
│   ├── dependencies.py
│   ├── admin/
│   │   ├── applications.py
│   │   ├── knowledge_bases.py
│   │   ├── documents.py
│   │   ├── conversations.py
│   │   ├── widgets.py
│   │   └── settings.py
│   ├── client/
│   │   └── chat.py
│   └── schemas/
│       ├── applications.py
│       ├── knowledge_bases.py
│       ├── documents.py
│       ├── conversations.py
│       ├── widgets.py
│       ├── settings.py
│       └── chat.py
│
├── config/
│   ├── settings.py
│   ├── logging.py
│   ├── security.py
│   ├── database.py
│   └── provider_registry.py
│
├── core/
│   ├── constants.py
│   ├── enums.py
│   ├── exceptions.py
│   ├── responses.py
│   ├── types.py
│   └── ids.py
│
├── modules/
│   ├── applications/
│   │   ├── domain/
│   │   │   ├── entities.py
│   │   │   ├── value_objects.py
│   │   │   ├── policies.py
│   │   │   └── repository_interfaces.py
│   │   ├── application/
│   │   │   ├── commands.py
│   │   │   ├── queries.py
│   │   │   ├── dto.py
│   │   │   └── services.py
│   │   └── infrastructure/
│   │       ├── orm_models.py
│   │       ├── repositories.py
│   │       └── mappers.py
│   │
│   ├── knowledge_bases/
│   │   ├── domain/
│   │   │   ├── entities.py
│   │   │   ├── value_objects.py
│   │   │   ├── policies.py
│   │   │   └── repository_interfaces.py
│   │   ├── application/
│   │   │   ├── commands.py
│   │   │   ├── queries.py
│   │   │   ├── dto.py
│   │   │   └── services.py
│   │   └── infrastructure/
│   │       ├── orm_models.py
│   │       ├── repositories.py
│   │       └── mappers.py
│   │
│   ├── documents/
│   │   ├── domain/
│   │   │   ├── entities.py
│   │   │   ├── value_objects.py
│   │   │   ├── policies.py
│   │   │   └── repository_interfaces.py
│   │   ├── application/
│   │   │   ├── commands.py
│   │   │   ├── queries.py
│   │   │   ├── dto.py
│   │   │   └── services.py
│   │   └── infrastructure/
│   │       ├── orm_models.py
│   │       ├── repositories.py
│   │       └── mappers.py
│   │
│   ├── conversations/
│   │   ├── domain/
│   │   │   ├── entities.py
│   │   │   ├── value_objects.py
│   │   │   ├── policies.py
│   │   │   └── repository_interfaces.py
│   │   ├── application/
│   │   │   ├── commands.py
│   │   │   ├── queries.py
│   │   │   ├── dto.py
│   │   │   └── services.py
│   │   └── infrastructure/
│   │       ├── orm_models.py
│   │       ├── repositories.py
│   │       └── mappers.py
│   │
│   ├── widgets/
│   │   ├── domain/
│   │   │   ├── entities.py
│   │   │   ├── value_objects.py
│   │   │   ├── policies.py
│   │   │   └── repository_interfaces.py
│   │   ├── application/
│   │   │   ├── commands.py
│   │   │   ├── queries.py
│   │   │   ├── dto.py
│   │   │   └── services.py
│   │   └── infrastructure/
│   │       ├── orm_models.py
│   │       ├── repositories.py
│   │       └── mappers.py
│   │
│   ├── settings/
│   │   ├── domain/
│   │   │   ├── entities.py
│   │   │   ├── value_objects.py
│   │   │   ├── policies.py
│   │   │   └── repository_interfaces.py
│   │   ├── application/
│   │   │   ├── commands.py
│   │   │   ├── queries.py
│   │   │   ├── dto.py
│   │   │   └── services.py
│   │   └── infrastructure/
│   │       ├── orm_models.py
│   │       ├── repositories.py
│   │       └── mappers.py
│   │
│   └── chat/
│       ├── application/
│       │   ├── commands.py
│       │   ├── dto.py
│       │   └── services.py
│       └── contracts/
│           ├── request_models.py
│           └── response_models.py
│
├── knowledge_engine/
│   ├── contracts/
│   │   ├── llm.py
│   │   ├── embeddings.py
│   │   ├── vector_store.py
│   │   ├── storage.py
│   │   └── parsing.py
│   ├── ingestion/
│   │   ├── source_loaders/
│   │   │   ├── base.py
│   │   │   ├── file_loader.py
│   │   │   ├── website_loader.py
│   │   │   └── csv_loader.py
│   │   ├── parsers/
│   │   │   ├── base.py
│   │   │   ├── structured_document_parser.py
│   │   │   ├── html_parser.py
│   │   │   └── ocr_parser.py
│   │   ├── normalizer.py
│   │   ├── chunker.py
│   │   ├── metadata_enricher.py
│   │   ├── embedding_generator.py
│   │   └── vector_indexer.py
│   ├── retrieval/
│   │   ├── query_embedder.py
│   │   ├── hybrid_retriever.py
│   │   ├── metadata_filter.py
│   │   ├── reranker.py
│   │   └── conversation_context_builder.py
│   ├── generation/
│   │   ├── prompt_builder.py
│   │   ├── response_generator.py
│   │   ├── citation_builder.py
│   │   └── response_formatter.py
│   ├── pipelines/
│   │   ├── knowledge_ingestion_pipeline.py
│   │   └── question_answering_pipeline.py
│   └── shared/
│       ├── models.py
│       ├── types.py
│       └── helpers.py
│
└── infrastructure/
    ├── db/
    │   ├── base.py
    │   ├── engine.py
    │   ├── session.py
    │   ├── registry.py
    │   ├── models/
    │   │   ├── application_model.py
    │   │   ├── knowledge_base_model.py
    │   │   ├── document_model.py
    │   │   ├── conversation_model.py
    │   │   ├── message_model.py
    │   │   ├── widget_model.py
    │   │   ├── settings_model.py
    │   │   └── api_key_model.py
    │   └── migrations/
    ├── providers/
    │   ├── llm/
    │   │   ├── ollama_provider.py
    │   │   ├── openai_provider.py
    │   │   ├── gemini_provider.py
    │   │   └── anthropic_provider.py
    │   ├── embeddings/
    │   │   ├── nomic_provider.py
    │   │   ├── openai_provider.py
    │   │   └── oracle_provider.py
    │   ├── vector/
    │   │   ├── pgvector_provider.py
    │   │   ├── oracle_vector_provider.py
    │   │   └── qdrant_provider.py
    │   ├── storage/
    │   │   ├── supabase_storage_provider.py
    │   │   ├── s3_storage_provider.py
    │   │   └── azure_blob_storage_provider.py
    │   └── parsing/
    │       ├── pymupdf_provider.py
    │       ├── python_docx_provider.py
    │       ├── html_parsing_provider.py
    │       └── ocr_provider.py
    ├── security/
    │   ├── api_key_validator.py
    │   ├── admin_authenticator.py
    │   └── origin_validator.py
    └── observability/
        ├── logging.py
        ├── tracing.py
        └── metrics.py
MIT
