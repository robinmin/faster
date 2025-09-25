#!/bin/bash

# 🚀 Pre-deployment checks for Cloudflare Workers
# This script performs various checks before deployment

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🔍 Pre-deployment Checks${NC}"
echo "=========================="

# Check 1: Code quality
echo ""
echo -e "${YELLOW}1. 📝 Checking code quality...${NC}"
if make lint; then
    echo -e "${GREEN}✅ Code quality checks passed${NC}"
else
    echo -e "${RED}❌ Code quality checks failed${NC}"
    exit 1
fi

# Check 2: Tests
echo ""
echo -e "${YELLOW}2. 🧪 Running tests...${NC}"
if make test; then
    echo -e "${GREEN}✅ Tests passed${NC}"
else
    echo -e "${RED}❌ Tests failed${NC}"
    exit 1
fi

# Check 3: Wrangler CLI
echo ""
echo -e "${YELLOW}3. 🔧 Checking Wrangler CLI...${NC}"
if command -v wrangler &> /dev/null; then
    WRANGLER_VERSION=$(wrangler --version)
    echo -e "${GREEN}✅ Wrangler CLI installed: ${WRANGLER_VERSION}${NC}"
else
    echo -e "${RED}❌ Wrangler CLI not found${NC}"
    echo "Install with: npm install -g wrangler"
    exit 1
fi

# Check 4: Cloudflare authentication
echo ""
echo -e "${YELLOW}4. 🔐 Checking Cloudflare authentication...${NC}"
if wrangler whoami &> /dev/null; then
    WHOAMI_OUTPUT=$(wrangler whoami)
    echo -e "${GREEN}✅ Authenticated with Cloudflare${NC}"
    echo "   Account: $(echo "$WHOAMI_OUTPUT" | grep 'Account' | head -1)"
else
    echo -e "${RED}❌ Not authenticated with Cloudflare${NC}"
    echo "Run: make wrangler-login"
    exit 1
fi

# Check 5: Build process
echo ""
echo -e "${YELLOW}5. 🏗️  Testing build process...${NC}"
if make build-worker; then
    echo -e "${GREEN}✅ Build process successful${NC}"
else
    echo -e "${RED}❌ Build process failed${NC}"
    exit 1
fi

# Check 6: Configuration files
echo ""
echo -e "${YELLOW}6. ⚙️  Checking configuration files...${NC}"

if [ -f "wrangler.toml" ]; then
    echo -e "${GREEN}✅ wrangler.toml found${NC}"
else
    echo -e "${RED}❌ wrangler.toml not found${NC}"
    exit 1
fi

if [ -f "worker.js" ]; then
    echo -e "${GREEN}✅ worker.js found${NC}"
else
    echo -e "${RED}❌ worker.js not found${NC}"
    exit 1
fi

if [ -f "main.py" ]; then
    echo -e "${GREEN}✅ main.py found${NC}"
else
    echo -e "${RED}❌ main.py not found${NC}"
    exit 1
fi

# Check 7: Git status
echo ""
echo -e "${YELLOW}7. 📋 Checking git status...${NC}"
if git diff --quiet && git diff --cached --quiet; then
    echo -e "${GREEN}✅ No uncommitted changes${NC}"
else
    echo -e "${YELLOW}⚠️  You have uncommitted changes${NC}"
    echo "Consider committing your changes before deployment"
fi

CURRENT_BRANCH=$(git branch --show-current)
echo "   Current branch: ${CURRENT_BRANCH}"

# Final summary
echo ""
echo -e "${GREEN}🎉 All pre-deployment checks passed!${NC}"
echo ""
echo -e "${BLUE}📊 Ready for deployment:${NC}"
echo "• Development: make deploy"
echo "• Staging:     make deploy-staging"
echo "• Production:  make deploy-production"
echo ""
echo -e "${YELLOW}💡 Pro tip: Use 'make tag-release version=vX.Y.Z' to trigger automated deployment${NC}"