#!/bin/bash

# 🔐 Set Cloudflare Workers secrets for different environments
# Usage: ./scripts/set-secrets.sh [development|staging|production]

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Check if environment is provided
if [ -z "$1" ]; then
    echo -e "${RED}❌ Error: Environment not specified${NC}"
    echo "Usage: $0 [development|staging|production]"
    exit 1
fi

ENVIRONMENT=$1

# Validate environment
if [[ "$ENVIRONMENT" != "development" && "$ENVIRONMENT" != "staging" && "$ENVIRONMENT" != "production" ]]; then
    echo -e "${RED}❌ Error: Invalid environment '$ENVIRONMENT'${NC}"
    echo "Valid environments: development, staging, production"
    exit 1
fi

echo -e "${BLUE}🔐 Setting secrets for ${ENVIRONMENT} environment${NC}"
echo "======================================================"

# Check if wrangler is installed
if ! command -v wrangler &> /dev/null; then
    echo -e "${RED}❌ Wrangler CLI not found. Install it with: npm install -g wrangler${NC}"
    exit 1
fi

# Function to set a secret
set_secret() {
    local secret_name=$1
    local secret_description=$2
    local is_required=${3:-true}

    echo ""
    echo -e "${YELLOW}📝 Setting ${secret_name}${NC}"
    echo "Description: ${secret_description}"

    if [ "$is_required" = "true" ]; then
        echo -n "Enter value (required): "
    else
        echo -n "Enter value (optional, press Enter to skip): "
    fi

    read -r secret_value

    if [ -z "$secret_value" ] && [ "$is_required" = "true" ]; then
        echo -e "${RED}❌ Error: ${secret_name} is required${NC}"
        exit 1
    fi

    if [ -n "$secret_value" ]; then
        echo "$secret_value" | wrangler secret put "$secret_name" --env "$ENVIRONMENT"
        echo -e "${GREEN}✅ ${secret_name} set successfully${NC}"
    else
        echo -e "${YELLOW}⏭️  Skipped ${secret_name}${NC}"
    fi
}

# Required secrets
echo -e "${BLUE}📋 Required Secrets${NC}"
echo "==================="

set_secret "DATABASE_URL" \
    "PostgreSQL connection string (e.g., postgresql+asyncpg://user:pass@host:5432/db)" \
    true

set_secret "REDIS_URL" \
    "Redis connection string (e.g., redis://host:6379/0)" \
    true

set_secret "SUPABASE_URL" \
    "Supabase project URL (e.g., https://your-project.supabase.co)" \
    true

set_secret "SUPABASE_ANON_KEY" \
    "Supabase anonymous key for client-side access" \
    true

set_secret "SUPABASE_SERVICE_ROLE_KEY" \
    "Supabase service role key for server-side access (admin privileges)" \
    true

# Optional secrets
echo ""
echo -e "${BLUE}🔧 Optional Secrets${NC}"
echo "==================="

set_secret "REDIS_PASSWORD" \
    "edis password for local, and token for Upstash" \
    false

set_secret "SENTRY_DSN" \
    "Sentry DSN for error tracking (optional)" \
    false

set_secret "SENTRY_CLIENT_DSN" \
    "Client side Sentry DSN for error tracking" \
    false

echo ""
echo -e "${GREEN}🎉 All secrets have been configured for ${ENVIRONMENT} environment!${NC}"
echo ""
echo -e "${BLUE}📊 Next steps:${NC}"
echo "1. Deploy your application: make deploy-${ENVIRONMENT}"
echo "2. Check deployment status: make wrangler-status"
echo "3. View logs: make wrangler-tail-${ENVIRONMENT}"
echo ""
echo -e "${YELLOW}💡 Tip: You can run this script again anytime to update secrets${NC}"
