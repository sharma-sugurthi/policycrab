#!/bin/bash
set -e

# Project configuration
PROJECT_ID="project-9676fda5-8ba6-476c-8d9"
SERVICE_NAME="policycrab-backend"
REGION="us-east1"

echo "🚀 Starting PolicyCrab Cloud Run Deployment..."
echo "Project: $PROJECT_ID"
echo "Service: $SERVICE_NAME"
echo "Region: $REGION"

# Navigate to backend directory
cd "$(dirname "$0")/.."

# Ensure gcloud project is set
gcloud config set project $PROJECT_ID

# Read .env file and build a comma-separated string of variables for Cloud Run
if [ ! -f .env ]; then
  echo "❌ Error: .env file not found!"
  exit 1
fi

echo "🔐 Parsing .env for secrets..."
SECRETS=""
while IFS='=' read -r key value; do
  # Ignore comments and empty lines
  if [[ $key != \#* ]] && [[ -n $key ]]; then
    # Remove surrounding quotes from value if present
    value=$(echo "$value" | sed -e 's/^"//' -e 's/"$//' -e "s/^'//" -e "s/'$//")
    # Escape commas in value
    escaped_value=$(echo "$value" | sed 's/,/\\,/g')
    SECRETS="${SECRETS}${key}=${escaped_value},"
  fi
done < .env

# Remove trailing comma
SECRETS=${SECRETS%,}

echo "📦 Deploying to Cloud Run..."
gcloud run deploy $SERVICE_NAME \
  --source . \
  --region $REGION \
  --allow-unauthenticated \
  --set-env-vars "$SECRETS" \
  --project $PROJECT_ID

echo "✅ Deployment successful!"
