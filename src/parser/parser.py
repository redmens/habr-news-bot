"""
Модуль для парсинга статей с Habr
"""
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import logging
import re
import time
from typing import List, Dict, Optional
from src.config import HABR_HUB_URL_TEMPLATE, HUB_SLUGS
from src.utils import habr_rate_limiter, format_number_with_noun

logger = logging.getLogger(__name__)

# Заголовки для запросов
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}


def parse_time_string(time_str: str) -> Optional[datetime]:
    """
    Парсит строку времени в объект datetime
    
    Обрабатывает форматы:
    - ISO формат: "2023-11-19T18:22:52.000Z" или "2023-11-19t18:22:52.000z" (UTC)
    - "X часов назад"
    - "X минут назад"
    - "вчера в HH:MM"
    - "сегодня в HH:MM"
    - "DD месяц YYYY в HH:MM"
    
    Args:
        time_str: строка с временем
        
    Returns:
        datetime объект или None
    """
    if not time_str:
        return None
        
    now = datetime.now()
    original_time_str = time_str.strip()
    time_str_lower = original_time_str.lower()

    # ISO формат: "2023-11-19T18:22:52.000Z" или "2023-11-19t18:22:52.000z"
    # Пробуем распарсить ISO формат с UTC
    iso_patterns = [
        r'(\d{4})-(\d{2})-(\d{2})[tT](\d{2}):(\d{2}):(\d{2})(?:\.\d+)?[zZ]',
        r'(\d{4})-(\d{2})-(\d{2})[tT](\d{2}):(\d{2}):(\d{2})(?:\.\d+)?',
        r'(\d{4})-(\d{2})-(\d{2})[tT](\d{2}):(\d{2}):(\d{2})',
    ]
    
    for pattern in iso_patterns:
        match = re.search(pattern, original_time_str)
        if match:
            try:
                year = int(match.group(1))
                month = int(match.group(2))
                day = int(match.group(3))
                hour = int(match.group(4))
                minute = int(match.group(5))
                second = int(match.group(6))
                
                # Создаем datetime объект (предполагаем UTC если есть Z в конце)
                parsed_time = datetime(year, month, day, hour, minute, second)
                
                # Если в строке есть Z, значит это UTC время
                # Конвертируем в локальное время (примерно, добавляя 3 часа для Москвы)
                if 'z' in original_time_str.lower():
                    # UTC+3 для Москвы (можно улучшить, используя pytz)
                    parsed_time = parsed_time + timedelta(hours=3)
                
                return parsed_time
            except (ValueError, IndexError) as e:
                logger.debug(f"Ошибка при парсинге ISO формата: {e}")
                continue

    # "X часов/часа/час назад" - обрабатываем все варианты склонения
    # "1 час назад", "2 часа назад", "5 часов назад"
    match = re.search(r'(\d+)\s+час(?:ов|а|)', time_str_lower)
    if match:
        hours = int(match.group(1))
        return now - timedelta(hours=hours)

    # "X минут/минуты/минуту назад" - обрабатываем все варианты склонения
    # "1 минуту назад", "2 минуты назад", "5 минут назад"
    match = re.search(r'(\d+)\s+минут(?:у|ы|)', time_str_lower)
    if match:
        minutes = int(match.group(1))
        return now - timedelta(minutes=minutes)

    # "вчера в HH:MM"
    if 'вчера' in time_str_lower:
        match = re.search(r'(\d{1,2}):(\d{2})', original_time_str)
        if match:
            hour = int(match.group(1))
            minute = int(match.group(2))
            yesterday = now - timedelta(days=1)
            return yesterday.replace(hour=hour, minute=minute, second=0, microsecond=0)

    # "сегодня в HH:MM"
    if 'сегодня' in time_str_lower:
        match = re.search(r'(\d{1,2}):(\d{2})', original_time_str)
        if match:
            hour = int(match.group(1))
            minute = int(match.group(2))
            return now.replace(hour=hour, minute=minute, second=0, microsecond=0)

    # Абсолютная дата "DD месяц YYYY в HH:MM"
    months_ru = {
        'января': 1, 'февраля': 2, 'марта': 3, 'апреля': 4,
        'мая': 5, 'июня': 6, 'июля': 7, 'августа': 8,
        'сентября': 9, 'октября': 10, 'ноября': 11, 'декабря': 12
    }
    
    for month_name, month_num in months_ru.items():
        pattern = rf'(\d{{1,2}})\s+{month_name}\s+(\d{{4}})\s+в\s+(\d{{1,2}}):(\d{{2}})'
        match = re.search(pattern, time_str_lower)
        if match:
            day = int(match.group(1))
            year = int(match.group(2))
            hour = int(match.group(3))
            minute = int(match.group(4))
            try:
                return datetime(year, month_num, day, hour, minute)
            except ValueError:
                continue

    logger.warning(f"Не удалось распарсить время: {original_time_str}")
    return None


def parse_page_articles(url: str) -> List[Dict[str, any]]:
    """
    Парсит статьи с одной страницы хаба
    
    Args:
        url: URL страницы хаба
        
    Returns:
        Список словарей с информацией о статьях
    """
    articles = []
    
    try:
        # Ограничение частоты запросов к Habr
        habr_rate_limiter.wait_if_needed()
        
        response = requests.get(url, headers=HEADERS, timeout=10)
        response.raise_for_status()
        
        # Используем html.parser вместо lxml (встроенный парсер)
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Ищем элементы article с классом tm-articles-list__item
        # Это правильная структура статей на Habr
        article_elements = soup.find_all('article', class_=lambda x: x and 'tm-articles-list__item' in str(x))
        
        # Если не нашли по классу, пробуем найти все article элементы
        if not article_elements:
            article_elements = soup.find_all('article')
        
        articles = []
        seen_urls = set()
        
        for article_elem in article_elements:
            try:
                # Ищем ссылку на статью в заголовке
                # Обычно это ссылка в h2 с классом tm-title__link
                title_link = article_elem.find('a', class_=lambda x: x and 'tm-title__link' in str(x))
                
                # Если не нашли по классу, ищем ссылку в h2
                # Ссылки могут быть: /ru/articles/123/ или /ru/companies/name/articles/123/
                if not title_link:
                    h2 = article_elem.find('h2')
                    if h2:
                        title_link = h2.find('a', href=re.compile(r'/ru/(?:articles|companies/[^/]+/articles)/\d+/'))
                
                # Если все еще не нашли, ищем любую ссылку на статью в article
                if not title_link:
                    title_link = article_elem.find('a', href=re.compile(r'/ru/(?:articles|companies/[^/]+/articles)/\d+/'))
                
                if not title_link:
                    continue
                
                href = title_link.get('href', '')
                if not href:
                    continue
                
                # Получаем полный URL
                if href.startswith('/'):
                    url_full = f"https://habr.com{href}"
                else:
                    url_full = href
                
                # Пропускаем дубликаты
                if url_full in seen_urls:
                    continue
                seen_urls.add(url_full)
                
                # Ищем заголовок статьи
                title = None
                # Пробуем найти заголовок в ссылке
                title_text = title_link.get_text(strip=True)
                if title_text and len(title_text) > 5:
                    title = title_text
                else:
                    # Ищем в span внутри ссылки
                    span = title_link.find('span')
                    if span:
                        title = span.get_text(strip=True)
                
                if not title or len(title) < 5:
                    continue
                
                # Ищем время публикации
                # Ищем элемент time с атрибутом datetime (может быть вложен в ссылку)
                time_elem = None
                time_str = None
                
                # Сначала ищем time элемент внутри article
                time_elem = article_elem.find('time')
                
                # Если не нашли, ищем внутри ссылок с классом tm-article-datetime-published
                if not time_elem:
                    datetime_link = article_elem.find('a', class_=lambda x: x and 'tm-article-datetime-published' in str(x))
                    if datetime_link:
                        time_elem = datetime_link.find('time')
                
                # Если все еще не нашли, ищем внутри всех ссылок
                if not time_elem:
                    links = article_elem.find_all('a')
                    for link in links:
                        time_elem = link.find('time')
                        if time_elem:
                            break
                
                if time_elem:
                    # Приоритет: атрибут datetime (это ISO формат в UTC)
                    datetime_attr = time_elem.get('datetime', '')
                    time_text = time_elem.get_text(strip=True)
                    
                    # Если есть datetime, используем его (он более точный)
                    # Если нет datetime или он пустой, используем текст (например, "1 час назад")
                    if datetime_attr:
                        time_str = datetime_attr
                        logger.debug(f"Найдено время из datetime атрибута: {time_str}")
                    elif time_text:
                        time_str = time_text
                        logger.debug(f"Найдено время из текста time элемента: {time_str}")
                    else:
                        time_str = None
                
                # Если не нашли time, ищем текст с временем в article
                # Ищем паттерны: "X час/часа/часов назад", "X минут/минуты/минуту назад", "вчера", "сегодня", даты
                if not time_str:
                    time_text = article_elem.find(string=re.compile(r'(\d+\s+час(?:ов|а|)|\d+\s+минут(?:у|ы|)|вчера|сегодня|\d+\s+\w+\s+\d{4})'))
                    if time_text:
                        if hasattr(time_text, 'strip'):
                            time_str = time_text.strip()
                        else:
                            time_str = str(time_text).strip()
                        logger.debug(f"Найдено время из текста статьи: {time_str}")
                
                if title and url_full:
                    articles.append({
                        'title': title,
                        'url': url_full,
                        'time_str': time_str,
                        'published_at': parse_time_string(time_str) if time_str else None
                    })
            except Exception as e:
                logger.warning(f"Ошибка при парсинге статьи: {e}")
                continue
        
        # Удаляем дубликаты по URL (на всякий случай)
        seen_urls = set()
        unique_articles = []
        for article in articles:
            if article['url'] not in seen_urls:
                seen_urls.add(article['url'])
                unique_articles.append(article)
        
        articles_word = format_number_with_noun(len(unique_articles), 'статья', 'статьи', 'статей')
        logger.info(f"Спарсено {articles_word} со страницы {url}")
        return unique_articles
        
    except requests.RequestException as e:
        logger.error(f"Ошибка при запросе к {url}: {e}")
        return []
    except Exception as e:
        logger.error(f"Ошибка при парсинге страницы {url}: {e}")
        return []


def parse_hub_articles(hub_name: str, hours_back: int) -> List[Dict[str, any]]:
    """
    Парсит статьи из конкретного хаба за последние N часов
    
    Args:
        hub_name: название хаба (из config.HUB_SLUGS)
        hours_back: количество часов назад для фильтрации
        
    Returns:
        Список словарей с информацией о статьях: [{"title": "...", "url": "...", "published_at": datetime}]
    """
    if hub_name not in HUB_SLUGS:
        logger.warning(f"Хаб {hub_name} не найден в конфигурации")
        return []
    
    hub_slug = HUB_SLUGS[hub_name]
    all_articles = []
    
    # Вычисляем граничное время
    # Добавляем небольшой запас (5 минут) чтобы статьи с "X часов назад" точно попадали в фильтр
    # Это компенсирует небольшую разницу во времени между вычислением порога и парсингом времени статьи
    time_threshold = datetime.now() - timedelta(hours=hours_back) - timedelta(minutes=5)
    
    page = 1
    max_pages = 50  # Ограничение на количество страниц для безопасности
    
    while page <= max_pages:
        url = HABR_HUB_URL_TEMPLATE.format(slug=hub_slug, page=page)
        logger.info(f"Парсинг страницы {page} хаба {hub_name}: {url}")
        
        page_articles = parse_page_articles(url)
        
        if not page_articles:
            logger.info(f"На странице {page} не найдено статей, прекращаем парсинг")
            break
        
        # Фильтруем статьи по времени
        filtered_articles = []
        all_old = True  # Флаг: все статьи на странице старше нужного периода
        articles_without_time = 0
        
        for article in page_articles:
            if article['published_at']:
                # Сравниваем время публикации с порогом
                article_time = article['published_at']
                if article_time >= time_threshold:
                    filtered_articles.append(article)
                    all_old = False
                    logger.debug(f"Статья включена: {article.get('title', 'Unknown')[:50]} - время: {article_time}")
                else:
                    # Статья старше нужного периода
                    all_old = all_old and True
                    logger.debug(f"Статья пропущена (старая): {article.get('title', 'Unknown')[:50]} - время: {article_time}, порог: {time_threshold}")
            else:
                # Если время не удалось распарсить, НЕ включаем статью
                articles_without_time += 1
                logger.debug(f"Статья без времени пропущена: {article.get('title', 'Unknown')[:50]}, time_str: {article.get('time_str', 'None')}")
        
        if articles_without_time > 0:
            articles_word = format_number_with_noun(articles_without_time, 'статья', 'статьи', 'статей')
            logger.warning(f"На странице {page} найдено {articles_word} без времени публикации")
        
        found_word = format_number_with_noun(len(page_articles), 'статья', 'статьи', 'статей')
        filtered_word = format_number_with_noun(len(filtered_articles), 'статья', 'статьи', 'статей')
        hours_word = format_number_with_noun(hours_back, 'час', 'часа', 'часов')
        logger.info(f"На странице {page}: найдено {found_word}, отфильтровано {filtered_word} за последние {hours_word}")
        
        all_articles.extend(filtered_articles)
        
        # Если все статьи на странице старше нужного периода, прекращаем парсинг
        if all_old and page_articles:
            logger.info(f"Все статьи на странице {page} старше {hours_back} часов, прекращаем парсинг")
            break
        
        # Если на странице не было статей с временем или все они новые, продолжаем
        page += 1
        
        # Rate limiter уже контролирует частоту запросов, но небольшая задержка не помешает
        # для дополнительной безопасности и снижения нагрузки на сервер
        time.sleep(0.2)
    
    articles_word = format_number_with_noun(len(all_articles), 'статья', 'статьи', 'статей')
    hours_word = format_number_with_noun(hours_back, 'час', 'часа', 'часов')
    logger.info(f"Всего найдено {articles_word} в хабе {hub_name} за последние {hours_word}")
    return all_articles

