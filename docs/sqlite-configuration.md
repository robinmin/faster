# 🗄️ SQLite Configuration Guide - Docker Edition

## 🎯 **Why SQLite for Docker?**

Your Docker setup now uses **SQLite** instead of PostgreSQL for several compelling reasons:

### ✅ **Advantages**
- **⚡ Faster Startup**: No separate database container to initialize
- **💾 Smaller Memory Footprint**: Eliminates PostgreSQL overhead
- **🔧 Simpler Setup**: One less service to manage
- **📦 Portable**: Database file travels with your application
- **🧪 Perfect for Testing**: In-memory SQLite for ultra-fast tests
- **🔄 Consistent Environment**: Same database engine across all environments

### 🎯 **When SQLite Works Best**
- **Development & Testing**: Fast iteration cycles
- **Single-Application Deployments**: Containerized apps
- **Read-Heavy Workloads**: Excellent performance for most use cases
- **Small to Medium Data**: < 1TB databases
- **Embedded Applications**: Self-contained deployments

---

## 📁 **Environment File Structure**

Your Docker setup uses **file-based environment configuration** instead of inline environment variables:

```
docker/
├── .env.dev       # Development configuration
├── .env.test      # Testing configuration (in-memory SQLite)
├── .env.prod      # Production configuration
└── docker-compose*.yml  # Reference env files
```

### 🔧 **Environment File Benefits**
- **🔐 Security**: Keep secrets out of Docker files
- **🔄 Flexibility**: Easy environment switching
- **📋 Version Control**: Template files in git, actual values in .env files
- **🛠️ Maintainability**: Centralized configuration management

---

## 🗄️ **SQLite Configuration Options**

### **🚀 Development** (`.env.dev`)
```bash
# Persistent SQLite with volume mount
DATABASE_URL=sqlite+aiosqlite:///./data/dev.db
```

### **🧪 Testing** (`.env.test`)
```bash
# In-memory SQLite for maximum speed
DATABASE_URL=sqlite+aiosqlite:///:memory:
```

### **🌟 Production** (`.env.prod`)
```bash
# Persistent SQLite with backups
DATABASE_URL=sqlite+aiosqlite:///./data/production.db
```

---

## 🐳 **Docker Volume Strategy**

### **📦 Volume Mapping**

| Environment | Volume | Purpose |
|-------------|--------|---------|
| **Development** | `app_data:/app/data` | Persistent dev database |
| **Testing** | `test_data:/app/data` | Isolated test data |
| **Production** | `app_data:/app/data` | Production database storage |

### **🔧 Volume Commands**
```bash
# View volumes
docker volume ls

# Inspect volume
docker volume inspect faster_app_data

# Backup database
docker run --rm -v faster_app_data:/data -v $(pwd):/backup alpine tar czf /backup/db-backup.tar.gz /data

# Restore database
docker run --rm -v faster_app_data:/data -v $(pwd):/backup alpine tar xzf /backup/db-backup.tar.gz -C /
```

---

## 🧪 **Testing Configuration**

### **⚡ In-Memory Testing**
```yaml
# docker-compose.test.yml
services:
  app-test:
    env_file:
      - docker/.env.test  # Uses :memory: SQLite
```

**Benefits:**
- **🚀 Ultra Fast**: No disk I/O
- **🧹 Clean Slate**: Fresh database for each test
- **🔄 Parallel Tests**: No database conflicts
- **💾 Resource Efficient**: Minimal memory usage

### **🔬 Test Data Management**
```bash
# Each test container gets isolated data
volumes:
  - test_data:/app/data   # Isolated from other environments
```

---

## 📊 **Performance Considerations**

### **🎯 SQLite Performance Tips**

1. **WAL Mode** (Write-Ahead Logging)
```python
# In your FastAPI app configuration
PRAGMA journal_mode=WAL;
PRAGMA synchronous=NORMAL;
PRAGMA cache_size=1000000;
PRAGMA temp_store=memory;
```

2. **Connection Pooling**
```python
# SQLite doesn't need traditional pooling, but async connection management
DATABASE_URL="sqlite+aiosqlite:///./data/app.db?check_same_thread=False"
```

3. **Backup Strategy**
```bash
# Regular backups in production
sqlite3 /app/data/production.db ".backup /app/data/backup.db"
```

---

## 🔄 **Migration from PostgreSQL**

If you need to migrate existing PostgreSQL data to SQLite:

### **1. Export PostgreSQL Data**
```bash
pg_dump --data-only --inserts your_database > data_export.sql
```

### **2. Clean SQL for SQLite**
```bash
# Remove PostgreSQL-specific syntax
sed -i 's/SEQUENCE/AUTOINCREMENT/g' data_export.sql
sed -i 's/SERIAL/INTEGER/g' data_export.sql
```

### **3. Import to SQLite**
```bash
sqlite3 app.db < cleaned_data_export.sql
```

### **4. Update Alembic Migrations**
```python
# Recreate migrations for SQLite
alembic init --template generic migrations
alembic revision --autogenerate -m "Initial SQLite migration"
```

---

## 🚀 **Deployment Considerations**

### **☁️ Cloud Deployment with SQLite**

#### **✅ Good for:**
- **Single Container Apps**: One app instance
- **Read-Heavy Workloads**: High read performance
- **Development/Testing**: Fast iteration
- **Small Applications**: Minimal infrastructure

#### **⚠️ Consider Alternatives for:**
- **High Concurrency Writes**: Multiple writers
- **Distributed Systems**: Multiple app instances
- **Very Large Databases**: > 1TB data
- **Complex Queries**: Advanced SQL features

### **🔄 Scaling Strategy**
```bash
# Start with SQLite
DATABASE_URL=sqlite+aiosqlite:///./data/app.db

# Scale to PostgreSQL when needed (via environment variables)
DATABASE_URL=postgresql+asyncpg://user:pass@db:5432/app
```

---

## 🛡️ **Backup & Recovery**

### **📋 Automated Backup Script**
```bash
#!/bin/bash
# backup-sqlite.sh

DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/app/backups"
DB_FILE="/app/data/production.db"

mkdir -p $BACKUP_DIR

# Create backup
sqlite3 $DB_FILE ".backup ${BACKUP_DIR}/backup_${DATE}.db"

# Compress backup
gzip "${BACKUP_DIR}/backup_${DATE}.db"

# Keep only last 7 days of backups
find $BACKUP_DIR -name "backup_*.db.gz" -mtime +7 -delete

echo "Backup completed: backup_${DATE}.db.gz"
```

### **🔧 Docker Backup Integration**
```yaml
# Add to docker-compose-full.yml
services:
  backup:
    image: alpine
    volumes:
      - app_data:/app/data:ro
      - ./backups:/backups
    command: |
      sh -c "
        apk add --no-cache sqlite &&
        sqlite3 /app/data/production.db '.backup /backups/backup_$(date +%Y%m%d_%H%M%S).db'
      "
    profiles:
      - backup  # Only run when explicitly called
```

---

## 🔍 **Monitoring & Maintenance**

### **📊 SQLite Health Checks**
```python
# Add to your FastAPI health endpoint
@app.get("/health")
async def health_check():
    try:
        # Test database connection
        async with get_session() as session:
            await session.execute(text("SELECT 1"))

        return {
            "status": "healthy",
            "database": "sqlite",
            "timestamp": datetime.utcnow()
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.utcnow()
        }
```

### **🔧 Database Maintenance**
```bash
# Optimize SQLite database
sqlite3 /app/data/production.db "VACUUM;"
sqlite3 /app/data/production.db "ANALYZE;"

# Check database integrity
sqlite3 /app/data/production.db "PRAGMA integrity_check;"
```

---

## 📝 **Best Practices**

### **✅ Do's**
1. **Use WAL mode** for better concurrency
2. **Regular backups** in production
3. **Monitor database size** and performance
4. **Use foreign keys** for data integrity
5. **Optimize queries** with proper indexes

### **❌ Don'ts**
1. **Don't share database files** between containers
2. **Don't skip migrations** when schema changes
3. **Don't ignore backup strategies**
4. **Don't use for high-concurrency writes**
5. **Don't store large files** in SQLite

### **🔄 Migration Path**
Start with SQLite → Monitor performance → Scale to PostgreSQL if needed

---

## 🎉 **Summary**

Your enhanced Docker setup with SQLite provides:

- **⚡ Faster Development**: No database container startup delays
- **🧪 Efficient Testing**: In-memory SQLite for ultra-fast tests
- **🔧 Simpler Configuration**: File-based environment management
- **📦 Portable Deployment**: Self-contained application
- **🔄 Scalability**: Easy migration path to PostgreSQL when needed

**Perfect for**: Development, testing, small to medium applications, and single-container deployments.

---

*Updated: September 2024 - Optimized for Docker deployment with SQLite*