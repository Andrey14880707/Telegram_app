import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes

# Вставьте ваш токен доступа сюда
TOKEN = '7249695336:AAFELK_6plwS7pt2G9QvoS8BFjZ1LYIZADM'

# Включите логирование
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Обработчик команды /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.message.from_user
    logger.info("User %s started the conversation.", user.first_name)

    # Создаем кнопку для открытия веб-приложения
    keyboard = [
        [InlineKeyboardButton("Open App", url="https://t.me/CondomCoin_bot/Condom")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text('Welcome! Click the button below to open the app:', reply_markup=reply_markup)

def main() -> None:
    """Запуск бота."""
    # Инициализация приложения
    application = Application.builder().token(TOKEN).build()

    # Добавляем обработчик команды /start
    application.add_handler(CommandHandler("start", start))

    # Запускаем бота
    application.run_polling()

if __name__ == '__main__':
    main()

