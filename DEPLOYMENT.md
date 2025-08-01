# Munchzone Production Deployment Guide

This guide covers deploying the Munchzone Django application to production using Caddy as a reverse proxy with automatic HTTPS termination.

## Architecture Overview

- **Caddy**: Handles HTTPS termination, serves static/media files, reverse proxy to Django
- **Django**: Runs on HTTP only via Uvicorn ASGI server
- **PostgreSQL**: Database with PostGIS extension for geographic data
- **System**: Ubuntu/Debian-based server

## 1. Server Setup

### Create application user
```bash
sudo useradd -m -s /bin/bash munch
```

## 2. Database Setup

### Create PostgreSQL user and database
```bash
# Create user without password (will use peer authentication)
sudo -u postgres createuser --createdb munch
sudo -u postgres createdb -O munch munch
```

### Enable PostGIS extension
```bash
sudo -u postgres psql -d munch -c "CREATE EXTENSION IF NOT EXISTS postgis;"
sudo -u postgres psql -d munch -c "CREATE EXTENSION IF NOT EXISTS postgis_topology;"
```


## 3. Application Deployment

### Switch to application user
```bash
sudo su - munch
```

### Install uv (Python package manager)
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
source $HOME/.cargo/env
```

### Clone repository
```bash
cd /home/munch
git clone https://github.com/leifmetcalf/munch-claude.git munchzone
cd munchzone
```

### Install Python dependencies
```bash
uv sync
```

**Note**: Node.js/npm is not required for deployment as Tailwind CSS outputs are already compiled and included in the source tree.

### Create environment file
```bash
nano /home/munch/munchzone/systemd.env
```

Add the following content:
```bash
# Django Settings
SECRET_KEY=your-very-long-secret-key-here-change-this

# Database
DB_NAME=munch
DB_USER=munch
# DB_HOST and DB_PORT are not needed when using unix socket connection
# DB_PASSWORD is not needed when using peer authentication
```

**Important**: Generate a secure SECRET_KEY:
```bash
uv run python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

### Set environment file permissions
```bash
chmod 600 /home/munch/munchzone/systemd.env
```

### Build static files
```bash
set -a; source systemd.env; set +a
uv run manage.py collectstatic --noinput
```

### Set static files permissions
```bash
# Exit munch user session
exit

# Set permissions so Caddy can serve static files
sudo chmod 755 /home/munch
sudo chmod 755 /home/munch/munchzone
sudo chmod -R 755 /home/munch/munchzone/staticfiles
sudo chmod -R 755 /home/munch/munchzone/media
```

### Run database migrations
```bash
set -a; source systemd.env; set +a
uv run manage.py migrate
```

### Create Django superuser
```bash
set -a; source systemd.env; set +a
uv run manage.py createsuperuser
```

### Test the application
```bash
set -a; source systemd.env; set +a
uv run manage.py check --deploy
```

## 4. Uvicorn Configuration

### Install Uvicorn
```bash
uv add "uvicorn[standard]"
```

### Create systemd service file
Exit the munch user session and return to admin user:
```bash
exit
```

Create the systemd service file:
```bash
sudo nano /etc/systemd/system/munchzone.service
```

Add the following content:
```ini
[Unit]
Description=Munchzone Django Application
After=network.target postgresql.service
Requires=postgresql.service

[Service]
Type=exec
User=munch
Group=munch
WorkingDirectory=/home/munch/munchzone
EnvironmentFile=/home/munch/munchzone/systemd.env
ExecStart=/home/munch/.local/bin/uv run uvicorn munch.asgi:application --host 127.0.0.1 --port 8000
Restart=on-failure
RestartSec=5
StartLimitBurst=3
StartLimitIntervalSec=60

# Security hardening
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=true
PrivateTmp=true

# Allow Django to write to required directories
ReadWritePaths=/home/munch/munchzone/media
ReadWritePaths=/home/munch/munchzone/staticfiles

# Process management
KillMode=mixed
TimeoutStopSec=30

[Install]
WantedBy=multi-user.target
```

### Enable and start the service
```bash
sudo systemctl daemon-reload
sudo systemctl enable munchzone
sudo systemctl start munchzone
sudo systemctl status munchzone
```

## 5. Caddy Installation and Configuration

### Install Caddy
```bash
sudo apt install -y debian-keyring debian-archive-keyring apt-transport-https curl
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | sudo tee /etc/apt/sources.list.d/caddy-stable.list
chmod o+r /usr/share/keyrings/caddy-stable-archive-keyring.gpg
chmod o+r /etc/apt/sources.list.d/caddy-stable.list
sudo apt update
sudo apt install caddy
```

### Create Caddyfile
```bash
sudo nano /etc/caddy/Caddyfile
```

Add the following content:
```caddy
www.munchzone.net {
    redir https://munchzone.net{uri}
}

munchzone.net {
    # Serve static files
    handle_path /static/* {
        file_server {
            root /home/munch/munchzone/staticfiles
        }
    }
    
    # Serve media files
    handle_path /media/* {
        file_server {
            root /home/munch/munchzone/media
        }
    }
    
    # Proxy everything else to Django
    reverse_proxy 127.0.0.1:8000
}
```


### Test Caddy configuration
```bash
sudo caddy validate --config /etc/caddy/Caddyfile
```

### Enable and start Caddy
```bash
sudo systemctl enable caddy
sudo systemctl start caddy
sudo systemctl status caddy
```

## 6. Firewall Configuration

### Configure UFW firewall
```bash
sudo ufw allow 22/tcp      # SSH
sudo ufw allow 80/tcp      # HTTP
sudo ufw allow 443/tcp     # HTTPS
sudo ufw enable
```

## 7. Deployment Checklist

### Pre-deployment
- [ ] Domain DNS points to server IP
- [ ] Server has sufficient resources (2GB+ RAM)
- [ ] Firewall configured (ports 22, 80, 443)
- [ ] SSL certificates can be obtained (port 80/443 accessible)

### During deployment
- [ ] Database created and PostGIS extension enabled
- [ ] Environment variables configured
- [ ] Static files collected
- [ ] Database migrations applied
- [ ] Superuser created
- [ ] Django deployment check passes
- [ ] Uvicorn service starts successfully
- [ ] Caddy configuration validates
- [ ] HTTPS redirects working
- [ ] Static files served correctly
- [ ] Media files upload/serve correctly

### Post-deployment
- [ ] Monitor logs for errors
- [ ] Verify all functionality works
- [ ] Set up monitoring/alerting
- [ ] Configure automated backups
- [ ] Document any custom configurations
- [ ] Plan regular security updates

## 8. Maintenance

### Regular tasks
- **Weekly**: Review logs for errors or security issues
- **Monthly**: Update system packages and restart services
- **Quarterly**: Review and rotate secret keys if needed
- **As needed**: Update Django and dependencies

### Update deployment
```bash
# Switch to application user
sudo su - munch
cd /home/munch/munchzone

# Pull latest changes
git pull origin master

# Update dependencies
uv sync

# Rebuild static files
set -a; source systemd.env; set +a && uv run manage.py collectstatic --noinput

# Apply database migrations
set -a; source systemd.env; set +a && uv run manage.py migrate

# Restart services
sudo systemctl restart munchzone
```

This deployment guide provides a robust, production-ready setup for Munchzone with automatic HTTPS, proper security headers, and efficient static file serving through Caddy.
