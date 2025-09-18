import logging
import io
import requests
from telegram import Update, InputFile, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

# --- Configuration ---
TELEGRAM_BOT_TOKEN = "7996065957:AAHXcXq7nFYMEsZMd_m7hyddqnbQebsltjM"
REMOVE_BG_API_KEY = "gvoeRyGciuGqfAY6i8Hm5SLc"
REMOVE_BG_API_URL = "https://api.remove.bg/v1.0/removebg"

# --- Constants ---
BTN_REMOVE_BACKGROUND = "🖼️ Remove Background"
STATE_WAITING_FOR_IMAGE = "waiting_for_image"

# --- Logging ---
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

def get_main_keyboard():
    keyboard = [[KeyboardButton(BTN_REMOVE_BACKGROUND)]]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)

# --- Handlers ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop(STATE_WAITING_FOR_IMAGE, None)
    await update.message.reply_text(
        f"Hello! I'm your Background Remover Bot.\nTap '{BTN_REMOVE_BACKGROUND}' to start.",
        reply_markup=get_main_keyboard()
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop(STATE_WAITING_FOR_IMAGE, None)
    await update.message.reply_text(
        f"How to use me:\n1. Tap '{BTN_REMOVE_BACKGROUND}'\n"
        "2. Send your image\n3. Get background removed PNG\nPowered by remove.bg",
        reply_markup=get_main_keyboard()
    )

async def handle_remove_bg_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data[STATE_WAITING_FOR_IMAGE] = True
    await update.message.reply_text(
        "Okay, send me the image now.",
        reply_markup=get_main_keyboard()
    )

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    message = update.message

    if not context.user_data.get(STATE_WAITING_FOR_IMAGE):
        await message.reply_text(
            f"Tap '{BTN_REMOVE_BACKGROUND}' first before sending an image.",
            reply_markup=get_main_keyboard()
        )
        return

    # Send typing action
    typing_msg = await message.reply_text("Processing your image, please wait...", reply_markup=get_main_keyboard())

    try:
        # Get largest photo
        photo_file = await context.bot.get_file(message.photo[-1].file_id)
        image_bytes = await photo_file.download_as_bytearray()
        image_io = io.BytesIO(image_bytes)
        image_io.name = photo_file.file_path.split('/')[-1] if photo_file.file_path else "input.jpg"

        # Send to remove.bg
        headers = {'X-Api-Key': REMOVE_BG_API_KEY}
        data = {'format': 'png', 'size': 'auto'}
        files = {'image_file': image_io}

        response = requests.post(REMOVE_BG_API_URL, headers=headers, files=files, data=data, timeout=45)
        response.raise_for_status()

        if 'image/png' not in response.headers.get('Content-Type', '').lower():
            error_text = response.content.decode('utf-8', errors='ignore')
            await typing_msg.edit_text(f"Error from remove.bg:\n{error_text[:500]}")
            return

        processed_bytes = response.content
        output_file = InputFile(io.BytesIO(processed_bytes), filename="bg_removed.png")

        # Edit typing message to final result
        await typing_msg.edit_text("Done! Sending your image...")
        await context.bot.send_document(chat_id=message.chat_id, document=output_file,
                                        caption="Here's your background-removed image!", reply_markup=get_main_keyboard())

    except requests.exceptions.RequestException as e:
        logger.error(f"Remove.bg request failed: {e}")
        await typing_msg.edit_text("Failed to process your image. Please try again later.")
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        await typing_msg.edit_text("An unexpected error occurred.")
    finally:
        context.user_data[STATE_WAITING_FOR_IMAGE] = False

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get(STATE_WAITING_FOR_IMAGE):
        await update.message.reply_text("Please send a photo to process, not text.", reply_markup=get_main_keyboard())
    else:
        await update.message.reply_text(f"Tap '{BTN_REMOVE_BACKGROUND}' to start.", reply_markup=get_main_keyboard())

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Update {update} caused error {context.error}", exc_info=context.error)
    if update and hasattr(update, 'message') and update.message:
        await update.message.reply_text("Oops! Something went wrong. Use /start to try again.", reply_markup=get_main_keyboard())

# --- Main ---
def main():
    logger.info("Starting bot...")
    application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(MessageHandler(filters.TEXT & filters.Regex(f'^{BTN_REMOVE_BACKGROUND}$'), handle_remove_bg_button))
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    application.add_handler(MessageHandler(~filters.TEXT & ~filters.PHOTO & ~filters.COMMAND, handle_text))
    application.add_error_handler(error_handler)

    logger.info("Bot polling started...")
    application.run_polling()

if __name__ == "__main__":
    main()
