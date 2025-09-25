#!/bin/bash

# 🏥 Health check script for deployed Cloudflare Workers
# Usage: ./scripts/health-check.sh [development|staging|production] [account-id]

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default values
ENVIRONMENT=${1:-development}
ACCOUNT_ID=${2:-}

# If no account ID provided, try to get it from wrangler
if [ -z "$ACCOUNT_ID" ] && command -v wrangler &> /dev/null; then
    ACCOUNT_ID=$(wrangler whoami 2>/dev/null | grep 'Account ID' | cut -d: -f2 | xargs || echo "")
fi

# Validate environment
if [[ "$ENVIRONMENT" != "development" && "$ENVIRONMENT" != "staging" && "$ENVIRONMENT" != "production" ]]; then
    echo -e "${RED}❌ Error: Invalid environment '$ENVIRONMENT'${NC}"
    echo "Valid environments: development, staging, production"
    exit 1
fi

# Construct URL based on environment
if [ -n "$ACCOUNT_ID" ]; then
    case $ENVIRONMENT in
        development)
            URL="https://faster-app-dev.${ACCOUNT_ID}.workers.dev"
            ;;
        staging)
            URL="https://faster-app-staging.${ACCOUNT_ID}.workers.dev"
            ;;
        production)
            URL="https://faster-app-prod.${ACCOUNT_ID}.workers.dev"
            ;;
    esac
else
    echo -e "${YELLOW}⚠️  Account ID not found. Please provide it as second argument${NC}"
    echo "Usage: $0 $ENVIRONMENT [account-id]"
    exit 1
fi

echo -e "${BLUE}🏥 Health Check for ${ENVIRONMENT} environment${NC}"
echo "=============================================="
echo "URL: $URL"
echo ""

# Function to check endpoint
check_endpoint() {
    local endpoint=$1
    local description=$2
    local expected_status=${3:-200}

    echo -e "${YELLOW}🔍 Checking ${description}...${NC}"

    local full_url="${URL}${endpoint}"
    local response=$(curl -s -w "%{http_code}" -o /dev/null "$full_url" 2>/dev/null || echo "000")

    if [ "$response" = "$expected_status" ]; then
        echo -e "${GREEN}✅ ${description}: HTTP $response${NC}"
        return 0
    else
        echo -e "${RED}❌ ${description}: HTTP $response (expected $expected_status)${NC}"
        return 1
    fi
}

# Function to check endpoint with response body
check_endpoint_with_body() {
    local endpoint=$1
    local description=$2

    echo -e "${YELLOW}🔍 Checking ${description}...${NC}"

    local full_url="${URL}${endpoint}"
    local response=$(curl -s "$full_url" 2>/dev/null || echo '{"error":"request_failed"}')
    local http_code=$(curl -s -w "%{http_code}" -o /dev/null "$full_url" 2>/dev/null || echo "000")

    if [ "$http_code" = "200" ]; then
        echo -e "${GREEN}✅ ${description}: HTTP $http_code${NC}"
        echo "   Response: $response"
        return 0
    else
        echo -e "${RED}❌ ${description}: HTTP $http_code${NC}"
        echo "   Response: $response"
        return 1
    fi
}

# Initialize counters
TOTAL_CHECKS=0
PASSED_CHECKS=0

# Health checks
echo -e "${BLUE}📋 Running health checks...${NC}"
echo ""

# Check 1: Root endpoint
TOTAL_CHECKS=$((TOTAL_CHECKS + 1))
if check_endpoint "/" "Root endpoint"; then
    PASSED_CHECKS=$((PASSED_CHECKS + 1))
fi

# Check 2: Health endpoint
TOTAL_CHECKS=$((TOTAL_CHECKS + 1))
if check_endpoint "/health" "Health endpoint"; then
    PASSED_CHECKS=$((PASSED_CHECKS + 1))
fi

# Check 3: Custom endpoint
TOTAL_CHECKS=$((TOTAL_CHECKS + 1))
if check_endpoint_with_body "/custom" "Custom endpoint"; then
    PASSED_CHECKS=$((PASSED_CHECKS + 1))
fi

# Check 4: API docs
TOTAL_CHECKS=$((TOTAL_CHECKS + 1))
if check_endpoint "/docs" "API Documentation"; then
    PASSED_CHECKS=$((PASSED_CHECKS + 1))
fi

# Check 5: OpenAPI spec
TOTAL_CHECKS=$((TOTAL_CHECKS + 1))
if check_endpoint "/openapi.json" "OpenAPI specification"; then
    PASSED_CHECKS=$((PASSED_CHECKS + 1))
fi

echo ""
echo "=============================================="
echo -e "${BLUE}📊 Health Check Summary${NC}"
echo "=============================================="
echo "Environment: $ENVIRONMENT"
echo "URL: $URL"
echo "Checks passed: $PASSED_CHECKS/$TOTAL_CHECKS"

if [ $PASSED_CHECKS -eq $TOTAL_CHECKS ]; then
    echo -e "${GREEN}🎉 All health checks passed!${NC}"
    echo ""
    echo -e "${BLUE}🔗 Quick Links:${NC}"
    echo "• Application: $URL"
    echo "• API Docs: $URL/docs"
    echo "• Health Check: $URL/health"
    exit 0
else
    FAILED_CHECKS=$((TOTAL_CHECKS - PASSED_CHECKS))
    echo -e "${RED}❌ $FAILED_CHECKS health check(s) failed${NC}"
    echo ""
    echo -e "${YELLOW}💡 Troubleshooting tips:${NC}"
    echo "1. Check deployment status: make wrangler-status"
    echo "2. View logs: make wrangler-tail-$ENVIRONMENT"
    echo "3. Verify secrets: wrangler secret list --env $ENVIRONMENT"
    echo "4. Redeploy if needed: make deploy-$ENVIRONMENT"
    exit 1
fi