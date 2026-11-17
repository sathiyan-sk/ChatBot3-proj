#!/usr/bin/env bash
set -Eeuo pipefail

APP_DIR="/home/sathyan/Myfile/chatbot3"
WEB_ROOT="/var/www/chatbot"
BACKEND_SERVICE="chatbot-backend.service"
BRANCH="main"

# Usage: ./deploy.sh <commit_sha> <frontend_changed> <backend_changed>
TARGET_COMMIT="${1:-}"
DEPLOY_FRONTEND="${2:-}"
DEPLOY_BACKEND="${3:-}"

if [[ ! "$TARGET_COMMIT" =~ ^[0-9a-fA-F]{40}$ ]]; then
    echo "ERROR: A valid 40-character commit SHA is required."
    exit 1
fi

if [[ "$DEPLOY_FRONTEND" != "true" && "$DEPLOY_FRONTEND" != "false" ]]; then
    echo "ERROR: frontend_changed must be true or false."
    exit 1
fi

if [[ "$DEPLOY_BACKEND" != "true" && "$DEPLOY_BACKEND" != "false" ]]; then
    echo "ERROR: backend_changed must be true or false."
    exit 1
fi

cd "$APP_DIR"
# Initialize NVM for non-interactive SSH sessions.
export NVM_DIR="/home/sathyan/.nvm"

if [[ -s "$NVM_DIR/nvm.sh" ]]; then
    source "$NVM_DIR/nvm.sh"
    nvm use --silent default
else
    echo "ERROR: NVM initialization script not found."
    exit 1
fi

# Prevent concurrent deployments.
exec 9>/tmp/chatbot-deploy.lock
if ! flock -n 9; then
    echo "ERROR: Another deployment is already running."
    exit 1
fi

# Required tools.
for tool in git npm rsync curl flock; do
    command -v "$tool" >/dev/null 2>&1 || {
        echo "ERROR: Required command not found: $tool"
        exit 1
    }
done

# Protect local configuration and uncommitted source changes.
if [[ -n "$(git status --porcelain --untracked-files=normal)" ]]; then
    echo "ERROR: Working tree is not clean. Aborting deployment."
    git status --short
    exit 1
fi

if [[ ! -f frontend/.env.production ]]; then
    echo "ERROR: frontend/.env.production is missing."
    exit 1
fi

if [[ ! -x backend/.venv/bin/pip ]]; then
    echo "ERROR: Backend virtual environment is missing."
    exit 1
fi

OLD_COMMIT="$(git rev-parse HEAD)"

echo "Fetching latest main branch..."
git fetch origin "$BRANCH"

if ! git cat-file -e "${TARGET_COMMIT}^{commit}" 2>/dev/null; then
    echo "ERROR: Target commit is not available locally."
    exit 1
fi

if ! git merge-base --is-ancestor "$TARGET_COMMIT" "origin/$BRANCH"; then
    echo "ERROR: Target commit is not part of origin/$BRANCH."
    exit 1
fi

# Detect dependency changes before moving the working tree.
REQUIREMENTS_CHANGED=false
if ! git diff --quiet "$OLD_COMMIT" "$TARGET_COMMIT" -- backend/requirements.txt; then
    REQUIREMENTS_CHANGED=true
fi

if [[ "$REQUIREMENTS_CHANGED" == "true" && "$DEPLOY_BACKEND" != "true" ]]; then
    echo "ERROR: Backend requirements changed, but backend deployment was disabled."
    exit 1
fi

echo "Updating source to $TARGET_COMMIT..."
git checkout "$BRANCH"
git reset --hard "$TARGET_COMMIT"

STAGE_ADMIN=""
STAGE_WIDGET=""

cleanup() {
    [[ -z "$STAGE_ADMIN" ]] || rm -rf -- "$STAGE_ADMIN"
    [[ -z "$STAGE_WIDGET" ]] || rm -rf -- "$STAGE_WIDGET"
}
trap cleanup EXIT

# Frontend deployment.
if [[ "$DEPLOY_FRONTEND" == "true" ]]; then
    echo "Building frontend..."
    cd "$APP_DIR/frontend"
    npm ci
    npm run build

    if [[ ! -f dist/index.html || ! -f dist/widget/widget.js || ! -f dist/widget/widget.css ]]; then
        echo "ERROR: Frontend build output is incomplete."
        exit 1
    fi

    STAGE_ADMIN="$(mktemp -d "$WEB_ROOT/.admin-deploy.XXXXXX")"
    STAGE_WIDGET="$(mktemp -d "$WEB_ROOT/.widget-deploy.XXXXXX")"

    rsync -a --delete "$APP_DIR/frontend/dist/" "$STAGE_ADMIN/"
    rsync -a --delete "$APP_DIR/frontend/dist/widget/" "$STAGE_WIDGET/"

    echo "Publishing dashboard assets..."
    rsync -a --delete "$STAGE_ADMIN/" "$WEB_ROOT/admin/"

    echo "Publishing widget assets..."
    rsync -a --delete "$STAGE_WIDGET/" "$WEB_ROOT/widget/"
fi

# Backend deployment.
if [[ "$DEPLOY_BACKEND" == "true" ]]; then
    cd "$APP_DIR"

    if [[ "$REQUIREMENTS_CHANGED" == "true" ]]; then
        echo "Installing updated backend dependencies..."
        backend/.venv/bin/pip install -r backend/requirements.txt
    else
        echo "Backend requirements unchanged; skipping dependency installation."
    fi

    echo "Restarting backend service..."
    sudo -n systemctl restart "$BACKEND_SERVICE"

    echo "Checking backend health..."
    for attempt in {1..10}; do
        if curl --silent --fail http://127.0.0.1:8010/health >/dev/null; then
            echo "Backend health check passed."
            break
        fi

        if [[ "$attempt" -eq 10 ]]; then
            echo "ERROR: Backend health check failed."
            sudo -n systemctl status "$BACKEND_SERVICE" --no-pager || true
            exit 1
        fi

        sleep 3
    done
fi

echo "Deployment completed successfully: $TARGET_COMMIT"
