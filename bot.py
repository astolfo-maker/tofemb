import telebot
import os
from flask import Flask, request

# 1. Настройка Flask (Чтобы Render не падал)
app = Flask(__name__)


BOT_TOKEN = "8135298684:AAGaOUd-THoiNkZpSE7m9xxi799v-M6fjeI"

bot = telebot.TeleBot(BOT_TOKEN)

# 2. Логика бота
@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.send_message(message.chat.id, "Привет жирный толстый пухлый. Вот твоя ссылка: https://t.me/Fnmby_bot/Femboyleggs_bot")

# 3. Route для Render (чтобы он думал, что это сайт)
@app.route('/')
def index():
    return "Бот работает!"

# 4. Запуск
if __name__ == '__main__':
    # Запускаем бота в отдельном потоке, чтобы не мешать Flask
    import threading
    threading.Thread(target=bot.infinity_polling, daemon=True).start()
    
    # Запускаем Flask на порту Render
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, use_reloader=False)
