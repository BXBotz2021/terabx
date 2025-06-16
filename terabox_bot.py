import os
import json
import requests
import time
import tempfile
import aiohttp
import asyncio
import telegram  # Needed for error handling

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

# Get environment variables
BOT_TOKEN = os.getenv('BOT_TOKEN') or '7797507155:AAGB6NG4tzxzxU_IYZrpkX8g-nLcIGYJtXw'
TARGET_CHANNEL_ID = int(os.getenv('TARGET_CHANNEL_ID', '-1002598011167'))

# Terabox API URL
TERABOX_API = 'https://terabox-pro-api.vercel.app/api'

# Supported Terabox domains
TERABOX_DOMAINS = ['teraboxlink.com', '1024terabox.com']

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_message = (
        "Welcome! 👋\n\n"
        "I can help you generate direct download links from Terabox links.\n"
        "Just send me a Terabox link and I'll convert it for you.\n\n"
        "Supported domains:\n"
        "- teraboxlink.com\n"
        "- 1024terabox.com"
    )
    await update.message.reply_text(welcome_message)

def is_valid_terabox_link(url: str) -> bool:
    return any(domain in url.lower() for domain in TERABOX_DOMAINS)

def get_direct_link(terabox_url: str) -> dict:
    try:
        response = requests.get(f'{TERABOX_API}?link={terabox_url}')
        response.raise_for_status()
        data = response.json()

        if data.get('status') == '✅ Success' and data.get('📋 Extracted Info'):
            info = data['📋 Extracted Info'][0]
            return {
                'success': True,
                'title': info.get('📄 Title', 'Unknown'),
                'size': info.get('📦 Size', 'Unknown'),
                'direct_link': info.get('🔗 Direct Download Link', '')
            }
        return {'success': False, 'error': 'Failed to extract information'}
    except Exception as e:
        return {'success': False, 'error': str(e)}

async def download_and_send_file(context: ContextTypes.DEFAULT_TYPE, file_url: str, file_name: str):
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file_name)[1]) as temp_file:
            async with aiohttp.ClientSession() as session:
                async with session.get(file_url) as response:
                    if response.status == 200:
                        with open(temp_file.name, 'wb') as f:
                            while True:
                                chunk = await response.content.read(8192)
                                if not chunk:
                                    break
                                f.write(chunk)
                        await context.bot.send_document(
                            chat_id=TARGET_CHANNEL_ID,
                            document=open(temp_file.name, 'rb'),
                            filename=file_name
                        )
                        os.unlink(temp_file.name)
                        return True
                    else:
                        return False
    except Exception as e:
        print(f"Error downloading/sending file: {str(e)}")
        return False

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message.text

    if not is_valid_terabox_link(message):
        await update.message.reply_text(
            "❌ Please send a valid Terabox link from supported domains:\n"
            "- teraboxlink.com\n"
            "- 1024terabox.com"
        )
        return

    await update.message.reply_text("🔄 Processing your link...")
    result = get_direct_link(message)

    if result['success']:
        video_url = result['direct_link']
        video_title = result['title']
        player_url = f'http://localhost:8000/player.html?url={video_url}&title={video_title}'

        await update.message.reply_text("📥 Starting download and upload to channel...")
        download_success = await download_and_send_file(context, video_url, video_title)

        response_text = (
            f"✅ Successfully processed!\n\n"
            f"📁 File: {result['title']}\n"
            f"📦 Size: {result['size']}\n\n"
            f"🔗 Direct Download Link:\n{result['direct_link']}\n\n"
            f"🎥 Watch Online:\n{player_url}\n\n"
        )

        if download_success:
            response_text += "✅ File has been uploaded to the channel successfully!"
        else:
            response_text += "❌ Failed to upload file to the channel. Please try again later."
    else:
        response_text = f"❌ Error: {result['error']}\n\nPlease try again later."

    await update.message.reply_text(response_text)

async def run_bot():
    max_retries = 3
    retry_delay = 5

    for attempt in range(max_retries):
        try:
            application = Application.builder().token(BOT_TOKEN).build()
            application.add_handler(CommandHandler("start", start))
            application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

            print(f"Bot is running... (Attempt {attempt + 1}/{max_retries})")
            await application.run_polling()
            break
        except telegram.error.TimedOut:
            if attempt < max_retries - 1:
                print(f"Connection timed out. Retrying in {retry_delay} seconds...")
                await asyncio.sleep(retry_delay)
            else:
                print("Failed to connect after multiple attempts.")
                raise
        except Exception as e:
            print(f"Error: {e}")
            raise

def main():
    asyncio.run(run_bot())

if __name__ == '__main__':
    main()
