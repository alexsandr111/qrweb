# README 2: Установка на сервер и обновление

Этот документ — практическая инструкция для деплоя QR-сервиса на Linux-сервер (Ubuntu 22.04/24.04) с `systemd` + `nginx`.

## 1) Что понадобится

- Сервер с Linux и доступом по SSH.
- Домен (опционально, но рекомендуется для HTTPS).
- Установленные пакеты: `git`, `python3`, `python3-venv`, `nginx`.

Установка базовых пакетов:

```bash
sudo apt update
sudo apt install -y git python3 python3-venv nginx
```

---

## 2) Первичная установка приложения на сервер

### Шаг 1. Создайте директорию и клонируйте проект

```bash
sudo mkdir -p /opt/qrweb
sudo chown -R $USER:$USER /opt/qrweb
cd /opt/qrweb
git clone https://github.com/alexsandr111/qrweb .
```

### Шаг 2. Создайте виртуальное окружение и установите зависимости

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### Шаг 3. Подготовьте папку для данных

> База SQLite (`payments.db`) должна храниться в отдельной директории, чтобы не потерять данные при переустановке кода.

```bash
sudo mkdir -p /var/lib/qrweb
sudo chown -R $USER:$USER /var/lib/qrweb
```

### Шаг 4. Создайте systemd unit

Создайте файл `/etc/systemd/system/qrweb.service`:

```ini
[Unit]
Description=QR Web Service (FastAPI)
After=network.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=/opt/qrweb
Environment="PAYMENTS_DB=/var/lib/qrweb/payments.db"
ExecStart=/opt/qrweb/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --app-dir .
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

Права на директории:

```bash
sudo chown -R www-data:www-data /opt/qrweb
sudo chown -R www-data:www-data /var/lib/qrweb
```

Запуск сервиса:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now qrweb
sudo systemctl status qrweb --no-pager
```

### Шаг 5. Настройте nginx (reverse proxy)

Создайте файл `/etc/nginx/sites-available/qrweb`:

```nginx
server {
    listen 80;
    server_name yourdomain.ru;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Включите сайт:

```bash
sudo ln -s /etc/nginx/sites-available/qrweb /etc/nginx/sites-enabled/qrweb
sudo nginx -t
sudo systemctl reload nginx
```

### Шаг 6. Проверка

```bash
curl -sS http://127.0.0.1:8000/health
curl -I http://yourdomain.ru/
```

Ожидаемо:
- `{"status":"ok"}` от `/health`
- `HTTP/1.1 200 OK` (или `303`/`307` при редиректах)

---

## 3) Включение HTTPS (рекомендуется)

Если домен уже указывает на сервер:

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d yourdomain.ru
```

Проверка автообновления сертификатов:

```bash
sudo systemctl status certbot.timer --no-pager
```

---

## 4) Как обновлять приложение на сервере

Ниже безопасный базовый сценарий обновления без потери базы данных.

### Вариант A (рекомендуемый): с бэкапом перед обновлением

```bash
cd /opt/qrweb

# 1. Бэкап базы
cp /var/lib/qrweb/payments.db /var/lib/qrweb/payments.db.bak-$(date +%F-%H%M%S)

# 2. Забрать свежий код
git fetch --all
git checkout main
git pull --ff-only origin main
# при необходимости проверьте remote: git remote -v

# 3. Обновить зависимости
source .venv/bin/activate
pip install -r requirements.txt

# 4. Перезапустить сервис
sudo systemctl restart qrweb

# 5. Проверить
sudo systemctl status qrweb --no-pager
curl -sS http://127.0.0.1:8000/health
```

### Вариант B: если используете теги/релизы

```bash
cd /opt/qrweb
git fetch --tags
git checkout tags/vX.Y.Z
source .venv/bin/activate
pip install -r requirements.txt
sudo systemctl restart qrweb
```

---

## 5) Что делать, если обновление неудачное

### Быстрый откат к предыдущему коммиту

```bash
cd /opt/qrweb
git log --oneline -n 5
git checkout <PREVIOUS_COMMIT>
source .venv/bin/activate
pip install -r requirements.txt
sudo systemctl restart qrweb
```

### Откат базы (если нужно)

```bash
sudo systemctl stop qrweb
cp /var/lib/qrweb/payments.db.bak-YYYY-MM-DD-HHMMSS /var/lib/qrweb/payments.db
sudo chown www-data:www-data /var/lib/qrweb/payments.db
sudo systemctl start qrweb
```

---

## 6) Полезные команды эксплуатации

Логи приложения:

```bash
sudo journalctl -u qrweb -n 200 --no-pager
sudo journalctl -u qrweb -f
```

Проверка конфигурации nginx:

```bash
sudo nginx -t
sudo systemctl reload nginx
```

Проверка, что сервис слушает локальный порт:

```bash
ss -tulpn | rg 8000
```

---

## 7) Рекомендации по продакшену

- Делайте бэкап `/var/lib/qrweb/payments.db` по расписанию (cron/systemd timer).
- Ограничьте SSH-доступ (ключи, отключить пароль, fail2ban).
- Обновляйте систему: `sudo apt update && sudo apt upgrade`.
- Следите за свободным местом: `df -h`.

---

Если нужно, можно сделать отдельный `deploy.sh` и `update.sh`, чтобы установка и обновления выполнялись одной командой.
