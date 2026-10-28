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
are eligible for automatic worker reclamation; a delayed heartbeat may renew
an expired lease only while the document remains in `processing` at the same
ingestion version, so a reclaimed attempt cannot renew the newer owner's lease.
Attempts are bounded by
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
processing uses layout and table structure analysis with RapidOCR enabled in
PDF-aware layout mode, so it can extract text from scanned pages and image
regions while retaining selectable PDF text. RapidOCR uses ONNX Runtime and
defaults to English; set `DOCLING_OCR_LANGUAGE` to one supported RapidOCR
language code (for example `en`, `ch`, or `de`) for documents in another
language. RapidOCR processes one language per run. OCR is only enabled for
Docling PDF parsing; DOCX uses Docling's document conversion without the PDF
OCR pipeline. A document that produces no usable text chunks still cannot be
published as ready. Docling exports heading-aware sections and tables as
Markdown; section headings are carried into generated chunks. Text, Markdown,
JSON, CSV, website, and image sources keep their dedicated parsers.

Docling's PDF OCR, layout, and table analysis are more compute-intensive than
plain text extraction and may download model artifacts on first use. The
ingestion worker runs each document in a fresh subprocess and enforces
`INGESTION_TIMEOUT_SECONDS` (default `900`), so first-use downloads and
conversion must fit the configured timeout and service CPU/memory limits.
Prewarm Docling model artifacts during deployment and set
`DOCLING_ARTIFACTS_PATH` to that directory when running offline; a configured
path must contain all required Docling layout and OCR artifacts. Otherwise,
leave `DOCLING_ARTIFACTS_PATH` unset/blank so Docling can use its default cache
and model download behavior. Do not set it to `.` unless that directory
actually contains the required layout and OCR artifacts. Monitor the
`parse_document` stage duration and Docling conversion logs. The parser logs
dependency import, converter initialization, document conversion, and
Markdown export timings, as well as page count and extracted character count,
but never document text. Use
`DOCUMENT_PARSER_PROVIDER=native` only when choosing the legacy PDF/DOCX
parsers intentionally. Native PDF parsing is the fast, text-layer-only path:
selectable text is collected across all pages and image-only pages or regions
are skipped without OCR. A PDF with no selectable text on any page is rejected.

`DOCUMENT_PARSER_PROVIDER=auto` (opt-in) selects parsing per document instead
of per provider. PDFs are first extracted with PyMuPDF's fast text layer, and
only documents that PyMuPDF cannot read as selectable text fall back to Docling
OCR. Mixed pages keep their selectable text, and only image-only pages are
rasterized for OCR, so recoverable text is never lost and selectable text is
never OCR'd twice (see `QualityAwareDocumentParser`). When the fraction of
pages with selectable text falls below `SELECTABLE_TEXT_RATIO_THRESHOLD`
(default `0.5`), the image-only pages are sent to Docling for selective OCR
rather than a full re-scan. PyMuPDF now also retries `text` -> `words` -> `blocks`
extraction per page, which prevents text-based PDFs from being falsely rejected
as "scanned". This is the recommended mode for mixed text/scanned workloads;
the default remains `docling` to preserve the no-silent-retry guarantee above.

> **Troubleshooting OCR timeouts:** if a scanned/image-only PDF (e.g. an Aadhaar
> card scan) hangs at "Docling conversion started" and the ingestion is killed
> at `INGESTION_TIMEOUT_SECONDS` (default `900`): PyMuPDF correctly determined
> the page has no selectable text, so the document is routed to Docling full OCR
> — that part is working as intended. Docling loads a layout-detection model
> (`ds4sd/docling-layout-detection`, Transformers) and an ONNX OCR model on
> first use, and the ingestion worker runs that work in a **fresh `spawn`
> subprocess**, so each cold attempt can re-download/re-load those models.
> Diagnose which phase the hang occurs in using the existing stage logs:
> - If the log **stops before** `Docling converter initialization completed` →
>   the hang is at model import/load/download. Fix: prewarm Docling at deploy
>   time (run one representative scanned PDF through ingestion once) so the
>   models populate the shared HuggingFace cache (`~/.cache/huggingface`), or
>   set `DOCLING_ARTIFACTS_PATH` to a pre-staged artifacts directory. This is
>   almost always the cause of a single-page doc exceeding the timeout.
> - If the log **stops after** `Docling document conversion started` (but before
>   `Docling document conversion returned`) → the hang is model inference, not
>   download. Lower per-page rasterization cost with `DOCLING_OCR_IMAGE_DPI`
>   (selective OCR only; default `144`), or reduce `INGESTION_TIMEOUT_SECONDS`
>   so failures surface faster instead of blocking the worker for the full
>   window. Lowering the timeout below the typical OCR budget makes slow
>   documents fail fast with a clear `ingestion_timeout` rather than occupying a
>   worker; they remain eligible for job-level retry.

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

## Performance: Docling OCR & ingestion timeouts

Ingestion runs in a **fresh `spawn` subprocess** whose lifetime is bounded by
`INGESTION_TIMEOUT_SECONDS` (default `900`, enforced in
`app/api/admin/ingestion.py`). On timeout the job is killed and retried up to
`INGESTION_MAX_ATTEMPTS`. The most common cause of a 900s OCR timeout is
**Docling downloading/loading its layout + OCR models on first use inside that
subprocess** (each ingestion gets a clean cache), not a parsing-logic bug.

Mitigations, ordered by impact:

1. **Prewarm Docling models at deploy time.** Run the API once against a
   representative scanned PDF so HuggingFace caches the layout and OCR models in
   `~/.cache/huggingface` (or a shared volume mounted at `DOCLING_ARTIFACTS_PATH`).
   This is the single most effective fix.
2. `DOCUMENT_PARSER_PROVIDER=auto` (recommended). PyMuPDF extracts the text layer
   first; Docling OCR runs **only** on image-only pages, so text-based PDFs skip
   OCR entirely. A fully scanned doc (no text layer at all) still falls back to a
   full Docling pass.
3. `DOCLING_SKIP_LAYOUT=1` — for **scanned/image-only PDFs**, skip Docling's
   layout-detection model: the text is still fully OCR'd but no section/table
   structure is generated, which removes the slowest CPU stage. Turn this on for
   ingestion-only workloads that only need searchable text.
4. `DOCLING_OCR_IMAGE_DPI=144` (lower for large scanned images) — speeds up the
   selective page-OCR raster step.
5. `DOCLING_OCR_MODE` selects the OCR input regions for scanned pages. Valid
   values in Docling 2.118.0: `default` (layout-aware regions — recommended),
   `full_page`, `layout_regions`, `pdf_aware_layout_regions`. `onnxruntime` is
   the OCR backend. Note: `skip` is **not** a valid OCR mode here — to disable
   OCR entirely, use `DOCUMENT_PARSER_PROVIDER=native` (PyMuPDF text
   extraction, no OCR).
6. `INGESTION_TIMEOUT_SECONDS=300` (or similar) to **fail fast** instead of
   holding a worker for 900s; failed docs are retried automatically.
7. `MAX_PDF_PAGES` caps how many pages a single doc can contain.

> Note: `DOCLING_SKIP_LAYOUT`, `DOCLING_OCR_IMAGE_DPI`, and
> `DOCLING_OCR_MODE` only affect the Docling-backed OCR path. The fast PyMuPDF
> path and `DOCUMENT_PARSER_PROVIDER=native` are unaffected.

MIT
