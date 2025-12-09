"""
Главный файл для запуска Telegram бота Habr
"""
import os
import logging
import asyncio
from pathlib import Path
from dotenv import load_dotenv
from src.database import Database
from src.bot import HabrBot, Scheduler

# Определяем базовую директорию проекта (где находится main.py)
BASE_DIR = Path(__file__).parent.absolute()

# Настройка логирования
logs_dir = BASE_DIR / 'logs'
logs_dir.mkdir(exist_ok=True)
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.FileHandler(logs_dir / 'bot.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)


async def main():
    """Главная функция запуска бота"""
    # Загружаем переменные окружения из директории проекта
    env_path = BASE_DIR / '.env'
    load_dotenv(dotenv_path=env_path)
    
    # Получаем токен бота
    bot_token = os.getenv('BOT_TOKEN')
    if not bot_token:
        logger.error("BOT_TOKEN не найден в переменных окружения!")
        logger.error("Создайте файл .env и укажите BOT_TOKEN=your_token_here")
        return
    
    logger.info("Инициализация базы данных...")
    data_dir = BASE_DIR / 'data'
    data_dir.mkdir(exist_ok=True)
    db = Database(db_path=str(data_dir / 'habr_bot.db'))
    
    logger.info("Инициализация бота...")
    bot = HabrBot(bot_token, db)
    
    logger.info("Инициализация планировщика...")
    scheduler = Scheduler(bot, db)
    
    # Запускаем бота
    await bot.start()
    
    # Запускаем планировщик
    await scheduler.start()
    
    logger.info("Бот запущен и готов к работе!")
    logger.info("Рассылка будет происходить в 8:00, 14:00 и 18:00")
    
    try:
        # Держим программу работающей
        while True:
            await asyncio.sleep(1)
            
    except KeyboardInterrupt:
        logger.info("Получен сигнал остановки...")
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}")
    finally:
        logger.info("Остановка планировщика...")
        await scheduler.stop()
        logger.info("Остановка бота...")
        await bot.stop()
        logger.info("Бот остановлен")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Программа завершена пользователем")
    except Exception as e:
        logger.error(f"Критическая ошибка при запуске: {e}")

