-- Supabase/Postgres migration for the ChatBot backend
-- This script aligns the live database schema with the SQLAlchemy ORM.
-- All identifiers are NATIVE UUID columns (matching the ORM models in
-- app/infrastructure/db/models/*), so the app and the DB agree on types.
-- Run it against the target Supabase/Postgres database using psql or the
-- Supabase SQL editor. Safe to re-run (idempotent).

CREATE EXTENSION IF NOT EXISTS vector;

CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Helper: convert a legacy varchar(36) id column to native UUID if needed.
-- (Kept for databases that were first created with varchar(36) columns.)

-- Applications table
CREATE TABLE IF NOT EXISTS public.applications (
    id UUID PRIMARY KEY,
    name varchar(150) NOT NULL UNIQUE,
    slug varchar(150) NOT NULL UNIQUE,
    description text,
    client_type varchar(50) NOT NULL,
    allowed_origins text[] NULL,
    is_active boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT NOW(),
    updated_at timestamptz NOT NULL DEFAULT NOW()
);

DO $$
BEGIN
    -- Legacy column-type repair: convert varchar(36) ids to UUID.
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'applications'
          AND column_name = 'id' AND data_type <> 'uuid'
    ) THEN
        ALTER TABLE public.applications ALTER COLUMN id TYPE UUID USING id::uuid;
    END IF;
END $$;

ALTER TABLE public.applications
    ADD COLUMN IF NOT EXISTS description text,
    ADD COLUMN IF NOT EXISTS client_type varchar(50),
    ADD COLUMN IF NOT EXISTS allowed_origins text[] NULL,
    ADD COLUMN IF NOT EXISTS is_active boolean DEFAULT true,
    ADD COLUMN IF NOT EXISTS created_at timestamptz DEFAULT NOW(),
    ADD COLUMN IF NOT EXISTS updated_at timestamptz DEFAULT NOW();

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'applications'
          AND column_name = 'allowed_origins'
          AND data_type <> 'ARRAY'
    ) THEN
        ALTER TABLE public.applications
            ALTER COLUMN allowed_origins TYPE text[]
            USING CASE
                WHEN allowed_origins IS NULL THEN NULL
                WHEN allowed_origins::text = '' THEN ARRAY[]::text[]
                ELSE string_to_array(allowed_origins::text, ',')
            END;
    END IF;
END $$;

ALTER TABLE public.applications
    ALTER COLUMN name SET NOT NULL,
    ALTER COLUMN slug SET NOT NULL,
    ALTER COLUMN client_type SET NOT NULL,
    ALTER COLUMN is_active SET DEFAULT true,
    ALTER COLUMN created_at SET DEFAULT NOW(),
    ALTER COLUMN updated_at SET DEFAULT NOW();

CREATE INDEX IF NOT EXISTS ix_applications_name ON public.applications (name);
CREATE INDEX IF NOT EXISTS ix_applications_slug ON public.applications (slug);
CREATE INDEX IF NOT EXISTS ix_applications_is_active ON public.applications (is_active);
DROP TRIGGER IF EXISTS applications_set_updated_at ON public.applications;
CREATE TRIGGER applications_set_updated_at
BEFORE UPDATE ON public.applications
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

-- Knowledge bases table
CREATE TABLE IF NOT EXISTS public.knowledge_bases (
    id UUID PRIMARY KEY,
    application_id UUID NOT NULL UNIQUE,
    name varchar(150) NOT NULL,
    slug varchar(180) NOT NULL UNIQUE,
    status varchar(50) NOT NULL DEFAULT 'ready',
    is_active boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT NOW(),
    updated_at timestamptz NOT NULL DEFAULT NOW(),
    CONSTRAINT fk_knowledge_bases_application
        FOREIGN KEY (application_id) REFERENCES public.applications(id) ON DELETE CASCADE
);

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'knowledge_bases'
          AND column_name = 'id' AND data_type <> 'uuid'
    ) THEN
        ALTER TABLE public.knowledge_bases ALTER COLUMN id TYPE UUID USING id::uuid;
    END IF;
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'knowledge_bases'
          AND column_name = 'application_id' AND data_type <> 'uuid'
    ) THEN
        ALTER TABLE public.knowledge_bases ALTER COLUMN application_id TYPE UUID USING application_id::uuid;
    END IF;
END $$;

ALTER TABLE public.knowledge_bases
    ADD COLUMN IF NOT EXISTS name varchar(150),
    ADD COLUMN IF NOT EXISTS slug varchar(180),
    ADD COLUMN IF NOT EXISTS status varchar(50) DEFAULT 'ready',
    ADD COLUMN IF NOT EXISTS is_active boolean DEFAULT true,
    ADD COLUMN IF NOT EXISTS created_at timestamptz DEFAULT NOW(),
    ADD COLUMN IF NOT EXISTS updated_at timestamptz DEFAULT NOW();

ALTER TABLE public.knowledge_bases
    ALTER COLUMN application_id SET NOT NULL,
    ALTER COLUMN name SET NOT NULL,
    ALTER COLUMN slug SET NOT NULL,
    ALTER COLUMN status SET DEFAULT 'ready',
    ALTER COLUMN is_active SET DEFAULT true,
    ALTER COLUMN created_at SET DEFAULT NOW(),
    ALTER COLUMN updated_at SET DEFAULT NOW();

CREATE UNIQUE INDEX IF NOT EXISTS ux_knowledge_bases_slug ON public.knowledge_bases (slug);
CREATE INDEX IF NOT EXISTS ix_knowledge_bases_application_id ON public.knowledge_bases (application_id);
CREATE INDEX IF NOT EXISTS ix_knowledge_bases_status ON public.knowledge_bases (status);
CREATE INDEX IF NOT EXISTS ix_knowledge_bases_is_active ON public.knowledge_bases (is_active);
DROP TRIGGER IF EXISTS knowledge_bases_set_updated_at ON public.knowledge_bases;
CREATE TRIGGER knowledge_bases_set_updated_at
BEFORE UPDATE ON public.knowledge_bases
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

-- Documents table
CREATE TABLE IF NOT EXISTS public.documents (
    id UUID PRIMARY KEY,
    application_id UUID NOT NULL,
    knowledge_base_id UUID NOT NULL,
    title varchar(255) NOT NULL,
    description text,
    source_type varchar(50) NOT NULL,
    source_uri text,
    storage_path text,
    mime_type varchar(150),
    file_size_bytes integer,
    checksum_sha256 varchar(128),
    status varchar(50) NOT NULL DEFAULT 'pending',
    failure_reason text,
    created_at timestamptz NOT NULL DEFAULT NOW(),
    updated_at timestamptz NOT NULL DEFAULT NOW(),
    CONSTRAINT fk_documents_application FOREIGN KEY (application_id) REFERENCES public.applications(id) ON DELETE CASCADE,
    CONSTRAINT fk_documents_knowledge_base FOREIGN KEY (knowledge_base_id) REFERENCES public.knowledge_bases(id) ON DELETE CASCADE
);

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'documents'
          AND column_name = 'id' AND data_type <> 'uuid'
    ) THEN
        ALTER TABLE public.documents ALTER COLUMN id TYPE UUID USING id::uuid;
    END IF;
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'documents'
          AND column_name = 'application_id' AND data_type <> 'uuid'
    ) THEN
        ALTER TABLE public.documents ALTER COLUMN application_id TYPE UUID USING application_id::uuid;
    END IF;
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'documents'
          AND column_name = 'knowledge_base_id' AND data_type <> 'uuid'
    ) THEN
        ALTER TABLE public.documents ALTER COLUMN knowledge_base_id TYPE UUID USING knowledge_base_id::uuid;
    END IF;
END $$;

ALTER TABLE public.documents
    ADD COLUMN IF NOT EXISTS title varchar(255),
    ADD COLUMN IF NOT EXISTS description text,
    ADD COLUMN IF NOT EXISTS source_type varchar(50),
    ADD COLUMN IF NOT EXISTS source_uri text,
    ADD COLUMN IF NOT EXISTS storage_path text,
    ADD COLUMN IF NOT EXISTS mime_type varchar(150),
    ADD COLUMN IF NOT EXISTS file_size_bytes integer,
    ADD COLUMN IF NOT EXISTS checksum_sha256 varchar(128),
    ADD COLUMN IF NOT EXISTS status varchar(50) DEFAULT 'pending',
    ADD COLUMN IF NOT EXISTS failure_reason text,
    ADD COLUMN IF NOT EXISTS created_at timestamptz DEFAULT NOW(),
    ADD COLUMN IF NOT EXISTS updated_at timestamptz DEFAULT NOW();

ALTER TABLE public.documents
    ALTER COLUMN application_id SET NOT NULL,
    ALTER COLUMN knowledge_base_id SET NOT NULL,
    ALTER COLUMN title SET NOT NULL,
    ALTER COLUMN source_type SET NOT NULL,
    ALTER COLUMN status SET DEFAULT 'pending',
    ALTER COLUMN created_at SET DEFAULT NOW(),
    ALTER COLUMN updated_at SET DEFAULT NOW();

CREATE INDEX IF NOT EXISTS ix_documents_application_id ON public.documents (application_id);
CREATE INDEX IF NOT EXISTS ix_documents_knowledge_base_id ON public.documents (knowledge_base_id);
CREATE INDEX IF NOT EXISTS ix_documents_status ON public.documents (status);
CREATE INDEX IF NOT EXISTS ix_documents_source_type ON public.documents (source_type);
DROP TRIGGER IF EXISTS documents_set_updated_at ON public.documents;
CREATE TRIGGER documents_set_updated_at
BEFORE UPDATE ON public.documents
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

-- Conversations table
CREATE TABLE IF NOT EXISTS public.conversations (
    id UUID PRIMARY KEY,
    application_id UUID NOT NULL,
    conversation_identity varchar(255) NOT NULL,
    title varchar(255),
    summary text,
    is_active boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT NOW(),
    updated_at timestamptz NOT NULL DEFAULT NOW(),
    CONSTRAINT fk_conversations_application FOREIGN KEY (application_id) REFERENCES public.applications(id) ON DELETE CASCADE
);

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'conversations'
          AND column_name = 'id' AND data_type <> 'uuid'
    ) THEN
        ALTER TABLE public.conversations ALTER COLUMN id TYPE UUID USING id::uuid;
    END IF;
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'conversations'
          AND column_name = 'application_id' AND data_type <> 'uuid'
    ) THEN
        ALTER TABLE public.conversations ALTER COLUMN application_id TYPE UUID USING application_id::uuid;
    END IF;
END $$;

ALTER TABLE public.conversations
    ADD COLUMN IF NOT EXISTS conversation_identity varchar(255),
    ADD COLUMN IF NOT EXISTS title varchar(255),
    ADD COLUMN IF NOT EXISTS summary text,
    ADD COLUMN IF NOT EXISTS is_active boolean DEFAULT true,
    ADD COLUMN IF NOT EXISTS created_at timestamptz DEFAULT NOW(),
    ADD COLUMN IF NOT EXISTS updated_at timestamptz DEFAULT NOW();

ALTER TABLE public.conversations
    ALTER COLUMN application_id SET NOT NULL,
    ALTER COLUMN conversation_identity SET NOT NULL,
    ALTER COLUMN is_active SET DEFAULT true,
    ALTER COLUMN created_at SET DEFAULT NOW(),
    ALTER COLUMN updated_at SET DEFAULT NOW();

CREATE INDEX IF NOT EXISTS ix_conversations_application_id ON public.conversations (application_id);
CREATE INDEX IF NOT EXISTS ix_conversations_conversation_identity ON public.conversations (conversation_identity);
CREATE INDEX IF NOT EXISTS ix_conversations_is_active ON public.conversations (is_active);
DROP TRIGGER IF EXISTS conversations_set_updated_at ON public.conversations;
CREATE TRIGGER conversations_set_updated_at
BEFORE UPDATE ON public.conversations
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

-- Messages table
CREATE TABLE IF NOT EXISTS public.messages (
    id UUID PRIMARY KEY,
    conversation_id UUID NOT NULL,
    role varchar(50) NOT NULL,
    content text NOT NULL,
    sequence_number integer NOT NULL,
    citations_json text,
    metadata_json text,
    created_at timestamptz NOT NULL DEFAULT NOW(),
    updated_at timestamptz NOT NULL DEFAULT NOW(),
    CONSTRAINT fk_messages_conversation FOREIGN KEY (conversation_id) REFERENCES public.conversations(id) ON DELETE CASCADE
);

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'messages'
          AND column_name = 'id' AND data_type <> 'uuid'
    ) THEN
        ALTER TABLE public.messages ALTER COLUMN id TYPE UUID USING id::uuid;
    END IF;
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'messages'
          AND column_name = 'conversation_id' AND data_type <> 'uuid'
    ) THEN
        ALTER TABLE public.messages ALTER COLUMN conversation_id TYPE UUID USING conversation_id::uuid;
    END IF;
END $$;

ALTER TABLE public.messages
    ADD COLUMN IF NOT EXISTS role varchar(50),
    ADD COLUMN IF NOT EXISTS content text,
    ADD COLUMN IF NOT EXISTS sequence_number integer,
    ADD COLUMN IF NOT EXISTS citations_json text,
    ADD COLUMN IF NOT EXISTS metadata_json text,
    ADD COLUMN IF NOT EXISTS created_at timestamptz DEFAULT NOW(),
    ADD COLUMN IF NOT EXISTS updated_at timestamptz DEFAULT NOW();

ALTER TABLE public.messages
    ALTER COLUMN conversation_id SET NOT NULL,
    ALTER COLUMN role SET NOT NULL,
    ALTER COLUMN content SET NOT NULL,
    ALTER COLUMN sequence_number SET NOT NULL,
    ALTER COLUMN created_at SET DEFAULT NOW(),
    ALTER COLUMN updated_at SET DEFAULT NOW();

CREATE INDEX IF NOT EXISTS ix_messages_conversation_id ON public.messages (conversation_id);
CREATE INDEX IF NOT EXISTS ix_messages_role ON public.messages (role);
CREATE INDEX IF NOT EXISTS ix_messages_sequence_number ON public.messages (sequence_number);
DROP TRIGGER IF EXISTS messages_set_updated_at ON public.messages;
CREATE TRIGGER messages_set_updated_at
BEFORE UPDATE ON public.messages
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

-- Api keys table
CREATE TABLE IF NOT EXISTS public.api_keys (
    id UUID PRIMARY KEY,
    application_id UUID NOT NULL,
    name varchar(120) NOT NULL,
    key_prefix varchar(32) NOT NULL,
    key_hash text NOT NULL,
    is_active boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT NOW(),
    updated_at timestamptz NOT NULL DEFAULT NOW(),
    CONSTRAINT fk_api_keys_application FOREIGN KEY (application_id) REFERENCES public.applications(id) ON DELETE CASCADE
);

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'api_keys'
          AND column_name = 'id' AND data_type <> 'uuid'
    ) THEN
        ALTER TABLE public.api_keys ALTER COLUMN id TYPE UUID USING id::uuid;
    END IF;
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'api_keys'
          AND column_name = 'application_id' AND data_type <> 'uuid'
    ) THEN
        ALTER TABLE public.api_keys ALTER COLUMN application_id TYPE UUID USING application_id::uuid;
    END IF;
END $$;

ALTER TABLE public.api_keys
    ADD COLUMN IF NOT EXISTS name varchar(120),
    ADD COLUMN IF NOT EXISTS key_prefix varchar(32),
    ADD COLUMN IF NOT EXISTS key_hash text,
    ADD COLUMN IF NOT EXISTS is_active boolean DEFAULT true,
    ADD COLUMN IF NOT EXISTS created_at timestamptz DEFAULT NOW(),
    ADD COLUMN IF NOT EXISTS updated_at timestamptz DEFAULT NOW();

ALTER TABLE public.api_keys
    ALTER COLUMN application_id SET NOT NULL,
    ALTER COLUMN name SET NOT NULL,
    ALTER COLUMN key_prefix SET NOT NULL,
    ALTER COLUMN key_hash SET NOT NULL,
    ALTER COLUMN is_active SET DEFAULT true,
    ALTER COLUMN created_at SET DEFAULT NOW(),
    ALTER COLUMN updated_at SET DEFAULT NOW();

CREATE INDEX IF NOT EXISTS ix_api_keys_application_id ON public.api_keys (application_id);
CREATE INDEX IF NOT EXISTS ix_api_keys_key_prefix ON public.api_keys (key_prefix);
CREATE INDEX IF NOT EXISTS ix_api_keys_is_active ON public.api_keys (is_active);
DROP TRIGGER IF EXISTS api_keys_set_updated_at ON public.api_keys;
CREATE TRIGGER api_keys_set_updated_at
BEFORE UPDATE ON public.api_keys
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

-- Application settings table
CREATE TABLE IF NOT EXISTS public.application_settings (
    id UUID PRIMARY KEY,
    application_id UUID NOT NULL UNIQUE,
    llm_temperature varchar(20) NOT NULL DEFAULT '0.2',
    max_context_messages integer NOT NULL DEFAULT 12,
    inactivity_timeout_minutes integer NOT NULL DEFAULT 30,
    retention_days integer NOT NULL DEFAULT 30,
    prompt_system_template text,
    created_at timestamptz NOT NULL DEFAULT NOW(),
    updated_at timestamptz NOT NULL DEFAULT NOW(),
    CONSTRAINT fk_application_settings_application
        FOREIGN KEY (application_id) REFERENCES public.applications(id) ON DELETE CASCADE
);

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'application_settings'
          AND column_name = 'id' AND data_type <> 'uuid'
    ) THEN
        ALTER TABLE public.application_settings ALTER COLUMN id TYPE UUID USING id::uuid;
    END IF;
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'application_settings'
          AND column_name = 'application_id' AND data_type <> 'uuid'
    ) THEN
        ALTER TABLE public.application_settings ALTER COLUMN application_id TYPE UUID USING application_id::uuid;
    END IF;
END $$;

ALTER TABLE public.application_settings
    ADD COLUMN IF NOT EXISTS llm_temperature varchar(20) DEFAULT '0.2',
    ADD COLUMN IF NOT EXISTS max_context_messages integer DEFAULT 12,
    ADD COLUMN IF NOT EXISTS inactivity_timeout_minutes integer DEFAULT 30,
    ADD COLUMN IF NOT EXISTS retention_days integer DEFAULT 30,
    ADD COLUMN IF NOT EXISTS prompt_system_template text,
    ADD COLUMN IF NOT EXISTS created_at timestamptz DEFAULT NOW(),
    ADD COLUMN IF NOT EXISTS updated_at timestamptz DEFAULT NOW();

ALTER TABLE public.application_settings
    ALTER COLUMN application_id SET NOT NULL,
    ALTER COLUMN llm_temperature SET DEFAULT '0.2',
    ALTER COLUMN max_context_messages SET DEFAULT 12,
    ALTER COLUMN inactivity_timeout_minutes SET DEFAULT 30,
    ALTER COLUMN retention_days SET DEFAULT 30,
    ALTER COLUMN created_at SET DEFAULT NOW(),
    ALTER COLUMN updated_at SET DEFAULT NOW();

CREATE INDEX IF NOT EXISTS ix_application_settings_application_id ON public.application_settings (application_id);
DROP TRIGGER IF EXISTS application_settings_set_updated_at ON public.application_settings;
CREATE TRIGGER application_settings_set_updated_at
BEFORE UPDATE ON public.application_settings
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

-- Widgets table
CREATE TABLE IF NOT EXISTS public.widgets (
    id UUID PRIMARY KEY,
    application_id UUID NOT NULL,
    display_name varchar(150) NOT NULL,
    public_key varchar(150) UNIQUE,
    theme varchar(50) NOT NULL DEFAULT 'light',
    launcher_label varchar(100),
    welcome_message text,
    placeholder_text varchar(255),
    is_enabled boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT NOW(),
    updated_at timestamptz NOT NULL DEFAULT NOW(),
    CONSTRAINT fk_widgets_application FOREIGN KEY (application_id) REFERENCES public.applications(id) ON DELETE CASCADE
);

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'widgets'
          AND column_name = 'id' AND data_type <> 'uuid'
    ) THEN
        ALTER TABLE public.widgets ALTER COLUMN id TYPE UUID USING id::uuid;
    END IF;
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'widgets'
          AND column_name = 'application_id' AND data_type <> 'uuid'
    ) THEN
        ALTER TABLE public.widgets ALTER COLUMN application_id TYPE UUID USING application_id::uuid;
    END IF;
END $$;

ALTER TABLE public.widgets
    ADD COLUMN IF NOT EXISTS display_name varchar(150),
    ADD COLUMN IF NOT EXISTS public_key varchar(150),
    ADD COLUMN IF NOT EXISTS theme varchar(50) DEFAULT 'light',
    ADD COLUMN IF NOT EXISTS launcher_label varchar(100),
    ADD COLUMN IF NOT EXISTS welcome_message text,
    ADD COLUMN IF NOT EXISTS placeholder_text varchar(255),
    ADD COLUMN IF NOT EXISTS is_enabled boolean DEFAULT true,
    ADD COLUMN IF NOT EXISTS created_at timestamptz DEFAULT NOW(),
    ADD COLUMN IF NOT EXISTS updated_at timestamptz DEFAULT NOW();

ALTER TABLE public.widgets
    ALTER COLUMN application_id SET NOT NULL,
    ALTER COLUMN display_name SET NOT NULL,
    ALTER COLUMN theme SET DEFAULT 'light',
    ALTER COLUMN is_enabled SET DEFAULT true,
    ALTER COLUMN created_at SET DEFAULT NOW(),
    ALTER COLUMN updated_at SET DEFAULT NOW();

CREATE INDEX IF NOT EXISTS ix_widgets_application_id ON public.widgets (application_id);
CREATE INDEX IF NOT EXISTS ix_widgets_is_enabled ON public.widgets (is_enabled);
CREATE INDEX IF NOT EXISTS ix_widgets_public_key ON public.widgets (public_key);
DROP TRIGGER IF EXISTS widgets_set_updated_at ON public.widgets;
CREATE TRIGGER widgets_set_updated_at
BEFORE UPDATE ON public.widgets
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

-- Vector store table used by the ingestion pipeline.
-- NOTE: the embedding dimension must match VECTOR_STORE_DIMENSION in the
-- backend .env (1024 for qwen3-embedding-8b, 768 for nomic-embed-text).
-- If you change the dimension, drop and recreate this table.
CREATE TABLE IF NOT EXISTS public.document_chunks (
    chunk_id text PRIMARY KEY,
    knowledge_base_id text NOT NULL,
    document_id text NOT NULL,
    document_title text NOT NULL,
    content text NOT NULL,
    source_uri text,
    metadata_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    embedding vector(1024) NOT NULL
);

CREATE INDEX IF NOT EXISTS document_chunks_kb_idx ON public.document_chunks (knowledge_base_id);
CREATE INDEX IF NOT EXISTS document_chunks_content_fts_idx ON public.document_chunks USING gin (to_tsvector('english', content));
CREATE INDEX IF NOT EXISTS document_chunks_embedding_idx ON public.document_chunks USING hnsw (embedding vector_cosine_ops);

-- Final schema note:
-- The application layer stores allowed_origins as a list/array on Postgres, not as a comma-delimited string.
-- If you have a legacy row set, convert any existing comma-delimited values before running the app.
-- Example:
-- UPDATE public.applications
-- SET allowed_origins = string_to_array(allowed_origins, ',')
-- WHERE allowed_origins IS NOT NULL AND NOT (allowed_origins @> ARRAY[]::text[]);