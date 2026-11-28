#!/usr/bin/env bash
# Provisions the GCP infrastructure. Safe to re-run: existing resources are kept.
#
#   VPC + subnet (VPC-native ranges) -> Cloud Router + Cloud NAT
#   -> Private Service Access -> Cloud SQL (private IP only)
#   -> Artifact Registry -> node service account -> static IP
#   -> regional private-node GKE cluster (Dataplane V2, autoscaling)

source "$(dirname "${BASH_SOURCE[0]}")/common.sh"

log "Project: $PROJECT_ID  Region: $REGION"

log "Enabling required APIs (first run can take a few minutes)"
gcloud services enable \
  compute.googleapis.com \
  container.googleapis.com \
  sqladmin.googleapis.com \
  servicenetworking.googleapis.com \
  artifactregistry.googleapis.com \
  cloudbuild.googleapis.com \
  secretmanager.googleapis.com \
  iam.googleapis.com \
  logging.googleapis.com \
  monitoring.googleapis.com

# ------------------------------------------------------------------ Network
log "VPC network $NETWORK"
if ! exists gcloud compute networks describe "$NETWORK"; then
  gcloud compute networks create "$NETWORK" --subnet-mode=custom
fi

log "Subnet $SUBNET (nodes $SUBNET_RANGE, pods $PODS_RANGE, services $SERVICES_RANGE)"
if ! exists gcloud compute networks subnets describe "$SUBNET" --region "$REGION"; then
  gcloud compute networks subnets create "$SUBNET" \
    --network "$NETWORK" \
    --region "$REGION" \
    --range "$SUBNET_RANGE" \
    --secondary-range "pods=$PODS_RANGE,services=$SERVICES_RANGE" \
    --enable-private-ip-google-access
fi

log "Cloud Router + Cloud NAT (outbound internet for private nodes, e.g. Gemini API)"
if ! exists gcloud compute routers describe "$ROUTER_NAME" --region "$REGION"; then
  gcloud compute routers create "$ROUTER_NAME" \
    --network "$NETWORK" \
    --region "$REGION"
fi
if ! exists gcloud compute routers nats describe "$NAT_NAME" --router "$ROUTER_NAME" --region "$REGION"; then
  gcloud compute routers nats create "$NAT_NAME" \
    --router "$ROUTER_NAME" \
    --region "$REGION" \
    --auto-allocate-nat-external-ips \
    --nat-all-subnet-ip-ranges
fi

log "Private Service Access (private IP connectivity to Cloud SQL)"
if ! exists gcloud compute addresses describe "$PSA_RANGE_NAME" --global; then
  gcloud compute addresses create "$PSA_RANGE_NAME" \
    --global \
    --purpose=VPC_PEERING \
    --prefix-length=20 \
    --network="$NETWORK"
fi
PEERINGS="$(gcloud services vpc-peerings list --network="$NETWORK" --format='value(peering)' 2>/dev/null || true)"
if [[ -z "$PEERINGS" ]]; then
  gcloud services vpc-peerings connect \
    --service=servicenetworking.googleapis.com \
    --ranges="$PSA_RANGE_NAME" \
    --network="$NETWORK"
fi

# ----------------------------------------------------------------- Database
log "Database password in Secret Manager ($DB_PASSWORD_SECRET)"
if ! exists gcloud secrets describe "$DB_PASSWORD_SECRET"; then
  python3 -c 'import secrets; print(secrets.token_urlsafe(24), end="")' \
    | gcloud secrets create "$DB_PASSWORD_SECRET" \
        --replication-policy=automatic \
        --data-file=-
fi
DB_PASSWORD="$(gcloud secrets versions access latest --secret="$DB_PASSWORD_SECRET")"

log "Cloud SQL instance $DB_INSTANCE ($DB_TIER, $DB_AVAILABILITY) - takes ~10 minutes"
if ! exists gcloud sql instances describe "$DB_INSTANCE"; then
  gcloud sql instances create "$DB_INSTANCE" \
    --database-version=POSTGRES_16 \
    --edition=ENTERPRISE \
    --tier="$DB_TIER" \
    --region="$REGION" \
    --availability-type="$DB_AVAILABILITY" \
    --network="projects/$PROJECT_ID/global/networks/$NETWORK" \
    --no-assign-ip \
    --storage-type=SSD \
    --storage-size=10 \
    --storage-auto-increase \
    --backup-start-time=02:00
fi

if ! exists gcloud sql databases describe "$DB_NAME" --instance "$DB_INSTANCE"; then
  gcloud sql databases create "$DB_NAME" --instance "$DB_INSTANCE"
fi

DB_USERS="$(gcloud sql users list --instance "$DB_INSTANCE" --format='value(name)')"
if grep -qx "$DB_USER" <<< "$DB_USERS"; then
  gcloud sql users set-password "$DB_USER" --instance "$DB_INSTANCE" --password "$DB_PASSWORD" >/dev/null
else
  gcloud sql users create "$DB_USER" --instance "$DB_INSTANCE" --password "$DB_PASSWORD" >/dev/null
fi

# ------------------------------------------------------------------- Images
log "Artifact Registry repository $AR_REPO"
if ! exists gcloud artifacts repositories describe "$AR_REPO" --location "$REGION"; then
  gcloud artifacts repositories create "$AR_REPO" \
    --repository-format=docker \
    --location="$REGION" \
    --description="Storytelling container images"
fi

if [[ "$BUILD_WITH" == "cloudbuild" ]]; then
  log "Granting Cloud Build (default compute service account) push and log access"
  PROJECT_NUMBER="$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')"
  BUILD_SA="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"
  for role in roles/artifactregistry.writer roles/logging.logWriter roles/storage.objectViewer; do
    grant_project_role "$BUILD_SA" "$role"
  done
fi

# --------------------------------------------------------- Node identity
log "Least-privilege node service account $NODE_SA_EMAIL"
if ! exists gcloud iam service-accounts describe "$NODE_SA_EMAIL"; then
  gcloud iam service-accounts create "$NODE_SA_NAME" \
    --display-name="Storytelling GKE nodes"
fi
for role in \
  roles/logging.logWriter \
  roles/monitoring.metricWriter \
  roles/monitoring.viewer \
  roles/stackdriver.resourceMetadata.writer \
  roles/autoscaling.metricsWriter \
  roles/artifactregistry.reader; do
  grant_project_role "serviceAccount:$NODE_SA_EMAIL" "$role"
done

# ------------------------------------------------------------ Static IP
log "Global static IP $STATIC_IP_NAME for the load balancer"
if ! exists gcloud compute addresses describe "$STATIC_IP_NAME" --global; then
  gcloud compute addresses create "$STATIC_IP_NAME" --global
fi

# ------------------------------------------------------------------ GKE
log "GKE cluster $CLUSTER_NAME (regional, private nodes) - takes ~10 minutes"
if ! exists gcloud container clusters describe "$CLUSTER_NAME" --region "$REGION"; then
  gcloud container clusters create "$CLUSTER_NAME" \
    --region "$REGION" \
    --release-channel regular \
    --network "$NETWORK" \
    --subnetwork "$SUBNET" \
    --enable-ip-alias \
    --cluster-secondary-range-name pods \
    --services-secondary-range-name services \
    --enable-private-nodes \
    --enable-dataplane-v2 \
    --workload-pool "${PROJECT_ID}.svc.id.goog" \
    --service-account "$NODE_SA_EMAIL" \
    --machine-type "$NODE_MACHINE_TYPE" \
    --disk-type pd-balanced \
    --disk-size 50 \
    --num-nodes 1 \
    --enable-autoscaling \
    --total-min-nodes "$MIN_NODES" \
    --total-max-nodes "$MAX_NODES" \
    --shielded-secure-boot \
    --shielded-integrity-monitoring \
    --logging SYSTEM,WORKLOAD \
    --monitoring SYSTEM,POD,DEPLOYMENT,HPA \
    --enable-managed-prometheus
fi

gcloud container clusters get-credentials "$CLUSTER_NAME" --region "$REGION"

log "Provisioning complete"
kubectl get nodes -o wide -L topology.kubernetes.io/zone
echo
echo "Cloud SQL private IP: $(db_private_ip)"
echo "Static IP:            $(gcloud compute addresses describe "$STATIC_IP_NAME" --global --format='value(address)')"
echo
echo "Next: scripts/gcp/02-build.sh"
