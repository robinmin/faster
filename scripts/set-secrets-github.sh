#!/bin/bash

# 🔐 Set GitHub Actions secrets for different environments
# Usage: ./scripts/set-secrets-github.sh [development|staging|production]

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

echo -e "${BLUE}🔐 Setting GitHub Actions secrets for ${ENVIRONMENT} environment${NC}"
echo "======================================================"

# Check if GitHub CLI is installed
if ! command -v gh &> /dev/null; then
    echo -e "${RED}❌ GitHub CLI not found. Install it with:${NC}"
    echo "  macOS: brew install gh"
    echo "  Linux: https://github.com/cli/cli/blob/trunk/docs/install_linux.md"
    echo "  Windows: https://github.com/cli/cli/releases"
    exit 1
fi

# Check if authenticated
if ! gh auth status &> /dev/null; then
    echo -e "${RED}❌ Not authenticated with GitHub. Run: gh auth login${NC}"
    exit 1
fi

# Function to set a GitHub secret
set_github_secret() {
    local secret_name=$1
    local secret_description=$2
    local is_required=${3:-true}
    local github_secret_name=""

    # Map environment-specific secret names for GitHub
    case $ENVIRONMENT in
        development)
            github_secret_name="DEV_${secret_name}"
            ;;
        staging)
            github_secret_name="STAGING_${secret_name}"
            ;;
        production)
            github_secret_name="PROD_${secret_name}"
            ;;
    esac

    echo ""
    echo -e "${YELLOW}📝 Setting ${github_secret_name}${NC}"
    echo "Description: ${secret_description}"

    if [ "$is_required" = "true" ]; then
        echo -n "Enter value (required): "
    else
        echo -n "Enter value (optional, press Enter to skip): "
    fi

    read -r secret_value

    if [ -z "$secret_value" ] && [ "$is_required" = "true" ]; then
        echo -e "${RED}❌ Error: ${github_secret_name} is required${NC}"
        exit 1
    fi

    if [ -n "$secret_value" ]; then
        echo "$secret_value" | gh secret set "$github_secret_name"
        echo -e "${GREEN}✅ ${github_secret_name} set successfully${NC}"
    else
        echo -e "${YELLOW}⏭️  Skipped ${github_secret_name}${NC}"
    fi
}

# GitHub Actions specific secrets (always required)
echo -e "${BLUE}🐙 GitHub Actions Authentication${NC}"
echo "=================================="

set_github_secret "CLOUDFLARE_API_TOKEN" \
    "Cloudflare API token for deployment" \
    true

set_github_secret "CLOUDFLARE_ACCOUNT_ID" \
    "Cloudflare account ID" \
    true

# Application secrets (environment-specific)
echo ""
echo -e "${BLUE}📋 Application Secrets${NC}"
echo "======================="

set_github_secret "DATABASE_URL" \
    "Database connection string (e.g., postgresql+asyncpg://user:pass@host:5432/db)" \
    true

set_github_secret "REDIS_URL" \
    "Redis connection string (e.g., redis://host:6379/0)" \
    true

set_github_secret "SUPABASE_URL" \
    "Supabase project URL (e.g., https://your-project.supabase.co)" \
    true

set_github_secret "SUPABASE_ANON_KEY" \
    "Supabase anonymous key for client-side access" \
    true

set_github_secret "SUPABASE_SERVICE_ROLE_KEY" \
    "Supabase service role key for server-side access (admin privileges)" \
    true

# Optional secrets
echo ""
echo -e "${BLUE}🔧 Optional Secrets${NC}"
echo "==================="

set_github_secret "REDIS_PASSWORD" \
    "Redis password for local, and token for Upstash" \
    false

set_github_secret "SENTRY_DSN" \
    "Sentry DSN for error tracking (optional)" \
    false

set_github_secret "SENTRY_CLIENT_DSN" \
    "Client side Sentry DSN for error tracking" \
    false

echo ""
echo -e "${GREEN}🎉 All GitHub Actions secrets have been configured for ${ENVIRONMENT} environment!${NC}"
echo ""
echo -e "${BLUE}📊 Next steps:${NC}"
echo "1. Push a tag to trigger GitHub Actions: make tag-release version=v1.0.0"
echo "2. Check GitHub Actions workflow: gh run list"
echo "3. Monitor deployment: gh run watch"
echo ""
echo -e "${YELLOW}💡 Tip: Use ./scripts/set-secrets.sh to set Cloudflare Workers secrets${NC}"