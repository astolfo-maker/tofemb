from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")

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
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      font-family: 'Comic Neue', cursive, Arial, sans-serif;
      user-select: none;
      color: #fff;
      text-shadow: 0 0 5px #ff77cc;
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
      -webkit-tap-highlight-color: transparent; /* Убираем подсветку при тапе */
    }
    #circle img {
      width: 100%;
      height: 100%;
      object-fit: cover;
      border-radius: 50%;
      pointer-events: none;
      user-select: none;
    }
    /* Стиль для эффекта нажатия */
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
    }
    #coin {
      width: 50px;
      height: 50px;
      user-select: none;
      box-shadow: 0 8px 70px rgba(255, 102, 204, 0.6);
    }
  </style>
</head>
<body>

  <div id="circle" tabindex="0" role="button" aria-pressed="false">
    <img id="femboyImg" src="/static/Photo_femb_static.jpg" alt="фембой" />
  </div>
  <div id="score">
    Счет: 0
    <img id="coin" src="/static/FemboyCoinsPink.png" alt="монетки" />
  </div>

  <script>
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
  // Текстность у score - это текстовый узел (firstChild)
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

  // Мышь
  circle.addEventListener('mousedown', (e) => {
    // чтобы сработало не только левое, но и touch emulate
    if (e.button === 0) { 
      pressVisualOn();
      incrementScore();
    }
  });
  circle.addEventListener('mouseup', pressVisualOff);
  circle.addEventListener('mouseleave', pressVisualOff);

  // Тач события

  circle.addEventListener('touchstart', (e) => {
    e.preventDefault(); // Отключаем эмуляцию mouse events, чтобы не дублировать
    pressVisualOn();
    incrementScore();
  }, {passive:false});
  circle.addEventListener('touchend', (e) => {
    pressVisualOff();
  });

  // На всякий случай keyboard support (если кто-то нажмет Enter или пробел на div)

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