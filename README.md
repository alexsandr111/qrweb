# QR веб-сервис для платёжных поручений

Минималистичный сервис на FastAPI, который принимает ФИО плательщика и сумму, сохраняет их в SQLite и выдаёт страницу с QR-кодом в формате ST00011.

## Возможности
- Фиксированные банковские реквизиты получателя (ООО "ЭНЕРДЖИ МЕНЕДЖМЕНТ").
- Генерация QR-кода на лету по короткой ссылке `/qr/<id>`.
- Сохранение платежей в локальный файл `payments.db` (без внешних СУБД).
- Возможность скачать QR в PNG и скопировать ссылку.

## Установка
1. Клонируйте репозиторий и перейдите в директорию проекта.
2. Создайте виртуальное окружение и установите зависимости:
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

## Запуск
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --app-dir .
```

> Если возникает ошибка `ModuleNotFoundError: No module named 'app'`, убедитесь, что команда запускается из корня
> репозитория или добавьте путь к проекту в `PYTHONPATH`, например: `PYTHONPATH=. uvicorn app.main:app --host 0.0.0.0
> --port 8000 --app-dir .`.

После запуска форма доступна на `http://localhost:8000/`, а QR-страницы — по `http://localhost:8000/qr/<id>`.

### Переменные окружения
- `PAYMENTS_DB` — путь к файлу SQLite (по умолчанию `payments.db`).

## Формат ST00011
QR-строка собирается из фиксированных реквизитов и введённых данных. Пример:
```
ST00011|Name=ООО "ЭНЕРДЖИ МЕНЕДЖМЕНТ"|PersonalAcc=40702810900000057455|BankName=Банк ГПБ (АО) г. Москва|BIC=044525823|CorrespAcc=30101810200000000823|PayeeINN=9709082458|KPP=770401001|Purpose=Возврат|LastName=Иванов Иван Иванович|SUM=96993200
```

## Пример конфигурации Nginx + HTTPS
```
server {
    listen 80;
    server_name yourdomain.ru;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name yourdomain.ru;

    ssl_certificate /etc/letsencrypt/live/yourdomain.ru/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/yourdomain.ru/privkey.pem;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

## Безопасность и ограничения
- Все SQL-запросы параметризованы.
- Браузерная часть не отправляет данные третьим лицам.
- Для продакшена включите HTTPS и, при необходимости, ограничение частоты запросов на уровне reverse-proxy (Nginx/nginx-lua или fail2ban).

## Тестовое использование
1. Откройте главную страницу.
2. Введите ФИО и сумму (например, `5000.75`).
3. Нажмите «Создать QR» — вы будете перенаправлены на страницу с QR-кодом, который можно сканировать в банковском приложении.
