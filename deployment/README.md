# Deployment Guide for Faster Framework

This directory contains deployment configurations and examples for the Faster framework across different platforms.

## Supported Platforms

### 1. Self-Hosted VPS

The VPS deployment is optimized for traditional server environments with full control over the infrastructure.

#### Features
- **Traefik Integration**: Native support for Traefik reverse proxy and load balancer
- **Auto-scaling Workers**: Automatic worker scaling based on CPU cores
- **Static File Serving**: Efficient static file handling
- **Metrics Endpoint**: Prometheus metrics for monitoring
- **Health Checks**: Built-in health monitoring with Traefik integration
- **SSL Termination**: Automatic SSL/TLS certificates via Let's Encrypt
- **Rate Limiting**: Built-in Traefik rate limiting and security headers

#### Quick Start

1. **Setup Traefik Network**:
```bash
docker network create traefik
```

2. **Environment Setup**:
```bash
cd deployment/vps
cp .env.example .env
# Edit .env with your configuration (especially APP_DOMAIN)
```

3. **Deploy Traefik** (if not already running):
```bash
# Create Traefik service
docker run -d \
  --name traefik \
  --restart unless-stopped \
  --network traefik \
  -p 80:80 -p 443:443 \
  -v /var/run/docker.sock:/var/run/docker.sock:ro \
  -v $PWD/traefik.yml:/etc/traefik/traefik.yml:ro \
  -v $PWD/dynamic.yml:/etc/traefik/dynamic.yml:ro \
  -v traefik-data:/data \
  traefik:v3.0
```

4. **Deploy Application**:
```bash
docker-compose -f docker-compose.production.yml up -d
```

5. **Key Environment Variables**:
```env
APP_DOMAIN=your-domain.com
ENVIRONMENT=production
DEPLOYMENT_PLATFORM=vps
VPS_REVERSE_PROXY=true
AUTO_SCALE_WORKERS=true
DATABASE_URL=postgresql://user:pass@db:5432/dbname
JWT_SECRET_KEY=your-secret-key
```

#### Configuration Options

- `APP_DOMAIN`: Your application domain (required for Traefik routing)
- `VPS_REVERSE_PROXY`: Enable when running behind Traefik (recommended: true)
- `VPS_STATIC_FILES_PATH`: Directory for static files
- `VPS_ENABLE_METRICS`: Enable `/metrics` endpoint for monitoring
- `AUTO_SCALE_WORKERS`: Automatically scale workers based on CPU
- `MIN_WORKERS` / `MAX_WORKERS`: Worker scaling limits

#### Traefik Features

The deployment includes these Traefik features out of the box:
- **Automatic HTTPS**: Let's Encrypt SSL certificates
- **Load Balancing**: Built-in load balancing with health checks
- **Rate Limiting**: 100 requests/minute average, 50 burst
- **Security Headers**: HSTS, frame denial, XSS protection
- **HTTP to HTTPS Redirect**: Automatic redirection
- **Gzip Compression**: Automatic response compression

### 2. Cloudflare Workers

Cloudflare Workers deployment provides serverless execution with global edge distribution.

#### Features
- **Edge Computing**: Global distribution across 200+ locations
- **KV Storage**: Use Cloudflare KV for caching
- **D1 Database**: Serverless SQL database integration
- **Automatic Scaling**: Serverless scaling based on demand
- **Cost Effective**: Pay-per-request pricing model

#### Quick Start

1. **Install Wrangler CLI**:
```bash
npm install -g wrangler
wrangler login
```

2. **Configure wrangler.toml**:
```bash
cd deployment/cloudflare-workers
# Edit wrangler.toml with your settings
```

3. **Set up bindings**:
```bash
# Create KV namespace
wrangler kv:namespace create "CACHE"

# Create D1 database
wrangler d1 create your-database-name
```

4. **Deploy**:
```bash
npm install
wrangler deploy
```

#### Configuration Options

- `CF_WORKERS_COMPATIBILITY_DATE`: Cloudflare Workers compatibility date
- `CF_WORKERS_MEMORY_LIMIT`: Memory limit in MB (128-1024)
- `CF_WORKERS_TIMEOUT`: Maximum execution time in seconds
- `CF_WORKERS_KV_NAMESPACE`: KV namespace binding for caching
- `CF_WORKERS_D1_DATABASE`: D1 database binding

## Platform Detection

The Faster framework automatically detects the deployment platform:

```python
from faster.core.config import Settings

settings = Settings()
print(f"Detected platform: {settings.detected_platform}")
print(f"Is VPS deployment: {settings.is_vps_deployment}")
print(f"Is Cloudflare Workers: {settings.is_cloudflare_workers}")
```

## Platform-Specific Optimizations

### VPS Optimizations
- **Database Connection Pooling**: Optimized for persistent connections
- **Redis Integration**: Full Redis feature support including pub/sub
- **Static File Serving**: Direct static file serving
- **Metrics Collection**: Prometheus metrics endpoint
- **Process Management**: Multi-worker support with auto-scaling

### Cloudflare Workers Optimizations
- **KV Storage**: Replaces Redis for caching operations
- **D1 Database**: Serverless database for data persistence
- **Middleware Optimization**: Reduces middleware overhead
- **Documentation Disabled**: API docs disabled in production
- **Memory Management**: Optimized for limited memory environment

## Migration Guide

### From Standard Deployment to VPS

1. Set environment variables:
```env
DEPLOYMENT_PLATFORM=vps
VPS_REVERSE_PROXY=true  # if using Nginx/Apache
```

2. Configure reverse proxy (Nginx example provided)

3. Enable metrics and health checks:
```env
VPS_ENABLE_METRICS=true
```

### From VPS to Cloudflare Workers

1. Update configuration:
```env
DEPLOYMENT_PLATFORM=cloudflare-workers
```

2. Set up KV and D1 bindings in wrangler.toml

3. Deploy using Wrangler CLI

## Monitoring and Observability

### VPS Monitoring
- **Health Endpoint**: `GET /health` (integrated with Traefik health checks)
- **Metrics Endpoint**: `GET /metrics` (Prometheus format, IP-restricted)
- **Traefik Dashboard**: Access at `https://your-domain.com:8080` (if enabled)
- **Log Aggregation**: Structured JSON logging

### Cloudflare Workers Monitoring
- **Workers Analytics**: Built-in Cloudflare analytics
- **Real User Monitoring**: Automatic RUM data collection
- **Error Tracking**: Integration with Sentry

## Best Practices

### Security
- Use environment variables for secrets
- Enable SSL/TLS in production
- Configure CORS properly
- Implement rate limiting (VPS: Nginx, Workers: automatic)

### Performance
- Enable compression (automatic in Workers)
- Use CDN for static assets
- Implement proper caching strategies
- Monitor resource usage

### Reliability
- Set up health checks
- Configure graceful shutdowns
- Implement circuit breakers
- Use database connection pooling

## Troubleshooting

### Common VPS Issues
1. **Domain Not Resolving**: Ensure `APP_DOMAIN` is set correctly and DNS points to server
2. **SSL Certificate Issues**: Check Let's Encrypt rate limits and domain validation
3. **Traefik Network Issues**: Verify `traefik` network exists: `docker network create traefik`
4. **Database Connection Errors**: Check connection string and network connectivity
5. **Static Files Not Loading**: Verify `VPS_STATIC_FILES_PATH` setting and volume mounts

### Common Cloudflare Workers Issues
1. **Memory Limit Exceeded**: Increase `CF_WORKERS_MEMORY_LIMIT`
2. **Timeout Errors**: Adjust `CF_WORKERS_TIMEOUT` setting
3. **KV Not Accessible**: Verify namespace binding in wrangler.toml

## Support

For deployment-specific questions:
1. Check the deployment logs
2. Verify environment variable configuration
3. Test with platform detection utility
4. Review platform-specific documentation

## Examples

See the `examples/` directory for complete working examples of both deployment types.