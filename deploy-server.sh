#!/bin/bash
# Deploy Script for BeautyAssist
# Run this script to deploy updates
# Usage: cd /var/www/BeautyAssist && bash deploy-server.sh

set -e  # Exit on error

PROJECT_DIR="/var/www/BeautyAssist"

echo "🚀 Starting deployment..."

# Navigate to project directory
cd $PROJECT_DIR

# Pull latest changes
echo "📥 Pulling latest changes from git..."
git fetch origin
git reset --hard origin/main

# Activate virtual environment
source venv/bin/activate

# Install/update dependencies
echo "📦 Updating Python dependencies..."
pip install -r requirements.txt --upgrade

# Run database migrations
echo "🗄️ Running database migrations..."
alembic upgrade head

# Restart bot service
echo "🔄 Restarting bot service..."
systemctl restart beautyassist-bot

# Wait a moment for service to start
sleep 2

# Check service status
echo "✅ Checking service status..."
systemctl status beautyassist-bot --no-pager

# Check if service is running
if systemctl is-active --quiet beautyassist-bot; then
    echo ""
    echo "✅ Deployment successful!"
    echo "🤖 Bot is running"
    echo ""
    echo "📋 View logs: journalctl -u beautyassist-bot -n 50 -f"
else
    echo ""
    echo "❌ Deployment failed! Service is not running."
    echo "📋 Check logs: journalctl -u beautyassist-bot -n 50"
    exit 1
fi
