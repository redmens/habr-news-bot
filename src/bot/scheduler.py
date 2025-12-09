"""
Модуль планировщика отправки сообщений
"""
import asyncio
import logging
from datetime import datetime, time as dt_time
from src.database import Database
from src.parser import parse_hub_articles
from src.config import SCHEDULE_TIMES
from src.bot.bot import HabrBot
from src.utils import format_number_with_noun

logger = logging.getLogger(__name__)


class Scheduler:
    def __init__(self, bot: HabrBot, db: Database):
        """
        Инициализация планировщика
        
        Args:
            bot: экземпляр HabrBot
            db: экземпляр Database
        """
        self.bot = bot
        self.db = db
        self.running = False
        self.task = None

    async def send_scheduled_news(self, hours_back: int):
        """
        Отправка новостей всем подписчикам
        
        Args:
            hours_back: количество часов назад для фильтрации статей
        """
        logger.info(f"Начало рассылки новостей за последние {hours_back} часов")
        
        subscribed_users = self.db.get_subscribed_users()
        
        if not subscribed_users:
            logger.info("Нет подписчиков для рассылки")
            return
        
        logger.info(f"Найдено {len(subscribed_users)} подписчиков")
        
        for user_id in subscribed_users:
            try:
                # Получаем хабы пользователя
                user_hubs = self.db.get_user_hubs(user_id)
                
                if not user_hubs:
                    logger.info(f"У пользователя {user_id} нет выбранных хабов, пропускаем")
                    continue
                
                # Собираем все статьи из хабов пользователя
                all_articles = []
                seen_urls = set()  # Для удаления дубликатов
                
                for hub_name in user_hubs:
                    try:
                        logger.info(f"Парсинг хаба '{hub_name}' для пользователя {user_id}")
                        articles = parse_hub_articles(hub_name, hours_back)
                        
                        for article in articles:
                            if article['url'] not in seen_urls:
                                seen_urls.add(article['url'])
                                all_articles.append(article)
                    except Exception as e:
                        logger.error(f"Ошибка при парсинге хаба '{hub_name}' для пользователя {user_id}: {e}")
                        continue
                
                # Сортируем статьи по времени публикации (новые сначала)
                all_articles.sort(key=lambda x: x['published_at'] or datetime.min, reverse=True)
                
                # Отправляем статьи пользователю
                if all_articles:
                    await self.bot.send_articles_to_user(user_id, all_articles)
                    articles_word = format_number_with_noun(len(all_articles), 'статья', 'статьи', 'статей')
                    logger.info(f"Отправлено {articles_word} пользователю {user_id}")
                else:
                    logger.info(f"Нет новых статей для пользователя {user_id}")
                
                # Небольшая задержка между пользователями
                await asyncio.sleep(1)
                
            except Exception as e:
                logger.error(f"Ошибка при обработке пользователя {user_id}: {e}")
                continue
        
        logger.info("Рассылка завершена")

    async def check_and_send(self):
        """Проверка времени и отправка сообщений по расписанию"""
        while self.running:
            try:
                now = datetime.now()
                current_time = now.time()
                
                # Проверяем каждое время из расписания
                for schedule_time_str, hours_back in SCHEDULE_TIMES.items():
                    # Парсим время из строки "HH:MM"
                    hour, minute = map(int, schedule_time_str.split(':'))
                    schedule_time = dt_time(hour, minute)
                    
                    # Проверяем, наступило ли время рассылки (с точностью до минуты)
                    if (current_time.hour == schedule_time.hour and 
                        current_time.minute == schedule_time.minute):
                        
                        logger.info(f"Время рассылки: {schedule_time_str}, часов назад: {hours_back}")
                        await self.send_scheduled_news(hours_back)
                        
                        # Ждем минуту, чтобы не отправить дважды
                        await asyncio.sleep(60)
                
                # Проверяем каждую минуту
                await asyncio.sleep(60)
                
            except Exception as e:
                logger.error(f"Ошибка в планировщике: {e}")
                await asyncio.sleep(60)

    async def start(self):
        """Запуск планировщика"""
        if self.running:
            logger.warning("Планировщик уже запущен")
            return
        
        self.running = True
        logger.info("Планировщик запущен")
        self.task = asyncio.create_task(self.check_and_send())

    async def stop(self):
        """Остановка планировщика"""
        self.running = False
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
        logger.info("Планировщик остановлен")

