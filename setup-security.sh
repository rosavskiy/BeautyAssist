#!/bin/bash
# Скрипт для быстрой настройки UFW и Fail2Ban для BeautyAssist
# Выполнять на сервере от root

set -e

echo "=== Настройка UFW Firewall ==="

# Проверка, установлен ли UFW
if ! command -v ufw &> /dev/null; then
    echo "Установка UFW..."
    apt update
    apt install -y ufw
fi

# КРИТИЧНО: Разрешить SSH перед активацией!
echo "Разрешение SSH (порт 22)..."
ufw allow 22/tcp comment 'SSH access'

# Разрешить HTTP/HTTPS для nginx
echo "Разрешение HTTP/HTTPS..."
ufw allow 80/tcp comment 'HTTP nginx'
ufw allow 443/tcp comment 'HTTPS nginx'

# Заблокировать прямой доступ к порту 8080 извне
echo "Блокировка порта 8080 извне..."
ufw deny 8080/tcp comment 'Block direct bot access'

# Активировать UFW
echo "Активация UFW..."
ufw --force enable

# Показать статус
echo ""
echo "=== Статус UFW ==="
ufw status verbose

echo ""
echo "=== Настройка Fail2Ban ==="

# Проверка, установлен ли Fail2Ban
if ! command -v fail2ban-client &> /dev/null; then
    echo "Установка Fail2Ban..."
    apt update
    apt install -y fail2ban
fi

# Создать конфигурацию jail.local
echo "Создание /etc/fail2ban/jail.local..."
cat > /etc/fail2ban/jail.local <<'EOF'
[DEFAULT]
# Ban hosts for 1 hour (3600 seconds)
bantime = 3600

# A host is banned if it has generated "maxretry" during the last "findtime" seconds
findtime = 600

# "maxretry" is the number of failures before a host get banned
maxretry = 5

# Destination email for action that send you an email (optional)
# destemail = your-email@example.com

[sshd]
enabled = true
port = ssh
logpath = /var/log/auth.log
maxretry = 3

[nginx-http-auth]
enabled = true
port = http,https
logpath = /var/log/nginx/beautyassist_error.log
maxretry = 5

[nginx-limit-req]
enabled = true
port = http,https
filter = nginx-limit-req
logpath = /var/log/nginx/beautyassist_error.log
maxretry = 10
findtime = 60
bantime = 600

[nginx-botsearch]
enabled = true
port = http,https
filter = nginx-botsearch
logpath = /var/log/nginx/beautyassist_access.log
logpath = /var/log/nginx/beautyassist_blocked.log
maxretry = 5
findtime = 300
EOF

# Создать фильтр для блокировки ботов-сканеров
echo "Создание фильтра nginx-botsearch..."
cat > /etc/fail2ban/filter.d/nginx-botsearch.conf <<'EOF'
[Definition]
failregex = ^<HOST> -.*GET.*(\.php|\.asp|\.exe|\.pl|\.cgi|\.scgi|/admin|/wp-admin|phpmyadmin|phpMyAdmin)
ignoreregex =
EOF

# Перезапустить Fail2Ban
echo "Перезапуск Fail2Ban..."
systemctl restart fail2ban
systemctl enable fail2ban

# Показать статус
echo ""
echo "=== Статус Fail2Ban ==="
fail2ban-client status

echo ""
echo "=== Активные jail'ы ==="
fail2ban-client status sshd 2>/dev/null || echo "sshd jail: не активен"
fail2ban-client status nginx-http-auth 2>/dev/null || echo "nginx-http-auth: не активен"
fail2ban-client status nginx-limit-req 2>/dev/null || echo "nginx-limit-req: не активен"
fail2ban-client status nginx-botsearch 2>/dev/null || echo "nginx-botsearch: не активен"

echo ""
echo "✅ Настройка завершена!"
echo ""
echo "Проверка:"
echo "  - UFW статус: ufw status verbose"
echo "  - Fail2Ban статус: fail2ban-client status"
echo "  - Заблокированные IP: fail2ban-client status nginx-botsearch"
echo "  - Разблокировать IP: fail2ban-client set nginx-botsearch unbanip <IP>"
