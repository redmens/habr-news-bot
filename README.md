# Habr Telegram Bot

Telegram бот для парсинга новостей с Habr по выбранным хабам с автоматической рассылкой.

## Установка

1. Клонируйте репозиторий или скачайте файлы

2. Создайте виртуальное окружение:
```bash
python -m venv venv
```

3. Активируйте виртуальное окружение:
- Windows: `venv\Scripts\activate`
- Linux/Mac: `source venv/bin/activate`

4. Установите зависимости:
```bash
pip install -r requirements.txt
```

5. Создайте файл `.env` на основе `.env.example` и укажите токен вашего Telegram бота:
```
BOT_TOKEN=your_telegram_bot_token_here
```

## Получение токена бота

1. Найдите [@BotFather](https://t.me/BotFather) в Telegram
2. Отправьте команду `/newbot`
3. Следуйте инструкциям для создания бота
4. Скопируйте полученный токен в файл `.env`

## Запуск

```bash
python main.py
```

## Запуск как сервис

### Linux (через systemd)

1. Создайте файл сервиса `/etc/systemd/system/habr-bot.service`:
```ini
[Unit]
Description=Habr Telegram Bot
After=network.target

[Service]
Type=simple
User=your_username
WorkingDirectory=/path/to/habr
Environment="PATH=/path/to/habr/venv/bin"
ExecStart=/path/to/habr/venv/bin/python /path/to/habr/main.py
Restart=always
RestartSec=10
StandardOutput=append:/path/to/habr/logs/service.log
StandardError=append:/path/to/habr/logs/service_error.log

[Install]
WantedBy=multi-user.target
```

2. Замените в файле:
   - `your_username` - на ваше имя пользователя
   - `/path/to/habr` - на полный путь к директории проекта

3. Перезагрузите конфигурацию systemd:
```bash
sudo systemctl daemon-reload
```

4. Включите автозапуск:
```bash
sudo systemctl enable habr-bot.service
```

5. Запустите сервис:
```bash
sudo systemctl start habr-bot.service
```

6. Проверьте статус:
```bash
sudo systemctl status habr-bot.service
```

7. Управление сервисом:
```bash
sudo systemctl stop habr-bot.service     # остановить
sudo systemctl restart habr-bot.service  # перезапустить
sudo systemctl disable habr-bot.service  # отключить автозапуск
```

## Команды бота

- `/start` - подписаться на рассылку новостей и начать работу с ботом
- `/help` - показать список всех доступных команд с описанием
- `/hubs` - посмотреть текущие выбранные хабы
- `/hubs_set` - настроить список хабов для получения новостей (откроется меню с кнопками)
- `/news [часов]` - получить новости вручную
  - По умолчанию: новости за последний час
  - Можно указать количество часов (максимум 24)
  - Пример: `/news 3` - получить новости за последние 3 часа
- `/stop` - отписаться от автоматической рассылки

## Расписание рассылки

Бот автоматически отправляет новости по московскому времени (МСК):
- **08:00** - посты за последние 14 часов
- **14:00** - посты за последние 6 часов
- **18:00** - посты за последние 4 часа

## Доступные хабы

- DevOps
- IT-инфраструктура
- Linux
- Python
- Анализ и проектирование систем
- Информационная безопасность
- Искусственный интеллект
- Машинное обучение
- Научно-популярное
- Программирование
- Сетевые технологии
- Системное администрирование

