from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

TOKEN = '8135298684:AAGaOUd-THoiNkZpSE7m9xxi799v-M6fjeI'

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text('приветствуем в империю пубертатников.')

def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler('start', start))

    app.run_polling()

if __name__ == '__main__':
    main()
    
    