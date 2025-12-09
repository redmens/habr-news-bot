"""
Модуль для работы с базой данных SQLite
"""
import sqlite3
import logging
import os
from datetime import datetime
from typing import List, Optional, Set

logger = logging.getLogger(__name__)


class Database:
    def __init__(self, db_path: str = "data/habr_bot.db"):
        """
        Инициализация подключения к базе данных
        
        Args:
            db_path: путь к файлу базы данных
        """
        # Создаем папку для базы данных, если её нет
        db_dir = os.path.dirname(db_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)
        
        self.db_path = db_path
        self.init_database()

    def get_connection(self):
        """Получить подключение к базе данных"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_database(self):
        """Инициализация таблиц базы данных"""
        conn = self.get_connection()
        cursor = conn.cursor()

        # Таблица пользователей
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                subscribed BOOLEAN DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Таблица хабов пользователей
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_hubs (
                user_id INTEGER,
                hub_name TEXT,
                PRIMARY KEY (user_id, hub_name),
                FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
            )
        """)

        conn.commit()
        conn.close()
        logger.info("База данных инициализирована")

    def add_user(self, user_id: int, username: Optional[str] = None) -> bool:
        """
        Добавить пользователя в базу данных
        
        Args:
            user_id: ID пользователя Telegram
            username: имя пользователя (опционально)
            
        Returns:
            True если пользователь добавлен, False если уже существует
        """
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("""
                INSERT OR IGNORE INTO users (user_id, username, subscribed)
                VALUES (?, ?, 1)
            """, (user_id, username))
            conn.commit()
            added = cursor.rowcount > 0
            logger.info(f"Пользователь {user_id} {'добавлен' if added else 'уже существует'}")
            return added
        except sqlite3.Error as e:
            logger.error(f"Ошибка при добавлении пользователя: {e}")
            return False
        finally:
            conn.close()

    def update_username(self, user_id: int, username: Optional[str]):
        """Обновить имя пользователя"""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("""
                UPDATE users SET username = ? WHERE user_id = ?
            """, (username, user_id))
            conn.commit()
        except sqlite3.Error as e:
            logger.error(f"Ошибка при обновлении имени пользователя: {e}")
        finally:
            conn.close()

    def subscribe_user(self, user_id: int) -> bool:
        """
        Подписать пользователя на рассылку
        
        Args:
            user_id: ID пользователя Telegram
            
        Returns:
            True если успешно
        """
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("""
                UPDATE users SET subscribed = 1 WHERE user_id = ?
            """, (user_id,))
            conn.commit()
            logger.info(f"Пользователь {user_id} подписан на рассылку")
            return True
        except sqlite3.Error as e:
            logger.error(f"Ошибка при подписке пользователя: {e}")
            return False
        finally:
            conn.close()

    def unsubscribe_user(self, user_id: int) -> bool:
        """
        Отписать пользователя от рассылки
        
        Args:
            user_id: ID пользователя Telegram
            
        Returns:
            True если успешно
        """
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("""
                UPDATE users SET subscribed = 0 WHERE user_id = ?
            """, (user_id,))
            conn.commit()
            logger.info(f"Пользователь {user_id} отписан от рассылки")
            return True
        except sqlite3.Error as e:
            logger.error(f"Ошибка при отписке пользователя: {e}")
            return False
        finally:
            conn.close()

    def is_subscribed(self, user_id: int) -> bool:
        """
        Проверить, подписан ли пользователь
        
        Args:
            user_id: ID пользователя Telegram
            
        Returns:
            True если подписан
        """
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("""
                SELECT subscribed FROM users WHERE user_id = ?
            """, (user_id,))
            row = cursor.fetchone()
            return row and row['subscribed'] == 1
        except sqlite3.Error as e:
            logger.error(f"Ошибка при проверке подписки: {e}")
            return False
        finally:
            conn.close()

    def get_subscribed_users(self) -> List[int]:
        """
        Получить список всех подписанных пользователей
        
        Returns:
            Список ID пользователей
        """
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("""
                SELECT user_id FROM users WHERE subscribed = 1
            """)
            users = [row['user_id'] for row in cursor.fetchall()]
            return users
        except sqlite3.Error as e:
            logger.error(f"Ошибка при получении подписчиков: {e}")
            return []
        finally:
            conn.close()

    def set_user_hubs(self, user_id: int, hubs: List[str]) -> bool:
        """
        Установить список хабов для пользователя
        
        Args:
            user_id: ID пользователя Telegram
            hubs: список названий хабов
            
        Returns:
            True если успешно
        """
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            # Удаляем старые хабы
            cursor.execute("""
                DELETE FROM user_hubs WHERE user_id = ?
            """, (user_id,))

            # Добавляем новые хабы
            for hub in hubs:
                cursor.execute("""
                    INSERT INTO user_hubs (user_id, hub_name)
                    VALUES (?, ?)
                """, (user_id, hub))

            conn.commit()
            logger.info(f"Установлены хабы для пользователя {user_id}: {hubs}")
            return True
        except sqlite3.Error as e:
            logger.error(f"Ошибка при установке хабов: {e}")
            return False
        finally:
            conn.close()

    def get_user_hubs(self, user_id: int) -> Set[str]:
        """
        Получить список хабов пользователя
        
        Args:
            user_id: ID пользователя Telegram
            
        Returns:
            Множество названий хабов
        """
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("""
                SELECT hub_name FROM user_hubs WHERE user_id = ?
            """, (user_id,))
            hubs = {row['hub_name'] for row in cursor.fetchall()}
            return hubs
        except sqlite3.Error as e:
            logger.error(f"Ошибка при получении хабов: {e}")
            return set()
        finally:
            conn.close()

    def add_user_hub(self, user_id: int, hub_name: str) -> bool:
        """
        Добавить хаб пользователю
        
        Args:
            user_id: ID пользователя Telegram
            hub_name: название хаба
            
        Returns:
            True если успешно
        """
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("""
                INSERT OR IGNORE INTO user_hubs (user_id, hub_name)
                VALUES (?, ?)
            """, (user_id, hub_name))
            conn.commit()
            return cursor.rowcount > 0
        except sqlite3.Error as e:
            logger.error(f"Ошибка при добавлении хаба: {e}")
            return False
        finally:
            conn.close()

    def remove_user_hub(self, user_id: int, hub_name: str) -> bool:
        """
        Удалить хаб у пользователя
        
        Args:
            user_id: ID пользователя Telegram
            hub_name: название хаба
            
        Returns:
            True если успешно
        """
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("""
                DELETE FROM user_hubs WHERE user_id = ? AND hub_name = ?
            """, (user_id, hub_name))
            conn.commit()
            return cursor.rowcount > 0
        except sqlite3.Error as e:
            logger.error(f"Ошибка при удалении хаба: {e}")
            return False
        finally:
            conn.close()

