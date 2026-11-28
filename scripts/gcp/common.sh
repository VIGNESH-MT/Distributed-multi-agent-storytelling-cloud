#!/usr/bin/env bash
# Shared configuration and helpers for the GCP deployment scripts.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
CONFIG_FILE="${CONFIG_FILE:-$SCRIPT_DIR/config.env}"

if [[ ! -f "$CONFIG_FILE" ]]; then
  echo "Missing $CONFIG_FILE" >&2
  echo "Run: cp scripts/gcp/config.env.example scripts/gcp/config.env  (then edit it)" >&2
  exit 1
fi

# shellcheck disable=SC1090
source "$CONFIG_FILE"

: "${PROJECT_ID:?PROJECT_ID must be set in config.env}"
REGION="${REGION:-europe-west2}"
NETWORK="${NETWORK:-storytelling-vpc}"
SUBNET="${SUBNET:-storytelling-subnet}"
SUBNET_RANGE="${SUBNET_RANGE:-10.10.0.0/20}"
PODS_RANGE="${PODS_RANGE:-10.20.0.0/16}"
SERVICES_RANGE="${SERVICES_RANGE:-10.30.0.0/20}"
CLUSTER_NAME="${CLUSTER_NAME:-storytelling-gke}"
NODE_MACHINE_TYPE="${NODE_MACHINE_TYPE:-e2-standard-2}"
MIN_NODES="${MIN_NODES:-3}"
MAX_NODES="${MAX_NODES:-4}"
DB_INSTANCE="${DB_INSTANCE:-storytelling-db}"
DB_NAME="${DB_NAME:-storytelling}"
DB_USER="${DB_USER:-storyapp}"
DB_AVAILABILITY="${DB_AVAILABILITY:-ZONAL}"
DB_TIER="${DB_TIER:-db-g1-small}"
AR_REPO="${AR_REPO:-storytelling}"
BUILD_WITH="${BUILD_WITH:-cloudbuild}"
STATIC_IP_NAME="${STATIC_IP_NAME:-storytelling-ip}"
AGENT_PROVIDER="${AGENT_PROVIDER:-gemini}"
GEMINI_MODEL="${GEMINI_MODEL:-gemini-3.6-flash}"
MOCK_AGENT_CPU_MS="${MOCK_AGENT_CPU_MS:-0}"

# Every gcloud command in these scripts targets this project.
export CLOUDSDK_CORE_PROJECT="$PROJECT_ID"

NAMESPACE="storytelling"
PSA_RANGE_NAME="${NETWORK}-psa-range"
ROUTER_NAME="${NETWORK}-router"
NAT_NAME="${NETWORK}-nat"
NODE_SA_NAME="storytelling-gke-nodes"
NODE_SA_EMAIL="${NODE_SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"
DB_PASSWORD_SECRET="storytelling-db-password"
GEMINI_KEY_SECRET="gemini-api-key"
IMAGE_REPO="${REGION}-docker.pkg.dev/${PROJECT_ID}/${AR_REPO}/storytelling-app"
IMAGE_FILE="$SCRIPT_DIR/.image"

log() {
  printf '\n\033[1;34m==> %s\033[0m\n' "$*"
}

warn() {
  printf '\033[1;33mWARNING: %s\033[0m\n' "$*" >&2
}

die() {
  printf '\033[1;31mERROR: %s\033[0m\n' "$*" >&2
  exit 1
}

# Succeeds when the given command succeeds, hiding its output.
exists() {
  "$@" >/dev/null 2>&1
}

# Retries a command (IAM changes can take a few seconds to propagate).
retry() {
  local attempt=1
  until "$@"; do
    if (( attempt >= 6 )); then
      return 1
    fi
    echo "  ...retrying in 10s (attempt $attempt)"
    sleep 10
    attempt=$((attempt + 1))
  done
}

grant_project_role() {
  local member="$1" role="$2"
  retry gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member="$member" \
    --role="$role" \
    --condition=None \
    --quiet >/dev/null
}

db_private_ip() {
  gcloud sql instances describe "$DB_INSTANCE" --format=json \
    | python3 -c 'import json,sys; print(next(a["ipAddress"] for a in json.load(sys.stdin)["ipAddresses"] if a["type"] == "PRIVATE"))'
}
