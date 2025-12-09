"""
Модуль для ограничения частоты запросов (rate limiting)
"""
import time
import logging
from collections import defaultdict
from typing import Dict, Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class RateLimiter:
    """
    Класс для ограничения частоты запросов
    
    Использует sliding window алгоритм для отслеживания запросов
    """
    
    def __init__(self, max_requests: int, time_window: float):
        """
        Инициализация rate limiter
        
        Args:
            max_requests: максимальное количество запросов
            time_window: временное окно в секундах
        """
        self.max_requests = max_requests
        self.time_window = time_window
        self.requests: list = []  # Список временных меток запросов
    
    def is_allowed(self) -> bool:
        """
        Проверяет, разрешен ли новый запрос
        
        Returns:
            True если запрос разрешен, False если превышен лимит
        """
        now = time.time()
        
        # Удаляем старые запросы, выходящие за пределы временного окна
        self.requests = [req_time for req_time in self.requests 
                        if now - req_time < self.time_window]
        
        # Проверяем, не превышен ли лимит
        if len(self.requests) >= self.max_requests:
            return False
        
        # Добавляем текущий запрос
        self.requests.append(now)
        return True
    
    def wait_if_needed(self):
        """
        Ждет, если необходимо, чтобы не превысить лимит запросов
        """
        if not self.is_allowed():
            # Вычисляем время до следующего разрешенного запроса
            if self.requests:
                oldest_request = min(self.requests)
                wait_time = self.time_window - (time.time() - oldest_request)
                if wait_time > 0:
                    logger.debug(f"Rate limit достигнут, ожидание {wait_time:.2f} секунд")
                    time.sleep(wait_time)
                    # Очищаем список после ожидания
                    self.requests = []
                    self.requests.append(time.time())


class UserRateLimiter:
    """
    Класс для ограничения частоты запросов от пользователей
    
    Отслеживает запросы каждого пользователя отдельно
    """
    
    def __init__(self, max_requests: int, time_window: float):
        """
        Инициализация user rate limiter
        
        Args:
            max_requests: максимальное количество запросов от одного пользователя
            time_window: временное окно в секундах
        """
        self.max_requests = max_requests
        self.time_window = time_window
        self.user_requests: Dict[int, list] = defaultdict(list)  # user_id -> список временных меток
    
    def is_allowed(self, user_id: int) -> bool:
        """
        Проверяет, разрешен ли новый запрос от пользователя
        
        Args:
            user_id: ID пользователя
            
        Returns:
            True если запрос разрешен, False если превышен лимит
        """
        now = time.time()
        
        # Получаем список запросов пользователя
        user_reqs = self.user_requests[user_id]
        
        # Удаляем старые запросы, выходящие за пределы временного окна
        user_reqs[:] = [req_time for req_time in user_reqs 
                       if now - req_time < self.time_window]
        
        # Проверяем, не превышен ли лимит
        if len(user_reqs) >= self.max_requests:
            return False
        
        # Добавляем текущий запрос
        user_reqs.append(now)
        return True
    
    def get_wait_time(self, user_id: int) -> float:
        """
        Возвращает время ожидания до следующего разрешенного запроса
        
        Args:
            user_id: ID пользователя
            
        Returns:
            Время ожидания в секундах (0 если запрос разрешен)
        """
        if self.is_allowed(user_id):
            return 0.0
        
        now = time.time()
        user_reqs = self.user_requests[user_id]
        
        if user_reqs:
            oldest_request = min(user_reqs)
            wait_time = self.time_window - (now - oldest_request)
            return max(0.0, wait_time)
        
        return 0.0
    
    def cleanup_old_entries(self):
        """
        Очищает старые записи пользователей, которые не делали запросы долгое время
        """
        now = time.time()
        users_to_remove = []
        
        for user_id, user_reqs in self.user_requests.items():
            # Удаляем старые запросы
            user_reqs[:] = [req_time for req_time in user_reqs 
                           if now - req_time < self.time_window]
            
            # Если у пользователя нет активных запросов, удаляем его из словаря
            if not user_reqs:
                users_to_remove.append(user_id)
        
        for user_id in users_to_remove:
            del self.user_requests[user_id]


# Импортируем настройки из config
try:
    from src.config import (
        HABR_RATE_LIMIT_REQUESTS,
        HABR_RATE_LIMIT_WINDOW,
        NEWS_COMMAND_LIMIT_REQUESTS,
        NEWS_COMMAND_LIMIT_WINDOW
    )
except ImportError:
    # Значения по умолчанию, если config не найден
    HABR_RATE_LIMIT_REQUESTS = 1
    HABR_RATE_LIMIT_WINDOW = 1.0
    NEWS_COMMAND_LIMIT_REQUESTS = 1
    NEWS_COMMAND_LIMIT_WINDOW = 60.0

# Глобальные rate limiters
# Ограничение для запросов к Habr
habr_rate_limiter = RateLimiter(
    max_requests=HABR_RATE_LIMIT_REQUESTS,
    time_window=HABR_RATE_LIMIT_WINDOW
)

# Ограничение для команды /news от одного пользователя
news_command_limiter = UserRateLimiter(
    max_requests=NEWS_COMMAND_LIMIT_REQUESTS,
    time_window=NEWS_COMMAND_LIMIT_WINDOW
)

