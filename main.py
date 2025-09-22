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
  <title>кружочек в стиле фембой</title>
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
      transition: transform 0.2s ease;
      display: flex;
      align-items: center;
      justify-content: center;
      overflow: hidden;
      background-color: transparent;
    }
    #circle img {
      width: 100%;
      height: 100%;
      object-fit: cover;
      border-radius: 50%;
      user-select: none;
      pointer-events: none;
    }
    #circle:active {
      transform: scale(0.95);
      box-shadow: 0 4px 12px rgba(255, 102, 204, 0.9);
    }
    #score {
      margin-top: 25px;
      font-size: 40px;
      font-weight: 700;
      text-shadow: 0 0 15px #ff66cc;
    }
  </style>
</head>
<body>

  <div id="circle">
    <img id="femboyImg" src="/static/femboy_normal.png" alt="фембой"/>
  </div>
  <div id="score">Счет: 0</div>

  <script>
    const circle = document.getElementById('circle');
    const img = document.getElementById('femboyImg');
    const scoreDisplay = document.getElementById('score');

    const imgNormal = "/static/femboy_normal.png";
    const imgActive = "/static/femboy_active.png";

    // Загружаем сохранённый счёт из localStorage или начинаем с 0
    let score = parseInt(localStorage.getItem('score')) || 0;
    scoreDisplay.textContent = 'Счет: ' + score;

    circle.addEventListener('click', () => {
      score++;
      scoreDisplay.textContent = 'Счет: ' + score;

      // Сохраняем счёт в localStorage
      localStorage.setItem('score', score);

      img.src = imgActive;
      setTimeout(() => {
        img.src = imgNormal;
      }, 500);
    });
  </script>

</body>
</html>
"""

@app.get("/", response_class=HTMLResponse)
async def root():
    return html_content