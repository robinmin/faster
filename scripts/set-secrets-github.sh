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

# Set Cloudflare credentials without environment prefix (used for all environments)
echo ""
echo -e "${YELLOW}📝 Setting CLOUDFLARE_API_TOKEN (no environment prefix)${NC}"
echo "Description: Cloudflare API token for deployment"
echo -n "Enter value (required): "
read -r api_token_value
if [ -z "$api_token_value" ]; then
    echo -e "${RED}❌ Error: CLOUDFLARE_API_TOKEN is required${NC}"
    exit 1
fi
echo "$api_token_value" | gh secret set "CLOUDFLARE_API_TOKEN"
echo -e "${GREEN}✅ CLOUDFLARE_API_TOKEN set successfully${NC}"

echo ""
echo -e "${YELLOW}📝 Setting CLOUDFLARE_ACCOUNT_ID (no environment prefix)${NC}"
echo "Description: Cloudflare account ID"
echo -n "Enter value (required): "
read -r account_id_value
if [ -z "$account_id_value" ]; then
    echo -e "${RED}❌ Error: CLOUDFLARE_ACCOUNT_ID is required${NC}"
    exit 1
fi
echo "$account_id_value" | gh secret set "CLOUDFLARE_ACCOUNT_ID"
echo -e "${GREEN}✅ CLOUDFLARE_ACCOUNT_ID set successfully${NC}"

# D1 Database IDs for placeholder replacement
echo ""
echo -e "${BLUE}🗄️ D1 Database Configuration${NC}"
echo "============================="

case $ENVIRONMENT in
    development)
        set_github_secret "DEV_DATABASE_ID" \
            "D1 Database ID for development environment" \
            false
        ;;
    staging)
        set_github_secret "STAGING_DATABASE_ID" \
            "D1 Database ID for staging environment" \
            false
        ;;
    production)
        set_github_secret "PROD_DATABASE_ID" \
            "D1 Database ID for production environment" \
            false
        ;;
esac

# Application secrets (environment-specific)
echo ""
echo -e "${BLUE}📋 Application Secrets${NC}"
echo "======================="

echo ""
echo -e "${YELLOW}🗄️ Database Configuration${NC}"
echo "Setting up environment-specific D1 database configuration for GitHub Actions..."

case $ENVIRONMENT in
    development)
        echo -e "${BLUE}Development Environment: D1 HTTP Client Mode${NC}"
        set_github_secret "DATABASE_URL" \
            "D1 HTTP connection string (format: d1+aiosqlite://database_id?account_id=ACCOUNT_ID&api_token=API_TOKEN)" \
            true
        ;;
    staging)
        echo -e "${BLUE}Staging Environment: D1 HTTP Client Mode${NC}"
        set_github_secret "DATABASE_URL" \
            "D1 HTTP connection string (format: d1+aiosqlite://database_id?account_id=ACCOUNT_ID&api_token=API_TOKEN)" \
            true
        ;;
    production)
        echo -e "${BLUE}Production Environment: D1 Workers Binding Mode${NC}"
        set_github_secret "DATABASE_URL" \
            "D1 Workers binding string (use: d1+binding://DB)" \
            true
        ;;
esac

echo ""
echo -e "${YELLOW}💡 D1 Credentials (shared across environments):${NC}"
set_github_secret "CLOUDFLARE_ACCOUNT_ID" \
    "Your Cloudflare Account ID (from: wrangler whoami)" \
    false

set_github_secret "CLOUDFLARE_API_TOKEN" \
    "Your Cloudflare API Token with D1 permissions" \
    false

set_github_secret "D1_DATABASE_ID" \
    "Your D1 Database ID for this environment (from: wrangler d1 list)" \
    false

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

# Verification section
echo ""
echo -e "${BLUE}🔍 Verification: Checking configured secrets...${NC}"
echo "========================================"

if gh secret list &> /dev/null; then
    SECRETS_LIST=$(gh secret list 2>/dev/null || echo "Unable to retrieve secrets list")
    if [ "$SECRETS_LIST" != "Unable to retrieve secrets list" ] && [ -n "$SECRETS_LIST" ]; then
        echo -e "${GREEN}✅ GitHub secrets successfully configured:${NC}"
        echo "$SECRETS_LIST"

        # Check for environment-specific secrets
        echo ""
        echo -e "${BLUE}🔍 Environment-specific secrets for ${ENVIRONMENT}:${NC}"
        case $ENVIRONMENT in
            development)
                echo "Looking for DEV_* secrets..."
                echo "$SECRETS_LIST" | grep "DEV_" || echo "No DEV_* secrets found"
                ;;
            staging)
                echo "Looking for STAGING_* secrets..."
                echo "$SECRETS_LIST" | grep "STAGING_" || echo "No STAGING_* secrets found"
                ;;
            production)
                echo "Looking for PROD_* secrets..."
                echo "$SECRETS_LIST" | grep "PROD_" || echo "No PROD_* secrets found"
                ;;
        esac
    else
        echo -e "${YELLOW}⚠️  No secrets found or unable to list secrets${NC}"
    fi
else
    echo -e "${RED}❌ Unable to verify secrets. Check your GitHub CLI authentication:${NC}"
    echo "Run: gh auth status"
fi

echo ""
echo -e "${BLUE}📊 Next steps:${NC}"
echo "1. Push a tag to trigger GitHub Actions: make tag-release version=v1.0.0"
echo "2. Check GitHub Actions workflow: gh run list"
echo "3. Monitor deployment: gh run watch"
echo ""
echo -e "${YELLOW}💡 Tip: Use ./scripts/set-secrets.sh to set Cloudflare Workers secrets${NC}"

# Additional verification tips
echo ""
echo -e "${BLUE}🔧 Verification Commands:${NC}"
echo "• List all GitHub secrets: gh secret list"
echo "• Check GitHub auth: gh auth status"
echo "• View recent workflow runs: gh run list"
echo "• Test workflow: Push a tag or create a pull request"