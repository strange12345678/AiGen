import asyncio
import base64
import io
import logging
import os
import signal

import google.generativeai as genai
from telegram import Update, BotCommand
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from PIL import Image
from aiohttp import web

# --- Configuration ---
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
PORT = int(os.environ.get('PORT', 8080))

# --- Set up Logging ---
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- Configure the Gemini API ---
try:
    if not GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY environment variable not set.")
    genai.configure(api_key=GEMINI_API_KEY)
    logger.info("Gemini API configured successfully.")
except Exception as e:
    logger.error(f"Failed to configure Gemini API: {e}")
    exit()

# --- Bot Command Handlers (No changes in this section) ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_name = update.effective_user.first_name
    welcome_message = (
        f"👋 Hi {user_name}!\n\n"
        "I'm an image generation bot. Just send me a text description, "
        "and I'll create an image for you.\n\n"
        "For example, try sending:\n"
        "🎨 `A futuristic cityscape at sunset`\n"
        "🚀 `A corgi astronaut floating in space`"
    )
    await update.message.reply_text(welcome_message)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    help_text = (
        "Here's how to use me:\n\n"
        "1. Simply type a description of the image you want to create.\n"
        "2. I will generate it and send it back to you.\n\n"
        "Tips for good prompts:\n"
        "✅ Be descriptive! (e.g., 'A hyperrealistic photo of a red sports car...')\n"
        "✅ Include styles (e.g., 'in the style of Van Gogh', 'as a 3D render').\n"
        "✅ Mention lighting or mood (e.g., 'dramatic lighting', 'a peaceful morning')."
    )
    await update.message.reply_text(help_text)

async def generate_image(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    prompt = update.message.text
    if not prompt:
        return

    chat_id = update.effective_chat.id
    logger.info(f"Received prompt from chat {chat_id}: '{prompt}'")

    processing_message = await context.bot.send_message(
        chat_id=chat_id,
        text="🎨 Generating your image, please wait a moment..."
    )

    try:
        model = genai.GenerativeModel('imagen-3.0-generate-002')
        response = await model.generate_content_async(prompt, generation_config={"sample_count": 1})
        
        base64_image_data = response.candidates[0].content.parts[0].inline_data.data
        image_bytes = base64.b64decode(base64_image_data)
        
        img = Image.open(io.BytesIO(image_bytes))
        if img.mode != 'RGB':
            img = img.convert('RGB')

        bio = io.BytesIO()
        bio.name = 'image.jpeg'
        img.save(bio, 'JPEG')
        bio.seek(0)

        await context.bot.send_photo(chat_id=chat_id, photo=bio)

    except Exception as e:
        logger.error(f"An error occurred during image generation or sending: {e}")
        error_message = (
            "😥 Sorry, something went wrong.\n\n"
            "This could be because the prompt was unsafe or the service is busy. "
            "Please try a different prompt."
        )
        await context.bot.send_message(chat_id=chat_id, text=error_message)
    finally:
        await context.bot.delete_message(
            chat_id=chat_id,
            message_id=processing_message.message_id
        )

async def post_init(application: Application):
    await application.bot.set_my_commands([
        BotCommand('/start', 'Start the bot'),
        BotCommand('/help', 'Get help and tips'),
    ])
    logger.info("Custom bot commands have been set.")
    
# --- Web Server for Render Health Check ---
async def health_check(request):
    return web.Response(text="OK")

# <<< CHANGE: MODIFIED MAIN FUNCTION AND SHUTDOWN LOGIC >>>
async def main() -> None:
    """Set up and run the bot and web server."""
    if not TELEGRAM_TOKEN:
        logger.error("!!! TELEGRAM_TOKEN environment variable not set !!!")
        return

    # Create the Telegram Application
    application = Application.builder().token(TELEGRAM_TOKEN).post_init(post_init).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, generate_image))

    # Set up the web server
    app = web.Application()
    app.router.add_get("/health", health_check)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', PORT)

    # Get the current asyncio event loop
    loop = asyncio.get_running_loop()

    # A function to handle graceful shutdown
    async def shutdown(sig):
        logger.info(f"Received exit signal {sig.name}...")
        logger.info("Stopping web server...")
        await runner.cleanup()
        logger.info("Stopping bot...")
        await application.updater.stop()
        await application.stop()
        logger.info("Cancelling pending tasks...")
        tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
        [task.cancel() for task in tasks]
        await asyncio.gather(*tasks, return_exceptions=True)
        loop.stop()

    # Add signal handlers for graceful shutdown
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, lambda sig=sig: asyncio.create_task(shutdown(sig)))

    # Start everything
    try:
        logger.info(f"Starting web server on port {PORT}...")
        await site.start()
        logger.info("Starting bot polling...")
        await application.initialize()
        await application.start()
        await application.updater.start_polling()
        
        # Keep the main task running
        while True:
            await asyncio.sleep(3600) # Sleep for a long time

    except (KeyboardInterrupt, SystemExit):
        logger.info("Shutdown initiated by user.")
    except Exception as e:
        logger.critical(f"An unhandled exception occurred: {e}")
    finally:
        logger.info("Application is shutting down.")
        # The shutdown logic will be handled by the signal handler

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except RuntimeError as e:
        if "Cannot run the event loop while another loop is running" in str(e):
             logger.warning("Event loop is already running. This is normal in some environments.")
        else:
            raise
