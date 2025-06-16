import os
import json
import requests
import time
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import tempfile
import aiohttp
import asyncio

# Get environment variables
BOT_TOKEN = os.getenv('BOT_TOKEN')
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
        # Create a temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file_name)[1]) as temp_file:
            # Download the file
            async with aiohttp.ClientSession() as session:
                async with session.get(file_url) as response:
                    if response.status == 200:
                        # Download in chunks to handle large files
                        with open(temp_file.name, 'wb') as f:
                            while True:
                                chunk = await response.content.read(8192)
                                if not chunk:
                                    break
                                f.write(chunk)
                        
                        # Send the file to the channel
                        await context.bot.send_document(
                            chat_id=TARGET_CHANNEL_ID,
                            document=open(temp_file.name, 'rb'),
                            filename=file_name
                        )
                        
                        # Clean up the temporary file
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
        # Construct player URL with video parameters
        video_url = result['direct_link']
        video_title = result['title']
        player_url = f'http://localhost:8000/player.html?url={video_url}&title={video_title}'
        
        # Start downloading and sending the file
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

def main():
    max_retries = 3
    retry_delay = 5  # seconds
    
    for attempt in range(max_retries):
        try:
            # Create application
            application = Application.builder().token(BOT_TOKEN).build()
    
            # Add handlers
            application.add_handler(CommandHandler("start", start))
            application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
            # Start the bot
            print(f"Bot is running... (Attempt {attempt + 1}/{max_retries})")
            application.run_polling()
            break
        except telegram.error.TimedOut:
            if attempt < max_retries - 1:
                print(f"Connection timed out. Retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)
            else:
                print("Failed to connect after multiple attempts. Please check your internet connection and bot token.")
                raise
        except Exception as e:
            print(f"Error: {str(e)}")
            raise

if __name__ == '__main__':
    main()
