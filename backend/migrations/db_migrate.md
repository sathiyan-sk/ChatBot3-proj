Build the empty testing database with Alembic
Set DATABASE_URL to the testing project’s PostgreSQL connection string, then, from the backend directory, run

python -m alembic -c alembic.ini upgrade head
python -m alembic -c alembic.ini current

The first command runs the repository’s migrations in order; the second should report:0003_version_document_chunks
