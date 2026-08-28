#!/usr/bin/env bash
set -euo pipefail

# Deploy the ADK agent after the Google Cloud project has billing enabled.
# Usage:
#   GOOGLE_CLOUD_PROJECT=my-project \
#   GOOGLE_CLOUD_LOCATION=us-central1 \
#   bash scripts/deploy_adk_cloud_run.sh

PROJECT_ID="${GOOGLE_CLOUD_PROJECT:-}"
REGION="${GOOGLE_CLOUD_LOCATION:-us-central1}"
SERVICE_NAME="${SERVICE_NAME:-signalsweep-agent}"
RUNTIME_SERVICE_ACCOUNT="${RUNTIME_SERVICE_ACCOUNT:-signalsweep-runtime@${PROJECT_ID}.iam.gserviceaccount.com}"
MODEL_LOCATION="${MODEL_LOCATION:-global}"

if [[ -z "$PROJECT_ID" ]]; then
  echo "Missing GOOGLE_CLOUD_PROJECT." >&2
  exit 2
fi

if ! command -v gcloud >/dev/null 2>&1; then
  echo "gcloud is not installed or is not on PATH." >&2
  exit 2
fi

if ! command -v adk >/dev/null 2>&1; then
  echo "adk is not installed or is not on PATH. Install google-adk first." >&2
  exit 2
fi

BILLING_ENABLED="$(gcloud billing projects describe "$PROJECT_ID" --format='value(billingEnabled)')"
if [[ "$BILLING_ENABLED" != "True" ]]; then
  echo "Billing is not enabled for project $PROJECT_ID." >&2
  echo "Attach the hackathon credits/billing account, then rerun this script." >&2
  exit 3
fi

gcloud config set project "$PROJECT_ID" >/dev/null
gcloud services enable \
  aiplatform.googleapis.com \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  artifactregistry.googleapis.com \
  --project="$PROJECT_ID"

cd "$(dirname "$0")/../src"
adk deploy cloud_run \
  --project="$PROJECT_ID" \
  --region="$REGION" \
  --service_name="$SERVICE_NAME" \
  signalsweep \
  -- \
  --service-account="$RUNTIME_SERVICE_ACCOUNT" \
  --set-env-vars="GOOGLE_CLOUD_LOCATION=$MODEL_LOCATION,GOOGLE_GENAI_USE_VERTEXAI=TRUE"
