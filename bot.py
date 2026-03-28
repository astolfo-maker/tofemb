 import telebot; 
bot = telebot.TeleBot('%8135298684:AAGaOUd-THoiNkZpSE7m9xxi799v-M6fjeI%');

@bot.message_handler(content_types=['text']) 
def get_text_messages(message):
    if message.text == "/start": 
        bot.send_message(message.from_user.id, "https://t.me/Fnmby_bot/Femboyleggs_bot") 
