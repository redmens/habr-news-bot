"""
Модуль Telegram бота
"""
import asyncio
import logging
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from src.database import Database
from src.config import AVAILABLE_HUBS
from src.parser import parse_hub_articles
from src.utils import news_command_limiter, format_number_with_noun

logger = logging.getLogger(__name__)


class HabrBot:
    def __init__(self, token: str, db: Database):
        """
        Инициализация бота
        
        Args:
            token: токен Telegram бота
            db: экземпляр Database
        """
        self.token = token
        self.db = db
        self.application = Application.builder().token(token).build()
        self._register_handlers()

    def _register_handlers(self):
        """Регистрация обработчиков команд"""
        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CommandHandler("help", self.help_command))
        self.application.add_handler(CommandHandler("hubs", self.hubs_command))
        self.application.add_handler(CommandHandler("hubs_set", self.hubs_set_command))
        self.application.add_handler(CommandHandler("stop", self.stop_command))
        self.application.add_handler(CommandHandler("news", self.news_command))
        self.application.add_handler(CallbackQueryHandler(self.hub_callback, pattern="^hub_"))
        self.application.add_handler(CallbackQueryHandler(self.hubs_done_callback, pattern="^done$"))

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка команды /start"""
        user = update.effective_user
        user_id = user.id
        username = user.username

        # Добавляем пользователя в БД
        self.db.add_user(user_id, username)
        self.db.subscribe_user(user_id)

        # Если у пользователя нет хабов, устанавливаем все по умолчанию
        user_hubs = self.db.get_user_hubs(user_id)
        if not user_hubs:
            self.db.set_user_hubs(user_id, AVAILABLE_HUBS)
            user_hubs = set(AVAILABLE_HUBS)

        welcome_message = (
            f"Привет, {user.first_name}! 👋\n\n"
            "Я бот для получения новостей с Habr по выбранным хабам.\n\n"
            "Используйте /help для просмотра всех доступных команд.\n\n"
            f"Сейчас выбрано {format_number_with_noun(len(user_hubs), 'хаб', 'хаба', 'хабов')}\n"
            "Рассылка происходит в 8:00, 14:00 и 18:00 по МСК."
        )

        await update.message.reply_text(welcome_message)

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка команды /help - показать описание всех команд"""
        help_message = (
            "📚 Список доступных команд:\n\n"
            "/start - подписаться на рассылку новостей и начать работу с ботом\n\n"
            "/help - показать это сообщение со списком команд\n\n"
            "/hubs - посмотреть текущие выбранные хабы\n\n"
            "/hubs_set - настроить список хабов для получения новостей\n"
            "   (откроется меню с кнопками для выбора/отмены хабов)\n\n"
            "/news [часов] - получить новости вручную\n"
            "   • По умолчанию: новости за последний час\n"
            "   • Можно указать количество часов (максимум 24)\n"
            "   • Пример: /news 3 - получить новости за последние 3 часа\n\n"
            "/stop - отписаться от автоматической рассылки\n\n"
            "⏰ Автоматическая рассылка:\n"
            "Рассылка происходит в 8:00, 14:00 и 18:00 по МСК."
        )
        
        await update.message.reply_text(help_message)

    async def hubs_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка команды /hubs - показать текущие хабы"""
        user_id = update.effective_user.id
        user_hubs = self.db.get_user_hubs(user_id)

        if not user_hubs:
            message = "У вас не выбрано ни одного хаба.\nИспользуйте /hubs_set для настройки."
        else:
            hubs_list = "\n".join(f"• {hub}" for hub in sorted(user_hubs))
            hubs_word = format_number_with_noun(len(user_hubs), 'хаб', 'хаба', 'хабов')
            message = f"Ваши текущие хабы ({hubs_word}):\n\n{hubs_list}\n\nИспользуйте /hubs_set для изменения."

        await update.message.reply_text(message)

    async def hubs_set_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка команды /hubs_set - настройка хабов"""
        user_id = update.effective_user.id
        user_hubs = self.db.get_user_hubs(user_id)

        # Создаем клавиатуру с кнопками для каждого хаба
        keyboard = []
        row = []
        
        for i, hub in enumerate(AVAILABLE_HUBS):
            # Добавляем галочку, если хаб уже выбран
            prefix = "✅ " if hub in user_hubs else "☐ "
            button_text = f"{prefix}{hub}"
            
            # Ограничиваем длину текста кнопки
            if len(button_text) > 30:
                button_text = button_text[:27] + "..."
            
            row.append(InlineKeyboardButton(button_text, callback_data=f"hub_{hub}"))
            
            # Размещаем по 1 кнопке в ряд для удобства
            if len(row) == 1:
                keyboard.append(row)
                row = []
        
        # Кнопка "Готово"
        keyboard.append([InlineKeyboardButton("✅ Готово", callback_data="done")])

        reply_markup = InlineKeyboardMarkup(keyboard)

        message = (
            "Выберите хабы для получения новостей:\n"
            "Нажмите на хаб, чтобы включить/выключить его.\n"
            "Нажмите 'Готово', когда закончите выбор."
        )

        await update.message.reply_text(message, reply_markup=reply_markup)

    async def hub_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка нажатия на кнопку хаба"""
        query = update.callback_query
        await query.answer()

        hub_name = query.data.replace("hub_", "")
        user_id = query.from_user.id

        user_hubs = self.db.get_user_hubs(user_id)

        if hub_name in user_hubs:
            # Удаляем хаб
            self.db.remove_user_hub(user_id, hub_name)
            await query.answer(f"Хаб '{hub_name}' удален")
        else:
            # Добавляем хаб
            self.db.add_user_hub(user_id, hub_name)
            await query.answer(f"Хаб '{hub_name}' добавлен")

        # Обновляем клавиатуру
        user_hubs = self.db.get_user_hubs(user_id)
        keyboard = []
        row = []

        for hub in AVAILABLE_HUBS:
            prefix = "✅ " if hub in user_hubs else "☐ "
            button_text = f"{prefix}{hub}"
            
            if len(button_text) > 30:
                button_text = button_text[:27] + "..."
            
            row.append(InlineKeyboardButton(button_text, callback_data=f"hub_{hub}"))
            
            if len(row) == 1:
                keyboard.append(row)
                row = []

        keyboard.append([InlineKeyboardButton("✅ Готово", callback_data="done")])
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_reply_markup(reply_markup=reply_markup)

    async def hubs_done_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка нажатия кнопки 'Готово'"""
        query = update.callback_query
        await query.answer()

        user_id = query.from_user.id
        user_hubs = self.db.get_user_hubs(user_id)

        if not user_hubs:
            message = "Вы не выбрали ни одного хаба. Рассылка не будет работать.\nИспользуйте /hubs_set для выбора хабов."
        else:
            hubs_list = "\n".join(f"• {hub}" for hub in sorted(user_hubs))
            hubs_word = format_number_with_noun(len(user_hubs), 'хаб', 'хаба', 'хабов')
            message = f"Отлично! Выбрано {hubs_word}:\n\n{hubs_list}\n\nРассылка будет происходить по этим хабам."

        await query.edit_message_text(message)

    async def stop_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка команды /stop - отписка от рассылки"""
        user_id = update.effective_user.id
        self.db.unsubscribe_user(user_id)

        message = "Вы отписаны от рассылки. Используйте /start для повторной подписки."
        await update.message.reply_text(message)

    async def news_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка команды /news - показать новости за указанное количество часов (максимум 24)"""
        user_id = update.effective_user.id
        
        # Проверяем rate limit для команды /news
        if not news_command_limiter.is_allowed(user_id):
            wait_time = news_command_limiter.get_wait_time(user_id)
            wait_minutes = int(wait_time // 60)
            wait_seconds = int(wait_time % 60)
            
            if wait_minutes > 0:
                message = f"⏱️ Слишком частые запросы. Подождите {wait_minutes} мин. {wait_seconds} сек. перед следующим запросом."
            else:
                message = f"⏱️ Слишком частые запросы. Подождите {wait_seconds} сек. перед следующим запросом."
            
            await update.message.reply_text(message)
            return
        
        # Парсим аргумент с количеством часов
        hours_back = 1  # По умолчанию 1 час
        if context.args and len(context.args) > 0:
            try:
                hours_back = int(context.args[0])
                if hours_back < 1:
                    hours_back = 1
                elif hours_back > 24:
                    hours_back = 24
                    await update.message.reply_text("⚠️ Максимальное количество часов - 24. Использую 24 часа.")
            except ValueError:
                await update.message.reply_text("⚠️ Неверный формат. Используйте: /news [количество часов]. Использую 1 час по умолчанию.")
        
        if hours_back == 1:
            loading_text = "⏳ Загружаю новости за последний час..."
        else:
            hours_word = format_number_with_noun(hours_back, 'час', 'часа', 'часов')
            loading_text = f"⏳ Загружаю новости за последние {hours_word}..."
        loading_message = await update.message.reply_text(loading_text)
        
        try:
            # Получаем хабы пользователя
            user_hubs = self.db.get_user_hubs(user_id)
            
            if not user_hubs:
                await loading_message.edit_text(
                    "У вас не выбрано ни одного хаба.\nИспользуйте /hubs_set для настройки."
                )
                return
            
            # Оптимизация: парсим каждый хаб один раз
            hub_articles_cache = {}  # {hub_name: [articles]}
            
            for hub_name in sorted(user_hubs):
                try:
                    logger.info(f"Парсинг хаба '{hub_name}' для команды /news пользователя {user_id}")
                    articles = parse_hub_articles(hub_name, hours_back=hours_back)
                    hub_articles_cache[hub_name] = articles
                except Exception as e:
                    logger.error(f"Ошибка при парсинге хаба '{hub_name}' для пользователя {user_id}: {e}")
                    hub_articles_cache[hub_name] = []
                    continue
            
            # Формируем словарь статей по хабам (только с непустыми хабами)
            user_hub_articles = {
                hub_name: articles 
                for hub_name, articles in hub_articles_cache.items() 
                if articles
            }
            
            # Отправляем статьи пользователю (отдельные сообщения по каждому хабу)
            if user_hub_articles:
                await self.send_articles_to_user(user_id, user_hub_articles)
                total_articles = sum(len(articles) for articles in user_hub_articles.values())
                articles_word = format_number_with_noun(total_articles, 'новость', 'новости', 'новостей')
                hubs_word = format_number_with_noun(len(user_hub_articles), 'хаб', 'хаба', 'хабов')
                await loading_message.edit_text(
                    f"✅ Найдено {articles_word} за последние {hours_word} из {hubs_word}"
                )
            else:
                await loading_message.edit_text(
                    f"📭 Новых статей за последние {hours_word} не найдено.\nПопробуйте позже или используйте автоматическую рассылку."
                )
                
        except Exception as e:
            logger.error(f"Ошибка при выполнении команды /news для пользователя {user_id}: {e}")
            await loading_message.edit_text(
                f"❌ Произошла ошибка при загрузке новостей: {e}"
            )

    async def send_hub_articles_to_user(self, user_id: int, hub_name: str, articles: list):
        """
        Отправка статей одного хаба пользователю
        
        Args:
            user_id: ID пользователя Telegram
            hub_name: название хаба
            articles: список словарей с информацией о статьях
        """
        if not articles:
            return
        
        # Сортируем статьи по времени публикации (новые сначала)
        articles_sorted = sorted(
            articles, 
            key=lambda x: x.get('published_at') or datetime.min, 
            reverse=True
        )
        
        # Формируем сообщение для хаба
        messages = []
        current_message = f"📰 {hub_name}\n\n"
        
        for article in articles_sorted:
            article_text = f"[{article['title']}]({article['url']})\n\n"
            
            # Если сообщение становится слишком длинным, отправляем текущее и начинаем новое
            if len(current_message) + len(article_text) > 4000:  # Лимит Telegram ~4096 символов
                messages.append(current_message)
                current_message = f"📰 {hub_name} (продолжение)\n\n{article_text}"
            else:
                current_message += article_text
        
        if current_message and current_message != f"📰 {hub_name}\n\n":
            messages.append(current_message)
        
        # Отправляем сообщения
        try:
            for i, msg in enumerate(messages):
                await self.application.bot.send_message(
                    chat_id=user_id,
                    text=msg,
                    parse_mode='Markdown',
                    disable_web_page_preview=True
                )
                # Добавляем задержку между сообщениями (кроме последнего)
                if i < len(messages) - 1:
                    await asyncio.sleep(0.5)
            articles_word = format_number_with_noun(len(articles), 'статья', 'статьи', 'статей')
            logger.info(f"Отправлено {articles_word} из хаба '{hub_name}' пользователю {user_id}")
        except Exception as e:
            logger.error(f"Ошибка при отправке сообщения пользователю {user_id} для хаба '{hub_name}': {e}")

    async def send_articles_to_user(self, user_id: int, hub_articles: dict):
        """
        Отправка статей пользователю, сгруппированных по хабам
        
        Args:
            user_id: ID пользователя Telegram
            hub_articles: словарь {hub_name: [articles]} с информацией о статьях по хабам
        """
        if not hub_articles:
            return
        
        # Удаляем дубликаты статей (по URL) между хабами
        # Если статья встречается в нескольких хабах, оставляем её только в первом
        seen_urls = set()
        deduplicated_hub_articles = {}
        
        for hub_name, articles in hub_articles.items():
            if not articles:
                continue
            
            # Фильтруем статьи, оставляя только те, которые еще не встречались
            unique_articles = []
            for article in articles:
                article_url = article.get('url')
                if article_url and article_url not in seen_urls:
                    seen_urls.add(article_url)
                    unique_articles.append(article)
            
            # Добавляем хаб только если в нем остались уникальные статьи
            if unique_articles:
                deduplicated_hub_articles[hub_name] = unique_articles
        
        # Отправляем отдельное сообщение для каждого хаба
        for hub_name, articles in deduplicated_hub_articles.items():
            await self.send_hub_articles_to_user(user_id, hub_name, articles)
            # Задержка между хабами для избежания блокировок Telegram
            await asyncio.sleep(1.0)

    async def start(self):
        """Запуск бота (async)"""
        logger.info("Запуск Telegram бота...")
        await self.application.initialize()
        await self.application.start()
        await self.application.updater.start_polling(
            allowed_updates=Update.ALL_TYPES,
            drop_pending_updates=True
        )

    async def stop(self):
        """Остановка бота"""
        if self.application.updater.running:
            await self.application.updater.stop()
        await self.application.stop()
        await self.application.shutdown()

