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

## .Create project

## Render CORS configuration

Set these environment variables on the **backend Render service**:

```env
FRONTEND_URL=https://chatbot3-proj-1.onrender.com
ALLOWED_ORIGINS=https://chatbot3-proj-1.onrender.com
CORS_ALLOW_LOCAL_ORIGINS=false
```

`FRONTEND_URL` is automatically merged into the backend global CORS allow-list,
so the deployed admin frontend can call the API. `ALLOWED_ORIGINS` may also
contain additional first-party origins separated by commas.

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
    │       ├── docling_provider.py
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
