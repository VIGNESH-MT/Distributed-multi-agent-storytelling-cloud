#!/usr/bin/env bash
# Builds the single application image (API + all agents) and pushes it to
# Artifact Registry, so every GKE node can pull it.

source "$(dirname "${BASH_SOURCE[0]}")/common.sh"

GIT_SHA="$(git -C "$REPO_ROOT" rev-parse --short HEAD 2>/dev/null || echo nogit)"
TAG="${IMAGE_TAG:-${GIT_SHA}-$(date -u +%Y%m%d%H%M%S)}"
IMAGE_URI="${IMAGE_REPO}:${TAG}"

log "Building $IMAGE_URI with $BUILD_WITH"

case "$BUILD_WITH" in
  cloudbuild)
    gcloud builds submit "$REPO_ROOT" \
      --config "$REPO_ROOT/cloudbuild.yaml" \
      --substitutions "_IMAGE=${IMAGE_REPO},_TAG=${TAG}"
    ;;
  docker)
    gcloud auth configure-docker "${REGION}-docker.pkg.dev" --quiet
    docker build -f "$REPO_ROOT/Containerfile" -t "$IMAGE_URI" "$REPO_ROOT"
    docker push "$IMAGE_URI"
    ;;
  *)
    die "BUILD_WITH must be 'cloudbuild' or 'docker' (got '$BUILD_WITH')"
    ;;
esac

echo "$IMAGE_URI" > "$IMAGE_FILE"

log "Image pushed: $IMAGE_URI"
echo "Next: scripts/gcp/03-deploy.sh"
