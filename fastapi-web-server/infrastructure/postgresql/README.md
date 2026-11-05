# PostgreSQL Database Layer

This directory contains the database infrastructure for the UUDEX FastAPI web server project. It provides PostgreSQL database and RabbitMQ message broker services using Docker Compose.

## Overview

The database layer includes:

- **PostgreSQL 14.1**: Primary database server with Alpine Linux base
- **RabbitMQ**: Message broker for asynchronous processing with management interface
- **Persistent Storage**: Docker volumes for data persistence
- **Database Initialization**: Custom SQL scripts for UUDEX schema setup

## Services

### PostgreSQL Database

- **Image**: `postgres:14.1-alpine`
- **Container**: `postgres`
- **Port**: `5432` (exposed to host)
- **Authentication**: MD5 with default postgres/postgres credentials
- **Data Volume**: `~/.docker-conf/postgresql_data` (persistent storage)
- **Init Scripts**: `./db-init-us` directory mounted for database initialization

### RabbitMQ Message Broker

- **Image**: `rabbitmq:3-management`
- **Container**: `rabbitmq`
- **Ports**:
  - `5672`: AMQP protocol
  - `15672`: Management web interface
- **Credentials**: `uudex/uudex` (default user/password)
- **Data Volume**: `~/.docker-conf/rabbitmq/data` (persistent storage)
- **Log Volume**: `~/.docker-conf/rabbitmq/log` (log files)

## Quick Start

### Start Services

```bash
# Navigate to postgresql directory
cd infrastructure/postgresql

# Start both database and RabbitMQ
docker-compose up -d

# Verify services are running
docker-compose ps
```

### Stop Services

```bash
# Stop services
docker-compose down

# Stop and remove volumes (data will be lost)
docker-compose down -v
```

### Restart with Fresh Data

Use the provided restart script to completely reset the database:

```bash
# Navigate to postgresql directory
cd infrastructure/postgresql

# Run restart script (removes all data and recreates)
python restart_docker_compose.py
```

**Warning**: This script removes all PostgreSQL data from `~/.docker-conf/postgresql_data/`

## Database Initialization

### Init Scripts Directory

The `db-init-us/` directory contains SQL scripts that are automatically executed when the PostgreSQL container starts for the first time:

1. **`01_create_role.sql`**: Creates database roles and users
2. **`02_create_db.sql`**: Creates the UUDEX database
3. **`03_uudex.sql`**: UUDEX-specific schema and data (excluded from git)

### Security Notice

The `03_uudex.sql` file is intentionally excluded from version control via `.gitignore` as it may contain sensitive database schema or data specific to your deployment.

## Connection Information

### PostgreSQL Connection

```bash
# Connection details
Host: localhost
Port: 5432
Database: postgres (or uudex after init)
Username: postgres
Password: postgres
```

### RabbitMQ Connection

```bash
# AMQP Connection
Host: localhost
Port: 5672
Username: uudex
Password: uudex

# Management Interface
URL: http://localhost:15672
Username: uudex
Password: uudex
```

## Data Persistence

### PostgreSQL Data

Data is stored in `~/.docker-conf/postgresql_data/` on the host system. This ensures data persists across container restarts.

### RabbitMQ Data

- **Data**: `~/.docker-conf/rabbitmq/data/`
- **Logs**: `~/.docker-conf/rabbitmq/log/`

## Development Workflow

### Normal Development

```bash
# Start services
docker-compose up -d

# Check logs
docker-compose logs -f

# Connect to database
psql -h localhost -U postgres -d postgres
```

### Reset Database

```bash
# Option 1: Use restart script
python restart_docker_compose.py

# Option 2: Manual reset
docker-compose down
sudo rm -rf ~/.docker-conf/postgresql_data/
docker-compose up -d
```

### Backup and Restore

```bash
# Backup database
docker exec postgres pg_dump -U postgres postgres > backup.sql

# Restore database
docker exec -i postgres psql -U postgres postgres < backup.sql
```

## Monitoring and Logs

### View Logs

```bash
# All services
docker-compose logs -f

# PostgreSQL only
docker-compose logs -f db

# RabbitMQ only
docker-compose logs -f rabbitmq
```

### Check Service Status

```bash
# Service status
docker-compose ps

# Resource usage
docker stats postgres rabbitmq
```

### RabbitMQ Management

Access the RabbitMQ management interface at `http://localhost:15672` to:

- Monitor queues and exchanges
- View connection statistics
- Manage users and permissions
- Monitor message rates

## Troubleshooting

### Common Issues

#### Port Conflicts

If ports 5432 or 5672 are already in use:

```bash
# Check what's using the ports
sudo lsof -i :5432
sudo lsof -i :5672

# Modify docker-compose.yml to use different ports
ports:
  - '5433:5432'  # Use 5433 instead of 5432
```

#### Permission Issues

```bash
# Fix volume permissions
sudo chown -R $USER:$USER ~/.docker-conf/postgresql_data/
sudo chown -R $USER:$USER ~/.docker-conf/rabbitmq/
```

#### Database Connection Refused

```bash
# Check if container is running
docker ps | grep postgres

# Check container logs
docker logs postgres

# Verify port mapping
docker port postgres
```

#### Init Scripts Not Running

Init scripts only run on first container creation. If they're not running:

```bash
# Remove existing data and recreate
docker-compose down
sudo rm -rf ~/.docker-conf/postgresql_data/
docker-compose up -d
```

### Useful Commands

```bash
# Connect to PostgreSQL container
docker exec -it postgres psql -U postgres

# Connect to RabbitMQ container
docker exec -it rabbitmq bash

# View PostgreSQL configuration
docker exec postgres cat /var/lib/postgresql/data/postgresql.conf

# Check RabbitMQ status
docker exec rabbitmq rabbitmqctl status
```

## Environment Variables

You can customize the setup by modifying the environment variables in `docker-compose.yml`:

| Service | Variable | Default | Description |
|---------|----------|---------|-------------|
| PostgreSQL | `POSTGRES_USER` | `postgres` | Database superuser |
| PostgreSQL | `POSTGRES_PASSWORD` | `postgres` | Superuser password |
| PostgreSQL | `POSTGRES_HOST_AUTH_METHOD` | `md5` | Authentication method |
| RabbitMQ | `RABBITMQ_DEFAULT_USER` | `uudex` | Default username |
| RabbitMQ | `RABBITMQ_DEFAULT_PASS` | `uudex` | Default password |

## Security Considerations

### Development Environment

The current configuration is designed for development and includes:

- Default passwords (should be changed for production)
- Exposed ports on localhost
- Permissive authentication methods

### Production Recommendations

For production deployment:

1. **Change default passwords**
2. **Use environment variables for credentials**
3. **Restrict network access**
4. **Enable SSL/TLS connections**
5. **Regular backups**
6. **Monitor resource usage**

## Integration with FastAPI

The UUDEX FastAPI application connects to these services using:

- **PostgreSQL**: For persistent data storage
- **RabbitMQ**: For asynchronous task processing

Connection strings and credentials should be configured in your FastAPI application's environment variables or configuration files.
