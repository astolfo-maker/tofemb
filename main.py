from pathlib import Path
from fastapi import FastAPI, Request, HTTPException, Depends
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
from pydantic import BaseModel, Field
from fastapi_cache import FastAPICache, Coder
from fastapi_cache.backends.redis import RedisBackend
from fastapi_cache.decorator import cache
from redis import asyncio as aioredis
import asyncio

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
redis_url = os.environ.get("REDIS_URL", "redis://localhost")

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

# Pydantic модели для валидации данных
class UserData(BaseModel):
    id: str
    first_name: str
    last_name: str = ""
    username: str = ""
    photo_url: str = ""
    score: int = 0
    total_clicks: int = 0
    walletAddress: str = ""
    walletTaskCompleted: bool = False
    referrals: List[str] = []
    lastReferralTaskCompletion: Optional[str] = None
    energy: int = 250
    lastEnergyUpdate: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    upgrades: List[str] = []

class ReferralData(BaseModel):
    referrer_id: str
    referred_id: str

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
    supabase = None

# Максимальное количество энергии
MAX_ENERGY = 250

# Декоратор для повторных попыток при ошибках соединения
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception_type((requests.exceptions.RequestException, Exception))
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
            
            # Обновляем уровень на основе очков
            user_data['level'] = get_level_by_score(user_data.get('score', 0))
            
            # Восстанавливаем энергию на основе времени последнего обновления
            last_energy_update = user_data.get('last_energy_update')
            if last_energy_update:
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
                    
                    # Убедимся, что дата имеет timezone
                    if last_update_time.tzinfo is None:
                        last_update_time = last_update_time.replace(tzinfo=timezone.utc)
                    
                    current_time = datetime.now(timezone.utc)
                    time_diff_seconds = (current_time - last_update_time).total_seconds()
                    
                    # Восстанавливаем энергию (1 единица в секунду)
                    current_energy = user_data.get('energy', MAX_ENERGY)
                    restored_energy = min(MAX_ENERGY, current_energy + int(time_diff_seconds))
                    
                    # Обновляем энергию и время последнего обновления
                    user_data['energy'] = restored_energy
                    user_data['last_energy_update'] = current_time.isoformat()
                except Exception as e:
                    logger.error(f"Error restoring energy: {e}")
                    # Устанавливаем значения по умолчанию при ошибке
                    user_data['energy'] = MAX_ENERGY
                    user_data['last_energy_update'] = datetime.now(timezone.utc).isoformat()
            else:
                # Если время последнего обновления отсутствует
                user_data['energy'] = MAX_ENERGY
                user_data['last_energy_update'] = datetime.now(timezone.utc).isoformat()
            
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
            "upgrades": user_data.get('upgrades', [])
        }
        
        # Проверяем, что все обязательные поля заполнены
        if not db_data["user_id"]:
            logger.error("User ID is required")
            return False
        
        def query():
            # Используем upsert для атомарной вставки или обновления
            return supabase.table("users").upsert(
                db_data, 
                on_conflict="user_id"
            ).execute()
        
        response = execute_supabase_query(query)
        
        if response.data:
            logger.info(f"Save operation completed with data: {response.data}")
            return True
        else:
            logger.error("Save operation failed: no data returned")
            return False
    except Exception as e:
        logger.error(f"Error saving user: {e}")
        return False

# Функция для получения топа пользователей
@cache(expire=60)  # Кэшировать на 60 секунд
def get_top_users(limit: int = 100) -> List[Dict[str, Any]]:
    if supabase is None:
        logger.error("Supabase client is not initialized")
        return []
        
    try:
        logger.info(f"Getting top {limit} users")
        
        def query():
            return supabase.table("users").select(
                "user_id, first_name, last_name, username, photo_url, score, level"
            ).order("score", desc=True).limit(limit).execute()
        
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
        
        # Проверяем, что реферер существует
        def referrer_query():
            return supabase.table("users").select("*").eq("user_id", referrer_id).execute()
        
        referrer_response = execute_supabase_query(referrer_query)
        
        if not referrer_response.data or len(referrer_response.data) == 0:
            logger.info(f"Referrer not found: {referrer_id}")
            return False
        
        # Проверяем, что реферал еще не добавлен
        referrals = referrer_response.data[0].get("referrals", [])
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

# Инициализация кэша при запуске
@app.on_event("startup")
async def startup():
    try:
        redis = aioredis.from_url(redis_url)
        FastAPICache.init(RedisBackend(redis), prefix="fastapi-cache")
        logger.info("Redis cache initialized successfully")
    except Exception as e:
        logger.warning(f"Failed to initialize Redis cache: {e}. Using in-memory cache instead.")
        # Если Redis недоступен, используем in-memory кэш
        from fastapi_cache.backends.inmemory import InMemoryBackend
        FastAPICache.init(InMemoryBackend(), prefix="fastapi-cache")

# Эндпоинт для получения данных пользователя
@app.get("/user/{user_id}")
async def get_user_data(user_id: str):
    """Получение данных пользователя по ID"""
    try:
        logger.info(f"GET /user/{user_id} endpoint called")
        
        if not user_id:
            return JSONResponse(content={"status": "error", "message": "User ID is required"}, status_code=400)
            
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
                "upgrades": user_data["upgrades"]
            }
            
            logger.info(f"Returning user data for {user_data['first_name']}")
            return JSONResponse(content={"user": response_data})
        else:
            logger.info(f"User not found with ID {user_id}")
            return JSONResponse(content={"status": "error", "message": "User not found"}, status_code=404)
    except Exception as e:
        logger.error(f"Error in /user/{user_id}: {e}")
        return JSONResponse(content={"status": "error", "message": str(e)}, status_code=500)

# Эндпоинт для сохранения данных пользователя
@app.post("/user")
async def save_user_data(user_data: UserData):
    """Сохранение данных пользователя на сервере"""
    try:
        logger.info(f"POST /user endpoint called")
        
        # Сохраняем в базу данных
        success = save_user(user_data.dict())
        
        if success:
            # Получаем обновленные данные
            user_id = str(user_data.id)
            loaded_user_data = load_user(user_id)
            
            if loaded_user_data:
                # Преобразуем данные для фронтенда
                response_data = {
                    "id": loaded_user_data["user_id"],
                    "first_name": loaded_user_data["first_name"],
                    "last_name": loaded_user_data["last_name"],
                    "username": loaded_user_data["username"],
                    "photo_url": loaded_user_data["photo_url"],
                    "score": loaded_user_data["score"],
                    "total_clicks": loaded_user_data["total_clicks"],
                    "level": loaded_user_data["level"],
                    "walletAddress": loaded_user_data["wallet_address"],
                    "walletTaskCompleted": loaded_user_data["wallet_task_completed"],
                    "referrals": loaded_user_data["referrals"],
                    "lastReferralTaskCompletion": loaded_user_data["last_referral_task_completion"],
                    "energy": loaded_user_data["energy"],
                    "lastEnergyUpdate": loaded_user_data["last_energy_update"],
                    "upgrades": loaded_user_data["upgrades"]
                }
                
                logger.info(f"User saved successfully: {loaded_user_data['first_name']}")
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

# Эндпоинт для обработки реферальной ссылки
@app.post("/referral")
async def handle_referral(referral_data: ReferralData):
    """Обработка реферальной ссылки"""
    try:
        logger.info(f"POST /referral endpoint called")
        referrer_id = str(referral_data.referrer_id)
        referred_id = str(referral_data.referred_id)
        
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

# Эндпоинт для получения топа пользователей
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

# Эндпоинт для применения пассивного дохода
@app.post("/user/{user_id}/passive-income")
async def apply_passive_income(user_id: str):
    """Применение пассивного дохода к пользователю"""
    try:
        user_data = load_user(user_id)
        if not user_data:
            return JSONResponse(content={"status": "error", "message": "User not found"}, status_code=404)
        
        # Рассчитываем пассивный доход
        passive_income = 0
        for upgrade_id in user_data.get("upgrades", []):
            upgrade = next((u for u in UPGRADES if u["id"] == upgrade_id), None)
            if upgrade and upgrade.get("effect", {}).get("passiveIncome"):
                passive_income += upgrade["effect"]["passiveIncome"]
        
        if passive_income > 0:
            user_data["score"] += passive_income
            save_user(user_data)
            return JSONResponse(content={"status": "success", "passive_income": passive_income})
        
        return JSONResponse(content={"status": "success", "passive_income": 0})
    except Exception as e:
        logger.error(f"Error applying passive income: {e}")
        return JSONResponse(content={"status": "error", "message": str(e)}, status_code=500)

# Эндпоинт для отладки - просмотр всех пользователей
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

# Эндпоинт для отладки - просмотр уровней
@app.get("/debug/levels")
async def debug_levels():
    """Эндпоинт для отладки - просмотр уровней"""
    logger.info(f"GET /debug/levels endpoint called")
    return JSONResponse(content={"levels": LEVELS})

# Эндпоинт для TonConnect манифеста
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

# Основная страница с HTML
@app.get("/", response_class=HTMLResponse)
async def root():
    return HTMLResponse(content=html_content)

# Запуск приложения
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    logger.info(f"Starting server on port {port}")
    uvicorn.run(app, host="0.0.0.0", port=port)
