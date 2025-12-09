"""
Модуль Telegram бота
"""
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
            "Команды:\n"
            "/hubs - посмотреть текущие хабы\n"
            "/hubs_set - настроить хабы\n"
            "/news - получить новости за последний час\n"
            "/stop - отписаться от рассылки\n\n"
            f"Сейчас выбрано {format_number_with_noun(len(user_hubs), 'хаб', 'хаба', 'хабов')}\n"
            "Рассылка происходит в 8:00, 14:00 и 18:00."
        )

        await update.message.reply_text(welcome_message)

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
        """Обработка команды /news - показать новости за последний час"""
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
        
        # Отправляем сообщение о начале загрузки
        loading_message = await update.message.reply_text("⏳ Загружаю новости за последний час...")
        
        try:
            # Получаем хабы пользователя
            user_hubs = self.db.get_user_hubs(user_id)
            
            if not user_hubs:
                await loading_message.edit_text(
                    "У вас не выбрано ни одного хаба.\nИспользуйте /hubs_set для настройки."
                )
                return
            
            # Собираем все статьи из хабов пользователя за последний час
            all_articles = []
            seen_urls = set()  # Для удаления дубликатов
            
            for hub_name in user_hubs:
                try:
                    logger.info(f"Парсинг хаба '{hub_name}' для команды /news пользователя {user_id}")
                    articles = parse_hub_articles(hub_name, hours_back=1)
                    
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
                await self.send_articles_to_user(user_id, all_articles)
                articles_word = format_number_with_noun(len(all_articles), 'новость', 'новости', 'новостей')
                hubs_word = format_number_with_noun(len(user_hubs), 'хаба', 'хабов', 'хабов')
                await loading_message.edit_text(
                    f"✅ Найдено {articles_word} за последний час из {hubs_word}"
                )
            else:
                await loading_message.edit_text(
                    "📭 Новых статей за последний час не найдено.\nПопробуйте позже или используйте автоматическую рассылку."
                )
                
        except Exception as e:
            logger.error(f"Ошибка при выполнении команды /news для пользователя {user_id}: {e}")
            await loading_message.edit_text(
                f"❌ Произошла ошибка при загрузке новостей: {e}"
            )

    async def send_articles_to_user(self, user_id: int, articles: list):
        """
        Отправка статей пользователю
        
        Args:
            user_id: ID пользователя Telegram
            articles: список словарей с информацией о статьях
        """
        if not articles:
            return

        # Группируем статьи по хабам (если есть информация о хабе)
        # Или просто отправляем все статьи списком
        
        # Формируем сообщение
        messages = []
        current_message = "📰 Новости с Habr:\n\n"
        
        for article in articles:
            article_text = f"[{article['title']}]({article['url']})\n\n"
            
            # Если сообщение становится слишком длинным, отправляем текущее и начинаем новое
            if len(current_message) + len(article_text) > 4000:  # Лимит Telegram ~4096 символов
                messages.append(current_message)
                current_message = article_text
            else:
                current_message += article_text
        
        if current_message:
            messages.append(current_message)

        # Отправляем сообщения
        try:
            for msg in messages:
                await self.application.bot.send_message(
                    chat_id=user_id,
                    text=msg,
                    parse_mode='Markdown',
                    disable_web_page_preview=False
                )
            articles_word = format_number_with_noun(len(articles), 'статья', 'статьи', 'статей')
            logger.info(f"Отправлено {articles_word} пользователю {user_id}")
        except Exception as e:
            logger.error(f"Ошибка при отправке сообщения пользователю {user_id}: {e}")

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

