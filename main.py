from pathlib import Path
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from typing import Dict, Any, List, Optional
import json
import os
import time
from datetime import datetime, timedelta, timezone
import requests
import uvicorn
from supabase import create_client, Client
from dotenv import load_dotenv
import logging
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Загрузка переменных окружения
load_dotenv()

app = FastAPI()

# Определяем базовую директорию
BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"

# Создаем директорию для статических файлов, если она не существует
if not STATIC_DIR.exists():
    STATIC_DIR.mkdir(parents=True, exist_ok=True)
    logger.info(f"Created static directory at {STATIC_DIR}")

# Проверка наличия необходимых переменных окружения
supabase_url = os.environ.get("SUPABASE_URL")
supabase_key = os.environ.get("SUPABASE_KEY")

if not supabase_url or not supabase_key:
    logger.error("Supabase URL and key must be set in environment variables")
    # В случае отсутствия переменных окружения, используем тестовые значения (только для разработки)
    supabase_url = "https://your-supabase-url.supabase.co"
    supabase_key = "your-supabase-key"
    logger.warning("Using default Supabase values. This should only happen in development!")

# Определение уровней
LEVELS = [
    {"score": 0, "name": "Новичок"},
    {"score": 100, "name": "Любитель"},
    {"score": 500, "name": "Профи"},
    {"score": 2000, "name": "Мастер"},
    {"score": 5000, "name": "Эксперт по Фембоям"},
    {"score": 10000, "name": "Фембой"},
    {"score": 50000, "name": "Фурри-Фембой"},
    {"score": 200000, "name": "Феликс"},
    {"score": 500000, "name": "Астольфо"},
    {"score": 1000000, "name": "Владелец фембоев"},
    {"score": 5000000, "name": "Император фембоев"},
    {"score": 10000000, "name": "Бог фембоев"}
]

# Определение улучшений
UPGRADES = [
    {"id": "upgrade1", "description": "+1 за клик", "cost": 1000, "effect": {"clickBonus": 1}, "image": "/static/upgrade1.png"},
    {"id": "upgrade2", "description": "+2 за клик", "cost": 5000, "effect": {"clickBonus": 2}, "image": "/static/upgrade2.png"},
    {"id": "upgrade3", "description": "+5 за клик", "cost": 10000, "effect": {"clickBonus": 5}, "image": "/static/upgrade3.png"},
    {"id": "upgrade4", "description": "+1 каждые 5 сек", "cost": 15000, "effect": {"passiveIncome": 1}, "image": "/static/upgrade4.png"},
    {"id": "upgrade5", "description": "+5 каждые 5 сек", "cost": 30000, "effect": {"passiveIncome": 5}, "image": "/static/upgrade5.png"},
    {"id": "upgrade6", "description": "+10 каждые 5 сек", "cost": 50000, "effect": {"passiveIncome": 10}, "image": "/static/upgrade6.png"},
    {"id": "upgrade7", "description": "+10 за клик", "cost": 75000, "effect": {"clickBonus": 10}, "image": "/static/upgrade7.png"},
    {"id": "upgrade8", "description": "+15 за клик", "cost": 100000, "effect": {"clickBonus": 15}, "image": "/static/upgrade8.png"},
    {"id": "upgrade9", "description": "+25 каждые 5 сек", "cost": 150000, "effect": {"passiveIncome": 25}, "image": "/static/upgrade9.png"},
    {"id": "upgrade10", "description": "+25 за клик", "cost": 250000, "effect": {"clickBonus": 25}, "image": "/static/upgrade10.png"},
    {"id": "upgrade11", "description": "+50 каждые 5 сек", "cost": 500000, "effect": {"passiveIncome": 50}, "image": "/static/upgrade11.png"},
    {"id": "upgrade12", "description": "+100 за клик", "cost": 1000000, "effect": {"clickBonus": 100}, "image": "/static/upgrade12.png"},
    # Новые улучшения
    {"id": "boost_2x", "description": "x2 очки на 10 минут", "cost": 5000, "effect": {"type": "temporary_boost", "multiplier": 2, "duration": 600}, "image": "/static/boost_2x.png"},
    {"id": "energy_max", "description": "+50 к макс. энергии", "cost": 10000, "effect": {"type": "max_energy", "value": 50}, "image": "/static/energy_max.png"},
    {"id": "skin_gold", "description": "Золотой скин", "cost": 20000, "effect": {"type": "visual", "skin": "gold"}, "image": "/static/skin_gold.png"},
    {"id": "auto_clicker", "description": "Автокликер (1 клик/сек)", "cost": 50000, "effect": {"type": "auto_clicker", "value": 1}, "image": "/static/auto_clicker.png"}
]

# Определение заданий
NORMAL_TASKS = [
    {
        "id": "wallet_task",
        "title": "Подключить TON кошелек",
        "reward": 1000,
        "type": "normal"
    },
    {
        "id": "channel_subscription",
        "title": "Подписка на канал",
        "reward": 2000,
        "type": "normal"
    }
]

DAILY_TASKS = [
    {
        "id": "referral_task",
        "title": "Пригласить 3-х друзей",
        "reward": 5000,
        "type": "daily"
    },
    {
        "id": "ads_task",
        "title": "Просмотр рекламы",
        "reward": 5000,
        "type": "daily",
        "no_reset": True
    }
]

# Определение достижений
ACHIEVEMENTS = [
    {
        "id": "first_click",
        "name": "Первый клик",
        "description": "Сделайте свой первый клик",
        "reward": 100,
        "condition": {"type": "clicks", "value": 1}
    },
    {
        "id": "click_master",
        "name": "Мастер кликов",
        "description": "Сделайте 1000 кликов",
        "reward": 5000,
        "condition": {"type": "clicks", "value": 1000}
    },
    {
        "id": "score_1000",
        "name": "Тысячник",
        "description": "Наберите 1000 очков",
        "reward": 1000,
        "condition": {"type": "score", "value": 1000}
    },
    {
        "id": "first_friend",
        "name": "Первый друг",
        "description": "Пригласите первого друга",
        "reward": 2000,
        "condition": {"type": "referrals", "value": 1}
    },
    {
        "id": "daily_login",
        "name": "Ежедневный вход",
        "description": "Входите в игру 7 дней подряд",
        "reward": 3000,
        "condition": {"type": "daily_streak", "value": 7}
    }
]

# Определение мини-игр
MINIGAMES = [
    {
        "id": "catch_coins",
        "name": "Поймай монетки",
        "description": "Ловите падающие монетки!",
        "reward": 100,
        "duration": 30
    }
]

# Определение ежедневных бонусов
DAILY_BONUSES = [
    {"day": 1, "reward": 100},
    {"day": 2, "reward": 200},
    {"day": 3, "reward": 300},
    {"day": 4, "reward": 400},
    {"day": 5, "reward": 500},
    {"day": 6, "reward": 600},
    {"day": 7, "reward": 1000}
]

# Функция для определения уровня по очкам
def get_level_by_score(score: int) -> str:
    for i in range(len(LEVELS) - 1, -1, -1):
        if score >= LEVELS[i]["score"]:
            return LEVELS[i]["name"]
    return LEVELS[0]["name"]

# Инициализация Supabase клиента (один раз для всего приложения)
try:
    supabase: Client = create_client(supabase_url, supabase_key)
    logger.info("Supabase client initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize Supabase client: {str(e)}")
    # Не прерываем работу приложения, а просто логируем ошибку
    # Это позволит приложению работать, даже если Supabase недоступен
    supabase = None

# Максимальное количество энергии
MAX_ENERGY = 250

# Декоратор для повторных попыток при ошибках соединения
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception_type(Exception)
)
def execute_supabase_query(func):
    """Выполняет запрос к Supabase с повторными попытками при ошибках"""
    if supabase is None:
        logger.error("Supabase client is not initialized")
        raise Exception("Supabase client is not initialized")
    
    try:
        return func()
    except Exception as e:
        logger.warning(f"Supabase query failed: {str(e)}, retrying...")
        raise

# Функция для загрузки данных пользователя
def load_user(user_id: str) -> Optional[Dict[str, Any]]:
    if supabase is None:
        logger.error("Supabase client is not initialized")
        return None
        
    try:
        logger.info(f"Loading user with ID: {user_id}")
        
        def query():
            return supabase.table("users").select("*").eq("user_id", user_id).execute()
        
        response = execute_supabase_query(query)
        
        if response.data and len(response.data) > 0:
            user_data = response.data[0]
            logger.info(f"User found: {user_data.get('first_name', 'Unknown')}")
            
            # Убедимся, что все поля присутствуют и имеют правильный тип
            if not isinstance(user_data.get('referrals'), list):
                user_data['referrals'] = []
                
            if not isinstance(user_data.get('upgrades'), list):
                user_data['upgrades'] = []
            
            # Добавляем поле для счетчика рекламы, если его нет
            if 'ads_watched' not in user_data:
                user_data['ads_watched'] = 0
                logger.info("Added default ads_watched value to user data")
            
            # Добавляем поле для задания подписки на канал, если его нет
            if 'channel_task_completed' not in user_data:
                user_data['channel_task_completed'] = False
                logger.info("Added default channel_task_completed value to user data")
            
            # Добавляем поля для достижений
            if 'achievements' not in user_data:
                user_data['achievements'] = []
                logger.info("Added default achievements value to user data")
            
            # Добавляем поля для друзей
            if 'friends' not in user_data:
                user_data['friends'] = []
                logger.info("Added default friends value to user data")
            
            # Добавляем поля для ежедневных бонусов
            if 'daily_bonus' not in user_data:
                user_data['daily_bonus'] = {
                    'last_claim': None,
                    'streak': 0,
                    'claimed_days': []
                }
                logger.info("Added default daily_bonus value to user data")
            
            # Добавляем поля для активных бустов
            if 'active_boosts' not in user_data:
                user_data['active_boosts'] = []
                logger.info("Added default active_boosts value to user data")
            
            # Добавляем поля для скинов
            if 'skins' not in user_data:
                user_data['skins'] = []
                logger.info("Added default skins value to user data")
            
            if 'active_skin' not in user_data:
                user_data['active_skin'] = 'default'
                logger.info("Added default active_skin value to user data")
            
            # Добавляем поля для автокликеров
            if 'auto_clickers' not in user_data:
                user_data['auto_clickers'] = 0
                logger.info("Added default auto_clickers value to user data")
            
            # Добавляем поле для языка
            if 'language' not in user_data:
                user_data['language'] = 'ru'
                logger.info("Added default language value to user data")
            
            # Обновляем уровень на основе очков
            user_data['level'] = get_level_by_score(user_data.get('score', 0))
            
            # Восстанавливаем энергию на основе времени последнего обновления
            last_energy_update = user_data.get('last_energy_update')
            current_time = datetime.now(timezone.utc)
            
            if not last_energy_update:
                # Если время последнего обновления отсутствует, устанавливаем текущее время и максимальную энергию
                user_data['energy'] = MAX_ENERGY
                user_data['last_energy_update'] = current_time.isoformat()
            else:
                try:
                    # Парсим дату с учетом возможного часового пояса
                    if isinstance(last_energy_update, str):
                        # Убираем 'Z' если есть и парсим как UTC
                        if last_energy_update.endswith('Z'):
                            last_update_time = datetime.fromisoformat(last_energy_update.replace('Z', '+00:00'))
                        else:
                            last_update_time = datetime.fromisoformat(last_energy_update)
                    else:
                        last_update_time = last_energy_update
                    
                    # Убедимся, что last_update_time имеет timezone
                    if last_update_time.tzinfo is None:
                        last_update_time = last_update_time.replace(tzinfo=timezone.utc)
                    
                    time_diff_seconds = (current_time - last_update_time).total_seconds()
                    
                    # Восстанавливаем энергию (1 единица в секунду)
                    current_energy = user_data.get('energy', MAX_ENERGY)
                    restored_energy = min(MAX_ENERGY, current_energy + int(time_diff_seconds))
                    
                    # Обновляем энергию и время последнего обновления
                    user_data['energy'] = restored_energy
                    user_data['last_energy_update'] = current_time.isoformat()
                except Exception as e:
                    logger.error(f"Error restoring energy: {e}")
                    # В случае ошибки, устанавливаем энергию в максимальное значение и текущее время
                    user_data['energy'] = MAX_ENERGY
                    user_data['last_energy_update'] = current_time.isoformat()
            
            return user_data
        else:
            logger.info(f"User not found with ID {user_id}")
            return None
    except Exception as e:
        logger.error(f"Error loading user: {e}")
        return None

# Функция для сохранения данных пользователя
def save_user(user_data: Dict[str, Any]) -> bool:
    if supabase is None:
        logger.error("Supabase client is not initialized")
        return False
        
    try:
        logger.info(f"Saving user: {user_data.get('first_name', 'Unknown')}")
        
        # Подготовка данных для вставки/обновления
        db_data = {
            "user_id": str(user_data.get('id', '')),
            "first_name": user_data.get('first_name', ''),
            "last_name": user_data.get('last_name', ''),
            "username": user_data.get('username', ''),
            "photo_url": user_data.get('photo_url', ''),
            "score": int(user_data.get('score', 0)),
            "total_clicks": int(user_data.get('total_clicks', 0)),
            "level": get_level_by_score(int(user_data.get('score', 0))),
            "wallet_address": user_data.get('walletAddress', ''),
            "wallet_task_completed": bool(user_data.get('walletTaskCompleted', False)),
            "channel_task_completed": bool(user_data.get('channelTaskCompleted', False)),
            "referrals": user_data.get('referrals', []),
            "last_referral_task_completion": user_data.get('lastReferralTaskCompletion'),
            "energy": int(user_data.get('energy', MAX_ENERGY)),
            "last_energy_update": user_data.get('lastEnergyUpdate', datetime.now(timezone.utc).isoformat()),
            "upgrades": user_data.get('upgrades', []),
            "ads_watched": int(user_data.get('ads_watched', 0)),
            "achievements": user_data.get('achievements', []),
            "friends": user_data.get('friends', []),
            "daily_bonus": user_data.get('daily_bonus', {
                'last_claim': None,
                'streak': 0,
                'claimed_days': []
            }),
            "active_boosts": user_data.get('active_boosts', []),
            "skins": user_data.get('skins', []),
            "active_skin": user_data.get('active_skin', 'default'),
            "auto_clickers": int(user_data.get('auto_clickers', 0)),
            "language": user_data.get('language', 'ru')
        }
        
        def query():
            # Используем upsert для атомарной вставки или обновления
            return supabase.table("users").upsert(
                db_data, 
                on_conflict="user_id"
            ).execute()
        
        response = execute_supabase_query(query)
        
        logger.info(f"Save operation completed with data: {response.data}")
        return response.data is not None
    except Exception as e:
        logger.error(f"Error saving user: {e}")
        return False

# Функция для получения топа пользователей
def get_top_users(limit: int = 100) -> List[Dict[str, Any]]:
    if supabase is None:
        logger.error("Supabase client is not initialized")
        return []
        
    try:
        logger.info(f"Getting top {limit} users")
        
        def query():
            return supabase.table("users").select("user_id, first_name, last_name, username, photo_url, score, level").order("score", desc=True).limit(limit).execute()
        
        response = execute_supabase_query(query)
        
        if response.data:
            logger.info(f"Found {len(response.data)} users")
            return response.data
        else:
            logger.info("No users found")
            return []
    except Exception as e:
        logger.error(f"Error getting top users: {e}")
        return []

# Функция для добавления реферала
def add_referral(referrer_id: str, referred_id: str) -> bool:
    if supabase is None:
        logger.error("Supabase client is not initialized")
        return False
        
    try:
        logger.info(f"Adding referral: {referrer_id} -> {referred_id}")
        
        # Получаем данные реферера
        def query():
            return supabase.table("users").select("referrals").eq("user_id", referrer_id).execute()
        
        response = execute_supabase_query(query)
        
        if not response.data or len(response.data) == 0:
            logger.info(f"Referrer not found: {referrer_id}")
            return False
        
        referrals = response.data[0].get("referrals", [])
        
        # Если реферал уже добавлен, ничего не делаем
        if referred_id in referrals:
            logger.info("Referral already exists")
            return True
        
        # Добавляем нового реферала
        referrals.append(referred_id)
        
        # Обновляем данные реферера
        def update_query():
            return supabase.table("users").update({"referrals": referrals}).eq("user_id", referrer_id).execute()
        
        update_response = execute_supabase_query(update_query)
        
        logger.info("Referral added successfully")
        return update_response.data is not None
    except Exception as e:
        logger.error(f"Error adding referral: {e}")
        return False

# Функция для получения достижений
def get_achievements(user_id: str) -> List[Dict[str, Any]]:
    if supabase is None:
        logger.error("Supabase client is not initialized")
        return []
        
    try:
        logger.info(f"Getting achievements for user: {user_id}")
        
        def query():
            return supabase.table("users").select("achievements").eq("user_id", user_id).execute()
        
        response = execute_supabase_query(query)
        
        if response.data and len(response.data) > 0:
            return response.data[0].get("achievements", [])
        else:
            return []
    except Exception as e:
        logger.error(f"Error getting achievements: {e}")
        return []

# Функция для добавления достижения
def add_achievement(user_id: str, achievement_id: str) -> bool:
    if supabase is None:
        logger.error("Supabase client is not initialized")
        return False
        
    try:
        logger.info(f"Adding achievement {achievement_id} to user: {user_id}")
        
        # Получаем текущие достижения пользователя
        def query():
            return supabase.table("users").select("achievements").eq("user_id", user_id).execute()
        
        response = execute_supabase_query(query)
        
        if not response.data or len(response.data) == 0:
            logger.info(f"User not found: {user_id}")
            return False
        
        achievements = response.data[0].get("achievements", [])
        
        # Если достижение уже добавлено, ничего не делаем
        if achievement_id in achievements:
            logger.info("Achievement already exists")
            return True
        
        # Добавляем новое достижение
        achievements.append(achievement_id)
        
        # Обновляем данные пользователя
        def update_query():
            return supabase.table("users").update({"achievements": achievements}).eq("user_id", user_id).execute()
        
        update_response = execute_supabase_query(update_query)
        
        logger.info("Achievement added successfully")
        return update_response.data is not None
    except Exception as e:
        logger.error(f"Error adding achievement: {e}")
        return False

# Функция для получения друзей
def get_friends(user_id: str) -> List[Dict[str, Any]]:
    if supabase is None:
        logger.error("Supabase client is not initialized")
        return []
        
    try:
        logger.info(f"Getting friends for user: {user_id}")
        
        def query():
            return supabase.table("users").select("friends").eq("user_id", user_id).execute()
        
        response = execute_supabase_query(query)
        
        if response.data and len(response.data) > 0:
            return response.data[0].get("friends", [])
        else:
            return []
    except Exception as e:
        logger.error(f"Error getting friends: {e}")
        return []

# Функция для добавления друга
def add_friend(user_id: str, friend_id: str) -> bool:
    if supabase is None:
        logger.error("Supabase client is not initialized")
        return False
        
    try:
        logger.info(f"Adding friend {friend_id} to user: {user_id}")
        
        # Получаем текущих друзей пользователя
        def query():
            return supabase.table("users").select("friends").eq("user_id", user_id).execute()
        
        response = execute_supabase_query(query)
        
        if not response.data or len(response.data) == 0:
            logger.info(f"User not found: {user_id}")
            return False
        
        friends = response.data[0].get("friends", [])
        
        # Если друг уже добавлен, ничего не делаем
        if friend_id in friends:
            logger.info("Friend already exists")
            return True
        
        # Добавляем нового друга
        friends.append(friend_id)
        
        # Обновляем данные пользователя
        def update_query():
            return supabase.table("users").update({"friends": friends}).eq("user_id", user_id).execute()
        
        update_response = execute_supabase_query(update_query)
        
        logger.info("Friend added successfully")
        return update_response.data is not None
    except Exception as e:
        logger.error(f"Error adding friend: {e}")
        return False

# Функция для отправки подарка
def send_gift(sender_id: str, receiver_id: str, gift_type: str, gift_value: int) -> bool:
    if supabase is None:
        logger.error("Supabase client is not initialized")
        return False
        
    try:
        logger.info(f"Sending gift from {sender_id} to {receiver_id}: {gift_type} ({gift_value})")
        
        # Получаем данные отправителя
        def sender_query():
            return supabase.table("users").select("score").eq("user_id", sender_id).execute()
        
        sender_response = execute_supabase_query(sender_query)
        
        if not sender_response.data or len(sender_response.data) == 0:
            logger.info(f"Sender not found: {sender_id}")
            return False
        
        sender_score = sender_response.data[0].get("score", 0)
        
        # Проверяем, достаточно ли очков у отправителя
        if sender_score < gift_value:
            logger.info("Sender doesn't have enough score")
            return False
        
        # Получаем данные получателя
        def receiver_query():
            return supabase.table("users").select("score").eq("user_id", receiver_id).execute()
        
        receiver_response = execute_supabase_query(receiver_query)
        
        if not receiver_response.data or len(receiver_response.data) == 0:
            logger.info(f"Receiver not found: {receiver_id}")
            return False
        
        receiver_score = receiver_response.data[0].get("score", 0)
        
        # Списываем очки у отправителя
        def update_sender_query():
            return supabase.table("users").update({"score": sender_score - gift_value}).eq("user_id", sender_id).execute()
        
        update_sender_response = execute_supabase_query(update_sender_query)
        
        if not update_sender_response.data:
            logger.info("Failed to update sender score")
            return False
        
        # Добавляем очки получателю
        def update_receiver_query():
            return supabase.table("users").update({"score": receiver_score + gift_value}).eq("user_id", receiver_id).execute()
        
        update_receiver_response = execute_supabase_query(update_receiver_query)
        
        if not update_receiver_response.data:
            logger.info("Failed to update receiver score")
            return False
        
        logger.info("Gift sent successfully")
        return True
    except Exception as e:
        logger.error(f"Error sending gift: {e}")
        return False

# Функция для получения ежедневного бонуса
def claim_daily_bonus(user_id: str) -> Dict[str, Any]:
    if supabase is None:
        logger.error("Supabase client is not initialized")
        return {"status": "error", "message": "Supabase client is not initialized"}
        
    try:
        logger.info(f"Claiming daily bonus for user: {user_id}")
        
        # Получаем данные пользователя
        def query():
            return supabase.table("users").select("*").eq("user_id", user_id).execute()
        
        response = execute_supabase_query(query)
        
        if not response.data or len(response.data) == 0:
            logger.info(f"User not found: {user_id}")
            return {"status": "error", "message": "User not found"}
        
        user_data = response.data[0]
        daily_bonus = user_data.get("daily_bonus", {
            'last_claim': None,
            'streak': 0,
            'claimed_days': []
        })
        
        current_time = datetime.now(timezone.utc)
        today = current_time.date().isoformat()
        
        # Проверяем, был ли уже получен бонус сегодня
        if daily_bonus.get('last_claim') and daily_bonus['last_claim'].date() == current_time.date():
            logger.info("Daily bonus already claimed today")
            return {"status": "error", "message": "Daily bonus already claimed today"}
        
        # Определяем день бонуса
        if daily_bonus['streak'] == 0 or (daily_bonus.get('last_claim') and 
                                         (current_time.date() - daily_bonus['last_claim'].date()).days > 1):
            # Если серия прервана, начинаем заново
            daily_bonus['streak'] = 1
        else:
            # Увеличиваем серию
            daily_bonus['streak'] += 1
        
        # Ограничиваем серию максимальным количеством дней
        if daily_bonus['streak'] > len(DAILY_BONUSES):
            daily_bonus['streak'] = len(DAILY_BONUSES)
        
        # Определяем награду
        bonus_day = min(daily_bonus['streak'], len(DAILY_BONUSES))
        bonus_reward = DAILY_BONUSES[bonus_day - 1]['reward']
        
        # Обновляем данные пользователя
        daily_bonus['last_claim'] = current_time
        if today not in daily_bonus['claimed_days']:
            daily_bonus['claimed_days'].append(today)
        
        # Добавляем очки пользователю
        new_score = user_data.get('score', 0) + bonus_reward
        
        def update_query():
            return supabase.table("users").update({
                "score": new_score,
                "daily_bonus": daily_bonus
            }).eq("user_id", user_id).execute()
        
        update_response = execute_supabase_query(update_query)
        
        if not update_response.data:
            logger.info("Failed to update user data")
            return {"status": "error", "message": "Failed to update user data"}
        
        logger.info(f"Daily bonus claimed successfully: {bonus_reward}")
        return {
            "status": "success", 
            "reward": bonus_reward,
            "streak": daily_bonus['streak']
        }
    except Exception as e:
        logger.error(f"Error claiming daily bonus: {e}")
        return {"status": "error", "message": str(e)}

# Функция для сохранения аналитики
def save_analytics(user_id: str, event: str, data: Dict[str, Any]) -> bool:
    if supabase is None:
        logger.error("Supabase client is not initialized")
        return False
        
    try:
        logger.info(f"Saving analytics for user {user_id}: {event}")
        
        analytics_data = {
            "user_id": user_id,
            "event": event,
            "data": data,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        def query():
            return supabase.table("analytics").insert(analytics_data).execute()
        
        response = execute_supabase_query(query)
        
        logger.info(f"Analytics saved successfully")
        return response.data is not None
    except Exception as e:
        logger.error(f"Error saving analytics: {e}")
        return False

# Монтируем статические файлы
try:
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
    logger.info(f"Static files mounted from {STATIC_DIR}")
except Exception as e:
    logger.error(f"Error mounting static files: {e}")

# Обработчик для favicon.ico
@app.get("/favicon.ico")
async def favicon():
    return Response(status_code=204)  # Возвращаем пустой ответ без содержимого

# Эндпоинт для обработки уведомлений от Adsgram
@app.get("/adsgram-reward")
async def adsgram_reward(request: Request):
    """Обработка уведомлений о просмотре рекламы от Adsgram"""
    try:
        logger.info(f"GET /adsgram-reward endpoint called")
        
        # Получаем ID пользователя из параметров запроса
        user_id = request.query_params.get("userid")
        
        if not user_id:
            logger.warning("Missing userid parameter in Adsgram request")
            return JSONResponse(content={"status": "error", "message": "Missing userid parameter"}, status_code=400)
        
        logger.info(f"Processing Adsgram reward for user {user_id}")
        
        # Загружаем данные пользователя
        user_data = load_user(user_id)
        
        if not user_data:
            logger.warning(f"User not found: {user_id}")
            return JSONResponse(content={"status": "error", "message": "User not found"}, status_code=404)
        
        # Увеличиваем счетчик просмотренной рекламы
        if 'ads_watched' not in user_data:
            user_data['ads_watched'] = 0
        
        old_count = user_data['ads_watched']
        user_data['ads_watched'] += 1
        
        logger.info(f"Updated ads_watched for user {user_id}: {old_count} -> {user_data['ads_watched']}")
        
        # Сохраняем обновленные данные
        success = save_user(user_data)
        
        if success:
            logger.info(f"Successfully updated ads_watched for user {user_id}: {user_data['ads_watched']}")
            return JSONResponse(content={"status": "success", "ads_watched": user_data['ads_watched']})
        else:
            logger.error(f"Failed to save user data for {user_id}")
            return JSONResponse(content={"status": "error", "message": "Failed to save user data"}, status_code=500)
            
    except Exception as e:
        logger.error(f"Error in /adsgram-reward: {e}")
        return JSONResponse(content={"status": "error", "message": str(e)}, status_code=500)

html_content = """
<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
  <title>ляжки фембоя</title>
  <script src="https://telegram.org/js/telegram-web-app.js"></script>
  <script src="https://unpkg.com/@tonconnect/ui@latest/dist/tonconnect-ui.min.js"></script>
  <script src="https://sad.adsgram.ai/js/sad.min.js"></script>
  <style>
    @import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@700&display=swap');

    body {
      margin: 0;
      height: 100vh;
      background: linear-gradient(135deg, #ff9a9e 0%, #fad0c4 50%, #a18cd1 100%);
      font-family: 'Montserrat', sans-serif;
      user-select: none;
      color: #fff;
      text-shadow: 0 0 5px #ff77cc;
      display: flex;
      flex-direction: column;
      padding-bottom: 60px;
      overflow-x: hidden;
      touch-action: none;
      overscroll-behavior: none;
    }

    #content {
      flex-grow: 1;
      display: flex;
      justify-content: center;
      align-items: center;
      position: relative;
    }

    .page {
      display: none;
      width: 100%;
      max-width: 400px;
      padding: 20px;
      box-sizing: border-box;
      text-align: center;
    }

    .active {
      display: block;
    }

    #circle {
      width: 150px;
      height: 150px;
      cursor: pointer;
      border-radius: 50%;
      box-shadow: 0 8px 20px rgba(255, 102, 204, 0.6);
      transition: transform 0.2s ease, box-shadow 0.2s ease;
      display: flex;
      align-items: center;
      justify-content: center;
      overflow: hidden;
      background-color: transparent;
      user-select: none;
      -webkit-tap-highlight-color: transparent;
      margin: 0 auto;
    }
    #circle img {
      width: 100%;
      height: 100%;
      object-fit: cover;
      border-radius: 50%;
      pointer-events: none;
      user-select: none;
    }
    #circle.pressed {
      transform: scale(0.95);
      box-shadow: 0 4px 12px rgba(255, 102, 204, 0.9);
    }
    #score {
      margin-top: 25px;
      font-size: 40px;
      font-weight: 700;
      text-shadow: 0 0 15px #ff66cc;
      display: flex;
      align-items: center;
      gap: 10px;
      user-select: none;
      justify-content: center;
    }
    #coin {
      width: 50px;
      height: 50px;
      user-select: none;
    }

    #bottom-menu {
      position: fixed;
      bottom: 0;
      left: 0;
      width: 100%;
      height: 60px;
      background: rgba(0,0,0,0.3);
      backdrop-filter: blur(10px);
      display: flex;
      justify-content: space-around;
      align-items: center;
      box-shadow: 0 -2px 10px rgba(255, 102, 204, 0.5);
      z-index: 100;
      overflow-x: auto;
      white-space: nowrap;
      -webkit-overflow-scrolling: touch;
      scrollbar-width: none; /* Firefox */
    }
    #bottom-menu::-webkit-scrollbar {
      display: none; /* Chrome, Safari, Edge */
    }
    #bottom-menu button {
      background: transparent;
      border: none;
      color: #fff;
      font-size: 16px;
      font-weight: 700;
      cursor: pointer;
      padding: 8px 12px;
      border-radius: 12px;
      transition: background-color 0.3s, color 0.3s;
      user-select: none;
      pointer-events: auto;
      flex-shrink: 0;
    }
    #bottom-menu button.active {
      background-color: #ff66cc;
      color: #fff;
      box-shadow: 0 0 8px #ff66cc;
    }
    #bottom-menu button:focus {
      outline: 2px solid #ff66cc;
      outline-offset: 2px;
    }

    #profile, #tasks, #top, #achievements, #friends, #minigames, #daily {
      font-size: 18px;
      line-height: 1.5;
      user-select: text;
    }
    
    #userProfile {
      display: flex;
      flex-direction: column;
      align-items: center;
      margin-bottom: 20px;
    }
    #userAvatar {
      width: 120px;
      height: 120px;
      border-radius: 50%;
      border: 3px solid #ff66cc;
      box-shadow: 0 0 15px rgba(255, 102, 204, 0.7);
      margin-bottom: 15px;
    }
    #userName {
      font-size: 24px;
      margin: 0 0 10px;
      text-shadow: 0 0 10px #ff66cc;
    }
    #userHandle {
      font-size: 18px;
      margin: 0 0 15px;
      opacity: 0.8;
    }
    #profileScore {
      font-size: 20px;
      margin: 10px 0;
    }
    .profile-stats {
      background: rgba(0,0,0,0.2);
      border-radius: 15px;
      padding: 15px;
      margin-top: 20px;
      width: 100%;
      box-sizing: border-box;
    }
    .profile-stats p {
      margin: 10px 0;
      display: flex;
      justify-content: space-between;
    }
    .profile-stats span {
      font-weight: bold;
    }
    #loadingIndicator {
      display: none;
      text-align: center;
      margin: 20px 0;
    }
    
    /* Розовая полоска сверху */
    .telegram-header {
      position: fixed;
      top: 0;
      left: 0;
      width: 100%;
      height: 60px;
      background: linear-gradient(135deg, rgba(255, 102, 204, 0.8), rgba(255, 154, 158, 0.8));
      z-index: 40;
    }
    
    /* Стили для кнопки топа */
    #topButton {
      position: fixed;
      top: 60px;
      left: 0;
      width: 100%;
      background: linear-gradient(135deg, rgba(255, 102, 204, 0.8), rgba(255, 154, 158, 0.8));
      border: none;
      padding: 15px 0;
      color: white;
      font-weight: bold;
      cursor: pointer;
      font-size: 18px;
      box-shadow: 0 4px 12px rgba(255, 102, 204, 0.5);
      transition: all 0.3s ease;
      z-index: 50;
      display: flex;
      flex-direction: column;
      align-items: center;
      backdrop-filter: blur(5px);
      min-height: 120px;
      justify-content: center;
    }
    #topButton:hover {
      background: linear-gradient(135deg, rgba(255, 102, 204, 0.9), rgba(255, 154, 158, 0.9));
    }
    #topButton:active {
      transform: translateY(1px);
    }
    .top-preview {
      display: flex;
      flex-direction: column;
      justify-content: center;
      width: 100%;
      margin-top: 10px;
      font-size: 14px;
      position: relative;
      height: 60px;
      overflow: hidden;
    }
    .top-preview-item {
      margin: 3px 0;
      opacity: 0.9;
      transition: opacity 0.3s ease;
      text-align: center;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
      padding: 0 10px;
    }
    .top-preview-item:nth-child(2) {
      opacity: 0.7;
    }
    .top-preview-item:nth-child(3) {
      opacity: 0.5;
      position: relative;
    }
    .top-preview-item:nth-child(3)::after {
      content: '';
      position: absolute;
      bottom: 0;
      left: 0;
      width: 100%;
      height: 15px;
      background: linear-gradient(to bottom, rgba(255, 154, 158, 0), rgba(255, 154, 158, 0.8));
      pointer-events: none;
    }
    
    /* Стили для секции топа */
    #topList {
      margin-top: 20px;
      max-height: 70vh;
      overflow-y: auto;
      text-align: left;
    }
    .top-item {
      display: flex;
      align-items: center;
      margin-bottom: 12px;
      background: rgba(0, 0, 0, 0.2);
      border-radius: 12px;
      padding: 10px;
      transition: transform 0.2s ease;
    }
    .top-item:hover {
      transform: translateX(5px);
    }
    .top-rank {
      width: 30px;
      font-weight: bold;
      margin-right: 10px;
      font-size: 18px;
      text-align: center;
    }
    .top-avatar {
      width: 40px;
      height: 40px;
      border-radius: 50%;
      margin-right: 10px;
      object-fit: cover;
    }
    .top-info {
      flex-grow: 1;
    }
    .top-name {
      font-weight: bold;
      font-size: 16px;
    }
    .top-score {
      font-size: 14px;
      opacity: 0.8;
      display: flex;
      align-items: center;
      gap: 5px;
    }
    .top-level {
      font-size: 12px;
      background: rgba(255, 102, 204, 0.3);
      padding: 2px 6px;
      border-radius: 10px;
      margin-left: 5px;
    }
    .top-coin {
      width: 16px;
      height: 16px;
    }
    .current-user {
      background: rgba(255, 102, 204, 0.3);
      border: 1px solid #ff66cc;
    }
    #topHeader {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 15px;
    }
    #backButton {
      background: rgba(255, 255, 255, 0.2);
      border: none;
      border-radius: 10px;
      padding: 5px 10px;
      color: white;
      font-weight: bold;
      cursor: pointer;
      font-size: 14px;
    }
    
    /* Стили для прогресс-бара уровня */
    #levelProgress {
      position: relative;
      width: 250px;
      height: 30px;
      margin: 20px auto 0;
      background: rgba(0, 0, 0, 0.2);
      border-radius: 15px;
      overflow: hidden;
      box-shadow: 0 5px 15px rgba(255, 102, 204, 0.4);
    }
    #levelProgressBar {
      height: 100%;
      background: linear-gradient(90deg, #ff66cc, #ff9a9e);
      border-radius: 15px;
      transition: width 0.5s ease;
      position: relative;
    }
    #levelProgressBar::after {
      content: '';
      position: absolute;
      top: 0;
      left: 0;
      right: 0;
      bottom: 0;
      background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.3), transparent);
      animation: shimmer 2s infinite;
    }
    @keyframes shimmer {
      0% { transform: translateX(-100%); }
      100% { transform: translateX(100%); }
    }
    #levelProgressText {
      position: absolute;
      top: 0;
      left: 0;
      width: 100%;
      height: 100%;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 14px;
      font-weight: bold;
      text-shadow: 0 0 5px rgba(0, 0, 0, 0.5);
    }
    
    /* Стили для энергии */
    #energyContainer {
      margin-top: 15px;
      display: flex;
      flex-direction: column;
      align-items: center;
      position: relative;
    }
    #energyBar {
      width: 250px;
      height: 20px;
      background: rgba(0, 0, 0, 0.2);
      border-radius: 10px;
      overflow: hidden;
      margin-bottom: 5px;
      box-shadow: 0 5px 15px rgba(255, 215, 0, 0.3);
    }
    #energyProgress {
      height: 100%;
      background: linear-gradient(90deg, #FFD700, #FFA500);
      border-radius: 10px;
      transition: width 0.3s ease;
      position: relative;
    }
    #energyProgress::after {
      content: '';
      position: absolute;
      top: 0;
      left: 0;
      right: 0;
      bottom: 0;
      background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.4), transparent);
      animation: energyShimmer 2s infinite;
    }
    @keyframes energyShimmer {
      0% { transform: translateX(-100%); }
      100% { transform: translateX(100%); }
    }
    #energyText {
      font-size: 14px;
      font-weight: bold;
      display: flex;
      align-items: center;
      gap: 5px;
    }
    #energyIcon {
      font-size: 18px;
      color: #FFD700;
      text-shadow: 0 0 5px rgba(255, 215, 0, 0.7);
    }
    
    /* Стили для пассивного дохода (фиксированный вверху справа) */
    #passive-income-display {
      position: fixed;
      top: 190px;
      right: 10px;
      background: rgba(0, 0, 0, 0.7);
      color: #FFD700;
      padding: 8px 12px;
      border-radius: 10px;
      font-size: 14px;
      font-weight: bold;
      z-index: 95;
      display: flex;
      align-items: center;
      gap: 5px;
    }
    #passive-income-icon {
      font-size: 16px;
    }
    
    /* Стили для молний */
    .lightning {
      position: absolute;
      width: 10px;
      height: 20px;
      background: linear-gradient(to bottom, #FFD700, #FFA500);
      clip-path: polygon(50% 0%, 0% 100%, 100% 100%);
      opacity: 0;
      z-index: 10;
      filter: drop-shadow(0 0 6px #FFD700);
    }
    .lightning.active {
      animation: lightningBolt 0.5s ease-out forwards;
    }
    @keyframes lightningBolt {
      0% {
        transform: translate(-50%, -50%) scale(0);
        opacity: 1;
      }
      50% {
        opacity: 1;
      }
      100% {
        transform: translate(-50%, -50%) scale(1.5);
        opacity: 0;
      }
    }
    
    /* Стили для модального окна уровня */
    #levelUpModal {
      position: fixed;
      top: 0;
      left: 0;
      width: 100%;
      height: 100%;
      background: rgba(0, 0, 0, 0.7);
      display: none;
      justify-content: center;
      align-items: center;
      z-index: 1000;
    }
    .levelUpContent {
      background: linear-gradient(135deg, #ff66cc, #ff9a9e);
      border-radius: 20px;
      padding: 30px;
      text-align: center;
      max-width: 80%;
      box-shadow: 0 10px 30px rgba(255, 102, 204, 0.6);
      transform: scale(0);
      animation: popIn 0.5s forwards;
    }
    @keyframes popIn {
      0% { transform: scale(0); }
      70% { transform: scale(1.1); }
      100% { transform: scale(1); }
    }
    .levelUpTitle {
      font-size: 28px;
      margin-bottom: 15px;
      text-shadow: 0 0 10px rgba(255, 255, 255, 0.5);
    }
    .levelUpLevel {
      font-size: 36px;
      margin-bottom: 20px;
      color: #fff;
      text-shadow: 0 0 15px rgba(255, 255, 255, 0.7);
    }
    .levelUpButton {
      background: rgba(255, 255, 255, 0.3);
      border: none;
      border-radius: 15px;
      padding: 10px 20px;
      color: white;
      font-weight: bold;
      cursor: pointer;
      font-size: 16px;
      transition: all 0.3s ease;
    }
    .levelUpButton:hover {
      background: rgba(255, 255, 255, 0.4);
      transform: translateY(-2px);
    }
    
    /* Стили для фейерверка */
    .firework {
      position: fixed;
      top: 50%;
      left: 50%;
      transform: translate(-50%, -50%);
      width: 5px;
      height: 5px;
      border-radius: 50%;
      box-shadow: 0 0 #ff66cc, 0 0 #ff9a9e, 0 0 #fad0c4;
      animation: firework 1s ease-out forwards;
      z-index: 999;
    }
    @keyframes firework {
      0% {
        box-shadow: 
          0 0 #ff66cc, 0 0 #ff9a9e, 0 0 #fad0c4,
          0 0 #ff66cc, 0 0 #ff9a9e, 0 0 #fad0c4,
          0 0 #ff66cc, 0 0 #ff9a9e, 0 0 #fad0c4;
      }
      100% {
        box-shadow: 
          0 0 60px 10px #ff66cc, 40px 40px 60px 10px #ff9a9e, -40px 40px 60px 10px #fad0c4,
          40px -40px 60px 10px #ff66cc, -40px -40px 60px 10px #ff9a9e, 60px 0 60px 10px #fad0c4,
          -60px 0 60px 10px #ff66cc, 0 60px 60px 10px #ff9a9e, 0 -60px 60px 10px #fad0c4;
      }
    }
    
    /* Стили для заданий */
    .task-tabs {
      display: flex;
      margin-bottom: 20px;
      border-bottom: 1px solid rgba(255, 255, 255, 0.2);
    }
    .task-tab {
      flex: 1;
      padding: 10px;
      text-align: center;
      cursor: pointer;
      font-weight: bold;
      transition: all 0.3s ease;
    }
    .task-tab.active {
      color: #ff66cc;
      border-bottom: 2px solid #ff66cc;
    }
    .task-content {
      display: none;
    }
    .task-content.active {
      display: block;
    }
    .task-item {
      background: rgba(0, 0, 0, 0.2);
      border-radius: 15px;
      padding: 15px;
      margin-bottom: 15px;
      text-align: left;
      display: flex;
      flex-direction: column;
    }
    .task-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 10px;
    }
    .task-title {
      font-size: 18px;
      font-weight: bold;
    }
    .task-button {
      background: linear-gradient(90deg, #ff66cc, #ff9a9e);
      border: none;
      border-radius: 10px;
      padding: 8px 15px;
      color: white;
      font-weight: bold;
      cursor: pointer;
      font-size: 14px;
      transition: all 0.3s ease;
      white-space: nowrap;
    }
    .task-button:hover {
      transform: translateY(-2px);
      box-shadow: 0 5px 15px rgba(255, 102, 204, 0.4);
    }
    .task-button:disabled {
      background: rgba(255, 255, 255, 0.2);
      cursor: not-allowed;
      transform: none;
    }
    .task-reward {
      display: flex;
      align-items: center;
      margin-bottom: 5px;
    }
    .task-reward img {
      width: 20px;
      height: 20px;
      margin-right: 5px;
    }
    .task-progress {
      font-size: 14px;
      opacity: 0.8;
    }
    .task-completed {
      color: #4ade80;
      font-weight: bold;
      margin-top: 5px;
    }
    .task-timer {
      font-size: 14px;
      opacity: 0.8;
      margin-top: 5px;
    }
    
    /* Стили для индикатора загрузки рекламы */
    .ads-loading {
      display: inline-block;
      width: 20px;
      height: 20px;
      border: 2px solid rgba(255, 255, 255, 0.3);
      border-radius: 50%;
      border-top-color: #fff;
      animation: spin 1s ease-in-out infinite;
      margin-right: 10px;
      vertical-align: middle;
    }

    @keyframes spin {
      to { transform: rotate(360deg); }
    }
    
    /* Стили для кошелька */
    #wallet-section {
      background: rgba(0, 0, 0, 0.2);
      border-radius: 15px;
      padding: 15px;
      margin-top: 20px;
      width: 100%;
      box-sizing: border-box;
    }
    #wallet-address {
      font-family: monospace;
      background: rgba(0, 0, 0, 0.3);
      padding: 8px 12px;
      border-radius: 8px;
      margin-top: 10px;
      word-break: break-all;
    }
    #ton-connect-button {
      background: linear-gradient(90deg, #0088cc, #00a2ff);
      border: none;
      border-radius: 10px;
      padding: 10px 15px;
      color: white;
      font-weight: bold;
      cursor: pointer;
      font-size: 16px;
      transition: all 0.3s ease;
      width: 100%;
      margin-top: 10px;
    }
    #ton-connect-button:hover {
      transform: translateY(-2px);
      box-shadow: 0 5px 15px rgba(0, 136, 204, 0.4);
    }
    
    /* Стили для модальных окон заданий */
    .task-modal-overlay {
      position: fixed;
      top: 0;
      left: 0;
      width: 100%;
      height: 100%;
      background: rgba(0, 0, 0, 0.5);
      z-index: 999;
      display: none;
    }
    .task-modal-overlay.active {
      display: block;
    }
    .task-modal {
      position: fixed;
      bottom: 0;
      left: 0;
      width: 100%;
      background: rgba(0, 0, 0, 0.9);
      backdrop-filter: blur(10px);
      border-top-left-radius: 20px;
      border-top-right-radius: 20px;
      padding: 20px;
      box-sizing: border-box;
      z-index: 1000;
      transform: translateY(100%);
      transition: transform 0.3s ease;
    }
    .task-modal.active {
      transform: translateY(0);
    }
    .task-modal-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 15px;
    }
    .task-modal-title {
      font-size: 20px;
      font-weight: bold;
    }
    .task-modal-close {
      background: transparent;
      border: none;
      color: white;
      font-size: 24px;
      cursor: pointer;
      width: 30px;
      height: 30px;
      display: flex;
      align-items: center;
      justify-content: center;
      border-radius: 50%;
      transition: background-color 0.3s;
    }
    .task-modal-close:hover {
      background-color: rgba(255, 255, 255, 0.2);
    }
    .task-modal-content {
      margin-bottom: 20px;
    }
    .task-modal-description {
      margin-bottom: 15px;
      line-height: 1.5;
    }
    .task-modal-button {
      background: linear-gradient(90deg, #ff66cc, #ff9a9e);
      border: none;
      border-radius: 10px;
      padding: 12px 20px;
      color: white;
      font-weight: bold;
      cursor: pointer;
      font-size: 16px;
      transition: all 0.3s ease;
      width: 100%;
      margin-bottom: 10px;
    }
    .task-modal-button:hover {
      transform: translateY(-2px);
      box-shadow: 0 5px 15px rgba(255, 102, 204, 0.4);
    }
    .task-modal-button-secondary {
      background: rgba(255, 255, 255, 0.2);
      border: none;
      border-radius: 10px;
      padding: 12px 20px;
      color: white;
      font-weight: bold;
      cursor: pointer;
      font-size: 16px;
      transition: all 0.3s ease;
      width: 100%;
    }
    .task-modal-button-secondary:hover {
      background: rgba(255, 255, 255, 0.3);
      transform: translateY(-2px);
    }
    .referral-link {
      background: rgba(255, 255, 255, 0.1);
      border-radius: 8px;
      padding: 10px;
      margin-bottom: 15px;
      word-break: break-all;
      font-family: monospace;
      font-size: 14px;
    }
    
    /* Стили для уведомлений */
    .notification {
      position: fixed;
      top: 70px;
      left: 50%;
      transform: translateX(-50%);
      background: rgba(0, 0, 0, 0.8);
      color: white;
      padding: 12px 20px;
      border-radius: 10px;
      z-index: 1000;
      opacity: 0;
      transition: opacity 0.3s ease;
      max-width: 80%;
      text-align: center;
    }
    .notification.show {
      opacity: 1;
    }
    
    /* Стили для недостатка энергии */
    .no-energy {
      position: fixed;
      top: 50%;
      left: 50%;
      transform: translate(-50%, -50%);
      background: rgba(0, 0, 0, 0.8);
      color: white;
      padding: 15px 25px;
      border-radius: 15px;
      font-size: 18px;
      font-weight: bold;
      z-index: 1001;
      opacity: 0;
      transition: opacity 0.3s ease;
    }
    .no-energy.show {
      opacity: 1;
    }
    
    /* Стили для улучшений */
    #upgrades-button {
      position: fixed;
      bottom: 70px;
      left: 0;
      width: 100%;
      height: 80px;
      background: linear-gradient(135deg, rgba(255, 102, 204, 0.8), rgba(255, 154, 158, 0.8));
      border: none;
      color: white;
      font-weight: bold;
      font-size: 18px;
      cursor: pointer;
      z-index: 90;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      box-shadow: 0 -2px 10px rgba(255, 102, 204, 0.5);
      transition: all 0.3s ease;
    }
    #upgrades-button:hover {
      background: linear-gradient(135deg, rgba(255, 102, 204, 0.9), rgba(255, 154, 158, 0.9));
    }
    #upgrades-button:active {
      transform: translateY(2px);
    }
    #upgrades-button span {
      font-size: 14px;
      opacity: 0.8;
      margin-top: 5px;
    }
    
    /* Модальное окно улучшений */
    #upgrades-modal-overlay {
      position: fixed;
      top: 0;
      left: 0;
      width: 100%;
      height: 100%;
      background: rgba(0, 0, 0, 0.7);
      z-index: 1001;
      display: none;
    }
    #upgrades-modal-overlay.active {
      display: block;
    }
    #upgrades-modal {
      position: fixed;
      bottom: 0;
      left: 0;
      width: 100%;
      max-height: 80vh;
      background: rgba(0, 0, 0, 0.9);
      backdrop-filter: blur(10px);
      border-top-left-radius: 20px;
      border-top-right-radius: 20px;
      padding: 20px;
      box-sizing: border-box;
      z-index: 1002;
      transform: translateY(100%);
      transition: transform 0.3s ease;
      overflow-y: auto;
    }
    #upgrades-modal.active {
      transform: translateY(0);
    }
    .upgrades-modal-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 15px;
    }
    .upgrades-modal-title {
      font-size: 22px;
      font-weight: bold;
    }
    .upgrades-modal-close {
      background: transparent;
      border: none;
      color: white;
      font-size: 24px;
      cursor: pointer;
      width: 30px;
      height: 30px;
      display: flex;
      align-items: center;
      justify-content: center;
      border-radius: 50%;
      transition: background-color 0.3s;
    }
    .upgrades-modal-close:hover {
      background-color: rgba(255, 255, 255, 0.2);
    }
    .upgrades-container {
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 15px;
      margin-bottom: 20px;
    }
    .upgrade-item {
      background: rgba(255, 255, 255, 0.1);
      border-radius: 15px;
      padding: 15px;
      text-align: center;
      transition: all 0.3s ease;
      cursor: pointer;
      position: relative;
      overflow: hidden;
    }
    .upgrade-item:hover {
      background: rgba(255, 255, 255, 0.2);
      transform: translateY(-5px);
    }
    .upgrade-item.purchased {
      background: rgba(76, 175, 80, 0.3);
      border: 1px solid #4ade80;
    }
    .upgrade-item.purchased::after {
      content: '✓';
      position: absolute;
      top: 5px;
      right: 5px;
      background: #4ade80;
      color: white;
      width: 20px;
      height: 20px;
      border-radius: 50%;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 14px;
    }
    .upgrade-image {
      width: 60px;
      height: 60px;
      margin: 0 auto 10px;
      border-radius: 50%;
      object-fit: cover;
      background-color: rgba(255, 255, 255, 0.2);
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 24px;
    }
    .upgrade-description {
      font-size: 12px;
      opacity: 0.8;
      margin-bottom: 10px;
    }
    .upgrade-cost {
      font-size: 14px;
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 5px;
    }
    .upgrade-cost img {
      width: 16px;
      height: 16px;
    }
    .upgrade-buy-button {
      background: linear-gradient(90deg, #ff66cc, #ff9a9e);
      border: none;
      border-radius: 8px;
      padding: 6px 12px;
      color: white;
      font-weight: bold;
      cursor: pointer;
      font-size: 12px;
      transition: all 0.3s ease;
      width: 100%;
      margin-top: 8px;
    }
    .upgrade-buy-button:hover {
      transform: translateY(-2px);
      box-shadow: 0 3px 10px rgba(255, 102, 204, 0.4);
    }
    .upgrade-buy-button:disabled {
      background: rgba(255, 255, 255, 0.2);
      cursor: not-allowed;
      transform: none;
    }
    
    /* Стили для достижений */
    #achievements-list {
      display: grid;
      grid-template-columns: repeat(2, 1fr);
      gap: 15px;
      margin-top: 20px;
    }
    .achievement-item {
      background: rgba(0, 0, 0, 0.2);
      border-radius: 15px;
      padding: 15px;
      text-align: center;
      transition: all 0.3s ease;
    }
    .achievement-item:hover {
      transform: translateY(-5px);
      box-shadow: 0 5px 15px rgba(255, 102, 204, 0.4);
    }
    .achievement-item.unlocked {
      background: rgba(76, 175, 80, 0.3);
      border: 1px solid #4ade80;
    }
    .achievement-icon {
      font-size: 30px;
      margin-bottom: 10px;
    }
    .achievement-name {
      font-size: 16px;
      font-weight: bold;
      margin-bottom: 5px;
    }
    .achievement-description {
      font-size: 12px;
      opacity: 0.8;
      margin-bottom: 10px;
    }
    .achievement-reward {
      font-size: 14px;
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 5px;
    }
    .achievement-reward img {
      width: 16px;
      height: 16px;
    }
    .achievement-progress {
      font-size: 12px;
      margin-top: 5px;
    }
    
    /* Стили для друзей */
    #friends-list {
      margin-top: 20px;
      max-height: 60vh;
      overflow-y: auto;
    }
    .friend-item {
      display: flex;
      align-items: center;
      margin-bottom: 12px;
      background: rgba(0, 0, 0, 0.2);
      border-radius: 12px;
      padding: 10px;
      transition: transform 0.2s ease;
    }
    .friend-item:hover {
      transform: translateX(5px);
    }
    .friend-avatar {
      width: 40px;
      height: 40px;
      border-radius: 50%;
      margin-right: 10px;
      object-fit: cover;
    }
    .friend-info {
      flex-grow: 1;
      text-align: left;
    }
    .friend-name {
      font-weight: bold;
      font-size: 16px;
    }
    .friend-score {
      font-size: 14px;
      opacity: 0.8;
      display: flex;
      align-items: center;
      gap: 5px;
    }
    .friend-actions {
      display: flex;
      flex-direction: column;
      gap: 5px;
    }
    .friend-button {
      background: linear-gradient(90deg, #ff66cc, #ff9a9e);
      border: none;
      border-radius: 8px;
      padding: 5px 10px;
      color: white;
      font-weight: bold;
      cursor: pointer;
      font-size: 12px;
      transition: all 0.3s ease;
    }
    .friend-button:hover {
      transform: translateY(-2px);
      box-shadow: 0 3px 10px rgba(255, 102, 204, 0.4);
    }
    #add-friend-button {
      background: linear-gradient(90deg, #ff66cc, #ff9a9e);
      border: none;
      border-radius: 10px;
      padding: 10px 15px;
      color: white;
      font-weight: bold;
      cursor: pointer;
      font-size: 16px;
      transition: all 0.3s ease;
      margin-top: 20px;
      width: 100%;
    }
    #add-friend-button:hover {
      transform: translateY(-2px);
      box-shadow: 0 5px 15px rgba(255, 102, 204, 0.4);
    }
    
    /* Стили для мини-игр */
    .minigames-container {
      display: grid;
      grid-template-columns: repeat(2, 1fr);
      gap: 15px;
      margin-top: 20px;
    }
    .minigame-item {
      background: rgba(0, 0, 0, 0.2);
      border-radius: 15px;
      padding: 15px;
      text-align: center;
      transition: all 0.3s ease;
    }
    .minigame-item:hover {
      transform: translateY(-5px);
      box-shadow: 0 5px 15px rgba(255, 102, 204, 0.4);
    }
    .minigame-icon {
      font-size: 30px;
      margin-bottom: 10px;
    }
    .minigame-name {
      font-size: 16px;
      font-weight: bold;
      margin-bottom: 5px;
    }
    .minigame-description {
      font-size: 12px;
      opacity: 0.8;
      margin-bottom: 10px;
    }
    .minigame-reward {
      font-size: 14px;
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 5px;
      margin-bottom: 10px;
    }
    .minigame-reward img {
      width: 16px;
      height: 16px;
    }
    .start-minigame-button {
      background: linear-gradient(90deg, #ff66cc, #ff9a9e);
      border: none;
      border-radius: 8px;
      padding: 8px 12px;
      color: white;
      font-weight: bold;
      cursor: pointer;
      font-size: 14px;
      transition: all 0.3s ease;
      width: 100%;
    }
    .start-minigame-button:hover {
      transform: translateY(-2px);
      box-shadow: 0 3px 10px rgba(255, 102, 204, 0.4);
    }
    
    /* Стили для мини-игры "Поймай монетки" */
    #minigame-catch-coins {
      position: fixed;
      top: 0;
      left: 0;
      width: 100%;
      height: 100%;
      background: rgba(0, 0, 0, 0.9);
      z-index: 2000;
      display: none;
      flex-direction: column;
      align-items: center;
      justify-content: center;
    }
    #minigame-catch-coins.active {
      display: flex;
    }
    .minigame-header {
      position: absolute;
      top: 20px;
      left: 0;
      width: 100%;
      display: flex;
      justify-content: space-between;
      padding: 0 20px;
      box-sizing: border-box;
    }
    .minigame-score {
      font-size: 20px;
      font-weight: bold;
    }
    .minigame-timer {
      font-size: 20px;
      font-weight: bold;
    }
    .minigame-close {
      background: rgba(255, 255, 255, 0.2);
      border: none;
      border-radius: 50%;
      width: 40px;
      height: 40px;
      color: white;
      font-size: 20px;
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
    }
    .minigame-close:hover {
      background: rgba(255, 255, 255, 0.3);
    }
    .minigame-area {
      position: relative;
      width: 90%;
      height: 70%;
      max-width: 400px;
      border: 2px solid #ff66cc;
      border-radius: 15px;
      overflow: hidden;
    }
    .coin {
      position: absolute;
      width: 30px;
      height: 30px;
      background: url('/static/FemboyCoinsPink.png') no-repeat center center;
      background-size: contain;
      cursor: pointer;
      z-index: 10;
    }
    .minigame-result {
      position: absolute;
      top: 50%;
      left: 50%;
      transform: translate(-50%, -50%);
      background: rgba(0, 0, 0, 0.8);
      border-radius: 15px;
      padding: 20px;
      text-align: center;
      z-index: 100;
      display: none;
    }
    .minigame-result.active {
      display: block;
    }
    .minigame-result-title {
      font-size: 24px;
      font-weight: bold;
      margin-bottom: 10px;
    }
    .minigame-result-score {
      font-size: 20px;
      margin-bottom: 15px;
    }
    .minigame-result-button {
      background: linear-gradient(90deg, #ff66cc, #ff9a9e);
      border: none;
      border-radius: 10px;
      padding: 10px 20px;
      color: white;
      font-weight: bold;
      cursor: pointer;
      font-size: 16px;
      transition: all 0.3s ease;
    }
    .minigame-result-button:hover {
      transform: translateY(-2px);
      box-shadow: 0 5px 15px rgba(255, 102, 204, 0.4);
    }
    
    /* Стили для ежедневных бонусов */
    #daily-bonus-calendar {
      display: grid;
      grid-template-columns: repeat(7, 1fr);
      gap: 10px;
      margin: 20px 0;
    }
    .bonus-day {
      background: rgba(0, 0, 0, 0.2);
      border-radius: 10px;
      padding: 15px 10px;
      text-align: center;
      transition: all 0.3s ease;
    }
    .bonus-day:hover {
      transform: translateY(-5px);
      box-shadow: 0 5px 15px rgba(255, 102, 204, 0.4);
    }
    .bonus-day.current {
      background: rgba(255, 102, 204, 0.3);
      border: 1px solid #ff66cc;
    }
    .bonus-day.claimed {
      background: rgba(76, 175, 80, 0.3);
      border: 1px solid #4ade80;
    }
    .bonus-day-number {
      font-size: 16px;
      font-weight: bold;
      margin-bottom: 5px;
    }
    .bonus-day-reward {
      font-size: 14px;
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 5px;
    }
    .bonus-day-reward img {
      width: 16px;
      height: 16px;
    }
    #claim-daily-bonus-button {
      background: linear-gradient(90deg, #ff66cc, #ff9a9e);
      border: none;
      border-radius: 10px;
      padding: 12px 20px;
      color: white;
      font-weight: bold;
      cursor: pointer;
      font-size: 16px;
      transition: all 0.3s ease;
      width: 100%;
      margin-top: 20px;
    }
    #claim-daily-bonus-button:hover {
      transform: translateY(-2px);
      box-shadow: 0 5px 15px rgba(255, 102, 204, 0.4);
    }
    #claim-daily-bonus-button:disabled {
      background: rgba(255, 255, 255, 0.2);
      cursor: not-allowed;
      transform: none;
    }
    .daily-bonus-streak {
      font-size: 18px;
      margin: 15px 0;
      font-weight: bold;
    }
    
    /* Стили для переключателя языка */
    #language-switcher {
      position: fixed;
      top: 70px;
      right: 10px;
      background: rgba(0, 0, 0, 0.7);
      border-radius: 10px;
      padding: 5px;
      z-index: 95;
    }
    #language-switcher button {
      background: transparent;
      border: none;
      color: white;
      font-size: 14px;
      font-weight: bold;
      cursor: pointer;
      padding: 5px 10px;
      border-radius: 8px;
      transition: background-color 0.3s;
    }
    #language-switcher button.active {
      background: rgba(255, 102, 204, 0.5);
    }
    #language-switcher button:hover {
      background: rgba(255, 102, 204, 0.3);
    }
    
    /* Стили для аналитики (скрыто от пользователей) */
    .analytics-indicator {
      position: fixed;
      bottom: 70px;
      right: 10px;
      width: 10px;
      height: 10px;
      background: #4ade80;
      border-radius: 50%;
      z-index: 95;
      opacity: 0.5;
    }
  </style>
</head>
<body>
  <!-- Розовая полоска сверху -->
  <div class="telegram-header"></div>

  <div id="content">
    <!-- Кликер (по умолчанию видим) -->
    <section id="clicker" class="page active" aria-label="Окно кликера">
      <button id="topButton">
        Топ 100 фембоев
        <div class="top-preview" id="topPreview">
          <div class="top-preview-item">Загрузка...</div>
        </div>
      </button>
      
      <div id="circle" tabindex="0" role="button" aria-pressed="false">
        <img id="femboyImg" src="/static/Photo_femb_static.jpg" alt="фембой" />
      </div>
      <div id="score" aria-live="polite">
        Счет: 0
        <img id="coin" src="/static/FemboyCoinsPink.png" alt="монетки" />
      </div>
      
      <!-- Прогресс-бар уровня -->
      <div id="levelProgress">
        <div id="levelProgressBar" style="width: 0%"></div>
        <div id="levelProgressText">Уровень: Новичок (0/100)</div>
      </div>
      
      <!-- Прогресс-бар энергии -->
      <div id="energyContainer">
        <div id="energyBar">
          <div id="energyProgress" style="width: 100%"></div>
        </div>
        <div id="energyText">
          <span id="energyIcon">⚡</span>
          <span>Энергия: 250/250</span>
        </div>
      </div>
    </section>

    <!-- Окно профиля -->
    <section id="profile" class="page" aria-label="Профиль">
      <h2>Профиль</h2>
      
      <div id="loadingIndicator">
        <p>Загрузка данных профиля...</p>
      </div>
      
      <div id="userProfile" style="display: none;">
        <img id="userAvatar" src="" alt="Аватар пользователя">
        <h3 id="userName"></h3>
        <p id="userHandle"></p>
      </div>
      
      <div class="profile-stats">
        <p>Собранные монетки: <span id="profileScore">0</span></p>
        <p>Уровень фембоя: <span id="userLevel">Новичок</span></p>
        <p>Всего кликов: <span id="totalClicks">0</span></p>
        <p>Бонус за клик: <span id="clickBonus">0</span></p>
        <p>Пассивный доход: <span id="passiveIncomeStat">0</span>/5 сек</p>
        <p>Друзей: <span id="friendsCount">0</span></p>
        <p>Достижений: <span id="achievementsCount">0</span>/<span id="totalAchievements">0</span></p>
      </div>
      
      <!-- Секция кошелька -->
      <div id="wallet-section">
        <h3>TON Кошелек</h3>
        <div id="wallet-address">Не подключен</div>
        <button id="ton-connect-button">Подключить кошелек</button>
      </div>
    </section>

    <!-- Окно заданий -->
    <section id="tasks" class="page" aria-label="задания">
      <h2>Задания</h2>
      
      <!-- Вкладки заданий -->
      <div class="task-tabs">
        <div class="task-tab active" data-tab="normal">Обычные</div>
        <div class="task-tab" data-tab="daily">Повседневные</div>
      </div>
      
      <!-- Содержимое вкладки "Обычные" -->
      <div class="task-content active" id="normal-tasks">
        <!-- Задание: Подключить TON кошелек -->
        <div class="task-item">
          <div class="task-header">
            <div class="task-title">Подключить TON кошелек</div>
            <button id="wallet-task-button" class="task-button">НАЧАТЬ</button>
          </div>
          <div class="task-reward">
            <img src="/static/FemboyCoinsPink.png" alt="монетки">
            <span>1000 монеток</span>
          </div>
          <div id="wallet-task-status" class="task-completed" style="display: none;">Задание выполнено</div>
        </div>
        
        <!-- Задание: Подписка на канал -->
        <div class="task-item">
          <div class="task-header">
            <div class="task-title">Подписка на канал</div>
            <button id="channel-task-button" class="task-button">НАЧАТЬ</button>
          </div>
          <div class="task-reward">
            <img src="/static/FemboyCoinsPink.png" alt="монетки">
            <span>2000 монеток</span>
          </div>
          <div id="channel-task-status" class="task-completed" style="display: none;">Задание выполнено</div>
        </div>
      </div>
      
      <!-- Содержимое вкладки "Повседневные" -->
      <div class="task-content" id="daily-tasks">
        <!-- Задание: Пригласить 3 друзей -->
        <div class="task-item">
          <div class="task-header">
            <div class="task-title">Пригласить 3-х друзей</div>
            <button id="referral-task-button" class="task-button">НАЧАТЬ</button>
          </div>
          <div class="task-reward">
            <img src="/static/FemboyCoinsPink.png" alt="монетки">
            <span>5000 монеток</span>
          </div>
          <div class="task-progress">Приглашено друзей: <span id="referral-count-value">0</span>/3</div>
          <div id="referral-task-status" class="task-completed" style="display: none;">Задание выполнено</div>
          <div id="referral-task-timer" class="task-timer" style="display: none;"></div>
        </div>
        
        <!-- Задание: Просмотр рекламы -->
        <div class="task-item">
          <div class="task-header">
            <div class="task-title">Просмотр рекламы</div>
            <button id="ads-task-button" class="task-button">НАЧАТЬ</button>
          </div>
          <div class="task-reward">
            <img src="/static/FemboyCoinsPink.png" alt="монетки">
            <span>5000 монеток</span>
          </div>
          <div class="task-progress">Просмотрено: <span id="ads-count-value">0</span>/10</div>
          <div id="ads-task-status" class="task-completed" style="display: none;">Задание выполнено</div>
        </div>
      </div>
    </section>
    
    <!-- Окно достижений -->
    <section id="achievements" class="page" aria-label="Достижения">
      <h2>Достижения</h2>
      <div id="achievements-list"></div>
    </section>
    
    <!-- Окно друзей -->
    <section id="friends" class="page" aria-label="Друзья">
      <h2>Друзья</h2>
      <div id="friends-list"></div>
      <button id="add-friend-button">Добавить друга</button>
    </section>
    
    <!-- Окно мини-игр -->
    <section id="minigames" class="page" aria-label="Мини-игры">
      <h2>Мини-игры</h2>
      <div class="minigames-container">
        <div class="minigame-item" data-minigame="catch_coins">
          <div class="minigame-icon">🪙</div>
          <div class="minigame-name">Поймай монетки</div>
          <div class="minigame-description">Ловите падающие монетки!</div>
          <div class="minigame-reward">
            <img src="/static/FemboyCoinsPink.png" alt="монетки">
            <span>100 монеток</span>
          </div>
          <button class="start-minigame-button">Играть</button>
        </div>
      </div>
    </section>
    
    <!-- Окно ежедневных бонусов -->
    <section id="daily" class="page" aria-label="Ежедневные бонусы">
      <h2>Ежедневные бонусы</h2>
      <div class="daily-bonus-streak">Текущая серия: <span id="current-streak">0</span> дней</div>
      <div id="daily-bonus-calendar"></div>
      <button id="claim-daily-bonus-button">Получить бонус</button>
    </section>
    
    <!-- Окно топа -->
    <section id="top" class="page" aria-label="Топ пользователей">
      <div id="topHeader">
        <button id="backButton">← Назад</button>
        <h2>Топ 100 фембоев</h2>
        <div></div> <!-- Для выравнивания -->
      </div>
      <div id="topList"></div>
    </section>
  </div>

  <!-- Отображение пассивного дохода (фиксированное вверху справа) -->
  <div id="passive-income-display">
    <span id="passive-income-icon">⏱</span>
    <span id="passive-income-value">0</span>/5 сек
  </div>

  <!-- Переключатель языка -->
  <div id="language-switcher">
    <button id="lang-ru" class="active">RU</button>
    <button id="lang-en">EN</button>
  </div>

  <!-- Индикатор аналитики -->
  <div class="analytics-indicator"></div>

  <!-- Модальное окно повышения уровня -->
  <div id="levelUpModal">
    <div class="levelUpContent">
      <div class="levelUpTitle">🎉 Новый уровень! 🎉</div>
      <div class="levelUpLevel" id="levelUpLevelText">Новичок</div>
      <button class="levelUpButton" id="levelUpButton">Отлично!</button>
    </div>
  </div>

  <!-- Затемнение фона для модальных окон -->
  <div id="task-modal-overlay" class="task-modal-overlay"></div>

  <!-- Модальное окно задания с кошельком -->
  <div id="wallet-task-modal" class="task-modal">
    <div class="task-modal-header">
      <div class="task-modal-title">Подключить TON кошелек</div>
      <button class="task-modal-close" id="wallet-modal-close">×</button>
    </div>
    <div class="task-modal-content">
      <div class="task-modal-description">
        Подключите свой TON кошелек через TonConnect, чтобы получить 1000 монеток. 
        Ваш кошелек будет привязан к вашему профилю и отображен в разделе "Профиль".
      </div>
    </div>
    <button id="wallet-modal-button" class="task-modal-button">Подключить кошелек</button>
  </div>

  <!-- Модальное окно задания с подпиской на канал -->
  <div id="channel-task-modal" class="task-modal">
    <div class="task-modal-header">
      <div class="task-modal-title">Подписка на канал</div>
      <button class="task-modal-close" id="channel-modal-close">×</button>
    </div>
    <div class="task-modal-content">
      <div class="task-modal-description">
        Подпишитесь на наш канал в Telegram, чтобы получить 2000 монеток. 
        После подписки вернитесь в приложение и нажмите "Проверить подписку".
      </div>
    </div>
    <button id="channel-modal-button" class="task-modal-button">Перейти к каналу</button>
    <button id="channel-verify-button" class="task-modal-button-secondary">Проверить подписку</button>
  </div>

  <!-- Модальное окно задания с рефералами -->
  <div id="referral-task-modal" class="task-modal">
    <div class="task-modal-header">
      <div class="task-modal-title">Пригласить 3-х друзей</div>
      <button class="task-modal-close" id="referral-modal-close">×</button>
    </div>
    <div class="task-modal-content">
      <div class="task-modal-description">
        Отправьте эту ссылку 3 друзьям, чтобы получить 5000 монеток. 
        Задание можно выполнять раз в 24 часа.
      </div>
      <div class="referral-link" id="referral-link">https://t.me/Fnmby_bot?startapp=123456</div>
    </div>
    <button id="referral-modal-button" class="task-modal-button">Скопировать ссылку</button>
    <button id="referral-share-button" class="task-modal-button-secondary">Переслать друзьям</button>
  </div>

  <!-- Кнопка улучшений -->
  <button id="upgrades-button">
    УЛУЧШЕНИЯ
  </button>

  <!-- Модальное окно улучшений -->
  <div id="upgrades-modal-overlay"></div>
  <div id="upgrades-modal">
    <div class="upgrades-modal-header">
      <div class="upgrades-modal-title">УЛУЧШЕНИЯ</div>
      <button class="upgrades-modal-close" id="upgrades-modal-close">×</button>
    </div>
    <div class="upgrades-container" id="upgrades-container">
      <!-- Улучшения будут добавлены через JavaScript -->
    </div>
  </div>

  <!-- Мини-игра "Поймай монетки" -->
  <div id="minigame-catch-coins">
    <div class="minigame-header">
      <div class="minigame-score">Счет: <span id="minigame-score">0</span></div>
      <div class="minigame-timer">Время: <span id="minigame-timer">30</span></div>
      <button class="minigame-close" id="minigame-close">×</button>
    </div>
    <div class="minigame-area" id="minigame-area"></div>
    <div class="minigame-result" id="minigame-result">
      <div class="minigame-result-title">Игра окончена!</div>
      <div class="minigame-result-score">Вы поймали <span id="minigame-result-score">0</span> монеток</div>
      <button class="minigame-result-button" id="minigame-result-button">Забрать награду</button>
    </div>
  </div>

  <!-- Уведомления -->
  <div id="notification" class="notification"></div>
  
  <!-- Уведомление о недостатке энергии -->
  <div id="noEnergyNotification" class="no-energy">Недостаточно энергии!</div>

  <nav id="bottom-menu" role="navigation" aria-label="Нижнее меню">
    <button id="btn-profile" data-page="profile">Профиль</button>
    <button id="btn-clicker" data-page="clicker" class="active">Кликер</button>
    <button id="btn-tasks" data-page="tasks">Задания</button>
    <button id="btn-achievements" data-page="achievements">Достижения</button>
    <button id="btn-friends" data-page="friends">Друзья</button>
    <button id="btn-minigames" data-page="minigames">Мини-игры</button>
    <button id="btn-daily" data-page="daily">Бонусы</button>
  </nav>

  <script>
    // Уровни игры
    const LEVELS = [
      {score: 0, name: "Новичок"},
      {score: 100, name: "Любитель"},
      {score: 500, name: "Профи"},
      {score: 2000, name: "Мастер"},
      {score: 5000, name: "Эксперт по Фембоям"},
      {score: 10000, name: "Фембой"},
      {score: 50000, name: "Фурри-Фембой"},
      {score: 200000, name: "Феликс"},
      {score: 500000, name: "Астольфо"},
      {score: 1000000, name: "Владелец фембоев"},
      {score: 5000000, name: "Император фембоев"},
      {score: 10000000, name: "Бог фембоев"}
    ];
    
    // Улучшения игры
    const UPGRADES = [
      {id: "upgrade1", description: "+1 за клик", cost: 1000, effect: {clickBonus: 1}, image: "/static/upgrade1.png"},
      {id: "upgrade2", description: "+2 за клик", cost: 5000, effect: {clickBonus: 2}, image: "/static/upgrade2.png"},
      {id: "upgrade3", description: "+5 за клик", cost: 10000, effect: {clickBonus: 5}, image: "/static/upgrade3.png"},
      {id: "upgrade4", description: "+1 каждые 5 сек", cost: 15000, effect: {passiveIncome: 1}, image: "/static/upgrade4.png"},
      {id: "upgrade5", description: "+5 каждые 5 сек", cost: 30000, effect: {passiveIncome: 5}, image: "/static/upgrade5.png"},
      {id: "upgrade6", description: "+10 каждые 5 сек", cost: 50000, effect: {passiveIncome: 10}, image: "/static/upgrade6.png"},
      {id: "upgrade7", description: "+10 за клик", cost: 75000, effect: {clickBonus: 10}, image: "/static/upgrade7.png"},
      {id: "upgrade8", description: "+15 за клик", cost: 100000, effect: {clickBonus: 15}, image: "/static/upgrade8.png"},
      {id: "upgrade9", description: "+25 каждые 5 сек", cost: 150000, effect: {passiveIncome: 25}, image: "/static/upgrade9.png"},
      {id: "upgrade10", description: "+25 за клик", cost: 250000, effect: {clickBonus: 25}, image: "/static/upgrade10.png"},
      {id: "upgrade11", description: "+50 каждые 5 сек", cost: 500000, effect: {passiveIncome: 50}, image: "/static/upgrade11.png"},
      {id: "upgrade12", description: "+100 за клик", cost: 1000000, effect: {clickBonus: 100}, image: "/static/upgrade12.png"},
      // Новые улучшения
      {id: "boost_2x", description: "x2 очки на 10 минут", cost: 5000, effect: {type: "temporary_boost", multiplier: 2, duration: 600}, image: "/static/boost_2x.png"},
      {id: "energy_max", description: "+50 к макс. энергии", cost: 10000, effect: {type: "max_energy", value: 50}, image: "/static/energy_max.png"},
      {id: "skin_gold", description: "Золотой скин", cost: 20000, effect: {type: "visual", skin: "gold"}, image: "/static/skin_gold.png"},
      {id: "auto_clicker", description: "Автокликер (1 клик/сек)", cost: 50000, effect: {type: "auto_clicker", value: 1}, image: "/static/auto_clicker.png"}
    ];
    
    // Задания игры
    const NORMAL_TASKS = [
      {id: "wallet_task", title: "Подключить TON кошелек", reward: 1000, type: "normal"},
      {id: "channel_subscription", title: "Подписка на канал", reward: 2000, type: "normal"}
    ];
    
    const DAILY_TASKS = [
      {id: "referral_task", title: "Пригласить 3-х друзей", reward: 5000, type: "daily"},
      {id: "ads_task", title: "Просмотр рекламы", reward: 5000, type: "daily", no_reset: true}
    ];
    
    // Достижения игры
    const ACHIEVEMENTS = [
      {id: "first_click", name: "Первый клик", description: "Сделайте свой первый клик", reward: 100, condition: {type: "clicks", value: 1}},
      {id: "click_master", name: "Мастер кликов", description: "Сделайте 1000 кликов", reward: 5000, condition: {type: "clicks", value: 1000}},
      {id: "score_1000", name: "Тысячник", description: "Наберите 1000 очков", reward: 1000, condition: {type: "score", value: 1000}},
      {id: "first_friend", name: "Первый друг", description: "Пригласите первого друга", reward: 2000, condition: {type: "referrals", value: 1}},
      {id: "daily_login", name: "Ежедневный вход", description: "Входите в игру 7 дней подряд", reward: 3000, condition: {type: "daily_streak", value: 7}}
    ];
    
    // Мини-игры
    const MINIGAMES = [
      {id: "catch_coins", name: "Поймай монетки", description: "Ловите падающие монетки!", reward: 100, duration: 30}
    ];
    
    // Ежедневные бонусы
    const DAILY_BONUSES = [
      {day: 1, reward: 100},
      {day: 2, reward: 200},
      {day: 3, reward: 300},
      {day: 4, reward: 400},
      {day: 5, reward: 500},
      {day: 6, reward: 600},
      {day: 7, reward: 1000}
    ];
    
    // Переводы для мультиязычности
    const translations = {
      ru: {
        "score": "Счет",
        "level": "Уровень",
        "energy": "Энергия",
        "profile": "Профиль",
        "clicker": "Кликер",
        "tasks": "Задания",
        "achievements": "Достижения",
        "friends": "Друзья",
        "minigames": "Мини-игры",
        "daily": "Бонусы",
        "top": "Топ",
        "upgrades": "УЛУЧШЕНИЯ",
        "wallet": "TON Кошелек",
        "connect_wallet": "Подключить кошелек",
        "disconnect_wallet": "Отключить кошелек",
        "wallet_connected": "TON кошелек успешно подключен!",
        "wallet_disconnected": "TON кошелек отключен",
        "no_energy": "Недостаточно энергии!",
        "level_up": "🎉 Новый уровень! 🎉",
        "achievement_unlocked": "Достижение разблокировано!",
        "friend_added": "Друг добавлен!",
        "gift_sent": "Подарок отправлен!",
        "daily_bonus_claimed": "Ежедневный бонус получен!",
        "minigame_reward": "Награда за мини-игру получена!",
        "copy_link": "Ссылка скопирована в буфер обмена!",
        "share_link": "Выберите чат для отправки ссылки",
        "ad_watched": "Реклама просмотрена!",
        "ad_error": "Ошибка при показе рекламы",
        "not_enough_coins": "Недостаточно монет!",
        "upgrade_purchased": "Улучшение куплено!",
        "upgrade_already_purchased": "Улучшение уже куплено!"
      },
      en: {
        "score": "Score",
        "level": "Level",
        "energy": "Energy",
        "profile": "Profile",
        "clicker": "Clicker",
        "tasks": "Tasks",
        "achievements": "Achievements",
        "friends": "Friends",
        "minigames": "Minigames",
        "daily": "Bonuses",
        "top": "Top",
        "upgrades": "UPGRADES",
        "wallet": "TON Wallet",
        "connect_wallet": "Connect Wallet",
        "disconnect_wallet": "Disconnect Wallet",
        "wallet_connected": "TON wallet connected successfully!",
        "wallet_disconnected": "TON wallet disconnected",
        "no_energy": "Not enough energy!",
        "level_up": "🎉 New level! 🎉",
        "achievement_unlocked": "Achievement unlocked!",
        "friend_added": "Friend added!",
        "gift_sent": "Gift sent!",
        "daily_bonus_claimed": "Daily bonus claimed!",
        "minigame_reward": "Minigame reward received!",
        "copy_link": "Link copied to clipboard!",
        "share_link": "Select chat to send link",
        "ad_watched": "Ad watched!",
        "ad_error": "Error showing ad",
        "not_enough_coins": "Not enough coins!",
        "upgrade_purchased": "Upgrade purchased!",
        "upgrade_already_purchased": "Upgrade already purchased!"
      }
    };
    
    // Функция для определения уровня по очкам
    function getLevelByScore(score) {
      for (let i = LEVELS.length - 1; i >= 0; i--) {
        if (score >= LEVELS[i].score) {
          return LEVELS[i];
        }
      }
      return LEVELS[0];
    }
    
    // Функция для получения следующего уровня
    function getNextLevel(currentScore) {
      for (let i = 0; i < LEVELS.length - 1; i++) {
        if (currentScore < LEVELS[i+1].score) {
          return LEVELS[i+1];
        }
      }
      return null; // Если достигнут максимальный уровень
    }

    // Инициализация Telegram Web App
    let tg = window.Telegram.WebApp;
    tg.ready();
    tg.expand();
    tg.disableVerticalSwipes(); // Запрет приближения/отдаления
    
    // Данные пользователя из Telegram
    let user = tg.initDataUnsafe.user;
    
    // Глобальные переменные для хранения данных пользователя
    let userData = {
      score: 0,
      total_clicks: 0,
      level: "Новичок",
      walletAddress: "",
      referrals: [],
      lastReferralTaskCompletion: null,
      walletTaskCompleted: false,
      channelTaskCompleted: false,
      energy: 250,
      lastEnergyUpdate: new Date().toISOString(),
      upgrades: [],
      ads_watched: 0,
      achievements: [],
      friends: [],
      daily_bonus: {
        last_claim: null,
        streak: 0,
        claimed_days: []
      },
      active_boosts: [],
      skins: [],
      active_skin: 'default',
      auto_clickers: 0,
      language: 'ru'
    };
    
    // Максимальное количество энергии
    const MAX_ENERGY = 250;
    
    // Текущий язык
    let currentLanguage = 'ru';
    
    // Инициализация TonConnect
    let tonConnectUI;
    
    // Инициализация Adsgram
    let adsgramAd;
    
    // Функция для инициализации TonConnect
    function initTonConnect() {
      tonConnectUI = new TON_CONNECT_UI.TonConnectUI({
        manifestUrl: 'https://tofemb.onrender.com/tonconnect-manifest.json',
        buttonRootId: 'ton-connect-button',
        actionsConfiguration: {
          twaReturnUrl: 'https://t.me/Fnmby_bot'
        }
      });
      
      // Обработка подключения кошелька
      tonConnectUI.onStatusChange(wallet => {
        if (wallet) {
          // Кошелек подключен
          const address = wallet.account.address;
          const formattedAddress = formatWalletAddress(address);
          
          // Сохраняем адрес кошелька
          userData.walletAddress = address;
          saveUserData();
          
          // Обновляем интерфейс
          document.getElementById('wallet-address').textContent = formattedAddress;
          document.getElementById('ton-connect-button').textContent = translations[currentLanguage].disconnect_wallet;
          
          // Проверяем задание
          checkWalletTask();
          
          // Показываем уведомление
          showNotification(translations[currentLanguage].wallet_connected);
        } else {
          // Кошелек отключен
          userData.walletAddress = "";
          saveUserData();
          
          // Обновляем интерфейс
          document.getElementById('wallet-address').textContent = translations[currentLanguage].connect_wallet;
          document.getElementById('ton-connect-button').textContent = translations[currentLanguage].connect_wallet;
          
          // Показываем уведомление
          showNotification(translations[currentLanguage].wallet_disconnected);
        }
      });
    }
    
    // Функция для инициализации Adsgram
    function initAdsgram() {
      // Используем ваш UnitID: int-16829
      adsgramAd = window.Adsgram.init({ 
        blockId: 'int-16829',
        debug: true,
        onReward: () => {
          // Реклама успешно просмотрена
          console.log('Ad watched successfully');
        },
        onError: (error) => {
          // Ошибка при показе рекламы
          console.error('Ad error:', error);
        },
        onSkip: () => {
          // Реклама пропущена
          console.log('Ad skipped');
        }
      });
    }
    
    // Форматирование адреса кошелька
    function formatWalletAddress(address) {
      if (!address) return translations[currentLanguage].connect_wallet;
      return `${address.substring(0, 6)}...${address.substring(address.length - 4)}`;
    }
    
    // Функция для создания эффекта молнии
    function createLightning() {
      const energyContainer = document.getElementById('energyContainer');
      const energyIcon = document.getElementById('energyIcon');
      
      // Получаем позицию иконки энергии
      const iconRect = energyIcon.getBoundingClientRect();
      const containerRect = energyContainer.getBoundingClientRect();
      
      // Создаем несколько молний
      for (let i = 0; i < 5; i++) {
        const lightning = document.createElement('div');
        lightning.className = 'lightning';
        
        // Случайное положение вокруг иконки
        const angle = Math.random() * Math.PI * 2;
        const distance = 20 + Math.random() * 30;
        const x = iconRect.left - containerRect.left + iconRect.width / 2 + Math.cos(angle) * distance;
        const y = iconRect.top - containerRect.top + iconRect.height / 2 + Math.sin(angle) * distance;
        
        lightning.style.left = `${x}px`;
        lightning.style.top = `${y}px`;
        
        energyContainer.appendChild(lightning);
        
        // Запускаем анимацию
        setTimeout(() => {
          lightning.classList.add('active');
        }, 10);
        
        // Удаляем элемент после анимации
        setTimeout(() => {
          lightning.remove();
        }, 500);
      }
    }
    
    // Функция для обновления энергии
    function updateEnergy() {
      const now = new Date();
      const lastUpdate = new Date(userData.lastEnergyUpdate);
      const timeDiff = Math.floor((now - lastUpdate) / 1000); // разница в секундах
      
      // Восстанавливаем энергию (1 единица в секунду)
      if (timeDiff > 0) {
        userData.energy = Math.min(MAX_ENERGY, userData.energy + timeDiff);
        userData.lastEnergyUpdate = now.toISOString();
        
        // Обновляем отображение энергии
        updateEnergyDisplay();
      }
    }
    
    // Функция для обновления отображения энергии
    function updateEnergyDisplay() {
      const energyProgress = document.getElementById('energyProgress');
      const energyText = document.getElementById('energyText');
      
      const energyPercent = (userData.energy / MAX_ENERGY) * 100;
      energyProgress.style.width = `${energyPercent}%`;
      energyText.innerHTML = `<span id="energyIcon">⚡</span><span>${translations[currentLanguage].energy}: ${userData.energy}/${MAX_ENERGY}</span>`;
    }
    
    // Функция для загрузки данных пользователя с сервера
    async function loadUserData() {
      if (!user) return;
      
      try {
        const response = await fetch(`/user/${user.id}`);
        if (response.ok) {
          const data = await response.json();
          if (data.user) {
            userData = data.user;
            // Убедимся, что referrals - это массив
            if (!userData.referrals) {
              userData.referrals = [];
            }
            // Убедимся, что все поля присутствуют
            if (!userData.walletAddress) {
              userData.walletAddress = "";
            }
            if (userData.walletTaskCompleted === undefined) {
              userData.walletTaskCompleted = false;
            }
            if (userData.channelTaskCompleted === undefined) {
              userData.channelTaskCompleted = false;
            }
            if (!userData.lastReferralTaskCompletion) {
              userData.lastReferralTaskCompletion = null;
            }
            // Проверяем поля энергии
            if (!userData.energy) {
              userData.energy = MAX_ENERGY;
            }
            if (!userData.lastEnergyUpdate) {
              userData.lastEnergyUpdate = new Date().toISOString();
            }
            // Проверяем поля улучшений
            if (!userData.upgrades) {
              userData.upgrades = [];
            }
            // Проверяем поле счетчика рекламы
            if (!userData.ads_watched) {
              userData.ads_watched = 0;
            }
            // Проверяем поля достижений
            if (!userData.achievements) {
              userData.achievements = [];
            }
            // Проверяем поля друзей
            if (!userData.friends) {
              userData.friends = [];
            }
            // Проверяем поля ежедневных бонусов
            if (!userData.daily_bonus) {
              userData.daily_bonus = {
                last_claim: null,
                streak: 0,
                claimed_days: []
              };
            }
            // Проверяем поля активных бустов
            if (!userData.active_boosts) {
              userData.active_boosts = [];
            }
            // Проверяем поля скинов
            if (!userData.skins) {
              userData.skins = [];
            }
            if (!userData.active_skin) {
              userData.active_skin = 'default';
            }
            // Проверяем поля автокликеров
            if (!userData.auto_clickers) {
              userData.auto_clickers = 0;
            }
            // Проверяем поле языка
            if (!userData.language) {
              userData.language = 'ru';
            }
            
            // Устанавливаем текущий язык
            currentLanguage = userData.language;
            updateLanguageUI();
            
            // Обновляем энергию при загрузке
            updateEnergy();
            
            // Обновляем бонусы
            updateBonuses();
            
            // Обновляем скин персонажа
            updateCharacterSkin();
            
            updateScoreDisplay();
            updateLevel();
            
            // Обновляем данные кошелька
            if (userData.walletAddress) {
              document.getElementById('wallet-address').textContent = formatWalletAddress(userData.walletAddress);
              document.getElementById('ton-connect-button').textContent = translations[currentLanguage].disconnect_wallet;
            }
            
            // Проверяем задания
            checkWalletTask();
            checkChannelTask();
            checkReferralTask();
            checkAdsTask();
            
            // Обновляем достижения
            updateAchievements();
            
            // Обновляем друзей
            updateFriends();
            
            // Обновляем ежедневные бонусы
            updateDailyBonus();
            
            // Проверяем активные бусты
            checkActiveBoosts();
            
            // Запускаем автокликеры
            startAutoClickers();
            
            return;
          }
        }
        
        // Если данных нет, создаем нового пользователя
        userData = {
          id: user.id,
          first_name: user.first_name,
          last_name: user.last_name || '',
          username: user.username || '',
          photo_url: user.photo_url || '',
          score: 0,
          total_clicks: 0,
          level: "Новичок",
          walletAddress: "",
          referrals: [],
          lastReferralTaskCompletion: null,
          walletTaskCompleted: false,
          channelTaskCompleted: false,
          energy: MAX_ENERGY,
          lastEnergyUpdate: new Date().toISOString(),
          upgrades: [],
          ads_watched: 0,
          achievements: [],
          friends: [],
          daily_bonus: {
            last_claim: null,
            streak: 0,
            claimed_days: []
          },
          active_boosts: [],
          skins: [],
          active_skin: 'default',
          auto_clickers: 0,
          language: 'ru'
        };
        
        // Сохраняем нового пользователя на сервере
        await saveUserData();
        // После сохранения обновляем состояние заданий
        checkWalletTask();
        checkChannelTask();
        checkReferralTask();
        checkAdsTask();
        updateAchievements();
        updateFriends();
        updateDailyBonus();
      } catch (error) {
        console.error('Error loading user data:', error);
        // Даже при ошибке, обновляем состояние заданий на основе локальных данных
        checkWalletTask();
        checkChannelTask();
        checkReferralTask();
        checkAdsTask();
        updateAchievements();
        updateFriends();
        updateDailyBonus();
      }
    }
    
    // Функция для сохранения данных пользователя на сервере
    async function saveUserData() {
      if (!user) return;
      
      try {
        // Создаем объект для отправки на сервер, сохраняя все текущие данные
        const dataToSend = {...userData};
        
        console.log('Saving user data:', dataToSend);
        
        const response = await fetch('/user', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json'
          },
          body: JSON.stringify(dataToSend)
        });
        
        console.log('Save response status:', response.status);
        
        if (response.ok) {
          const data = await response.json();
          console.log('Save response:', data);
          
          if (data.user) {
            // Обновляем userData, сохраняя текущие значения
            const oldScore = userData.score;
            const oldTotalClicks = userData.total_clicks;
            const oldReferrals = userData.referrals;
            const oldWalletTaskCompleted = userData.walletTaskCompleted;
            const oldChannelTaskCompleted = userData.channelTaskCompleted;
            const oldLastReferralTaskCompletion = userData.lastReferralTaskCompletion;
            const oldEnergy = userData.energy;
            const oldLastEnergyUpdate = userData.lastEnergyUpdate;
            const oldUpgrades = userData.upgrades;
            const oldAdsWatched = userData.ads_watched; // Сохраняем текущее значение ads_watched
            const oldAchievements = userData.achievements;
            const oldFriends = userData.friends;
            const oldDailyBonus = userData.daily_bonus;
            const oldActiveBoosts = userData.active_boosts;
            const oldSkins = userData.skins;
            const oldActiveSkin = userData.active_skin;
            const oldAutoClickers = userData.auto_clickers;
            const oldLanguage = userData.language;
            
            userData = data.user;
            
            // Восстанавливаем важные значения, которые могли быть изменены
            userData.score = oldScore;
            userData.total_clicks = oldTotalClicks;
            userData.referrals = oldReferrals;
            userData.walletTaskCompleted = oldWalletTaskCompleted;
            userData.channelTaskCompleted = oldChannelTaskCompleted;
            userData.lastReferralTaskCompletion = oldLastReferralTaskCompletion;
            userData.energy = oldEnergy;
            userData.lastEnergyUpdate = oldLastEnergyUpdate;
            userData.upgrades = oldUpgrades;
            userData.ads_watched = oldAdsWatched; // Восстанавливаем текущее значение ads_watched
            userData.achievements = oldAchievements;
            userData.friends = oldFriends;
            userData.daily_bonus = oldDailyBonus;
            userData.active_boosts = oldActiveBoosts;
            userData.skins = oldSkins;
            userData.active_skin = oldActiveSkin;
            userData.auto_clickers = oldAutoClickers;
            userData.language = oldLanguage;
            
            console.log('User data saved successfully');
            return true;
          } else {
            console.error('No user data in response');
            return false;
          }
        } else {
          const errorText = await response.text();
          console.error('Error saving user data:', response.status, response.statusText, errorText);
          return false;
        }
      } catch (error) {
        console.error('Error saving user data:', error);
        return false;
      }
    }
    
    // Функция для обновления отображения счета
    function updateScoreDisplay() {
      const scoreDisplay = document.getElementById('score');
      if(scoreDisplay.firstChild) {
        scoreDisplay.firstChild.textContent = `${translations[currentLanguage].score}: ` + userData.score;
      }
    }
    
    // Функция для обновления данных топа (и превью, и страницы топа если открыта)
    async function updateTopData() {
      try {
        const response = await fetch('/top');
        if (response.ok) {
          const data = await response.json();
          
          if (data.users && data.users.length > 0) {
            // Обновляем превью топа (первые 3)
            updateTopPreview(data.users.slice(0, 3));
            
            // Если текущая страница - топ, обновляем и топ
            if (document.getElementById('top').classList.contains('active')) {
              renderTop(data.users);
            }
          }
        }
      } catch (error) {
        console.error('Error updating top data:', error);
      }
    }
    
    // Переключение страниц по кнопкам меню
    const pages = {
      profile: document.getElementById('profile'),
      clicker: document.getElementById('clicker'),
      tasks: document.getElementById('tasks'),
      top: document.getElementById('top'),
      achievements: document.getElementById('achievements'),
      friends: document.getElementById('friends'),
      minigames: document.getElementById('minigames'),
      daily: document.getElementById('daily')
    };

    function showPage(pageKey) {
      // Скрываем все окна
      Object.values(pages).forEach(el => el.classList.remove('active'));
      // Показываем выбранное окно
      pages[pageKey].classList.add('active');

      // Обновляем кнопки
      document.querySelectorAll('#bottom-menu button').forEach(btn => {
        if (btn.getAttribute('data-page') === pageKey) {
          btn.classList.add('active');
        } else {
          btn.classList.remove('active');
        }
      });

      // Управляем видимостью кнопки улучшений
      const upgradesButton = document.getElementById('upgrades-button');
      if (pageKey === 'clicker') {
        upgradesButton.style.display = 'flex';
      } else {
        upgradesButton.style.display = 'none';
      }

      // Управляем видимостью индикатора пассивного дохода
      const passiveIncomeDisplay = document.getElementById('passive-income-display');
      if (pageKey === 'clicker') {
        passiveIncomeDisplay.style.display = 'flex';
      } else {
        passiveIncomeDisplay.style.display = 'none';
      }

      // При открытии профиля обновляем данные
      if (pageKey === 'profile') {
        updateProfile();
      }
      
      // При открытии топа загружаем данные
      if (pageKey === 'top') {
        loadTop();
      }
      
      // При открытии заданий обновляем статус
      if (pageKey === 'tasks') {
        checkWalletTask();
        checkChannelTask();
        checkReferralTask();
        checkAdsTask();
      }
      
      // При открытии достижений обновляем данные
      if (pageKey === 'achievements') {
        updateAchievements();
      }
      
      // При открытии друзей обновляем данные
      if (pageKey === 'friends') {
        updateFriends();
      }
      
      // При открытии мини-игр обновляем данные
      if (pageKey === 'minigames') {
        // Мини-игры не требуют обновления данных
      }
      
      // При открытии ежедневных бонусов обновляем данные
      if (pageKey === 'daily') {
        updateDailyBonus();
      }
    }

    // Обновление данных профиля
    function updateProfile() {
      const loadingIndicator = document.getElementById('loadingIndicator');
      const userProfile = document.getElementById('userProfile');
      
      // Показываем индикатор загрузки
      loadingIndicator.style.display = 'block';
      userProfile.style.display = 'none';
      
      // Уменьшаем время загрузки для профиля
      setTimeout(() => {
        // Обновляем счет
        document.getElementById('profileScore').textContent = userData.score;
        document.getElementById('totalClicks').textContent = userData.total_clicks;
        
        // Получаем уровень на основе очков
        const currentLevel = getLevelByScore(userData.score);
        document.getElementById('userLevel').textContent = currentLevel.name;
        
        // Обновляем бонусы
        const clickBonus = calculateClickBonus();
        const passiveIncome = calculatePassiveIncome();
        
        document.getElementById('clickBonus').textContent = clickBonus;
        document.getElementById('passiveIncomeStat').textContent = passiveIncome;
        
        // Обновляем количество друзей
        document.getElementById('friendsCount').textContent = userData.friends.length;
        
        // Обновляем количество достижений
        document.getElementById('achievementsCount').textContent = userData.achievements.length;
        document.getElementById('totalAchievements').textContent = ACHIEVEMENTS.length;
        
        // Обновляем данные пользователя из Telegram
        if (user) {
          // Формируем полное имя
          const fullName = `${user.first_name} ${user.last_name || ''}`.trim();
          document.getElementById('userName').textContent = fullName;
          
          // Отображаем никнейм, если он есть
          document.getElementById('userHandle').textContent = user.username ? `@${user.username}` : '';
          
          // Устанавливаем аватарку
          const avatarImg = document.getElementById('userAvatar');
          if (user.photo_url) {
            avatarImg.src = user.photo_url;
          } else {
            // Если нет photo_url, используем стандартный URL для аватарки Telegram
            avatarImg.src = `https://t.me/i/userpic/320/${user.id}.jpg`;
          }
          
          // Показываем профиль
          userProfile.style.display = 'flex';
        } else {
          // Если данные пользователя недоступны (открыто вне Telegram)
          document.getElementById('userName').textContent = 'Гость';
          document.getElementById('userHandle').textContent = '@guest';
          document.getElementById('userAvatar').src = '/static/default-avatar.png';
          userProfile.style.display = 'flex';
        }
        
        // Обновляем адрес кошелька
        document.getElementById('wallet-address').textContent = 
          userData.walletAddress ? formatWalletAddress(userData.walletAddress) : translations[currentLanguage].connect_wallet;
        
        // Обновляем текст кнопки TonConnect
        document.getElementById('ton-connect-button').textContent = 
          userData.walletAddress ? translations[currentLanguage].disconnect_wallet : translations[currentLanguage].connect_wallet;
        
        // Скрываем индикатор загрузки
        loadingIndicator.style.display = 'none';
      }, 300); // Уменьшаем задержку до 300мс
    }

    // Загрузка топа пользователей с сервера
    async function loadTop() {
      const topList = document.getElementById('topList');
      topList.innerHTML = '<p>Загрузка топа...</p>';
      
      try {
        const response = await fetch('/top');
        const data = await response.json();
        
        if (data.users && data.users.length > 0) {
          renderTop(data.users);
          updateTopPreview(data.users.slice(0, 3));
        } else {
          topList.innerHTML = '<p>Нет данных для отображения</p>';
        }
      } catch (error) {
        console.error('Error loading top:', error);
        topList.innerHTML = '<p>Ошибка загрузки топа</p>';
      }
    }

    // Обновление превью топа на кнопке
    function updateTopPreview(topUsers) {
      const topPreview = document.getElementById('topPreview');
      topPreview.innerHTML = '';
      
      topUsers.forEach((user, index) => {
        const item = document.createElement('div');
        item.className = 'top-preview-item';
        item.textContent = `${index + 1}. ${user.first_name} ${user.last_name || ''} - ${user.score}`;
        topPreview.appendChild(item);
      });
    }

    // Отрисовка топа пользователей
    function renderTop(users) {
      const topList = document.getElementById('topList');
      topList.innerHTML = '';
      
      // Получаем ID текущего пользователя
      const currentUserId = user ? user.id.toString() : null;
      
      users.forEach((user, index) => {
        const topItem = document.createElement('div');
        topItem.className = `top-item ${user.id === currentUserId ? 'current-user' : ''}`;
        
        topItem.innerHTML = `
          <div class="top-rank">${index + 1}</div>
          <img class="top-avatar" src="${user.photo_url || `https://t.me/i/userpic/320/${user.id}.jpg`}" alt="${user.first_name}">
          <div class="top-info">
            <div class="top-name">${user.first_name} ${user.last_name || ''}</div>
            <div class="top-score">
              ${user.score}
              <img class="top-coin" src="/static/FemboyCoinsPink.png" alt="монетки">
              <span class="top-level">${user.level}</span>
            </div>
          </div>
        `;
        
        topList.appendChild(topItem);
      });
    }

    // Обновление уровня игрока
    function updateLevel() {
      const score = userData.score;
      const currentLevel = getLevelByScore(score);
      const nextLevel = getNextLevel(score);
      
      // Обновляем прогресс-бар
      if (nextLevel) {
        // Если есть следующий уровень
        const currentLevelScore = currentLevel.score;
        const nextLevelScore = nextLevel.score;
        const progress = ((score - currentLevelScore) / (nextLevelScore - currentLevelScore)) * 100;
        
        document.getElementById('levelProgressBar').style.width = `${progress}%`;
        document.getElementById('levelProgressText').textContent = `${translations[currentLanguage].level}: ${currentLevel.name} (${score - currentLevelScore}/${nextLevelScore - currentLevelScore})`;
      } else {
        // Если достигнут максимальный уровень
        document.getElementById('levelProgressBar').style.width = '100%';
        document.getElementById('levelProgressText').textContent = `${translations[currentLanguage].level}: ${currentLevel.name}`;
      }
      
      // Обновляем уровень в профиле
      document.getElementById('userLevel').textContent = currentLevel.name;
      
      // Проверяем, был ли достигнут новый уровень
      const lastLevelName = localStorage.getItem('lastLevelName') || LEVELS[0].name;
      if (currentLevel.name !== lastLevelName) {
        localStorage.setItem('lastLevelName', currentLevel.name);
        showLevelUp(currentLevel.name);
      }
    }

    // Показать модальное окно повышения уровня
    function showLevelUp(levelName) {
      // Создаем фейерверки
      createFireworks();
      
      // Показываем модальное окно
      document.getElementById('levelUpLevelText').textContent = levelName;
      document.getElementById('levelUpModal').style.display = 'flex';
    }

    // Создать эффект фейерверка
    function createFireworks() {
      const colors = ['#ff66cc', '#ff9a9e', '#fad0c4', '#a18cd1'];
      
      for (let i = 0; i < 15; i++) {
        setTimeout(() => {
          const firework = document.createElement('div');
          firework.className = 'firework';
          firework.style.left = `${Math.random() * 100}%`;
          firework.style.top = `${Math.random() * 100}%`;
          firework.style.background = colors[Math.floor(Math.random() * colors.length)];
          document.body.appendChild(firework);
          
          // Удаляем элемент после анимации
          setTimeout(() => {
            firework.remove();
          }, 1000);
        }, i * 100);
      }
    }
    
    // Показать уведомление
    function showNotification(message) {
      const notification = document.getElementById('notification');
      notification.textContent = message;
      notification.classList.add('show');
      
      setTimeout(() => {
        notification.classList.remove('show');
      }, 3000);
    }
    
    // Показать уведомление о недостатке энергии
    function showNoEnergyNotification() {
      const notification = document.getElementById('noEnergyNotification');
      notification.classList.add('show');
      
      setTimeout(() => {
        notification.classList.remove('show');
      }, 1500);
    }
    
    // Проверка задания с кошельком
    function checkWalletTask() {
      if (userData.walletAddress && !userData.walletTaskCompleted) {
        // Задание выполнено, но награда не получена
        document.getElementById('wallet-task-button').textContent = 'Получить награду';
        document.getElementById('wallet-task-button').disabled = false;
      } else if (userData.walletTaskCompleted) {
        // Награда уже получена
        document.getElementById('wallet-task-button').style.display = 'none';
        document.getElementById('wallet-task-status').style.display = 'block';
      } else {
        // Задание не выполнено
        document.getElementById('wallet-task-button').textContent = 'НАЧАТЬ';
        document.getElementById('wallet-task-button').disabled = false;
      }
    }
    
    // Проверка задания с подпиской на канал
    function checkChannelTask() {
      if (userData.channelTaskCompleted) {
        // Награда уже получена
        document.getElementById('channel-task-button').style.display = 'none';
        document.getElementById('channel-task-status').style.display = 'block';
      } else {
        // Задание не выполнено
        document.getElementById('channel-task-button').textContent = 'НАЧАТЬ';
        document.getElementById('channel-task-button').disabled = false;
        document.getElementById('channel-task-button').style.display = 'block';
        document.getElementById('channel-task-status').style.display = 'none';
      }
    }
    
    // Проверка задания с рефералами
    function checkReferralTask() {
      // Убедимся, что referrals - это массив
      if (!Array.isArray(userData.referrals)) {
        userData.referrals = [];
      }
      
      // Обновляем счетчик рефералов
      document.getElementById('referral-count-value').textContent = userData.referrals.length;
      
      // Проверяем, можно ли выполнить задание
      const now = new Date();
      const lastCompletion = userData.lastReferralTaskCompletion ? 
        new Date(userData.lastReferralTaskCompletion) : null;
      
      // Если задание уже выполнено и прошло меньше 24 часов
      if (lastCompletion && (now - lastCompletion) < 24 * 60 * 60 * 1000) {
        // Показываем статус выполненного задания и таймер
        document.getElementById('referral-task-button').style.display = 'none';
        document.getElementById('referral-task-status').style.display = 'block';
        document.getElementById('referral-task-timer').style.display = 'block';
        
        // Обновляем таймер
        updateReferralTimer();
      } else if (userData.referrals.length >= 3) {
        // Задание доступно для выполнения
        document.getElementById('referral-task-button').textContent = 'Получить награду';
        document.getElementById('referral-task-button').disabled = false;
        document.getElementById('referral-task-button').style.display = 'block';
        document.getElementById('referral-task-status').style.display = 'none';
        document.getElementById('referral-task-timer').style.display = 'none';
      } else {
        // Задание не выполнено
        document.getElementById('referral-task-button').textContent = 'НАЧАТЬ';
        document.getElementById('referral-task-button').disabled = false;
        document.getElementById('referral-task-button').style.display = 'block';
        document.getElementById('referral-task-status').style.display = 'none';
        document.getElementById('referral-task-timer').style.display = 'none';
      }
    }
    
    // Проверка задания с рекламой
    function checkAdsTask() {
      console.log('Checking ads task, current ads_watched:', userData.ads_watched);
      
      // Убедимся, что ads_watched существует
      if (typeof userData.ads_watched === 'undefined') {
        userData.ads_watched = 0;
      }
      
      // Обновляем счетчик просмотренной рекламы
      const adsCountElement = document.getElementById('ads-count-value');
      if (adsCountElement) {
        adsCountElement.textContent = userData.ads_watched;
        console.log('Updated ads count display:', userData.ads_watched);
      }
      
      // Задание без отката, всегда доступно
      if (userData.ads_watched >= 10) {
        // Задание доступно для получения награды
        const adsTaskButton = document.getElementById('ads-task-button');
        if (adsTaskButton) {
          adsTaskButton.textContent = 'Получить награду';
          adsTaskButton.disabled = false;
          adsTaskButton.style.display = 'block';
        }
        const adsTaskStatus = document.getElementById('ads-task-status');
        if (adsTaskStatus) {
          adsTaskStatus.style.display = 'none';
        }
      } else {
        // Задание не выполнено
        const adsTaskButton = document.getElementById('ads-task-button');
        if (adsTaskButton) {
          adsTaskButton.textContent = 'НАЧАТЬ';
          adsTaskButton.disabled = false;
          adsTaskButton.style.display = 'block';
        }
        const adsTaskStatus = document.getElementById('ads-task-status');
        if (adsTaskStatus) {
          adsTaskStatus.style.display = 'none';
        }
      }
    }
    
    // Обновление таймера реферального задания
    function updateReferralTimer() {
      const lastCompletion = userData.lastReferralTaskCompletion ? 
        new Date(userData.lastReferralTaskCompletion) : null;
      
      if (!lastCompletion) return;
      
      const now = new Date();
      const timeLeft = 24 * 60 * 60 * 1000 - (now - lastCompletion);
      
      if (timeLeft <= 0) {
        // Время истекло
        document.getElementById('referral-task-timer').style.display = 'none';
        document.getElementById('referral-task-button').style.display = 'block';
        document.getElementById('referral-task-button').textContent = 'Получить награду';
        document.getElementById('referral-task-status').style.display = 'none';
        return;
      }
      
      // Вычисляем часы, минуты и секунды
      const hours = Math.floor(timeLeft / (60 * 60 * 1000));
      const minutes = Math.floor((timeLeft % (60 * 60 * 1000)) / (60 * 1000));
      const seconds = Math.floor((timeLeft % (60 * 1000)) / 1000);
      
      // Обновляем текст таймера
      document.getElementById('referral-task-timer').textContent = 
        `Задание будет доступно через: ${hours}ч ${minutes}м ${seconds}с`;
      
      // Запускаем обновление через секунду
      setTimeout(updateReferralTimer, 1000);
    }
    
    // Получение награды за задание с кошельком
    async function claimWalletTaskReward() {
      if (!userData.walletAddress || userData.walletTaskCompleted) return;
      
      // Добавляем награду
      userData.score += 1000;
      userData.walletTaskCompleted = true;
      
      // Сохраняем данные
      await saveUserData();
      
      // Обновляем интерфейс
      updateScoreDisplay();
      updateLevel();
      checkWalletTask();
      
      // Показываем уведомление
      showNotification('Вы получили 1000 монеток!');
    }
    
    // Получение награды за задание с подпиской на канал
    async function claimChannelTaskReward() {
      if (userData.channelTaskCompleted) return;
      
      // Добавляем награду
      userData.score += 2000;
      userData.channelTaskCompleted = true;
      
      // Сохраняем данные
      await saveUserData();
      
      // Обновляем интерфейс
      updateScoreDisplay();
      updateLevel();
      checkChannelTask();
      
      // Показываем уведомление
      showNotification('Вы получили 2000 монеток!');
    }
    
    // Получение награды за задание с рефералами
    async function claimReferralTaskReward() {
      if (userData.referrals.length < 3) return;
      
      const now = new Date();
      const lastCompletion = userData.lastReferralTaskCompletion ? 
        new Date(userData.lastReferralTaskCompletion) : null;
      
      // Проверяем, прошло ли 24 часа с последнего выполнения
      if (lastCompletion && (now - lastCompletion) < 24 * 60 * 60 * 1000) {
        showNotification('Задание можно выполнять раз в 24 часа');
        return;
      }
      
      // Добавляем награду
      userData.score += 5000;
      userData.lastReferralTaskCompletion = now.toISOString();
      
      // Сохраняем данные
      await saveUserData();
      
      // Обновляем интерфейс
      updateScoreDisplay();
      updateLevel();
      checkReferralTask();
      
      // Показываем уведомление
      showNotification('Вы получили 5000 монеток!');
    }
    
    // Получение награды за задание с рекламой
    async function claimAdsTaskReward() {
      console.log('Claiming ads task reward, current ads_watched:', userData.ads_watched);
      
      if (userData.ads_watched < 10) {
        console.log('Cannot claim reward, ads_watched < 10');
        return;
      }
      
      // Добавляем награду
      userData.score += 5000;
      
      // Сбрасываем счетчик (задание можно выполнять снова)
      userData.ads_watched = 0;
      
      // Сохраняем данные
      await saveUserData();
      
      // Обновляем интерфейс
      updateScoreDisplay();
      updateLevel();
      checkAdsTask();
      
      // Показываем уведомление
      showNotification('Вы получили 5000 монеток!');
    }
    
    // Функция для просмотра рекламы через Adsgram
    function watchAds() {
      console.log('Watching ads');
      
      if (!adsgramAd) {
        console.error('Adsgram ad not initialized');
        showNotification('Реклама не загружена');
        return;
      }
      
      // Блокируем кнопку просмотра рекламы на время показа
      const adsTaskButton = document.getElementById('ads-task-button');
      adsTaskButton.disabled = true;
      adsTaskButton.innerHTML = '<span class="ads-loading"></span>ЗАГРУЗКА...';
      
      // Показываем уведомление о начале загрузки рекламы
      showNotification('Реклама загружается...');
      
      // Запускаем таймер на 3 секунды
      setTimeout(() => {
        // Увеличиваем счетчик просмотренной рекламы
        userData.ads_watched = (userData.ads_watched || 0) + 1;
        console.log('Updated ads_watched locally:', userData.ads_watched);
        
        // Обновляем интерфейс
        checkAdsTask();
        
        // Показываем уведомление
        showNotification('Реклама просмотрена!');
        
        // Сохраняем данные
        saveUserData().catch(error => {
          console.error('Error saving user data after ad watch:', error);
        });
        
        // Разблокируем кнопку
        adsTaskButton.disabled = false;
      }, 3000);
      
      // Параллельно показываем рекламу (но не ждем ее завершения для начисления)
      adsgramAd.show().then(() => {
        // Реклама успешно показана
        console.log('Ad shown successfully');
      }).catch((error) => {
        // Ошибка при показе рекламы
        console.error('Error showing ad:', error);
        showNotification('Ошибка при показе рекламы');
        
        // Разблокируем кнопку в случае ошибки
        adsTaskButton.disabled = false;
        adsTaskButton.textContent = userData.ads_watched >= 10 ? 'Получить награду' : 'НАЧАТЬ';
      });
    }
    
    // Копирование реферальной ссылки
    function copyReferralLink() {
      if (!user) return;
      
      const botUsername = 'Fnmby_bot';
      const referralLink = `https://t.me/${botUsername}?startapp=${user.id}`;
      
      // Создаем временный элемент для копирования
      const tempInput = document.createElement('input');
      tempInput.value = referralLink;
      document.body.appendChild(tempInput);
      tempInput.select();
      
      try {
        // Копируем текст в буфер обмена
        const successful = document.execCommand('copy');
        document.body.removeChild(tempInput);
        
        if (successful) {
          // Тактильная обратная связь
          if (tg.HapticFeedback) {
            tg.HapticFeedback.notificationOccurred('success');
          }
          showNotification(translations[currentLanguage].copy_link);
        } else {
          showNotification('Не удалось скопировать ссылку');
        }
      } catch (err) {
        document.body.removeChild(tempInput);
        console.error('Ошибка при копировании ссылки: ', err);
        showNotification('Не удалось скопировать ссылку');
      }
    }
    
    // Пересылка реферальной ссылки
    function shareReferralLink() {
      if (!user) return;
      
      const botUsername = 'Fnmby_bot';
      const referralLink = `https://t.me/${botUsername}?startapp=${user.id}`;
      const shareText = `Привет! Заходи в классную игру про фембоев! ${referralLink}`;
      
      // Используем Telegram WebApp для открытия чата выбора
      if (tg.openTelegramLink) {
        tg.openTelegramLink(`https://t.me/share/url?url=${encodeURIComponent(referralLink)}&text=${encodeURIComponent('Привет! Заходи в классную игру про фембоев!')}`);
      } else {
        // Запасной вариант
        window.open(`https://t.me/share/url?url=${encodeURIComponent(referralLink)}&text=${encodeURIComponent('Привет! Заходи в классную игру про фембоев!')}`, '_blank');
      }
      
      // Тактильная обратная связь
      if (tg.HapticFeedback) {
        tg.HapticFeedback.notificationOccurred('success');
      }
      
      showNotification(translations[currentLanguage].share_link);
    }
    
    // Открытие модального окна задания с кошельком
    function openWalletTaskModal() {
      document.getElementById('task-modal-overlay').classList.add('active');
      document.getElementById('wallet-task-modal').classList.add('active');
    }
    
    // Закрытие модального окна задания с кошельком
    function closeWalletTaskModal() {
      document.getElementById('task-modal-overlay').classList.remove('active');
      document.getElementById('wallet-task-modal').classList.remove('active');
    }
    
    // Открытие модального окна задания с подпиской на канал
    function openChannelTaskModal() {
      document.getElementById('task-modal-overlay').classList.add('active');
      document.getElementById('channel-task-modal').classList.add('active');
    }
    
    // Закрытие модального окна задания с подпиской на канал
    function closeChannelTaskModal() {
      document.getElementById('task-modal-overlay').classList.remove('active');
      document.getElementById('channel-task-modal').classList.remove('active');
    }
    
    // Переход к каналу Telegram
    function goToChannel() {
      // Замените на ваш канал
      const channelLink = 'https://t.me/femboygamingofficial';
      
      // Открываем канал
      if (tg.openTelegramLink) {
        tg.openTelegramLink(channelLink);
      } else {
        window.open(channelLink, '_blank');
      }
      
      // Закрываем модальное окно
      closeChannelTaskModal();
    }
    
    // Открытие модального окна задания с рефералами
    function openReferalTaskModal() {
      // Обновляем ссылку в модальном окне
      if (user) {
        const botUsername = 'Fnmby_bot';
        const referralLink = `https://t.me/${botUsername}?startapp=${user.id}`;
        document.getElementById('referral-link').textContent = referralLink;
      }
      
      document.getElementById('task-modal-overlay').classList.add('active');
      document.getElementById('referral-task-modal').classList.add('active');
    }
    
    // Закрытие модального окна задания с рефералами
    function closeReferralTaskModal() {
      document.getElementById('task-modal-overlay').classList.remove('active');
      document.getElementById('referral-task-modal').classList.remove('active');
    }
    
    // Обработка реферального параметра при запуске
    async function processReferralParam() {
      if (!user || !tg.initDataUnsafe.start_param) return;
      
      const referrerId = tg.initDataUnsafe.start_param;
      
      // Проверяем, что это ID пользователя и не текущий пользователь
      if (referrerId && referrerId !== user.id.toString()) {
        try {
          const response = await fetch('/referral', {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json'
            },
            body: JSON.stringify({
              referrer_id: referrerId,
              referred_id: user.id.toString()
            })
          });
          
          if (response.ok) {
            const data = await response.json();
            if (data.status === 'success') {
              showNotification('Вы были приглашены по реферальной ссылке!');
            }
          }
        } catch (error) {
          console.error('Error processing referral:', error);
        }
      }
    }
    
    // Функции для улучшений
    // Открытие модального окна улучшений
    function openUpgradesModal() {
      document.getElementById('upgrades-modal-overlay').classList.add('active');
      document.getElementById('upgrades-modal').classList.add('active');
      
      // Обновляем контейнер улучшений
      renderUpgrades();
    }
    
    // Закрытие модального окна улучшений
    function closeUpgradesModal() {
      document.getElementById('upgrades-modal-overlay').classList.remove('active');
      document.getElementById('upgrades-modal').classList.remove('active');
    }
    
    // Отрисовка улучшений
    function renderUpgrades() {
      const container = document.getElementById('upgrades-container');
      container.innerHTML = '';
      
      UPGRADES.forEach(upgrade => {
        const isPurchased = userData.upgrades.includes(upgrade.id);
        
        const upgradeElement = document.createElement('div');
        upgradeElement.className = `upgrade-item ${isPurchased ? 'purchased' : ''}`;
        
        // Создаем элемент для изображения или иконки
        const imageElement = document.createElement('div');
        imageElement.className = 'upgrade-image';
        
        // Проверяем, существует ли изображение
        const img = new Image();
        img.onload = function() {
          imageElement.innerHTML = `<img src="${upgrade.image}" alt="Улучшение">`;
        };
        img.onerror = function() {
          // Если изображение не загрузилось, используем иконку
          const iconMap = {
            'upgrade1': '👆',
            'upgrade2': '👆',
            'upgrade3': '👆',
            'upgrade4': '⏱️',
            'upgrade5': '⏱️',
            'upgrade6': '⏱️',
            'upgrade7': '👆',
            'upgrade8': '👆',
            'upgrade9': '⏱️',
            'upgrade10': '👆',
            'upgrade11': '⏱️',
            'upgrade12': '👆',
            'boost_2x': '⚡',
            'energy_max': '🔋',
            'skin_gold': '👑',
            'auto_clicker': '🤖'
          };
          imageElement.textContent = iconMap[upgrade.id] || '📦';
        };
        img.src = upgrade.image;
        
        upgradeElement.appendChild(imageElement);
        
        upgradeElement.innerHTML += `
          <div class="upgrade-description">${upgrade.description}</div>
          <div class="upgrade-cost">
            <img src="/static/FemboyCoinsPink.png" alt="монетки">
            <span>${upgrade.cost}</span>
          </div>
          <button class="upgrade-buy-button" data-upgrade-id="${upgrade.id}" ${isPurchased ? 'disabled' : ''}>
            ${isPurchased ? 'КУПЛЕНО' : 'КУПИТЬ'}
          </button>
        `;
        
        container.appendChild(upgradeElement);
      });
      
      // Добавляем обработчики для кнопок покупки
      document.querySelectorAll('.upgrade-buy-button').forEach(button => {
        button.addEventListener('click', function() {
          const upgradeId = this.getAttribute('data-upgrade-id');
          buyUpgrade(upgradeId);
        });
      });
    }
    
    // Покупка улучшения
    async function buyUpgrade(upgradeId) {
      // Находим улучшение по ID
      const upgrade = UPGRADES.find(u => u.id === upgradeId);
      
      if (!upgrade) return;
      
      // Проверяем, не куплено ли уже это улучшение
      if (userData.upgrades.includes(upgradeId)) {
        showNotification(translations[currentLanguage].upgrade_already_purchased);
        return;
      }
      
      // Проверяем, достаточно ли монет
      if (userData.score < upgrade.cost) {
        showNotification(translations[currentLanguage].not_enough_coins);
        return;
      }
      
      // Списываем стоимость
      userData.score -= upgrade.cost;
      
      // Добавляем улучшение в список купленных
      userData.upgrades.push(upgradeId);
      
      // Применяем эффект улучшения
      applyUpgradeEffect(upgrade.effect);
      
      // Сохраняем данные
      await saveUserData();
      
      // Обновляем интерфейс
      updateScoreDisplay();
      updateBonuses();
      renderUpgrades();
      
      // Показываем уведомление
      showNotification(translations[currentLanguage].upgrade_purchased);
    }
    
    // Применение эффекта улучшения
    function applyUpgradeEffect(effect) {
      if (effect.type === 'temporary_boost') {
        // Временный буст
        const boost = {
          type: 'score_multiplier',
          multiplier: effect.multiplier,
          endTime: new Date().getTime() + (effect.duration * 1000)
        };
        userData.active_boosts.push(boost);
        checkActiveBoosts();
      } else if (effect.type === 'max_energy') {
        // Увеличение максимальной энергии
        MAX_ENERGY += effect.value;
        userData.energy = Math.min(userData.energy, MAX_ENERGY);
        updateEnergyDisplay();
      } else if (effect.type === 'visual') {
        // Визуальное улучшение (скин)
        if (!userData.skins.includes(effect.skin)) {
          userData.skins.push(effect.skin);
        }
        userData.active_skin = effect.skin;
        updateCharacterSkin();
      } else if (effect.type === 'auto_clicker') {
        // Автокликер
        userData.auto_clickers += effect.value;
        startAutoClickers();
      }
    }
    
    // Проверка активных бустов
    function checkActiveBoosts() {
      const now = new Date().getTime();
      
      // Фильтруем активные бусты, удаляя истекшие
      userData.active_boosts = userData.active_boosts.filter(boost => boost.endTime > now);
      
      // Если есть активные бусты, устанавливаем таймер для их проверки
      if (userData.active_boosts.length > 0) {
        // Находим ближайший истекающий буст
        const nextEndTime = Math.min(...userData.active_boosts.map(boost => boost.endTime));
        const timeToNext = nextEndTime - now;
        
        if (timeToNext > 0) {
          setTimeout(checkActiveBoosts, timeToNext);
        }
      }
    }
    
    // Обновление скина персонажа
    function updateCharacterSkin() {
      const femboyImg = document.getElementById('femboyImg');
      
      if (userData.active_skin === 'gold') {
        femboyImg.src = '/static/Photo_femb_gold.jpg';
      } else {
        femboyImg.src = '/static/Photo_femb_static.jpg';
      }
    }
    
    // Запуск автокликеров
    function startAutoClickers() {
      // Если уже есть запущенные автокликеры, не запускаем новые
      if (window.autoClickerInterval) {
        clearInterval(window.autoClickerInterval);
      }
      
      if (userData.auto_clickers > 0) {
        window.autoClickerInterval = setInterval(() => {
          // Проверяем, достаточно ли энергии
          if (userData.energy > 0) {
            // Тратим энергию
            userData.energy--;
            
            // Рассчитываем бонус за клик
            const clickBonus = calculateClickBonus();
            
            // Увеличиваем счет с учетом бонуса
            userData.score += (1 + clickBonus);
            userData.total_clicks++;
            
            // Обновляем отображение
            updateScoreDisplay();
            updateEnergyDisplay();
            updateLevel();
            
            // Сохраняем данные
            saveUserData();
          }
        }, 1000 / userData.auto_clickers);
      }
    }
    
    // Расчет бонуса за клик
    function calculateClickBonus() {
      let bonus = 0;
      
      userData.upgrades.forEach(upgradeId => {
        const upgrade = UPGRADES.find(u => u.id === upgradeId);
        if (upgrade && upgrade.effect.clickBonus) {
          bonus += upgrade.effect.clickBonus;
        }
      });
      
      return bonus;
    }
    
    // Расчет пассивного дохода
    function calculatePassiveIncome() {
      let income = 0;
      
      userData.upgrades.forEach(upgradeId => {
        const upgrade = UPGRADES.find(u => u.id === upgradeId);
        if (upgrade && upgrade.effect.passiveIncome) {
          income += upgrade.effect.passiveIncome;
        }
      });
      
      return income;
    }
    
    // Обновление бонусов
    function updateBonuses() {
      const clickBonus = calculateClickBonus();
      const passiveIncome = calculatePassiveIncome();
      
      // Обновляем отображение пассивного дохода
      document.getElementById('passive-income-value').textContent = passiveIncome;
      
      // Если в профиле, обновляем и там
      if (document.getElementById('profile').classList.contains('active')) {
        document.getElementById('clickBonus').textContent = clickBonus;
        document.getElementById('passiveIncomeStat').textContent = passiveIncome;
      }
    }
    
    // Применение пассивного дохода
    function applyPassiveIncome() {
      const passiveIncome = calculatePassiveIncome();
      
      if (passiveIncome > 0) {
        userData.score += passiveIncome;
        updateScoreDisplay();
        saveUserData();
        
        // Визуальный эффект получения монет
        const scoreElement = document.getElementById('score');
        scoreElement.style.transform = 'scale(1.1)';
        setTimeout(() => {
          scoreElement.style.transform = 'scale(1)';
        }, 300);
      }
    }
    
    // Обновление достижений
    function updateAchievements() {
      const achievementsList = document.getElementById('achievements-list');
      achievementsList.innerHTML = '';
      
      ACHIEVEMENTS.forEach(achievement => {
        const isUnlocked = userData.achievements.includes(achievement.id);
        
        const achievementElement = document.createElement('div');
        achievementElement.className = `achievement-item ${isUnlocked ? 'unlocked' : ''}`;
        
        // Определяем прогресс для достижения
        let progress = '';
        let progressValue = 0;
        
        if (achievement.condition.type === 'clicks') {
          progressValue = userData.total_clicks;
          progress = `${progressValue}/${achievement.condition.value}`;
        } else if (achievement.condition.type === 'score') {
          progressValue = userData.score;
          progress = `${progressValue}/${achievement.condition.value}`;
        } else if (achievement.condition.type === 'referrals') {
          progressValue = userData.referrals.length;
          progress = `${progressValue}/${achievement.condition.value}`;
        } else if (achievement.condition.type === 'daily_streak') {
          progressValue = userData.daily_bonus.streak;
          progress = `${progressValue}/${achievement.condition.value}`;
        }
        
        achievementElement.innerHTML = `
          <div class="achievement-icon">${isUnlocked ? '🏆' : '🔒'}</div>
          <div class="achievement-name">${achievement.name}</div>
          <div class="achievement-description">${achievement.description}</div>
          <div class="achievement-reward">
            <img src="/static/FemboyCoinsPink.png" alt="монетки">
            <span>${achievement.reward}</span>
          </div>
          ${!isUnlocked ? `<div class="achievement-progress">${progress}</div>` : ''}
        `;
        
        achievementsList.appendChild(achievementElement);
      });
      
      // Проверяем, не разблокированы ли новые достижения
      checkNewAchievements();
    }
    
    // Проверка новых достижений
    function checkNewAchievements() {
      ACHIEVEMENTS.forEach(achievement => {
        // Если достижение уже разблокировано, пропускаем
        if (userData.achievements.includes(achievement.id)) return;
        
        let isUnlocked = false;
        
        if (achievement.condition.type === 'clicks') {
          isUnlocked = userData.total_clicks >= achievement.condition.value;
        } else if (achievement.condition.type === 'score') {
          isUnlocked = userData.score >= achievement.condition.value;
        } else if (achievement.condition.type === 'referrals') {
          isUnlocked = userData.referrals.length >= achievement.condition.value;
        } else if (achievement.condition.type === 'daily_streak') {
          isUnlocked = userData.daily_bonus.streak >= achievement.condition.value;
        }
        
        if (isUnlocked) {
          // Разблокируем достижение
          userData.achievements.push(achievement.id);
          
          // Добавляем награду
          userData.score += achievement.reward;
          
          // Сохраняем данные
          saveUserData();
          
          // Обновляем интерфейс
          updateScoreDisplay();
          updateLevel();
          updateAchievements();
          
          // Показываем уведомление
          showNotification(`${translations[currentLanguage].achievement_unlocked}: ${achievement.name}`);
        }
      });
    }
    
    // Обновление друзей
    function updateFriends() {
      const friendsList = document.getElementById('friends-list');
      friendsList.innerHTML = '';
      
      if (userData.friends.length === 0) {
        friendsList.innerHTML = '<p>У вас пока нет друзей</p>';
        return;
      }
      
      // Загружаем данные друзей
      userData.friends.forEach(friendId => {
        // Создаем элемент друга
        const friendElement = document.createElement('div');
        friendElement.className = 'friend-item';
        
        // Временно показываем заглушку, пока данные не загружены
        friendElement.innerHTML = `
          <div class="friend-avatar" src="/static/default-avatar.png"></div>
          <div class="friend-info">
            <div class="friend-name">Загрузка...</div>
            <div class="friend-score">-</div>
          </div>
          <div class="friend-actions">
            <button class="friend-button send-gift" data-friend-id="${friendId}">Подарок</button>
          </div>
        `;
        
        friendsList.appendChild(friendElement);
        
        // Загружаем данные друга
        fetch(`/user/${friendId}`)
          .then(response => response.json())
          .then(data => {
            if (data.user) {
              const friend = data.user;
              friendElement.innerHTML = `
                <img class="friend-avatar" src="${friend.photo_url || `https://t.me/i/userpic/320/${friend.id}.jpg`}" alt="${friend.first_name}">
                <div class="friend-info">
                  <div class="friend-name">${friend.first_name} ${friend.last_name || ''}</div>
                  <div class="friend-score">${friend.score} <img src="/static/FemboyCoinsPink.png" alt="монетки" style="width: 16px; height: 16px;"></div>
                </div>
                <div class="friend-actions">
                  <button class="friend-button send-gift" data-friend-id="${friendId}">Подарок</button>
                </div>
              `;
            }
          })
          .catch(error => {
            console.error('Error loading friend data:', error);
          });
      });
      
      // Добавляем обработчики для кнопок подарков
      document.querySelectorAll('.send-gift').forEach(button => {
        button.addEventListener('click', function() {
          const friendId = this.getAttribute('data-friend-id');
          openGiftModal(friendId);
        });
      });
    }
    
    // Открытие модального окна подарка
    function openGiftModal(friendId) {
      // Создаем модальное окно для подарка
      const modalOverlay = document.createElement('div');
      modalOverlay.className = 'task-modal-overlay active';
      
      const modal = document.createElement('div');
      modal.className = 'task-modal active';
      modal.style.width = '90%';
      modal.style.maxWidth = '400px';
      
      modal.innerHTML = `
        <div class="task-modal-header">
          <div class="task-modal-title">Отправить подарок</div>
          <button class="task-modal-close">×</button>
        </div>
        <div class="task-modal-content">
          <div class="task-modal-description">
            Выберите количество монеток для подарка:
          </div>
          <div style="margin: 20px 0;">
            <input type="range" id="gift-amount" min="100" max="1000" value="100" step="100" style="width: 100%;">
            <div style="display: flex; justify-content: space-between; margin-top: 10px;">
              <span>100</span>
              <span id="gift-amount-display">100</span>
              <span>1000</span>
            </div>
          </div>
        </div>
        <button class="task-modal-button" id="send-gift-button">Отправить подарок</button>
      `;
      
      document.body.appendChild(modalOverlay);
      document.body.appendChild(modal);
      
      // Обработчик для закрытия модального окна
      modal.querySelector('.task-modal-close').addEventListener('click', function() {
        modalOverlay.remove();
        modal.remove();
      });
      
      // Обработчик для изменения суммы подарка
      const giftAmountInput = document.getElementById('gift-amount');
      const giftAmountDisplay = document.getElementById('gift-amount-display');
      
      giftAmountInput.addEventListener('input', function() {
        giftAmountDisplay.textContent = this.value;
      });
      
      // Обработчик для отправки подарка
      document.getElementById('send-gift-button').addEventListener('click', function() {
        const amount = parseInt(giftAmountInput.value);
        
        // Проверяем, достаточно ли монет
        if (userData.score < amount) {
          showNotification(translations[currentLanguage].not_enough_coins);
          return;
        }
        
        // Отправляем подарок
        sendGift(user.id, friendId, 'coins', amount);
        
        // Закрываем модальное окно
        modalOverlay.remove();
        modal.remove();
      });
    }
    
    // Отправка подарка
    async function sendGift(senderId, receiverId, giftType, giftValue) {
      try {
        const response = await fetch('/gift', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({
            sender_id: senderId,
            receiver_id: receiverId,
            gift_type: giftType,
            gift_value: giftValue
          })
        });
        
        if (response.ok) {
          const data = await response.json();
          
          if (data.status === 'success') {
            // Обновляем данные пользователя
            userData.score -= giftValue;
            updateScoreDisplay();
            saveUserData();
            
            // Показываем уведомление
            showNotification(translations[currentLanguage].gift_sent);
          } else {
            showNotification('Ошибка при отправке подарка');
          }
        } else {
          showNotification('Ошибка при отправке подарка');
        }
      } catch (error) {
        console.error('Error sending gift:', error);
        showNotification('Ошибка при отправке подарка');
      }
    }
    
    // Обновление ежедневных бонусов
    function updateDailyBonus() {
      const calendar = document.getElementById('daily-bonus-calendar');
      calendar.innerHTML = '';
      
      const today = new Date().getDate();
      const currentStreak = userData.daily_bonus.streak;
      
      // Отображаем календарь бонусов
      DAILY_BONUSES.forEach((bonus, index) => {
        const dayNumber = index + 1;
        const isCurrentDay = dayNumber === currentStreak + 1;
        const isClaimed = dayNumber <= currentStreak;
        
        const dayElement = document.createElement('div');
        dayElement.className = `bonus-day ${isCurrentDay ? 'current' : ''} ${isClaimed ? 'claimed' : ''}`;
        
        dayElement.innerHTML = `
          <div class="bonus-day-number">День ${dayNumber}</div>
          <div class="bonus-day-reward">
            <img src="/static/FemboyCoinsPink.png" alt="монетки">
            <span>${bonus.reward}</span>
          </div>
        `;
        
        calendar.appendChild(dayElement);
      });
      
      // Обновляем текущую серию
      document.getElementById('current-streak').textContent = currentStreak;
      
      // Проверяем, можно ли получить бонус сегодня
      checkDailyBonusAvailability();
    }
    
    // Проверка доступности ежедневного бонуса
    function checkDailyBonusAvailability() {
      const now = new Date();
      const today = now.toISOString().split('T')[0]; // YYYY-MM-DD
      
      const lastClaim = userData.daily_bonus.last_claim;
      const lastClaimDate = lastClaim ? new Date(lastClaim).toISOString().split('T')[0] : null;
      
      const claimButton = document.getElementById('claim-daily-bonus-button');
      
      if (lastClaimDate === today) {
        // Бонус уже получен сегодня
        claimButton.disabled = true;
        claimButton.textContent = 'Бонус получен';
      } else {
        // Бонус доступен для получения
        claimButton.disabled = false;
        claimButton.textContent = 'Получить бонус';
      }
    }
    
    // Получение ежедневного бонуса
    async function claimDailyBonus() {
      try {
        const response = await fetch('/daily-bonus', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({
            user_id: user.id
          })
        });
        
        if (response.ok) {
          const data = await response.json();
          
          if (data.status === 'success') {
            // Обновляем данные пользователя
            userData.score += data.reward;
            userData.daily_bonus = data.daily_bonus;
            
            // Обновляем интерфейс
            updateScoreDisplay();
            updateLevel();
            updateDailyBonus();
            
            // Показываем уведомление
            showNotification(`${translations[currentLanguage].daily_bonus_claimed}: ${data.reward} монеток`);
          } else {
            showNotification(data.message || 'Ошибка при получении бонуса');
          }
        } else {
          showNotification('Ошибка при получении бонуса');
        }
      } catch (error) {
        console.error('Error claiming daily bonus:', error);
        showNotification('Ошибка при получении бонуса');
      }
    }
    
    // Обновление языка интерфейса
    function updateLanguageUI() {
      // Обновляем тексты элементов интерфейса
      document.querySelectorAll('[data-i18n]').forEach(element => {
        const key = element.getAttribute('data-i18n');
        if (translations[currentLanguage][key]) {
          element.textContent = translations[currentLanguage][key];
        }
      });
      
      // Обновляем тексты кнопок
      document.getElementById('btn-profile').textContent = translations[currentLanguage].profile;
      document.getElementById('btn-clicker').textContent = translations[currentLanguage].clicker;
      document.getElementById('btn-tasks').textContent = translations[currentLanguage].tasks;
      document.getElementById('btn-achievements').textContent = translations[currentLanguage].achievements;
      document.getElementById('btn-friends').textContent = translations[currentLanguage].friends;
      document.getElementById('btn-minigames').textContent = translations[currentLanguage].minigames;
      document.getElementById('btn-daily').textContent = translations[currentLanguage].daily;
      document.getElementById('upgrades-button').textContent = translations[currentLanguage].upgrades;
      
      // Обновляем другие тексты
      updateScoreDisplay();
      updateEnergyDisplay();
      updateLevel();
    }
    
    // Функции для мини-игры "Поймай монетки"
    function startMinigame(minigameId) {
      if (minigameId === 'catch_coins') {
        startCatchCoinsMinigame();
      }
    }
    
    function startCatchCoinsMinigame() {
      const minigameContainer = document.getElementById('minigame-catch-coins');
      const minigameArea = document.getElementById('minigame-area');
      const scoreElement = document.getElementById('minigame-score');
      const timerElement = document.getElementById('minigame-timer');
      const resultElement = document.getElementById('minigame-result');
      const resultScoreElement = document.getElementById('minigame-result-score');
      
      // Сбрасываем состояние игры
      minigameArea.innerHTML = '';
      scoreElement.textContent = '0';
      timerElement.textContent = '30';
      resultElement.classList.remove('active');
      
      let score = 0;
      let timeLeft = 30;
      let gameActive = true;
      
      // Показываем мини-игру
      minigameContainer.classList.add('active');
      
      // Функция создания монетки
      function createCoin() {
        if (!gameActive) return;
        
        const coin = document.createElement('div');
        coin.className = 'coin';
        
        // Случайная позиция по горизонтали
        const maxX = minigameArea.offsetWidth - 30;
        const randomX = Math.floor(Math.random() * maxX);
        
        coin.style.left = `${randomX}px`;
        coin.style.top = '0px';
        
        // Добавляем монетку в игровую область
        minigameArea.appendChild(coin);
        
        // Анимация падения монетки
        let position = 0;
        const speed = 2 + Math.random() * 3; // Случайная скорость
        
        const fallInterval = setInterval(() => {
          if (!gameActive) {
            clearInterval(fallInterval);
            return;
          }
          
          position += speed;
          coin.style.top = `${position}px`;
          
          // Если монетка вышла за пределы игровой области
          if (position > minigameArea.offsetHeight) {
            clearInterval(fallInterval);
            coin.remove();
          }
        }, 16); // ~60 FPS
        
        // Обработчик клика по монетке
        coin.addEventListener('click', function() {
          if (!gameActive) return;
          
          // Увеличиваем счет
          score++;
          scoreElement.textContent = score;
          
          // Удаляем монетку
          clearInterval(fallInterval);
          coin.remove();
          
          // Визуальный эффект
          coin.style.transform = 'scale(1.5)';
          coin.style.opacity = '0';
        });
      }
      
      // Создаем монетки с интервалом
      const coinInterval = setInterval(() => {
        if (!gameActive) {
          clearInterval(coinInterval);
          return;
        }
        createCoin();
      }, 800); // Новая монетка каждые 800ms
      
      // Таймер игры
      const timerInterval = setInterval(() => {
        timeLeft--;
        timerElement.textContent = timeLeft;
        
        if (timeLeft <= 0) {
          // Игра окончена
          gameActive = false;
          clearInterval(coinInterval);
          clearInterval(timerInterval);
          
          // Показываем результат
          resultScoreElement.textContent = score;
          resultElement.classList.add('active');
        }
      }, 1000);
      
      // Обработчик закрытия мини-игры
      document.getElementById('minigame-close').addEventListener('click', function() {
        gameActive = false;
        clearInterval(coinInterval);
        clearInterval(timerInterval);
        minigameContainer.classList.remove('active');
      });
      
      // Обработчик кнопки результата
      document.getElementById('minigame-result-button').addEventListener('click', function() {
        // Закрываем мини-игру
        minigameContainer.classList.remove('active');
        
        // Начисляем награду
        const minigame = MINIGAMES.find(m => m.id === 'catch_coins');
        const reward = Math.min(score, minigame.reward);
        
        userData.score += reward;
        updateScoreDisplay();
        saveUserData();
        
        // Показываем уведомление
        showNotification(`${translations[currentLanguage].minigame_reward}: ${reward} монеток`);
      });
    }
    
    // Сохранение аналитики
    function saveAnalytics(event, data = {}) {
      if (!user) return;
      
      try {
        fetch('/analytics', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({
            user_id: user.id,
            event: event,
            data: data,
            timestamp: new Date().toISOString()
          })
        }).catch(error => {
          console.error('Error saving analytics:', error);
        });
      } catch (error) {
        console.error('Error saving analytics:', error);
      }
    }

    // Вешаем обработчики на кнопки
    document.addEventListener('DOMContentLoaded', async function() {
      // Инициализируем TonConnect
      initTonConnect();
      
      // Инициализируем Adsgram с вашим UnitID
      initAdsgram();
      
      // Загружаем данные пользователя при запуске
      if (user) {
        await loadUserData();
        // Обрабатываем реферальный параметр
        await processReferralParam();
        
        // Сохраняем аналитику запуска приложения
        saveAnalytics('app_start');
      }
      
      // Обработчик для кнопок меню
      document.querySelectorAll('#bottom-menu button').forEach(button => {
        button.addEventListener('click', function() {
          const pageKey = this.getAttribute('data-page');
          showPage(pageKey);
          
          // Сохраняем аналитику перехода на страницу
          saveAnalytics('page_view', { page: pageKey });
        });
      });
      
      // Обработчик для кнопки топа
      document.getElementById('topButton').addEventListener('click', function() {
        showPage('top');
      });
      
      // Обработчик для кнопки назад в топе
      document.getElementById('backButton').addEventListener('click', function() {
        showPage('clicker');
      });
      
      // Обработчик для кнопки закрытия модального окна
      document.getElementById('levelUpButton').addEventListener('click', function() {
        document.getElementById('levelUpModal').style.display = 'none';
      });
      
      // Обработчики для задания с кошельком
      document.getElementById('wallet-task-button').addEventListener('click', function() {
        if (userData.walletAddress && !userData.walletTaskCompleted) {
          claimWalletTaskReward();
        } else {
          openWalletTaskModal();
        }
      });
      
      document.getElementById('wallet-modal-close').addEventListener('click', closeWalletTaskModal);
      document.getElementById('wallet-modal-button').addEventListener('click', function() {
        closeWalletTaskModal();
        tonConnectUI.connectWallet();
      });
      
      // Обработчики для задания с подпиской на канал
      document.getElementById('channel-task-button').addEventListener('click', function() {
        if (!userData.channelTaskCompleted) {
          openChannelTaskModal();
        }
      });
      
      document.getElementById('channel-modal-close').addEventListener('click', closeChannelTaskModal);
      document.getElementById('channel-modal-button').addEventListener('click', goToChannel);
      document.getElementById('channel-verify-button').addEventListener('click', function() {
        claimChannelTaskReward();
        closeChannelTaskModal();
      });
      
      // Обработчики для задания с рефералами
      document.getElementById('referral-task-button').addEventListener('click', function() {
        if (userData.referrals.length >= 3) {
          claimReferralTaskReward();
        } else {
          openReferralTaskModal();
        }
      });
      
      document.getElementById('referral-modal-close').addEventListener('click', closeReferralTaskModal);
      document.getElementById('referral-modal-button').addEventListener('click', copyReferralLink);
      document.getElementById('referral-share-button').addEventListener('click', shareReferralLink);
      
      // Обработчики для задания с рекламой
      document.getElementById('ads-task-button').addEventListener('click', function() {
        if (userData.ads_watched >= 10) {
          claimAdsTaskReward();
        } else {
          watchAds();
        }
      });
      
      // Обработчик для кнопки TonConnect в профиле
      document.getElementById('ton-connect-button').addEventListener('click', function() {
        if (userData.walletAddress) {
          tonConnectUI.disconnect();
        } else {
          tonConnectUI.connectWallet();
        }
      });
      
      // Обработчик для затемнения фона
      document.getElementById('task-modal-overlay').addEventListener('click', function() {
        closeWalletTaskModal();
        closeChannelTaskModal();
        closeReferralTaskModal();
      });
      
      // Обработчики для улучшений
      document.getElementById('upgrades-button').addEventListener('click', openUpgradesModal);
      document.getElementById('upgrades-modal-close').addEventListener('click', closeUpgradesModal);
      document.getElementById('upgrades-modal-overlay').addEventListener('click', closeUpgradesModal);
      
      // Обработчики для вкладок заданий
      document.querySelectorAll('.task-tab').forEach(tab => {
        tab.addEventListener('click', function() {
          const tabType = this.getAttribute('data-tab');
          
          // Обновляем активную вкладку
          document.querySelectorAll('.task-tab').forEach(t => t.classList.remove('active'));
          this.classList.add('active');
          
          // Обновляем активное содержимое
          document.querySelectorAll('.task-content').forEach(content => {
            content.classList.remove('active');
          });
          document.getElementById(`${tabType}-tasks`).classList.add('active');
        });
      });
      
      // Обработчики для мини-игр
      document.querySelectorAll('.start-minigame-button').forEach(button => {
        button.addEventListener('click', function() {
          const minigameItem = this.closest('.minigame-item');
          const minigameId = minigameItem.getAttribute('data-minigame');
          startMinigame(minigameId);
          
          // Сохраняем аналитику запуска мини-игры
          saveAnalytics('minigame_start', { minigame_id: minigameId });
        });
      });
      
      // Обработчик для кнопки получения ежедневного бонуса
      document.getElementById('claim-daily-bonus-button').addEventListener('click', claimDailyBonus);
      
      // Обработчики для переключения языка
      document.getElementById('lang-ru').addEventListener('click', function() {
        currentLanguage = 'ru';
        userData.language = 'ru';
        updateLanguageUI();
        saveUserData();
        
        // Сохраняем аналитику смены языка
        saveAnalytics('language_change', { language: 'ru' });
      });
      
      document.getElementById('lang-en').addEventListener('click', function() {
        currentLanguage = 'en';
        userData.language = 'en';
        updateLanguageUI();
        saveUserData();
        
        // Сохраняем аналитику смены языка
        saveAnalytics('language_change', { language: 'en' });
      });
      
      // Устанавливаем начальную страницу
      showPage('clicker');
      
      // Загружаем превью топа
      await updateTopData();
      
      // Устанавливаем периодическое обновление топа каждые 3 секунды
      setInterval(updateTopData, 3000);
      
      // Устанавливаем интервал для обновления энергии каждую секунду
      setInterval(updateEnergy, 1000);
      
      // Устанавливаем интервал для пассивного дохода каждые 5 секунд
      setInterval(applyPassiveIncome, 5000);
      
      // Обновляем уровень при загрузке
      updateLevel();
    });

    // --- Код для клика ---

    const circle = document.getElementById('circle');
    const img = document.getElementById('femboyImg');
    const scoreDisplay = document.getElementById('score');

    const imgNormal = "/static/Photo_femb_static.jpg";
    const imgActive = "https://i.pinimg.com/736x/88/b3/b6/88b3b6e1175123e5c990931067c4b055.jpg";

    function incrementScore() {
      // Проверяем, достаточно ли энергии
      if (userData.energy <= 0) {
        showNoEnergyNotification();
        return;
      }
      
      // Тратим энергию
      userData.energy--;
      
      // Рассчитываем бонус за клик
      const clickBonus = calculateClickBonus();
      
      // Проверяем активные бусты
      let scoreMultiplier = 1;
      userData.active_boosts.forEach(boost => {
        if (boost.type === 'score_multiplier') {
          scoreMultiplier *= boost.multiplier;
        }
      });
      
      // Увеличиваем счет с учетом бонуса и бустов
      const scoreIncrease = Math.floor((1 + clickBonus) * scoreMultiplier);
      userData.score += scoreIncrease;
      userData.total_clicks++;
      
      // Создаем эффект молнии
      createLightning();
      
      // Обновляем отображение
      updateScoreDisplay();
      updateEnergyDisplay();
      updateLevel();
      
      // Сохраняем данные на сервере после каждого клика
      saveUserData();
      
      // Сохраняем аналитику клика
      saveAnalytics('click', { score_increase: scoreIncrease });
      
      // Проверяем достижения
      checkNewAchievements();
    }

    function pressVisualOn() {
      circle.classList.add('pressed');
      img.src = imgActive;
    }

    function pressVisualOff() {
      circle.classList.remove('pressed');
      img.src = imgNormal;
    }

    circle.addEventListener('mousedown', (e) => {
      if (e.button === 0) { 
        pressVisualOn();
        incrementScore();
      }
    });
    circle.addEventListener('mouseup', pressVisualOff);
    circle.addEventListener('mouseleave', pressVisualOff);

    circle.addEventListener('touchstart', (e) => {
      e.preventDefault();
      pressVisualOn();
      incrementScore();
    }, {passive:false});
    circle.addEventListener('touchend', (e) => {
      pressVisualOff();
    });

    circle.addEventListener('keydown', (e) => {
      if (e.code === 'Space' || e.code === 'Enter') {
        e.preventDefault();
        if (!circle.classList.contains('pressed')) {
          pressVisualOn();
          incrementScore();
        }
      }
    });

    circle.addEventListener('keyup', (e) => {
      if (e.code === 'Space' || e.code === 'Enter') {
        e.preventDefault();
        pressVisualOff();
      }
    });

    // Запрет масштабирования двумя пальцами
    document.addEventListener('touchstart', function(event) {
      if (event.touches.length > 1) {
        event.preventDefault();
      }
    }, { passive: false });

    document.addEventListener('touchmove', function(event) {
      if (event.touches.length > 1) {
        event.preventDefault();
      }
    }, { passive: false });

    document.addEventListener('gesturestart', function(event) {
      event.preventDefault();
    });

  </script>

</body>
</html>
"""

@app.get("/", response_class=HTMLResponse)
async def root():
    return HTMLResponse(content=html_content)

@app.get("/tonconnect-manifest.json")
async def tonconnect_manifest():
    manifest = {
        "url": "https://tofemb.onrender.com",
        "name": "Femboy Gaming",
        "iconUrl": "https://tofemb.onrender.com/static/FemboyCoinsPink.png",
        "termsOfUseUrl": "https://tofemb.onrender.com/terms",
        "privacyPolicyUrl": "https://tofemb.onrender.com/privacy"
    }
    return JSONResponse(content=manifest)

# Добавим эндпоинты для страниц условий использования и политики конфиденциальности
@app.get("/terms", response_class=HTMLResponse)
async def terms():
    return HTMLResponse(content="""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Условия использования</title>
        <meta charset="UTF-8">
        <style>
            body { font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }
            h1 { color: #ff66cc; }
        </style>
    </head>
    <body>
        <h1>Условия использования</h1>
        <p>Добро пожаловать в Femboy Gaming! Используя наше приложение, вы соглашаетесь с следующими условиями:</p>
        <ul>
            <li>Все игровые монеты являются виртуальной валютой и не имеют реальной ценности.</li>
            <li>Администрация оставляет за собой право изменять правила игры в любое время.</li>
            <li>Запрещено использование ботов, читов и других методов нечестной игры.</li>
            <li>Администрация не несет ответственности за утерю игровых монет из-за технических сбоев.</li>
        </ul>
        <p>Если у вас есть вопросы, свяжитесь с поддержкой через Telegram.</p>
    </body>
    </html>
    """)

@app.get("/privacy", response_class=HTMLResponse)
async def privacy():
    return HTMLResponse(content="""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Политика конфиденциальности</title>
        <meta charset="UTF-8">
        <style>
            body { font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }
            h1 { color: #ff66cc; }
        </style>
    </head>
    <body>
        <h1>Политика конфиденциальности</h1>
        <p>В Femboy Gaming мы ценим вашу конфиденциальность. Эта политика описывает, как мы собираем, используем и защищаем ваши данные:</p>
        <ul>
            <li>Мы собираем только минимально необходимые данные для работы приложения (ID пользователя, имя, никнейм).</li>
            <li>Мы не передаем ваши данные третьим лицам без вашего согласия.</li>
            <li>Все данные хранятся в зашифрованном виде на защищенных серверах.</li>
            <li>Вы можете запросить удаление своих данных в любой момент.</li>
        </ul>
        <p>Если у вас есть вопросы о вашей конфиденциальности, свяжитесь с нами через Telegram.</p>
    </body>
    </html>
    """)

@app.get("/user/{user_id}")
async def get_user_data(user_id: str):
    """Получение данных пользователя по ID"""
    try:
        logger.info(f"GET /user/{user_id} endpoint called")
        user_data = load_user(user_id)
        
        if user_data:
            # Преобразуем данные для фронтенда
            response_data = {
                "id": user_data["user_id"],
                "first_name": user_data["first_name"],
                "last_name": user_data["last_name"],
                "username": user_data["username"],
                "photo_url": user_data["photo_url"],
                "score": user_data["score"],
                "total_clicks": user_data["total_clicks"],
                "level": user_data["level"],
                "walletAddress": user_data["wallet_address"],
                "walletTaskCompleted": user_data["wallet_task_completed"],
                "channelTaskCompleted": user_data["channel_task_completed"],
                "referrals": user_data["referrals"],
                "lastReferralTaskCompletion": user_data["last_referral_task_completion"],
                "energy": user_data["energy"],
                "lastEnergyUpdate": user_data["last_energy_update"],
                "upgrades": user_data["upgrades"],
                "ads_watched": user_data["ads_watched"],
                "achievements": user_data["achievements"],
                "friends": user_data["friends"],
                "daily_bonus": user_data["daily_bonus"],
                "active_boosts": user_data["active_boosts"],
                "skins": user_data["skins"],
                "active_skin": user_data["active_skin"],
                "auto_clickers": user_data["auto_clickers"],
                "language": user_data["language"]
            }
            
            logger.info(f"Returning user data for {user_data['first_name']}")
            return JSONResponse(content={"user": response_data})
        else:
            logger.info(f"User not found with ID {user_id}")
            return JSONResponse(content={"status": "error", "message": "User not found"}, status_code=404)
    except Exception as e:
        logger.error(f"Error in /user/{user_id}: {e}")
        return JSONResponse(content={"status": "error", "message": str(e)}, status_code=500)

@app.post("/user")
async def save_user_data(request: Request):
    """Сохранение данных пользователя на сервере"""
    try:
        logger.info(f"POST /user endpoint called")
        data = await request.json()
        
        # Сохраняем в базу данных
        success = save_user(data)
        
        if success:
            # Получаем обновленные данные
            user_id = str(data.get('id'))
            user_data = load_user(user_id)
            
            if user_data:
                # Преобразуем данные для фронтенда
                response_data = {
                    "id": user_data["user_id"],
                    "first_name": user_data["first_name"],
                    "last_name": user_data["last_name"],
                    "username": user_data["username"],
                    "photo_url": user_data["photo_url"],
                    "score": user_data["score"],
                    "total_clicks": user_data["total_clicks"],
                    "level": user_data["level"],
                    "walletAddress": user_data["wallet_address"],
                    "walletTaskCompleted": user_data["wallet_task_completed"],
                    "channelTaskCompleted": user_data["channel_task_completed"],
                    "referrals": user_data["referrals"],
                    "lastReferralTaskCompletion": user_data["last_referral_task_completion"],
                    "energy": user_data["energy"],
                    "lastEnergyUpdate": user_data["last_energy_update"],
                    "upgrades": user_data["upgrades"],
                    "ads_watched": user_data["ads_watched"],
                    "achievements": user_data["achievements"],
                    "friends": user_data["friends"],
                    "daily_bonus": user_data["daily_bonus"],
                    "active_boosts": user_data["active_boosts"],
                    "skins": user_data["skins"],
                    "active_skin": user_data["active_skin"],
                    "auto_clickers": user_data["auto_clickers"],
                    "language": user_data["language"]
                }
                
                logger.info(f"User saved successfully: {user_data['first_name']}")
                return JSONResponse(content={"status": "success", "user": response_data})
            else:
                logger.info(f"Failed to retrieve saved user")
                return JSONResponse(content={"status": "error", "message": "Failed to retrieve saved user"}, status_code=500)
        else:
            logger.info(f"Failed to save user")
            return JSONResponse(content={"status": "error", "message": "Failed to save user"}, status_code=500)
    except Exception as e:
        logger.error(f"Error in POST /user: {e}")
        return JSONResponse(content={"status": "error", "message": str(e)}, status_code=500)

@app.post("/referral")
async def handle_referral(request: Request):
    """Обработка реферальной ссылки"""
    try:
        logger.info(f"POST /referral endpoint called")
        data = await request.json()
        referrer_id = str(data.get('referrer_id'))
        referred_id = str(data.get('referred_id'))
        
        if referrer_id and referred_id and referrer_id != referred_id:
            success = add_referral(referrer_id, referred_id)
            
            if success:
                logger.info(f"Referral added successfully: {referrer_id} -> {referred_id}")
                return JSONResponse(content={"status": "success"})
            else:
                logger.info(f"Failed to add referral")
                return JSONResponse(content={"status": "error", "message": "Failed to add referral"})
        else:
            logger.info(f"Invalid referral data")
            return JSONResponse(content={"status": "error", "message": "Invalid data"})
    except Exception as e:
        logger.error(f"Error in POST /referral: {e}")
        return JSONResponse(content={"status": "error", "message": str(e)}, status_code=500)

@app.get("/top")
async def get_top_users_endpoint():
    """Получение топа пользователей"""
    try:
        logger.info(f"GET /top endpoint called")
        top_users = get_top_users()
        
        # Преобразуем данные для фронтенда
        response_users = []
        for user in top_users:
            response_users.append({
                "id": user["user_id"],
                "first_name": user["first_name"],
                "last_name": user["last_name"],
                "username": user["username"],
                "photo_url": user["photo_url"],
                "score": user["score"],
                "level": user["level"]
            })
        
        logger.info(f"Returning {len(response_users)} top users")
        return JSONResponse(content={"users": response_users})
    except Exception as e:
        logger.error(f"Error in GET /top: {e}")
        return JSONResponse(content={"status": "error", "message": str(e)}, status_code=500)

@app.post("/daily-bonus")
async def claim_daily_bonus_endpoint(request: Request):
    """Получение ежедневного бонуса"""
    try:
        logger.info(f"POST /daily-bonus endpoint called")
        data = await request.json()
        user_id = data.get('user_id')
        
        if not user_id:
            return JSONResponse(content={"status": "error", "message": "Missing user_id"}, status_code=400)
        
        result = claim_daily_bonus(user_id)
        
        if result["status"] == "success":
            logger.info(f"Daily bonus claimed successfully for user {user_id}")
            return JSONResponse(content=result)
        else:
            logger.info(f"Failed to claim daily bonus for user {user_id}: {result['message']}")
            return JSONResponse(content=result, status_code=400)
    except Exception as e:
        logger.error(f"Error in POST /daily-bonus: {e}")
        return JSONResponse(content={"status": "error", "message": str(e)}, status_code=500)

@app.post("/gift")
async def send_gift_endpoint(request: Request):
    """Отправка подарка другу"""
    try:
        logger.info(f"POST /gift endpoint called")
        data = await request.json()
        sender_id = data.get('sender_id')
        receiver_id = data.get('receiver_id')
        gift_type = data.get('gift_type')
        gift_value = data.get('gift_value')
        
        if not all([sender_id, receiver_id, gift_type, gift_value]):
            return JSONResponse(content={"status": "error", "message": "Missing required fields"}, status_code=400)
        
        success = send_gift(sender_id, receiver_id, gift_type, gift_value)
        
        if success:
            logger.info(f"Gift sent successfully from {sender_id} to {receiver_id}")
            return JSONResponse(content={"status": "success"})
        else:
            logger.info(f"Failed to send gift from {sender_id} to {receiver_id}")
            return JSONResponse(content={"status": "error", "message": "Failed to send gift"})
    except Exception as e:
        logger.error(f"Error in POST /gift: {e}")
        return JSONResponse(content={"status": "error", "message": str(e)}, status_code=500)

@app.post("/analytics")
async def save_analytics_endpoint(request: Request):
    """Сохранение аналитики"""
    try:
        logger.info(f"POST /analytics endpoint called")
        data = await request.json()
        
        success = save_analytics(
            data.get('user_id'),
            data.get('event'),
            data.get('data', {})
        )
        
        if success:
            logger.info(f"Analytics saved successfully for event: {data.get('event')}")
            return JSONResponse(content={"status": "success"})
        else:
            logger.info(f"Failed to save analytics for event: {data.get('event')}")
            return JSONResponse(content={"status": "error", "message": "Failed to save analytics"})
    except Exception as e:
        logger.error(f"Error in POST /analytics: {e}")
        return JSONResponse(content={"status": "error", "message": str(e)}, status_code=500)

@app.get("/debug/users")
async def debug_users():
    """Эндпоинт для отладки - просмотр всех пользователей"""
    try:
        logger.info(f"GET /debug/users endpoint called")
        
        if supabase is None:
            return JSONResponse(content={"status": "error", "message": "Supabase client is not initialized"})
        
        response = supabase.table("users").select("user_id, first_name, last_name, score, level, ads_watched").order("score", desc=True).limit(50).execute()
        
        if response.data:
            logger.info(f"Found {len(response.data)} users")
            return JSONResponse(content={"users": response.data})
        else:
            logger.info(f"No users found")
            return JSONResponse(content={"users": []})
    except Exception as e:
        logger.error(f"Error in GET /debug/users: {e}")
        return JSONResponse(content={"status": "error", "message": str(e)}, status_code=500)

@app.get("/debug/analytics")
async def debug_analytics():
    """Эндпоинт для отладки - просмотр аналитики"""
    try:
        logger.info(f"GET /debug/analytics endpoint called")
        
        if supabase is None:
            return JSONResponse(content={"status": "error", "message": "Supabase client is not initialized"})
        
        response = supabase.table("analytics").select("*").order("timestamp", desc=True).limit(100).execute()
        
        if response.data:
            logger.info(f"Found {len(response.data)} analytics records")
            return JSONResponse(content={"analytics": response.data})
        else:
            logger.info(f"No analytics records found")
            return JSONResponse(content={"analytics": []})
    except Exception as e:
        logger.error(f"Error in GET /debug/analytics: {e}")
        return JSONResponse(content={"status": "error", "message": str(e)}, status_code=500)

@app.get("/debug/levels")
async def debug_levels():
    """Эндпоинт для отладки - просмотр уровней"""
    logger.info(f"GET /debug/levels endpoint called")
    return JSONResponse(content={"levels": LEVELS})

# Добавляем код для запуска на сервере
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    logger.info(f"Starting server on port {port}")
    uvicorn.run(app, host="0.0.0.0", port=port)
