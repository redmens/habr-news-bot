"""
Конфигурация бота и маппинг хабов Habr
"""

# Маппинг названий хабов на их URL slug'и
HUB_SLUGS = {
    "DevOps": "devops",
    "IT-инфраструктура": "it-infrastructure",
    "Linux": "linux",
    "Python": "python",
    "Анализ и проектирование систем": "analysis_design",
    "Информационная безопасность": "infosecurity",
    "Искусственный интеллект": "artificial_intelligence",
    "Машинное обучение": "machine_learning",
    "Научно-популярное": "popular_science",
    "Программирование": "programming",
    "Сетевые технологии": "network_technologies",
    "Системное администрирование": "sys_admin",
}

# Список всех доступных хабов
AVAILABLE_HUBS = list(HUB_SLUGS.keys())

# Настройки времени рассылки
SCHEDULE_TIMES = {
    "08:00": 14,  # часов назад
    "14:00": 6,   # часов назад
    "18:00": 4,   # часов назад
}

# Базовый URL для парсинга
HABR_BASE_URL = "https://habr.com"
HABR_HUB_URL_TEMPLATE = "https://habr.com/ru/hubs/{slug}/articles/page{page}/"

# Настройки rate limiting для защиты от блокировки IP
# Ограничение для запросов к Habr: не более N запросов за время T (в секундах)
HABR_RATE_LIMIT_REQUESTS = 1  # максимальное количество запросов
HABR_RATE_LIMIT_WINDOW = 1.0  # временное окно в секундах (1 запрос в секунду)

# Ограничение для команды /news от одного пользователя
NEWS_COMMAND_LIMIT_REQUESTS = 1  # максимальное количество запросов
NEWS_COMMAND_LIMIT_WINDOW = 60.0  # временное окно в секундах (1 запрос в минуту)

