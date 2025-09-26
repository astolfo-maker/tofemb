from fastapi import FastAPI, Request, Form
from fastapi.responses import RedirectResponse
import hmac
import hashlib
import time

app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")

TELEGRAM_BOT_TOKEN = "8135298684:AAGaOUd-THoiNkZpSE7m9xxi799v-M6fjeI"

@app.post("/auth/telegram")
async def telegram_auth(request: Request):
    data = await request.form()
    data_dict = dict(data)

    def check_auth(d):
        hash_ = d.pop('hash')
        data_check_str = '\n'.join(f"{k}={d[k]}" for k in sorted(d))
        secret_key = hashlib.sha256(TELEGRAM_BOT_TOKEN.encode()).digest()
        computed_hash = hmac.new(secret_key, data_check_str.encode(), hashlib.sha256).hexdigest()
        return hmac.compare_digest(computed_hash, hash_) and (int(d['auth_date']) > time.time() - 86400)

    if not check_auth(data_dict):
        return RedirectResponse("/")

    # Сохраняем данные в сессию или cookie
    user_id = data_dict['id']
    username = data_dict.get('username')
    photo_url = data_dict.get('photo_url')

    response = RedirectResponse("/profile")
    cookie_value = f"{user_id}|{username}|{photo_url}"
    response.set_cookie(key="telegram_user", value=cookie_value)
    return response

html_content = """
<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="UTF-8" />
  <title>ляжки фембоя</title>
  <style>
    @import url('https://fonts.googleapis.com/css2?family=Comic+Neue:wght@700&display=swap');

    body {
      margin: 0;
      height: 100vh;
      background: linear-gradient(135deg, #ff9a9e 0%, #fad0c4 50%, #a18cd1 100%);
      font-family: 'Comic Neue', cursive, Arial, sans-serif;
      user-select: none;
      color: #fff;
      text-shadow: 0 0 5px #ff77cc;
      display: flex;
      flex-direction: column;
      /* Отступ снизу для меню */
      padding-bottom: 60px;
      overflow-x: hidden;
    }

    /* Общий контейнер контента выше меню */
    #content {
      flex-grow: 1;
      display: flex;
      justify-content: center;
      align-items: center;
      position: relative;
    }

    /* Общие стили для всех окон */
    .page {
      display: none; /* по умолчанию скрыты */
      width: 100%;
      max-width: 400px;
      padding: 20px;
      box-sizing: border-box;
      text-align: center;
    }

    /* Активное окно */
    .active {
      display: block;
    }

    /* Кликер - можно оставить ваш существующий стиль */
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

    /* Нижнее меню */
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

    /* Пример оформления для окна профиля и заданий */
    #profile, #tasks {
      font-size: 18px;
      line-height: 1.5;
      user-select: text;
    }
  </style>
</head>
<body>

  <div id="content">
    <!-- Кликер (по умолчанию видим) -->
    <section id="clicker" class="page active" aria-label="Окно кликера">
      <div id="circle" tabindex="0" role="button" aria-pressed="false">
        <img id="femboyImg" src="/static/Photo_femb_static.jpg" alt="фембой" />
      </div>
      <div id="score" aria-live="polite">
        Счет: 0
        <img id="coin" src="/static/FemboyCoinsPink.png" alt="монетки" />
      </div>
    </section>

    

    <!-- Окно профиля -->
    <section id="profile" class="page" aria-label="Профиль нах"> 
      <h2>Профиль йоу</h2>
      <p>хз чет добавим</p>
      <p>Собранные монетки: <span id="profileScore">0</span></p>
      <p>чет добавим йоу но эт сложна капец йоу йоу йоу  чета долга делать йоу</p>
      <div id="telegram-login"></div> <!-- Добавьте сюда кнопку Telegram Login -->

<script async src="https://telegram.org/js/telegram-widget.js?15"
        data-telegram-login="Fnmby_bot"   <!-- <-- сюда ставьте username вашего бота, без @ -->
        data-size="large"
        data-userpic="true"
        data-auth-url="https://sturdy-space-doodle-p77g9v4xp5w27r5p-8000.app.github.dev/auth/telegram"             <!-- <-- URL на сервер, подробнее ниже -->
        data-request-access="write">
</script>
    </section>

    <!-- Окно заданий -->
    <section id="tasks" class="page" aria-label="задания нах">
      <h2>Задания</h2>
      <ul>
        <li>пасаси</li>
        <li>гунь на фембоеф, ну тут тупо вставлю кнопки, а в кнопкахь ссылки с рекламой</li>
        <li>скинь ножки</li>
      </ul>
    </section>
  </div>

  <nav id="bottom-menu" role="navigation" aria-label="Нижнее меню">
    <button id="btn-profile" aria-controls="profile" aria-selected="false" tabindex="0">Профиль нах</button>
    <button id="btn-clicker" aria-controls="clicker" aria-selected="true" tabindex="0" class="active">Кликер нах</button>
    <button id="btn-tasks" aria-controls="tasks" aria-selected="false" tabindex="0">Задания нах</button>
  </nav>

  <script>
    // Переключение страниц по кнопкам меню
    const pages = {
      profile: document.getElementById('profile'),
      clicker: document.getElementById('clicker'),
      tasks: document.getElementById('tasks')
    };

    const buttons = {
      profile: document.getElementById('btn-profile'),
      clicker: document.getElementById('btn-clicker'),
      tasks: document.getElementById('btn-tasks')
    };

    function showPage(pageKey) {
      // Скрываем все окна
      Object.values(pages).forEach(el => el.classList.remove('active'));
      // Показываем выбранное окно
      pages[pageKey].classList.add('active');

      // Обновляем кнопки - только у активной active и aria-selected=true
      Object.entries(buttons).forEach(([key, btn]) => {
        if (key === pageKey) {
          btn.classList.add('active');
          btn.setAttribute('aria-selected', 'true');
          btn.setAttribute('tabindex', '0');
        } else {
          btn.classList.remove('active');
          btn.setAttribute('aria-selected', 'false');
          btn.setAttribute('tabindex', '-1');
        }
      });

      // При открытии профиля обновим счет там
      if (pageKey === 'profile') {
        const score = localStorage.getItem('femboyScore') || 0;
        document.getElementById('profileScore').textContent = score;
      }
    }

    // Вешаем обработчики на кнопки
    for (const [key, btn] of Object.entries(buttons)) {
      btn.addEventListener('click', () => {
        showPage(key);
      });
    }

    // --- Ваш существующий код для клика ---

    const circle = document.getElementById('circle');
    const img = document.getElementById('femboyImg');
    const scoreDisplay = document.getElementById('score');

    const imgNormal = "/static/Photo_femb_static.jpg";
    const imgActive = "https://i.pinimg.com/736x/88/b3/b6/88b3b6e1175123e5c990931067c4b055.jpg";

    let score = localStorage.getItem('femboyScore');
    if (!score) {
      score = 0;
    } else {
      score = parseInt(score);
    }
    if(scoreDisplay.firstChild) {
      scoreDisplay.firstChild.textContent = 'Счет: ' + score;
    }

    function incrementScore() {
      score++;
      if(scoreDisplay.firstChild) {
        scoreDisplay.firstChild.textContent = 'Счет: ' + score;
      }
      localStorage.setItem('femboyScore', score);
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

  </script>

</body>
</html>
"""

@app.get("/", response_class=HTMLResponse)
async def root():
    return html_content