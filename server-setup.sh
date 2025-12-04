#!/bin/bash
# Server Setup Script for BeautyAssist
# Run this ONCE on a fresh server

set -e  # Exit on error

echo "🚀 BeautyAssist Server Setup Starting..."

# Update system
echo "📦 Updating system packages..."
apt update && apt upgrade -y

# Add deadsnakes PPA for Python 3.13
echo "📦 Adding deadsnakes PPA for Python 3.13..."
apt install -y software-properties-common
add-apt-repository -y ppa:deadsnakes/ppa
apt update

# Install required packages
echo "📦 Installing dependencies..."
apt install -y \
    python3.13 \
    python3.13-venv \
    python3.13-dev \
    python3-pip \
    postgresql \
    postgresql-contrib \
    nginx \
    git \
    certbot \
    python3-certbot-nginx

# Configure PostgreSQL
echo "🗄️ Configuring PostgreSQL..."
sudo -u postgres psql -c "CREATE USER beautyassist WITH PASSWORD 'your_secure_password_here';" || true
sudo -u postgres psql -c "CREATE DATABASE beautyassist_db OWNER beautyassist;" || true
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE beautyassist_db TO beautyassist;" || true

# Clone repository
echo "📥 Cloning repository..."
cd /root
if [ -d "BeautyAssist" ]; then
    echo "⚠️ Directory exists, skipping clone"
else
    git clone https://github.com/rosavskiy/BeautyAssist.git
fi
cd BeautyAssist

# Create virtual environment
echo "🐍 Creating Python virtual environment..."
python3.13 -m venv venv
source venv/bin/activate

# Install Python dependencies
echo "📦 Installing Python packages..."
pip install --upgrade pip
pip install -r requirements.txt

# Create .env file
echo "⚙️ Creating .env file..."
cat > .env << 'EOF'
# Telegram Bot
BOT_TOKEN=your_bot_token_here
WEBHOOK_URL=https://your-domain.com

# Database
DATABASE_URL=postgresql+asyncpg://beautyassist:your_secure_password_here@localhost/beautyassist_db

# Server
HOST=0.0.0.0
PORT=8080

# Admin
ADMIN_TELEGRAM_ID=your_telegram_id_here
EOF

echo "⚠️ IMPORTANT: Edit /root/BeautyAssist/.env and set your real values!"

# Run database migrations
echo "🗄️ Running database migrations..."
alembic upgrade head

# Create systemd service
echo "⚙️ Creating systemd service..."
cat > /etc/systemd/system/beautyassist-bot.service << 'EOF'
[Unit]
Description=BeautyAssist Telegram Bot
After=network.target postgresql.service

[Service]
Type=simple
User=root
WorkingDirectory=/root/BeautyAssist
Environment="PATH=/root/BeautyAssist/venv/bin"
ExecStart=/root/BeautyAssist/venv/bin/python /root/BeautyAssist/bot/main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Configure Nginx
echo "🌐 Configuring Nginx..."
cat > /etc/nginx/sites-available/beautyassist << 'EOF'
server {
    listen 80;
    server_name your-domain.com;

    # Redirect HTTP to HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name your-domain.com;

    # SSL certificates (will be configured by certbot)
    ssl_certificate /etc/letsencrypt/live/your-domain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/your-domain.com/privkey.pem;

    # Static files
    location /webapp/ {
        alias /root/BeautyAssist/webapp/;
        try_files $uri $uri/ =404;
    }

    location /webapp-master/ {
        alias /root/BeautyAssist/webapp-master/;
        try_files $uri $uri/ =404;
    }

    # Proxy to bot API
    location /api/ {
        proxy_pass http://127.0.0.1:8080;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
EOF

# Enable Nginx site
ln -sf /etc/nginx/sites-available/beautyassist /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default

# Test Nginx configuration
nginx -t

echo "✅ Server setup complete!"
echo ""
echo "📝 Next steps:"
echo "1. Edit /root/BeautyAssist/.env with your real values"
echo "2. Update Nginx config: nano /etc/nginx/sites-available/beautyassist"
echo "3. Get SSL certificate: certbot --nginx -d your-domain.com"
echo "4. Start the bot: systemctl start beautyassist-bot"
echo "5. Enable autostart: systemctl enable beautyassist-bot"
echo "6. Reload Nginx: systemctl reload nginx"
echo ""
echo "🔍 Check status: systemctl status beautyassist-bot"
echo "📋 View logs: journalctl -u beautyassist-bot -f"
