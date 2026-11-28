#!/usr/bin/env bash
# Deletes everything created by 01-provision.sh and 03-deploy.sh so the
# project stops incurring charges. Secret Manager secrets are kept unless
# DELETE_SECRETS=yes.

source "$(dirname "${BASH_SOURCE[0]}")/common.sh"

echo "This permanently deletes the cluster, the Cloud SQL database (all stories),"
echo "the network and the image repository in project '$PROJECT_ID'."
read -r -p "Type the project ID to confirm: " answer
[[ "$answer" == "$PROJECT_ID" ]] || die "Confirmation did not match; nothing deleted."

if exists gcloud container clusters describe "$CLUSTER_NAME" --region "$REGION"; then
  log "Removing the Ingress first so GKE deletes its load balancer"
  gcloud container clusters get-credentials "$CLUSTER_NAME" --region "$REGION" || true
  kubectl delete namespace "$NAMESPACE" --ignore-not-found --timeout=600s || true

  log "Deleting GKE cluster $CLUSTER_NAME"
  gcloud container clusters delete "$CLUSTER_NAME" --region "$REGION" --quiet || true
fi

log "Deleting Cloud SQL instance $DB_INSTANCE"
gcloud sql instances delete "$DB_INSTANCE" --quiet || true

log "Deleting static IP, image repository and node service account"
gcloud compute addresses delete "$STATIC_IP_NAME" --global --quiet || true
gcloud artifacts repositories delete "$AR_REPO" --location "$REGION" --quiet || true
gcloud iam service-accounts delete "$NODE_SA_EMAIL" --quiet || true

log "Deleting leftover load-balancer network endpoint groups and firewall rules"
NEGS="$(gcloud compute network-endpoint-groups list \
  --filter="network~/${NETWORK}\$" --format='value(name,zone.basename())' 2>/dev/null || true)"
while read -r name zone; do
  [[ -n "$name" ]] || continue
  gcloud compute network-endpoint-groups delete "$name" --zone "$zone" --quiet || true
done <<< "$NEGS"

RULES="$(gcloud compute firewall-rules list \
  --filter="network~/${NETWORK}\$" --format='value(name)' 2>/dev/null || true)"
while read -r rule; do
  [[ -n "$rule" ]] || continue
  gcloud compute firewall-rules delete "$rule" --quiet || true
done <<< "$RULES"

log "Deleting network: Private Service Access, NAT, router, subnet, VPC"
gcloud services vpc-peerings delete \
  --service=servicenetworking.googleapis.com \
  --network="$NETWORK" --quiet || warn "Peering not deleted (Cloud SQL may still be releasing it; re-run later)."
gcloud compute addresses delete "$PSA_RANGE_NAME" --global --quiet || true
gcloud compute routers nats delete "$NAT_NAME" --router "$ROUTER_NAME" --region "$REGION" --quiet || true
gcloud compute routers delete "$ROUTER_NAME" --region "$REGION" --quiet || true
gcloud compute networks subnets delete "$SUBNET" --region "$REGION" --quiet || true
gcloud compute networks delete "$NETWORK" --quiet || warn "Network not deleted yet; re-run this script in a few minutes."

if [[ "${DELETE_SECRETS:-no}" == "yes" ]]; then
  log "Deleting Secret Manager secrets"
  gcloud secrets delete "$DB_PASSWORD_SECRET" --quiet || true
  gcloud secrets delete "$GEMINI_KEY_SECRET" --quiet || true
fi

rm -f "$IMAGE_FILE"
log "Teardown finished. Check Billing > Reports in the console to confirm."
