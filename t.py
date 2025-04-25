from pynput import keyboard
import datetime
import os

# Путь к файлу, куда будут сохраняться записи
log_file = os.path.expanduser("~/Desktop/keyboard_log.txt")


def write_to_file(key):
    try:
        # Получаем текущую дату и время
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        # Преобразуем нажатие клавиши в строку
        key_str = str(key).replace("'", "")

        # Обрабатываем специальные клавиши
        if key_str.startswith("Key."):
            key_str = f"[{key_str}]"
        else:
            key_str = key_str

        # Записываем в файл
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(f"{timestamp}: {key_str}\n")

    except Exception as e:
        print(f"Ошибка при записи: {e}")


def on_press(key):
    try:
        write_to_file(key)
    except Exception as e:
        print(f"Ошибка: {e}")


def on_release(key):
    # Останавливаем программу при нажатии Esc
    if key == keyboard.Key.esc:
        return False


# Запускаем слушатель клавиатуры
print("Начало записи нажатий клавиш. Нажмите Esc, чтобы остановить.")
with keyboard.Listener(on_press=on_press, on_release=on_release) as listener:
    listener.join()
print("Запись остановлена. Проверьте файл на рабочем столе: keyboard_log.txt")