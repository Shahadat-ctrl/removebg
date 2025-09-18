import logging
import io
import requests
import asyncio

from telegram import Update, InputFile, ReplyKeyboardMarkup, KeyboardButton, ChatAction
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
STATE_WAITING_FOR_IMAGE = 'waiting_for_image'

# --- Logging ---
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

def get_main_keyboard():
    keyboard = [[KeyboardButton(BTN_REMOVE_BACKGROUND)]]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)

# --- Commands ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop(STATE_WAITING_FOR_IMAGE, None)
    await update.message.reply_text(
        "Hello! I'm your Background Remover Bot.\n"
        f"Tap the '{BTN_REMOVE_BACKGROUND}' button to begin.",
        reply_markup=get_main_keyboard()
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop(STATE_WAITING_FOR_IMAGE, None)
    await update.message.reply_text(
        "How to use me:\n"
        f"1. Tap '{BTN_REMOVE_BACKGROUND}'.\n"
        "2. Send me an image.\n"
        "3. I will return the background removed PNG.\n\n"
        "Powered by remove.bg",
        reply_markup=get_main_keyboard()
    )

async def handle_remove_bg_button_press(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data[STATE_WAITING_FOR_IMAGE] = True
    await update.message.reply_text(
        "Okay, please send me the image you want to process now.",
        reply_markup=get_main_keyboard()
    )

# --- Handle Photo ---
async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    user_id = update.effective_user.id

    if context.user_data.get(STATE_WAITING_FOR_IMAGE) is True:
        logger.info(f"User {user_id} sent a photo. Processing...")

        # Typing message
        processing_msg = await message.reply_text("Processing your image...")

        try:
            # --- Download Image ---
            await context.bot.send_chat_action(chat_id=message.chat_id, action=ChatAction.UPLOAD_PHOTO)

            photo_file_id = message.photo[-1].file_id
            photo_file_obj = await context.bot.get_file(photo_file_id)
            image_byte_array = await photo_file_obj.download_as_bytearray()
            image_bytes_io = io.BytesIO(image_byte_array)
            image_bytes_io.name = "input.jpg"

            # --- Call remove.bg ---
            headers = {'X-Api-Key': REMOVE_BG_API_KEY}
            files_payload = {'image_file': image_bytes_io}
            data_payload = {'format': 'png', 'size': 'auto'}

            response = requests.post(REMOVE_BG_API_URL, headers=headers, files=files_payload, data=data_payload, timeout=45)
            response.raise_for_status()
            processed_image_bytes = response.content

            # --- Send Result ---
            await processing_msg.edit_text("✅ Processing completed! Sending your result...")

            await context.bot.send_document(
                chat_id=message.chat_id,
                document=InputFile(io.BytesIO(processed_image_bytes), filename="bg_removed.png"),
                caption="Here’s your image with background removed.",
                reply_markup=get_main_keyboard()
            )

        except Exception as e:
            logger.error(f"Error: {e}", exc_info=True)
            await processing_msg.edit_text("❌ An error occurred while processing your image. Please try again.")

        finally:
            context.user_data[STATE_WAITING_FOR_IMAGE] = False
    else:
        await message.reply_text(
            f"Please tap '{BTN_REMOVE_BACKGROUND}' first before sending an image.",
            reply_markup=get_main_keyboard()
        )

# --- Handle Other ---
async def handle_other_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get(STATE_WAITING_FOR_IMAGE) is True:
        await update.message.reply_text(
            "I'm waiting for an image. Please send a photo.",
            reply_markup=get_main_keyboard()
        )
    else:
        await update.message.reply_text(
            f"I'm a background remover bot. Please tap '{BTN_REMOVE_BACKGROUND}' to start.",
            reply_markup=get_main_keyboard()
        )

# --- Error Handler ---
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error(f"Update {update} caused error {context.error}", exc_info=context.error)
    if update and hasattr(update, "message") and update.message:
        try:
            await update.message.reply_text("Oops! Something went wrong. Please try /start again.")
        except:
            pass

# --- Main ---
def main():
    application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(MessageHandler(filters.TEXT & filters.Regex(f'^{BTN_REMOVE_BACKGROUND}$'), handle_remove_bg_button_press))
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_other_messages))
    application.add_error_handler(error_handler)

    application.run_polling()

if __name__ == "__main__":
    main()
