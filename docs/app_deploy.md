# 🚀 Faster Framework - Cloudflare Workers Deployment Guide

[![Deploy Status](https://img.shields.io/badge/Deploy-Cloudflare%20Workers-orange.svg)](https://workers.cloudflare.com/)
[![CI/CD](https://img.shields.io/badge/CI%2FCD-GitHub%20Actions-blue.svg)](https://github.com/features/actions)
[![Automation](https://img.shields.io/badge/Automation-Makefile-green.svg)](https://www.gnu.org/software/make/)

## 📋 Table of Contents
- [🎯 Overview](#-overview)
- [🏗️ Architecture](#%EF%B8%8F-architecture)
- [⚙️ Prerequisites](#%EF%B8%8F-prerequisites)
- [🚀 Quick Start](#-quick-start)
- [🔧 Configuration](#-configuration)
- [📦 Deployment Process](#-deployment-process)
- [🌍 Environments](#-environments)
- [🔐 Secret Management](#-secret-management)
- [🤖 GitHub Actions CI/CD](#-github-actions-cicd)
- [📊 Monitoring & Health Checks](#-monitoring--health-checks)
- [🛠️ Troubleshooting](#%EF%B8%8F-troubleshooting)
- [📝 Best Practices](#-best-practices)

---

## 🎯 Overview

This guide provides a complete deployment pipeline for the **Faster Framework** on **Cloudflare Workers** using **Native Python Support**. The setup includes:

✅ **🐍 Native Python Workers** - No JavaScript bridge required!
✅ **Automated CI/CD** with GitHub Actions
✅ **Multi-environment** deployments (dev/staging/prod)
✅ **Tag-based releases** for production deployments
✅ **Automated testing** before deployment
✅ **Secret management** with Cloudflare Workers
✅ **Health checks** and monitoring
✅ **Rollback capabilities**

> **🚀 Major Advantage**: Your FastAPI application now runs **directly** in Cloudflare Workers using native Python support, eliminating the need for JavaScript bridge code and providing better performance.

---

## 🏗️ Architecture

```mermaid
graph TB
    A[Developer] -->|Push Tag| B[GitHub Repository]
    B -->|Trigger| C[GitHub Actions]
    C -->|Run Tests| D[Test Suite]
    D -->|✅ Pass| E[🐍 Native Python Workers]
    E -->|Direct Deploy| F[Cloudflare Workers]
    F -->|Deploy| G[Environment]

    G -->|Development| H[dev.workers.dev]
    G -->|Staging| I[staging.workers.dev]
    G -->|Production| J[prod.workers.dev]

    K[Makefile] -->|Local Deploy| E
    L[Scripts] -->|Secret Management| F
    M[FastAPI App] -->|Native Integration| E
```

### 🔄 Deployment Flow

1. **Code Development** → Local testing with `make test`
2. **Quality Checks** → Automated linting and type checking
3. **Tag Creation** → `make tag-release version=vX.Y.Z`
4. **🐍 Native Python Workers** → Direct FastAPI deployment (no JavaScript bridge!)
5. **GitHub Actions** → Automated testing and deployment
6. **Health Verification** → Post-deployment health checks
7. **Monitoring** → Continuous monitoring and alerts

> **⚡ Key Advantage**: Your FastAPI application runs natively in Python Workers without any JavaScript intermediary, providing better performance and simpler debugging.

---

## ⚙️ Prerequisites

### 📋 Required Tools
```bash
# Install required tools
npm install -g wrangler         # Cloudflare Workers CLI
pip install uv                  # Python package manager
```

### 🔑 Required Accounts
- **GitHub Account** with repository access
- **Cloudflare Account** with Workers enabled
- **Database Provider** (PostgreSQL compatible)
- **Redis Provider** (optional but recommended)
- **Supabase Account** (for authentication)

### 🌐 External Services
- **PostgreSQL Database** (Supabase, PlanetScale, or self-hosted)
- **Redis Cache** (Upstash, Redis Cloud, or self-hosted)
- **Supabase Auth** for user authentication

---

## 🚀 Quick Start

### 1. 🔧 Initial Setup
```bash
# Clone and setup the project
git clone <your-repo-url>
cd faster
make install

# Install Wrangler CLI
npm install -g wrangler

# Login to Cloudflare
make wrangler-login
```

### 2. 🔐 Configure Secrets
```bash
# Set up development secrets
make secrets-set-dev

# Set up staging secrets (optional)
make secrets-set-staging

# Set up production secrets
make secrets-set-prod
```

### 3. 🧪 Test Deployment
```bash
# Run pre-deployment checks
./scripts/deploy-check.sh

# Deploy to development
make deploy

# Verify deployment
./scripts/health-check.sh development
```

### 4. 🏷️ Create Release
```bash
# Create and push a release tag
make tag-release version=v1.0.0

# GitHub Actions will automatically deploy to production
```

---

## 🔧 Configuration

### 📁 Configuration Files

| File | Purpose | Description |
|------|---------|-------------|
| `wrangler.toml` | Workers Config | Cloudflare Workers Python configuration |
| `main.py` | Entry Point | **Native Python entry point** (no JavaScript needed!) |
| `.env.workers` | Env Template | Environment variables template |
| `.github/workflows/deploy.yml` | CI/CD | GitHub Actions workflow |

> **🎉 Removed**: `worker.js` is no longer needed thanks to native Python Workers support!

### ⚙️ Environment Variables

Copy `.env.workers` and configure for each environment:

```bash
# Database Configuration
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/db
REDIS_URL=redis://host:6379/0

# Supabase Authentication
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=your-anon-key
SUPABASE_SERVICE_ROLE_KEY=your-service-key

# Security
JWT_SECRET_KEY=your-secret-key
ENCRYPTION_KEY=your-encryption-key

# Monitoring (Optional)
SENTRY_DSN=your-sentry-dsn
```

---

## 📦 Deployment Process

### 🛠️ Available Commands

| Command | Description | Usage |
|---------|-------------|--------|
| `make deploy` | Deploy to development | `make deploy` |
| `make deploy-staging` | Deploy to staging | `make deploy-staging` |
| `make deploy-production` | Deploy to production | `make deploy-production` |
| `make build-worker` | Build for Workers | `make build-worker` |
| `make wrangler-status` | Check deployment status | `make wrangler-status` |

### 🏗️ Build Process

The native Python Workers build process:
1. **Code Quality** → Linting and type checking
2. **Testing** → Unit and integration tests
3. **🐍 Native Deployment** → Direct Python code deployment (no build step needed!)
4. **Workers Runtime** → Pyodide integration handles Python dependencies
5. **Verification** → Health checks

```bash
# Manual deployment workflow
make lint                    # Check code quality
make test                    # Run tests
make deploy                 # Deploy directly to Workers (no build needed!)
./scripts/health-check.sh   # Verify deployment
```

> **⚡ Simplified Process**: With native Python Workers, there's no complex build or packaging step. Your FastAPI code is deployed directly!

---

## 🌍 Environments

### 🏗️ Environment Structure

| Environment | Purpose | Trigger | URL Pattern |
|-------------|---------|---------|-------------|
| **Development** | Daily development | Manual deploy | `faster-app-dev.workers.dev` |
| **Staging** | Pre-release testing | Tags with `alpha/beta/rc` | `faster-app-staging.workers.dev` |
| **Production** | Live application | Stable version tags | `faster-app-prod.workers.dev` |

### 🔄 Environment Workflow

```bash
# Development workflow
git push origin feature-branch
make deploy                 # Test in development

# Staging workflow
make tag-prerelease version=v1.0.0-beta.1
git push origin v1.0.0-beta.1    # Auto-deploys to staging

# Production workflow
make tag-release version=v1.0.0
git push origin v1.0.0           # Auto-deploys to production
```

---

## 🔐 Secret Management

### 🔑 Types of Secrets

| Type | Description | Method | Example |
|------|-------------|--------|---------|
| **Database** | Connection strings | Wrangler secrets | `DATABASE_URL` |
| **Authentication** | API keys & tokens | Wrangler secrets | `SUPABASE_SERVICE_ROLE_KEY` |
| **Security** | Encryption keys | Wrangler secrets | `JWT_SECRET_KEY` |
| **Monitoring** | Service DSNs | Wrangler secrets | `SENTRY_DSN` |

### 🛠️ Secret Management Tools

#### 1. **Interactive Script** (Recommended)
```bash
# Use the interactive script
./scripts/set-secrets.sh development
./scripts/set-secrets.sh staging
./scripts/set-secrets.sh production
```

#### 2. **Manual Wrangler Commands**
```bash
# Set secrets manually
echo "your-secret-value" | wrangler secret put SECRET_NAME --env production
```

#### 3. **GitHub Secrets** (for CI/CD)
Add secrets in GitHub repository settings:
- `CLOUDFLARE_API_TOKEN`
- `CLOUDFLARE_ACCOUNT_ID`
- `PROD_DATABASE_URL`
- `STAGING_DATABASE_URL`
- And other environment-specific secrets

### 🔍 Secret Verification
```bash
# List configured secrets
wrangler secret list --env production

# Test secret access (in deployed worker)
curl https://your-app.workers.dev/health
```

---

## 🤖 GitHub Actions CI/CD

### 🔄 Workflow Triggers

| Trigger | Action | Environment |
|---------|--------|-------------|
| Push tag `v*.*.*` | Full deployment | Production |
| Push tag `*-alpha.*` | Pre-release | Staging |
| Push tag `*-beta.*` | Pre-release | Staging |
| Push tag `*-rc.*` | Release candidate | Staging |

### 📋 Workflow Steps

```yaml
# .github/workflows/deploy.yml
1. 🧪 Run Tests
   - Install dependencies
   - Lint code
   - Run unit tests

2. 🚀 Deploy Staging (pre-release tags)
   - Build application
   - Set secrets
   - Deploy to staging

3. 🌟 Deploy Production (stable tags)
   - Build application
   - Set secrets
   - Deploy to production
   - Create GitHub release
```

### 🔧 Required GitHub Secrets

Configure these in your GitHub repository settings:

```bash
# Cloudflare
CLOUDFLARE_API_TOKEN      # Cloudflare API token
CLOUDFLARE_ACCOUNT_ID     # Cloudflare account ID

# Production Environment
PROD_DATABASE_URL         # Production database
PROD_REDIS_URL           # Production Redis
PROD_SUPABASE_URL        # Production Supabase URL
PROD_SUPABASE_ANON_KEY   # Production Supabase anon key
PROD_SUPABASE_SERVICE_ROLE_KEY  # Production service key

# Staging Environment
STAGING_DATABASE_URL     # Staging database
STAGING_REDIS_URL       # Staging Redis
STAGING_SUPABASE_URL    # Staging Supabase URL
STAGING_SUPABASE_ANON_KEY    # Staging anon key
STAGING_SUPABASE_SERVICE_ROLE_KEY  # Staging service key
```

---

## 📊 Monitoring & Health Checks

### 🏥 Health Check Endpoints

| Endpoint | Purpose | Expected Response |
|----------|---------|-------------------|
| `/health` | Basic health | `{"status": "healthy"}` |
| `/custom` | Redis connectivity | `{"message": "Custom endpoint - Redis is connected!"}` |
| `/docs` | API documentation | HTML documentation |
| `/openapi.json` | OpenAPI spec | JSON specification |

### 🔍 Health Check Script

```bash
# Check deployment health
./scripts/health-check.sh development
./scripts/health-check.sh staging
./scripts/health-check.sh production [account-id]

# Health check includes:
✅ Root endpoint accessibility
✅ Health endpoint response
✅ Database connectivity
✅ Redis connectivity
✅ API documentation availability
```

### 📊 Monitoring Commands

```bash
# View real-time logs
make wrangler-tail                    # Development
make wrangler-tail-staging           # Staging
make wrangler-tail-production        # Production

# Check deployment status
make wrangler-status

# Performance metrics
wrangler dev --compatibility-date=2024-09-24
```

### 🚨 Error Monitoring

- **Sentry Integration**: Automatic error tracking
- **Cloudflare Analytics**: Built-in performance metrics
- **Custom Logging**: Structured logging with levels

---

## 🛠️ Troubleshooting

### ❌ Common Issues & Solutions

#### 1. **Authentication Issues**
```bash
# Problem: "Not authenticated with Cloudflare"
# Solution:
make wrangler-login
wrangler auth list
```

#### 2. **Build Failures**
```bash
# Problem: Build process fails
# Solution:
make clean                  # Clean build artifacts
make lint                   # Fix code issues
make test                   # Ensure tests pass
make build-worker          # Retry build
```

#### 3. **Deployment Failures**
```bash
# Problem: Deployment fails
# Solution:
wrangler whoami            # Verify authentication
./scripts/deploy-check.sh  # Run pre-deployment checks
wrangler secret list       # Verify secrets are set
```

#### 4. **Health Check Failures**
```bash
# Problem: Health checks fail after deployment
# Solution:
make wrangler-tail         # Check logs
wrangler secret list       # Verify secrets
curl -v https://your-app.workers.dev/health  # Manual test
```

#### 5. **Database Connection Issues**
```bash
# Problem: Database connection fails
# Solutions:
- Verify DATABASE_URL format: postgresql+asyncpg://user:pass@host:port/db
- Check database server accessibility
- Ensure database exists and user has permissions
- Verify SSL/TLS requirements
```

### 📋 Debug Commands

```bash
# Comprehensive debugging
./scripts/deploy-check.sh    # Pre-deployment verification
wrangler dev                 # Local development server
wrangler tail --format=pretty  # Formatted logs
curl -I https://your-app.workers.dev  # HTTP headers
```

### 🔄 Rollback Process

```bash
# Emergency rollback
git tag -d v1.2.0                    # Delete problematic tag locally
git push origin --delete v1.2.0     # Delete from remote
make tag-release version=v1.1.0     # Re-deploy previous version
```

---

## 📝 Best Practices

### 🚀 Deployment Best Practices

#### ✅ Do's
- **Test Thoroughly**: Always run `make test` before deployment
- **Use Pre-deployment Checks**: Run `./scripts/deploy-check.sh`
- **Follow Semantic Versioning**: Use proper version tags (v1.2.3)
- **Monitor Deployments**: Check health after each deployment
- **Stage Changes**: Test in development/staging first
- **Document Changes**: Update changelog for releases

#### ❌ Don'ts
- **Don't Skip Tests**: Never deploy without running tests
- **Don't Use Weak Secrets**: Generate strong random keys
- **Don't Mix Environments**: Keep environment secrets separate
- **Don't Deploy Uncommitted Code**: Commit and push first
- **Don't Ignore Health Checks**: Verify deployment success

### 🔐 Security Best Practices

#### 🛡️ Secret Management
- **Rotate Secrets Regularly**: Update keys periodically
- **Use Environment-Specific Secrets**: Different keys per environment
- **Never Commit Secrets**: Use `.env.workers` as template only
- **Audit Secret Access**: Monitor who has access to secrets

#### 🔒 Application Security
- **Enable HTTPS Only**: Configure secure headers
- **Validate Input**: Sanitize all user input
- **Rate Limiting**: Implement API rate limits
- **CORS Configuration**: Set appropriate CORS policies

### 📊 Monitoring Best Practices

#### 📈 Performance Monitoring
- **Set Up Alerts**: Configure alerts for failures
- **Monitor Response Times**: Track API performance
- **Database Monitoring**: Monitor connection pools
- **Resource Usage**: Track memory and CPU usage

#### 🔍 Log Management
- **Structured Logging**: Use consistent log formats
- **Appropriate Log Levels**: Debug/Info/Warn/Error
- **Sensitive Data**: Never log passwords or tokens
- **Log Retention**: Configure appropriate retention policies

### 🔄 Development Workflow

#### 🌟 Git Workflow
```bash
# Feature development
git checkout -b feature/new-feature
# ... make changes ...
git commit -m "feat: add new feature"
make test                           # Local testing
make deploy                        # Test in development
git push origin feature/new-feature

# Release process
git checkout main
git merge feature/new-feature
make tag-release version=v1.2.0   # Creates release tag
# GitHub Actions handles deployment
```

#### 🧪 Testing Strategy
- **Unit Tests**: Test business logic in isolation
- **Integration Tests**: Test API endpoints
- **E2E Tests**: Test complete user workflows
- **Performance Tests**: Load testing for critical paths

---

## 🔗 Additional Resources

### 📚 Documentation Links
- [Cloudflare Workers Docs](https://developers.cloudflare.com/workers/)
- [Wrangler CLI Reference](https://developers.cloudflare.com/workers/wrangler/)
- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Supabase Documentation](https://supabase.com/docs)

### 🛠️ Useful Commands Reference

```bash
# Development
make run                    # Local development server
make test                   # Run tests
make lint                   # Code quality checks
make autofix               # Auto-fix linting issues

# Deployment
make deploy                # Deploy to development
make deploy-staging        # Deploy to staging
make deploy-production     # Deploy to production
make build-worker         # Build for Workers

# Management
make wrangler-login       # Login to Cloudflare
make secrets-set-dev      # Set development secrets
make wrangler-status      # Check deployment status
make wrangler-tail        # View logs

# Health & Monitoring
./scripts/health-check.sh development
./scripts/deploy-check.sh
make wrangler-tail-production

# Release Management
make tag-release version=v1.0.0
make tag-prerelease version=v1.0.0-beta.1
```

---

## 🎉 Conclusion

This deployment setup provides a **production-ready**, **automated**, and **scalable** solution for deploying your Faster Framework application to Cloudflare Workers.

### Key Benefits:
✅ **Zero-downtime deployments**
✅ **Automated testing & quality checks**
✅ **Multi-environment support**
✅ **Secure secret management**
✅ **Comprehensive monitoring**
✅ **Easy rollback capabilities**

**Happy Deploying! 🚀**

---

*Last updated: September 2024*
*Version: 1.0.0*