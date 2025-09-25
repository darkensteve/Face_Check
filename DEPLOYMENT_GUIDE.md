# Production Deployment Guide - Face_Check

This guide provides comprehensive instructions for deploying Face_Check in production environments.

## 🚀 Production Checklist

### ✅ Pre-Deployment Security Checklist

**Critical Security Tasks:**
- [ ] Change default admin password (`admin` / `admin123`)
- [ ] Set strong `SECRET_KEY` in environment variables
- [ ] Configure HTTPS/SSL certificates
- [ ] Set up firewall rules
- [ ] Configure secure database permissions
- [ ] Remove debug mode (`FLASK_ENV=production`)
- [ ] Update all dependencies to latest versions
- [ ] Configure log rotation and monitoring

**Configuration Security:**
- [ ] Use environment variables for sensitive data
- [ ] Secure file upload directories
- [ ] Configure rate limiting appropriately
- [ ] Set up proper session timeouts
- [ ] Configure CORS policies if needed

## 🌍 Deployment Methods

### Method 1: Local Server Deployment

#### Using Gunicorn (Recommended)

1. **Install Gunicorn**
   ```bash
   pip install gunicorn
   ```

2. **Create Gunicorn Configuration**
   ```python
   # gunicorn_config.py
   bind = "0.0.0.0:5000"
   workers = 4
   worker_class = "sync"
   timeout = 300
   keepalive = 5
   max_requests = 1000
   max_requests_jitter = 50
   preload_app = True
   
   # Logging
   accesslog = "logs/access.log"
   errorlog = "logs/error.log"
   loglevel = "info"
   
   # Security
   limit_request_line = 4096
   limit_request_fields = 100
   limit_request_field_size = 8190
   ```

3. **Start the Application**
   ```bash
   # Create logs directory
   mkdir -p logs
   
   # Start with Gunicorn
   gunicorn -c gunicorn_config.py app:app
   ```

#### Using uWSGI

1. **Install uWSGI**
   ```bash
   pip install uwsgi
   ```

2. **Create uWSGI Configuration**
   ```ini
   # uwsgi.ini
   [uwsgi]
   module = app:app
   master = true
   processes = 4
   socket = face_check.sock
   chmod-socket = 666
   vacuum = true
   die-on-term = true
   logto = logs/uwsgi.log
   ```

3. **Start the Application**
   ```bash
   uwsgi --ini uwsgi.ini
   ```

### Method 2: Docker Deployment

#### Create Dockerfile
```dockerfile
# Dockerfile
FROM python:3.13-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    cmake \
    build-essential \
    libopencv-dev \
    python3-opencv \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install face recognition dependencies
RUN pip install dlib-bin face-recognition face_recognition_models setuptools

# Copy application code
COPY . .

# Create necessary directories
RUN mkdir -p known_faces temp face_features attendance logs

# Initialize database
RUN python db.py

# Expose port
EXPOSE 5000

# Start application
CMD ["gunicorn", "-c", "gunicorn_config.py", "app:app"]
```

#### Create Docker Compose
```yaml
# docker-compose.yml
version: '3.8'

services:
  face_check:
    build: .
    ports:
      - "5000:5000"
    volumes:
      - ./data:/app/data
      - ./logs:/app/logs
      - ./known_faces:/app/known_faces
      - ./face_features:/app/face_features
    environment:
      - FLASK_ENV=production
      - SECRET_KEY=your-super-secret-production-key
    restart: unless-stopped

  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
      - ./ssl:/etc/nginx/ssl
    depends_on:
      - face_check
    restart: unless-stopped
```

#### Deploy with Docker
```bash
# Build and start
docker-compose up -d

# View logs
docker-compose logs -f face_check

# Stop services
docker-compose down
```

### Method 3: Cloud Deployment (AWS/Azure/GCP)

#### AWS EC2 Deployment

1. **Launch EC2 Instance**
   - Choose Ubuntu 22.04 LTS
   - Select appropriate instance size (t3.medium recommended)
   - Configure security groups (ports 22, 80, 443)

2. **Setup Server**
   ```bash
   # Connect to instance
   ssh -i your-key.pem ubuntu@your-ec2-ip
   
   # Update system
   sudo apt update && sudo apt upgrade -y
   
   # Install Python and dependencies
   sudo apt install python3 python3-pip python3-venv git -y
   
   # Clone and setup application
   git clone https://github.com/darkensteve/Face_Check.git
   cd Face_Check
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   pip install gunicorn
   
   # Install face recognition dependencies
   pip install dlib-bin face-recognition face_recognition_models setuptools
   ```

3. **Setup Systemd Service**
   ```ini
   # /etc/systemd/system/face-check.service
   [Unit]
   Description=Face_Check Application
   After=network.target
   
   [Service]
   User=ubuntu
   Group=ubuntu
   WorkingDirectory=/home/ubuntu/Face_Check
   Environment=PATH=/home/ubuntu/Face_Check/.venv/bin
   ExecStart=/home/ubuntu/Face_Check/.venv/bin/gunicorn -c gunicorn_config.py app:app
   Restart=always
   
   [Install]
   WantedBy=multi-user.target
   ```

4. **Start Service**
   ```bash
   sudo systemctl enable face-check
   sudo systemctl start face-check
   sudo systemctl status face-check
   ```

## 🔒 SSL/HTTPS Configuration

### Using Let's Encrypt (Recommended)

1. **Install Certbot**
   ```bash
   sudo apt install certbot python3-certbot-nginx -y
   ```

2. **Setup Nginx Configuration**
   ```nginx
   # /etc/nginx/sites-available/face_check
   server {
       listen 80;
       server_name your-domain.com www.your-domain.com;
       
       location / {
           proxy_pass http://localhost:5000;
           proxy_set_header Host $host;
           proxy_set_header X-Real-IP $remote_addr;
           proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
           proxy_set_header X-Forwarded-Proto $scheme;
       }
       
       client_max_body_size 16M;
   }
   ```

3. **Enable Site and Get SSL Certificate**
   ```bash
   sudo ln -s /etc/nginx/sites-available/face_check /etc/nginx/sites-enabled/
   sudo nginx -t
   sudo systemctl reload nginx
   sudo certbot --nginx -d your-domain.com -d www.your-domain.com
   ```

### Manual SSL Configuration

```nginx
# /etc/nginx/sites-available/face_check
server {
    listen 80;
    server_name your-domain.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name your-domain.com;

    ssl_certificate /path/to/your/certificate.crt;
    ssl_certificate_key /path/to/your/private.key;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-RSA-AES256-GCM-SHA384:ECDHE-RSA-AES128-GCM-SHA256;

    location / {
        proxy_pass http://localhost:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
    
    client_max_body_size 16M;
}
```

## 🎛️ Environment Configuration

### Production Environment Variables

Create `.env` file:
```bash
# .env (Production)
FLASK_ENV=production
SECRET_KEY=your-super-secure-secret-key-minimum-32-characters
DATABASE_URL=sqlite:///data/facecheck.db

# Security Settings
SESSION_TIMEOUT=1800
MAX_LOGIN_ATTEMPTS=5
RATE_LIMIT_PER_MINUTE=60
MAX_UPLOAD_SIZE=16777216

# Face Recognition Settings
FACE_RECOGNITION_TOLERANCE=0.6
FACE_DETECTION_MODEL=hog

# Logging
LOG_LEVEL=INFO
LOG_FILE=logs/app.log

# Email Configuration (optional)
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USE_TLS=True
MAIL_USERNAME=your-email@domain.com
MAIL_PASSWORD=your-app-password
```

### Load Environment Variables

Update `app.py` to load environment variables:
```python
# app.py (add at top)
import os
from dotenv import load_dotenv

load_dotenv()

# Configuration
class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'fallback-secret-key'
    DATABASE_URL = os.environ.get('DATABASE_URL') or 'sqlite:///facecheck.db'
    MAX_UPLOAD_SIZE = int(os.environ.get('MAX_UPLOAD_SIZE', 16777216))
    SESSION_TIMEOUT = int(os.environ.get('SESSION_TIMEOUT', 1800))

app.config.from_object(Config)
```

## 📊 Monitoring and Logging

### Setup Application Logging

```python
# logging_config.py
import logging
import logging.handlers
import os

def setup_logging(app):
    if not os.path.exists('logs'):
        os.makedirs('logs')
    
    # File handler
    file_handler = logging.handlers.RotatingFileHandler(
        'logs/app.log', maxBytes=10240000, backupCount=10)
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s %(levelname)s %(name)s %(threadName)s : %(message)s'))
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter(
        '%(asctime)s %(levelname)s: %(message)s'))
    
    app.logger.addHandler(file_handler)
    app.logger.addHandler(console_handler)
    app.logger.setLevel(logging.INFO)
```

### System Monitoring Script

```bash
#!/bin/bash
# monitor.sh

check_service() {
    if systemctl is-active --quiet face-check; then
        echo "✅ Face_Check service is running"
    else
        echo "❌ Face_Check service is down"
        systemctl restart face-check
    fi
}

check_disk_space() {
    USAGE=$(df / | awk 'NR==2 {print $5}' | sed 's/%//')
    if [ $USAGE -gt 90 ]; then
        echo "⚠️ Disk usage is ${USAGE}%"
    fi
}

check_logs() {
    LOG_SIZE=$(du -sh logs/ | cut -f1)
    echo "📄 Log size: $LOG_SIZE"
    
    # Clean old logs
    find logs/ -name "*.log.*" -mtime +30 -delete
}

# Run checks
check_service
check_disk_space
check_logs
```

### Crontab for Regular Monitoring

```bash
# Add to crontab: crontab -e
# Check service every 5 minutes
*/5 * * * * /path/to/Face_Check/monitor.sh

# Daily backup
0 2 * * * cp /path/to/Face_Check/facecheck.db /path/to/backups/facecheck_$(date +\%Y\%m\%d).db

# Weekly log cleanup
0 1 * * 0 find /path/to/Face_Check/logs/ -name "*.log.*" -mtime +7 -delete
```

## 🔧 Performance Optimization

### Database Optimization

```python
# performance_tuning.py
import sqlite3

def optimize_database():
    conn = sqlite3.connect('facecheck.db')
    cursor = conn.cursor()
    
    # Create indexes for better performance
    indexes = [
        "CREATE INDEX IF NOT EXISTS idx_user_username ON user(username);",
        "CREATE INDEX IF NOT EXISTS idx_user_email ON user(email);",
        "CREATE INDEX IF NOT EXISTS idx_attendance_student ON attendance(student_id);",
        "CREATE INDEX IF NOT EXISTS idx_attendance_date ON attendance(date);",
    ]
    
    for index in indexes:
        cursor.execute(index)
    
    # Analyze database for query optimization
    cursor.execute("ANALYZE;")
    
    # Vacuum to reclaim space
    cursor.execute("VACUUM;")
    
    conn.commit()
    conn.close()
```

### Application Performance Settings

```python
# gunicorn_config.py (optimized)
import multiprocessing

# Server socket
bind = "0.0.0.0:5000"
backlog = 2048

# Worker processes
workers = multiprocessing.cpu_count() * 2 + 1
worker_class = "gevent"  # For I/O intensive applications
worker_connections = 1000
max_requests = 1000
max_requests_jitter = 50

# Timeout settings
timeout = 300
keepalive = 5
graceful_timeout = 30

# Memory management
preload_app = True
max_worker_memory = 200000  # 200MB

# Security
limit_request_line = 4096
limit_request_fields = 100
limit_request_field_size = 8190
```

## 🛡️ Security Hardening

### Firewall Configuration

```bash
# UFW Firewall setup
sudo ufw enable
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow ssh
sudo ufw allow 80
sudo ufw allow 443

# Rate limiting for SSH
sudo ufw limit ssh
```

### Application Security Headers

```python
# security_headers.py
from flask import Flask

def add_security_headers(app):
    @app.after_request
    def set_security_headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['X-XSS-Protection'] = '1; mode=block'
        response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
        response.headers['Content-Security-Policy'] = "default-src 'self'"
        return response
```

### Regular Security Updates

```bash
#!/bin/bash
# security_update.sh

# Update system packages
sudo apt update && sudo apt upgrade -y

# Update Python packages
source .venv/bin/activate
pip list --outdated --format=freeze | grep -v '^\-e' | cut -d = -f 1 | xargs -n1 pip install -U

# Check for security vulnerabilities
pip-audit

# Restart services
sudo systemctl restart face-check
sudo systemctl restart nginx
```

## 📋 Deployment Checklist

### Pre-Deployment
- [ ] All tests passing locally
- [ ] Environment variables configured
- [ ] Database initialized and migrated
- [ ] SSL certificates ready
- [ ] Monitoring scripts prepared
- [ ] Backup strategy implemented

### During Deployment
- [ ] Deploy code to production server
- [ ] Install dependencies in virtual environment
- [ ] Configure web server (Nginx/Apache)
- [ ] Set up SSL/HTTPS
- [ ] Configure systemd service
- [ ] Test all functionality

### Post-Deployment
- [ ] Verify application is accessible
- [ ] Test face recognition functionality
- [ ] Check database connectivity
- [ ] Verify logging is working
- [ ] Set up monitoring alerts
- [ ] Schedule regular backups
- [ ] Document deployment process

---

**⚠️ Important Notes:**
- Always test deployments in staging environment first
- Keep regular backups of database and face recognition data
- Monitor system resources and application performance
- Keep all dependencies updated for security
- Have a rollback plan ready for critical issues