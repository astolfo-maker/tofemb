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
    {"id": "upgrade12", "description": "+100 за клик", "cost": 1000000, "effect": {"clickBonus": 100}, "image": "/static/upgrade12.png"}
]

# Определение заданий
NORMAL_TASKS = [
    {
        "id": "wallet_task",
        "title": "Подключить TON кошелек",
        "reward": 1000,
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
        "no_reset": True  # Флаг, что задание не сбрасывается
    }
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
            "referrals": user_data.get('referrals', []),
            "last_referral_task_completion": user_data.get('lastReferralTaskCompletion'),
            "energy": int(user_data.get('energy', MAX_ENERGY)),
            "last_energy_update": user_data.get('lastEnergyUpdate', datetime.now(timezone.utc).isoformat()),
            "upgrades": user_data.get('upgrades', []),
            "ads_watched": int(user_data.get('ads_watched', 0))
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
        
        user_data['ads_watched'] += 1
        logger.info(f"Updated ads_watched for user {user_id}: {user_data['ads_watched']}")
        
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

    #profile, #tasks, #top {
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

  <!-- Уведомления -->
  <div id="notification" class="notification"></div>
  
  <!-- Уведомление о недостатке энергии -->
  <div id="noEnergyNotification" class="no-energy">Недостаточно энергии!</div>

  <nav id="bottom-menu" role="navigation" aria-label="Нижнее меню">
    <button id="btn-profile" data-page="profile">Профиль</button>
    <button id="btn-clicker" data-page="clicker" class="active">Кликер</button>
    <button id="btn-tasks" data-page="tasks">Задания</button>
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
      {id: "upgrade12", description: "+100 за клик", cost: 1000000, effect: {clickBonus: 100}, image: "/static/upgrade12.png"}
    ];
    
    // Задания игры
    const NORMAL_TASKS = [
      {id: "wallet_task", title: "Подключить TON кошелек", reward: 1000, type: "normal"}
    ];
    
    const DAILY_TASKS = [
      {id: "referral_task", title: "Пригласить 3-х друзей", reward: 5000, type: "daily"},
      {id: "ads_task", title: "Просмотр рекламы", reward: 5000, type: "daily", no_reset: true}
    ];
    
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
      totalClicks: 0,
      level: "Новичок",
      walletAddress: "",
      referrals: [],
      lastReferralTaskCompletion: null,
      walletTaskCompleted: false,
      energy: 250,
      lastEnergyUpdate: new Date().toISOString(),
      upgrades: [],
      ads_watched: 0
    };
    
    // Максимальное количество энергии
    const MAX_ENERGY = 250;
    
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
          document.getElementById('ton-connect-button').textContent = 'Отключить кошелек';
          
          // Проверяем задание
          checkWalletTask();
          
          // Показываем уведомление
          showNotification('TON кошелек успешно подключен!');
        } else {
          // Кошелек отключен
          userData.walletAddress = "";
          saveUserData();
          
          // Обновляем интерфейс
          document.getElementById('wallet-address').textContent = 'Не подключен';
          document.getElementById('ton-connect-button').textContent = 'Подключить кошелек';
          
          // Показываем уведомление
          showNotification('TON кошелек отключен');
        }
      });
    }
    
    // Функция для инициализации Adsgram
    function initAdsgram() {
      // Используем ваш UnitID: int-16829
      adsgramAd = window.Adsgram.init({ blockId: 'int-16829' });
      
      // Обработка событий Adsgram
      adsgramAd.addEventListener('onReward', () => {
        // Реклама успешно просмотрена
        console.log('Ad watched successfully');
        
        // Увеличиваем счетчик просмотренной рекламы
        userData.ads_watched = (userData.ads_watched || 0) + 1;
        
        // Сохраняем данные
        saveUserData();
        
        // Обновляем интерфейс
        checkAdsTask();
        
        // Показываем уведомление
        showNotification('Реклама просмотрена!');
      });
      
      adsgramAd.addEventListener('onError', (error) => {
        // Ошибка при показе рекламы
        console.error('Ad error:', error);
        showNotification('Ошибка при показе рекламы');
      });
      
      adsgramAd.addEventListener('onSkip', () => {
        // Реклама пропущена
        console.log('Ad skipped');
        showNotification('Реклама пропущена');
      });
    }
    
    // Форматирование адреса кошелька
    function formatWalletAddress(address) {
      if (!address) return 'Не подключен';
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
      energyText.innerHTML = `<span id="energyIcon">⚡</span><span>Энергия: ${userData.energy}/${MAX_ENERGY}</span>`;
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
            
            // Обновляем энергию при загрузке
            updateEnergy();
            
            // Обновляем бонусы
            updateBonuses();
            
            updateScoreDisplay();
            updateLevel();
            
            // Обновляем данные кошелька
            if (userData.walletAddress) {
              document.getElementById('wallet-address').textContent = formatWalletAddress(userData.walletAddress);
              document.getElementById('ton-connect-button').textContent = 'Отключить кошелек';
            }
            
            // Проверяем задания
            checkWalletTask();
            checkReferralTask();
            checkAdsTask();
            
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
          energy: MAX_ENERGY,
          lastEnergyUpdate: new Date().toISOString(),
          upgrades: [],
          ads_watched: 0
        };
        
        // Сохраняем нового пользователя на сервере
        await saveUserData();
        // После сохранения обновляем состояние заданий
        checkWalletTask();
        checkReferralTask();
        checkAdsTask();
      } catch (error) {
        console.error('Error loading user data:', error);
        // Даже при ошибке, обновляем состояние заданий на основе локальных данных
        checkWalletTask();
        checkReferralTask();
        checkAdsTask();
      }
    }
    
    // Функция для сохранения данных пользователя на сервере
    async function saveUserData() {
      if (!user) return;
      
      try {
        // Создаем объект для отправки на сервер, сохраняя все текущие данные
        const dataToSend = {...userData};
        
        const response = await fetch('/user', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json'
          },
          body: JSON.stringify(dataToSend)
        });
        
        if (response.ok) {
          const data = await response.json();
          if (data.user) {
            // Обновляем userData, сохраняя текущие значения
            const oldScore = userData.score;
            const oldTotalClicks = userData.total_clicks;
            const oldReferrals = userData.referrals;
            const oldWalletTaskCompleted = userData.walletTaskCompleted;
            const oldLastReferralTaskCompletion = userData.lastReferralTaskCompletion;
            const oldEnergy = userData.energy;
            const oldLastEnergyUpdate = userData.lastEnergyUpdate;
            const oldUpgrades = userData.upgrades;
            const oldAdsWatched = userData.ads_watched;
            
            userData = data.user;
            
            // Восстанавливаем важные значения, которые могли быть изменены
            userData.score = oldScore;
            userData.total_clicks = oldTotalClicks;
            userData.referrals = oldReferrals;
            userData.walletTaskCompleted = oldWalletTaskCompleted;
            userData.lastReferralTaskCompletion = oldLastReferralTaskCompletion;
            userData.energy = oldEnergy;
            userData.lastEnergyUpdate = oldLastEnergyUpdate;
            userData.upgrades = oldUpgrades;
            userData.ads_watched = oldAdsWatched;
          }
          // После сохранения обновляем топ
          await updateTopData();
        } else {
          console.error('Error saving user data');
        }
      } catch (error) {
        console.error('Error saving user data:', error);
      }
    }
    
    // Функция для обновления отображения счета
    function updateScoreDisplay() {
      const scoreDisplay = document.getElementById('score');
      if(scoreDisplay.firstChild) {
        scoreDisplay.firstChild.textContent = 'Счет: ' + userData.score;
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
      top: document.getElementById('top')
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
        checkReferralTask();
        checkAdsTask();
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
          userData.walletAddress ? formatWalletAddress(userData.walletAddress) : 'Не подключен';
        
        // Обновляем текст кнопки TonConnect
        document.getElementById('ton-connect-button').textContent = 
          userData.walletAddress ? 'Отключить кошелек' : 'Подключить кошелек';
        
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
        document.getElementById('levelProgressText').textContent = `Уровень: ${currentLevel.name} (${score - currentLevelScore}/${nextLevelScore - currentLevelScore})`;
      } else {
        // Если достигнут максимальный уровень
        document.getElementById('levelProgressBar').style.width = '100%';
        document.getElementById('levelProgressText').textContent = `Уровень: ${currentLevel.name}`;
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
      // Убедимся, что ads_watched существует
      if (typeof userData.ads_watched === 'undefined') {
        userData.ads_watched = 0;
      }
      
      // Обновляем счетчик просмотренной рекламы
      document.getElementById('ads-count-value').textContent = userData.ads_watched;
      
      // Задание без отката, всегда доступно
      if (userData.ads_watched >= 10) {
        // Задание доступно для получения награды
        document.getElementById('ads-task-button').textContent = 'Получить награду';
        document.getElementById('ads-task-button').disabled = false;
        document.getElementById('ads-task-button').style.display = 'block';
        document.getElementById('ads-task-status').style.display = 'none';
      } else {
        // Задание не выполнено
        document.getElementById('ads-task-button').textContent = 'НАЧАТЬ';
        document.getElementById('ads-task-button').disabled = false;
        document.getElementById('ads-task-button').style.display = 'block';
        document.getElementById('ads-task-status').style.display = 'none';
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
      if (userData.ads_watched < 10) return;
      
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
    
    // Просмотр рекламы через Adsgram
    function watchAds() {
      if (!adsgramAd) {
        showNotification('Реклама не загружена');
        return;
      }
      
      // Показываем рекламу
      adsgramAd.show().then(() => {
        // Реклама успешно показана
        console.log('Ad shown successfully');
      }).catch((error) => {
        // Ошибка при показе рекламы
        console.error('Error showing ad:', error);
        showNotification('Ошибка при показе рекламы');
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
          showNotification('Ссылка скопирована в буфер обмена!');
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
      
      showNotification('Выберите чат для отправки ссылки');
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
    
    // Открытие модального окна задания с рефералами
    function openReferralTaskModal() {
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
        
        upgradeElement.innerHTML = `
          <img class="upgrade-image" src="${upgrade.image}" alt="Улучшение">
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
        showNotification('Улучшение уже куплено!');
        return;
      }
      
      // Проверяем, достаточно ли монет
      if (userData.score < upgrade.cost) {
        showNotification('Недостаточно монет!');
        return;
      }
      
      // Списываем стоимость
      userData.score -= upgrade.cost;
      
      // Добавляем улучшение в список купленных
      userData.upgrades.push(upgradeId);
      
      // Сохраняем данные
      await saveUserData();
      
      // Обновляем интерфейс
      updateScoreDisplay();
      updateBonuses();
      renderUpgrades();
      
      // Показываем уведомление
      showNotification(`Вы купили улучшение!`);
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
      }
      
      // Обработчик для кнопок меню
      document.querySelectorAll('#bottom-menu button').forEach(button => {
        button.addEventListener('click', function() {
          const pageKey = this.getAttribute('data-page');
          showPage(pageKey);
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
      
      // Увеличиваем счет с учетом бонуса
      userData.score += (1 + clickBonus);
      userData.total_clicks++;
      
      // Создаем эффект молнии
      createLightning();
      
      // Обновляем отображение
      updateScoreDisplay();
      updateEnergyDisplay();
      updateLevel();
      
      // Сохраняем данные на сервере после каждого клика
      saveUserData();
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
                "referrals": user_data["referrals"],
                "lastReferralTaskCompletion": user_data["last_referral_task_completion"],
                "energy": user_data["energy"],
                "lastEnergyUpdate": user_data["last_energy_update"],
                "upgrades": user_data["upgrades"],
                "ads_watched": user_data["ads_watched"]
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
                    "referrals": user_data["referrals"],
                    "lastReferralTaskCompletion": user_data["last_referral_task_completion"],
                    "energy": user_data["energy"],
                    "lastEnergyUpdate": user_data["last_energy_update"],
                    "upgrades": user_data["upgrades"],
                    "ads_watched": user_data["ads_watched"]
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

@app.get("/debug/users")
async def debug_users():
    """Эндпоинт для отладки - просмотр всех пользователей"""
    try:
        logger.info(f"GET /debug/users endpoint called")
        
        if supabase is None:
            return JSONResponse(content={"status": "error", "message": "Supabase client is not initialized"})
        
        response = supabase.table("users").select("user_id, first_name, last_name, score, level").order("score", desc=True).limit(50).execute()
        
        if response.data:
            logger.info(f"Found {len(response.data)} users")
            return JSONResponse(content={"users": response.data})
        else:
            logger.info(f"No users found")
            return JSONResponse(content={"users": []})
    except Exception as e:
        logger.error(f"Error in GET /debug/users: {e}")
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





@app.get("/adsgram-reward")
