# Deployment script for BeautyAssist to 192.144.59.97
# Run this script after entering the server password

$SERVER = "root@192.144.59.97"
$PROJECT_PATH = "/root/BeautyAssist"

Write-Host "🚀 Starting deployment to $SERVER..." -ForegroundColor Cyan

# Check if we have uncommitted changes
Write-Host "📝 Checking git status..." -ForegroundColor Yellow
git status --short
if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Git error" -ForegroundColor Red
    exit 1
}

# Push to remote
Write-Host "📤 Pushing to remote repository..." -ForegroundColor Yellow
git push
if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Push failed" -ForegroundColor Red
    exit 1
}

Write-Host "✅ Local changes pushed successfully" -ForegroundColor Green

# Deploy commands
Write-Host "🔧 Deploying to server..." -ForegroundColor Yellow

$deployCommands = @"
cd $PROJECT_PATH && \
echo '📥 Pulling latest changes...' && \
git pull && \
echo '🔄 Restarting bot service...' && \
systemctl restart beautyassist-bot && \
systemctl status beautyassist-bot --no-pager && \
echo '✅ Deployment complete!'
"@

# Execute deployment on server
ssh $SERVER $deployCommands

if ($LASTEXITCODE -eq 0) {
    Write-Host "`n✅ Deployment successful!" -ForegroundColor Green
    Write-Host "🌐 Check the bot at https://t.me/your_bot" -ForegroundColor Cyan
} else {
    Write-Host "`n❌ Deployment failed!" -ForegroundColor Red
    exit 1
}
