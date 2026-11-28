#!/usr/bin/env bash
# Deploys (or updates) the application on GKE:
#   secrets -> config -> database migration Job -> agents -> API -> Ingress

source "$(dirname "${BASH_SOURCE[0]}")/common.sh"

IMAGE_URI="${IMAGE_URI:-$(cat "$IMAGE_FILE" 2>/dev/null || true)}"
[[ -n "$IMAGE_URI" ]] || die "No image found. Run scripts/gcp/02-build.sh first (or set IMAGE_URI)."

case "$AGENT_PROVIDER" in
  gemini|mock) ;;
  *) die "AGENT_PROVIDER must be 'gemini' or 'mock' (got '$AGENT_PROVIDER')" ;;
esac

log "Connecting kubectl to $CLUSTER_NAME"
gcloud container clusters get-credentials "$CLUSTER_NAME" --region "$REGION"

log "Reading configuration and secrets"
DB_HOST="$(db_private_ip)"
DB_PASSWORD="$(gcloud secrets versions access latest --secret="$DB_PASSWORD_SECRET")"

GEMINI_API_KEY=""
if exists gcloud secrets describe "$GEMINI_KEY_SECRET"; then
  GEMINI_API_KEY="$(gcloud secrets versions access latest --secret="$GEMINI_KEY_SECRET")"
elif [[ "$AGENT_PROVIDER" == "gemini" ]]; then
  die "AGENT_PROVIDER=gemini but Secret Manager has no '$GEMINI_KEY_SECRET'. Create it (see docs/gcp-deployment.md) or set AGENT_PROVIDER=mock."
fi

echo "  image:          $IMAGE_URI"
echo "  Cloud SQL host: $DB_HOST"
echo "  agent provider: $AGENT_PROVIDER (MOCK_AGENT_CPU_MS=$MOCK_AGENT_CPU_MS)"

# ------------------------------------------------------------- Render
RENDER_DIR="$(mktemp -d)"
trap 'rm -rf "$RENDER_DIR"' EXIT

render() {
  sed \
    -e "s|__IMAGE__|${IMAGE_URI}|g" \
    -e "s|__DB_HOST__|${DB_HOST}|g" \
    -e "s|__DB_NAME__|${DB_NAME}|g" \
    -e "s|__AGENT_PROVIDER__|${AGENT_PROVIDER}|g" \
    -e "s|__GEMINI_MODEL__|${GEMINI_MODEL}|g" \
    -e "s|__MOCK_AGENT_CPU_MS__|${MOCK_AGENT_CPU_MS}|g" \
    -e "s|__STATIC_IP_NAME__|${STATIC_IP_NAME}|g" \
    -e "s|__CONFIG_HASH__|${CONFIG_HASH:-}|g" \
    "$1" > "$2"
}

render "$REPO_ROOT/k8s/gke/20-config.yaml" "$RENDER_DIR/20-config.yaml"

# Pods only pick up ConfigMap/Secret changes on restart, so a hash of the
# configuration is stamped on every pod template to trigger a rollout.
CONFIG_HASH="$(
  { cat "$RENDER_DIR/20-config.yaml"; printf '%s|%s' "$DB_PASSWORD" "$GEMINI_API_KEY"; } \
    | sha256sum | cut -c1-16
)"

for manifest in "$REPO_ROOT"/k8s/gke/*.yaml; do
  render "$manifest" "$RENDER_DIR/$(basename "$manifest")"
done
render "$REPO_ROOT/k8s/gke/jobs/migrate.yaml" "$RENDER_DIR/migrate-job.yaml"

# -------------------------------------------------------------- Apply
log "Namespace, quotas and configuration"
kubectl apply -f "$RENDER_DIR/00-namespace.yaml"

kubectl -n "$NAMESPACE" create secret generic storytelling-db-credentials \
  --from-literal=POSTGRES_USER="$DB_USER" \
  --from-literal=POSTGRES_PASSWORD="$DB_PASSWORD" \
  --dry-run=client -o yaml | kubectl apply -f -

if [[ -n "$GEMINI_API_KEY" ]]; then
  kubectl -n "$NAMESPACE" create secret generic storytelling-model-secret \
    --from-literal=GEMINI_API_KEY="$GEMINI_API_KEY" \
    --dry-run=client -o yaml | kubectl apply -f -
fi

kubectl apply \
  -f "$RENDER_DIR/10-governance.yaml" \
  -f "$RENDER_DIR/20-config.yaml" \
  -f "$RENDER_DIR/30-network-policy.yaml"

log "Running database migrations (alembic upgrade head)"
kubectl -n "$NAMESPACE" delete job storytelling-migrate --ignore-not-found --wait=true
kubectl apply -f "$RENDER_DIR/migrate-job.yaml"

migration_done=""
for _ in $(seq 1 120); do
  succeeded="$(kubectl -n "$NAMESPACE" get job storytelling-migrate -o jsonpath='{.status.succeeded}' 2>/dev/null || true)"
  failed="$(kubectl -n "$NAMESPACE" get job storytelling-migrate -o jsonpath='{.status.conditions[?(@.type=="Failed")].status}' 2>/dev/null || true)"
  if [[ "$succeeded" == "1" ]]; then
    migration_done="yes"
    break
  fi
  if [[ "$failed" == "True" ]]; then
    break
  fi
  sleep 5
done

if [[ -z "$migration_done" ]]; then
  kubectl -n "$NAMESPACE" logs job/storytelling-migrate --tail=50 || true
  die "Database migration did not complete. See logs above."
fi
kubectl -n "$NAMESPACE" logs job/storytelling-migrate --tail=20 || true

log "Agents, API and load balancer"
kubectl apply \
  -f "$RENDER_DIR/40-agents.yaml" \
  -f "$RENDER_DIR/50-api.yaml" \
  -f "$RENDER_DIR/60-ingress.yaml"

for deployment in \
  storytelling-plot-agent \
  storytelling-character-agent \
  storytelling-critic-agent \
  storytelling-api; do
  kubectl -n "$NAMESPACE" rollout status "deployment/$deployment" --timeout=600s
done

STATIC_IP="$(gcloud compute addresses describe "$STATIC_IP_NAME" --global --format='value(address)')"

log "Deployment complete"
kubectl -n "$NAMESPACE" get pods -o wide
echo
kubectl -n "$NAMESPACE" get hpa
echo
echo "Application URL: http://${STATIC_IP}/"
echo "On the first deployment the load balancer needs 5-10 minutes before it"
echo "answers (HTTP 404/502 until then). Check with:"
echo "  curl http://${STATIC_IP}/health"
