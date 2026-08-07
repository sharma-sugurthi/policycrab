#!/bin/bash
set -e

# Project configuration
PROJECT_ID="project-9676fda5-8ba6-476c-8d9"
SERVICE_NAME="policycrab-backend"
REGION="us-east1"
IMAGE="us-east1-docker.pkg.dev/project-9676fda5-8ba6-476c-8d9/cloud-run-source-deploy/policycrab-backend:latest"

echo "🚀 Deploying Image to Cloud Run..."

# Navigate to backend directory
cd "$(dirname "$0")/.."

# Read .env file and build a comma-separated string of variables for Cloud Run
if [ ! -f .env ]; then
  echo "❌ Error: .env file not found!"
  exit 1
fi

SECRETS=""
while IFS='=' read -r key value; do
  # Ignore comments and empty lines
  if [[ $key != \#* ]] && [[ -n $key ]]; then
    value=$(echo "$value" | sed -e 's/^"//' -e 's/"$//' -e "s/^'//" -e "s/'$//")
    escaped_value=$(echo "$value" | sed 's/,/\\,/g')
    SECRETS="${SECRETS}${key}=${escaped_value},"
  fi
done < .env
SECRETS=${SECRETS%,}

echo "📦 Deploying..."
gcloud run deploy $SERVICE_NAME \
  --image $IMAGE \
  --region $REGION \
  --allow-unauthenticated \
  --set-env-vars "$SECRETS" \
  --project $PROJECT_ID

echo "✅ Deployment successful!"
