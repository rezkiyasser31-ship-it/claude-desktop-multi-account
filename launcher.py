import os
import sys
import json
import ctypes
import subprocess
import time
import psutil
from typing import Optional, List, Dict, Tuple

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROFILES_DIR = os.path.join(BASE_DIR, "profiles")
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")
ICON_PATH = os.path.join(BASE_DIR, "icon.ico")

os.makedirs(PROFILES_DIR, exist_ok=True)

user32 = ctypes.windll.user32

SW_RESTORE = 9
SW_SHOW = 5
SPI_GETWORKAREA = 0x0030

class RECT(ctypes.Structure):
    _fields_ = [
        ("left", ctypes.c_long),
        ("top", ctypes.c_long),
        ("right", ctypes.c_long),
        ("bottom", ctypes.c_long)
    ]

def get_browser_path() -> Tuple[str, str]:
    """Finds preferred browser: Brave first, then Edge fallback."""
    brave_paths = [
        r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe",
        r"C:\Program Files (x86)\BraveSoftware\Brave-Browser\Application\brave.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\BraveSoftware\Brave-Browser\Application\brave.exe")
    ]
    for p in brave_paths:
        if os.path.exists(p):
            return p, "brave"

    edge_paths = [
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\Edge\Application\msedge.exe"),
    ]
    for p in edge_paths:
        if os.path.exists(p):
            return p, "edge"

    raise FileNotFoundError("Neither Brave nor Edge was found on this system.")

def get_profile_dir(account_id: str) -> str:
    path = os.path.join(PROFILES_DIR, account_id)
    os.makedirs(path, exist_ok=True)
    return path

def load_config() -> dict:
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    # Fallback to config.example.json if present
    example_path = os.path.join(BASE_DIR, "config.example.json")
    if os.path.exists(example_path):
        try:
            with open(example_path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
                save_config(cfg)
                return cfg
        except Exception:
            pass

    default_config = {
        "accounts": [
            {"id": "account_1", "name": "Account 1", "color": "#D97757", "email": ""},
            {"id": "account_2", "name": "Account 2", "color": "#4A90E2", "email": ""}
        ],
        "active_account": "account_1"
    }
    save_config(default_config)
    return default_config

def save_config(config: dict) -> None:
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)

def get_work_area() -> Tuple[int, int, int, int]:
    rect = RECT()
    user32.SystemParametersInfoW(SPI_GETWORKAREA, 0, ctypes.byref(rect), 0)
    width = rect.right - rect.left
    height = rect.bottom - rect.top
    return rect.left, rect.top, width, height

def find_windows_for_profile(account_id: str) -> List[int]:
    """Find visible top-level windows matching the profile's browser processes using in-memory psutil."""
    profile_dir = os.path.abspath(get_profile_dir(account_id)).lower()
    pids = set()

    try:
        for proc in psutil.process_iter(['name', 'cmdline', 'pid']):
            try:
                name = proc.info.get('name')
                if name and any(b in name.lower() for b in ('brave.exe', 'msedge.exe', 'edge.exe')):
                    cmdline_list = proc.info.get('cmdline') or []
                    cmdline = ' '.join(cmdline_list).lower()
                    if profile_dir in cmdline:
                        pids.add(proc.info['pid'])
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
    except Exception:
        pass

    if not pids:
        return []

    hwnds = []

    def enum_proc(hwnd, lparam):
        if not user32.IsWindowVisible(hwnd):
            return True
        proc_id = ctypes.c_ulong()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(proc_id))
        if proc_id.value in pids:
            length = user32.GetWindowTextLengthW(hwnd)
            if length > 0:
                hwnds.append(hwnd)
        return True

    EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_int, ctypes.c_int)
    user32.EnumWindows(EnumWindowsProc(enum_proc), 0)
    return hwnds

def is_account_running(account_id: str) -> bool:
    """Checks if the browser is running for this profile without spawning subprocesses."""
    profile_dir = os.path.abspath(get_profile_dir(account_id)).lower()
    try:
        for proc in psutil.process_iter(['name', 'cmdline']):
            try:
                name = proc.info.get('name')
                if name and any(b in name.lower() for b in ('brave.exe', 'msedge.exe', 'edge.exe')):
                    cmdline_list = proc.info.get('cmdline') or []
                    cmdline = ' '.join(cmdline_list).lower()
                    if profile_dir in cmdline:
                        return True
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
    except Exception:
        pass
    return False

def is_account_logged_in(account_id: str) -> bool:
    """Checks if cookies/session storage exists for this profile, indicating an active login."""
    profile_dir = get_profile_dir(account_id)
    # Check default Network/Cookies or Cookies SQLite file
    possible_cookies = [
        os.path.join(profile_dir, "Default", "Network", "Cookies"),
        os.path.join(profile_dir, "Network", "Cookies"),
        os.path.join(profile_dir, "Default", "Cookies")
    ]
    for cp in possible_cookies:
        if os.path.exists(cp) and os.path.getsize(cp) > 5000:
            return True
    return False

def launch_account(account_id: str, url: str = "https://claude.ai") -> None:
    browser_path, browser_type = get_browser_path()
    profile_dir = get_profile_dir(account_id)
    
    # Note: --user-data-dir MUST be first for Chromium to guarantee isolation
    args = [
        browser_path,
        f"--user-data-dir={profile_dir}",
        f"--app={url}",
        "--no-first-run",
        "--no-default-browser-check"
    ]
    subprocess.Popen(args, close_fds=True)

def focus_account(account_id: str) -> bool:
    if not is_account_running(account_id):
        launch_account(account_id)
        return True
    
    hwnds = find_windows_for_profile(account_id)
    if hwnds:
        for hwnd in hwnds:
            user32.ShowWindow(hwnd, SW_RESTORE)
            user32.SetForegroundWindow(hwnd)
    else:
        launch_account(account_id)
    return True

def arrange_side_by_side(acc1_id: str, acc2_id: str) -> None:
    """Arranges Account 1 on the left half and Account 2 on the right half."""
    if not is_account_running(acc1_id):
        launch_account(acc1_id)
        time.sleep(1.5)

    if not is_account_running(acc2_id):
        launch_account(acc2_id)
        time.sleep(1.5)

    hw1 = find_windows_for_profile(acc1_id)
    hw2 = find_windows_for_profile(acc2_id)

    left, top, total_w, total_h = get_work_area()
    half_w = total_w // 2

    if hw1:
        hwnd = hw1[0]
        user32.ShowWindow(hwnd, SW_RESTORE)
        user32.MoveWindow(hwnd, left, top, half_w, total_h, True)
        user32.SetForegroundWindow(hwnd)

    if hw2:
        hwnd = hw2[0]
        user32.ShowWindow(hwnd, SW_RESTORE)
        user32.MoveWindow(hwnd, left + half_w, top, half_w, total_h, True)
        user32.SetForegroundWindow(hwnd)

def continue_chat_in_account(target_account_id: str, share_url: str) -> None:
    """Opens a shared conversation in the target account so it can be continued."""
    share_url = share_url.strip()
    if not share_url.startswith("http"):
        share_url = "https://" + share_url
    launch_account(target_account_id, url=share_url)
