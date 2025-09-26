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

echo -e "${BLUE}🔐 Setting Cloudflare Workers secrets for ${ENVIRONMENT} environment${NC}"
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

echo ""
echo -e "${YELLOW}🗄️ Database Configuration${NC}"
echo "Please choose your database option:"
echo "1) Traditional Database (PostgreSQL/SQLite)"
echo "2) Cloudflare D1 Database (Recommended for Workers)"
echo -n "Enter choice (1 or 2): "
read -r db_choice

case $db_choice in
    1)
        echo -e "${BLUE}Setting up Traditional Database${NC}"
        set_secret "DATABASE_URL" \
            "PostgreSQL/SQLite connection string (e.g., postgresql+asyncpg://user:pass@host:5432/db)" \
            true
        ;;
    2)
        echo -e "${BLUE}Setting up Cloudflare D1 Database${NC}"
        echo "For D1, we'll set up Workers Binding mode (recommended for production)"
        set_secret "DATABASE_URL" \
            "D1 connection string (use: d1+binding://DB for Workers binding)" \
            false

        echo ""
        echo -e "${YELLOW}💡 For D1 HTTP mode (development/testing), also set:${NC}"
        set_secret "CLOUDFLARE_ACCOUNT_ID" \
            "Your Cloudflare Account ID (from wrangler whoami)" \
            false

        set_secret "CLOUDFLARE_API_TOKEN" \
            "Your Cloudflare API Token with D1 permissions" \
            false

        set_secret "D1_DATABASE_ID" \
            "Your D1 Database ID for this environment" \
            false
        ;;
    *)
        echo -e "${YELLOW}⚠️  Invalid choice. Defaulting to traditional database.${NC}"
        set_secret "DATABASE_URL" \
            "Database connection string (e.g., postgresql+asyncpg://user:pass@host:5432/db)" \
            true
        ;;
esac

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
echo -e "${GREEN}🎉 All Cloudflare Workers secrets have been configured for ${ENVIRONMENT} environment!${NC}"

# Verification section
echo ""
echo -e "${BLUE}🔍 Verification: Checking configured secrets...${NC}"
echo "========================================"

if wrangler secret list --env "${ENVIRONMENT}" &> /dev/null; then
    SECRETS_LIST=$(wrangler secret list --env "${ENVIRONMENT}")
    if [ -n "$SECRETS_LIST" ]; then
        echo -e "${GREEN}✅ Secrets successfully configured:${NC}"
        echo "$SECRETS_LIST"
    else
        echo -e "${YELLOW}⚠️  No secrets found for ${ENVIRONMENT} environment${NC}"
    fi
else
    echo -e "${RED}❌ Unable to verify secrets. Check your authentication:${NC}"
    echo "Run: wrangler auth list"
fi

echo ""
echo -e "${BLUE}📊 Next steps:${NC}"
echo "1. Deploy your application: make deploy-${ENVIRONMENT}"
echo "2. Check deployment status: make wrangler-status"
echo "3. View logs: make wrangler-tail-${ENVIRONMENT}"
echo ""
echo -e "${YELLOW}💡 Tip: Use ./scripts/set-secrets-github.sh to set GitHub Actions secrets${NC}"

# Additional verification tips
echo ""
echo -e "${BLUE}🔧 Verification Commands:${NC}"
echo "• List all secrets: wrangler secret list --env ${ENVIRONMENT}"
echo "• Test deployment: make deploy"
echo "• Check logs: wrangler tail --env ${ENVIRONMENT}"
