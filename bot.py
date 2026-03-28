import telebot
import os

# Вставь сюда НОВЫЙ токен (БЕЗ кавычек %)
BOT_TOKEN = "8135298684:AAGaOUd-THoiNkZpSE7m9xxi799v-M6fjeI"

bot = telebot.TeleBot(BOT_TOKEN)

@bot.message_handler(commands=['start'])
def send_welcome(message):
    # Отправляем сообщение с кнопкой или просто ссылку
    bot.send_message(message.chat.id, "Привет жирный толстый пухлый, твоя ссылка: https://t.me/Fnmby_bot/Femboyleggs_bot")

# ЭТОЙ СТРОКИ НЕ ХВАТАЛО - ОНА ЗАПУСКАЕТ БОТА
if __name__ == '__main__':
    print("Бот запущен...")
    bot.infinity_polling()
