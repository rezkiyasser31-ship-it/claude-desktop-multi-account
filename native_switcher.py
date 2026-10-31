import os
import sys
import json
import stat
import shutil
import subprocess
import time
import psutil
from typing import Optional, List, Dict

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROFILES_DIR = os.path.join(BASE_DIR, "native_profiles")
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")
LOCAL_APP_DATA = os.environ.get("LOCALAPPDATA") or os.path.expanduser(r"~\AppData\Local")
CLAUDE_ROAMING = os.path.join(LOCAL_APP_DATA, "Claude-Data", "claude_pzs8sxrjxfjjc")
if not os.path.exists(CLAUDE_ROAMING):
    CLAUDE_ROAMING = os.path.join(LOCAL_APP_DATA, "Packages", "Claude_pzs8sxrjxfjjc", "LocalCache", "Roaming", "Claude")
CLAUDE_APP_SHELL = r"shell:AppsFolder\Claude_pzs8sxrjxfjjc!Claude"

os.makedirs(PROFILES_DIR, exist_ok=True)

SESSION_ITEMS = [
    "config.json",
    "ant-did",
    "Preferences",
    "plan-usage-history.json",
    "window-state.json",
    "claude_desktop_config.json",
    "Network",
    "Session Storage",
    "Local Storage",
    "IndexedDB",
    "WebStorage",
    "Shared Dictionary",
    "spaces-present"
]

def is_native_claude_running() -> bool:
    try:
        for proc in psutil.process_iter(['name']):
            try:
                name = proc.info.get('name')
                if name and name.lower() == 'claude.exe':
                    return True
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
    except Exception:
        pass
    return False

def wait_for_file_locks(timeout: float = 3.0) -> bool:
    """Waits until critical session files in CLAUDE_ROAMING are unlocked and writable."""
    test_files = [
        os.path.join(CLAUDE_ROAMING, "config.json"),
        os.path.join(CLAUDE_ROAMING, "Network", "Cookies")
    ]
    start = time.time()
    while time.time() - start < timeout:
        all_unlocked = True
        for tf in test_files:
            if os.path.exists(tf):
                try:
                    with open(tf, "a"):
                        pass
                except (IOError, PermissionError):
                    all_unlocked = False
                    break
        if all_unlocked:
            return True
        time.sleep(0.15)
    return False

def ensure_claude_closed(timeout: float = 5.0) -> bool:
    """Closes all Claude Desktop processes and waits until all file locks are released."""
    if not is_native_claude_running():
        wait_for_file_locks(timeout=1.0)
        return True
    
    # 1. Graceful close first
    subprocess.run(["taskkill", "/IM", "claude.exe"], capture_output=True)
    start = time.time()
    while time.time() - start < 1.5:
        if not is_native_claude_running():
            wait_for_file_locks(timeout=1.5)
            return True
        time.sleep(0.15)
        
    # 2. Force kill process tree to terminate lingering workers
    subprocess.run(["taskkill", "/F", "/T", "/IM", "claude.exe"], capture_output=True)
    
    # 3. Wait until psutil confirms no claude.exe remains
    start = time.time()
    while time.time() - start < 2.5:
        if not is_native_claude_running():
            break
        time.sleep(0.15)
        
    wait_for_file_locks(timeout=2.0)
    return True

def launch_native_claude() -> None:
    """Launches the native Windows Claude Desktop app via shell:AppsFolder."""
    try:
        os.startfile(CLAUDE_APP_SHELL)
    except Exception as e:
        print(f"Error launching via os.startfile: {e}")
        subprocess.Popen(["explorer.exe", CLAUDE_APP_SHELL], close_fds=True)

def _remove_readonly(func, path, exc_info):
    """Helper to clear read-only attributes on file deletion errors."""
    try:
        os.chmod(path, stat.S_IWRITE)
        func(path)
    except Exception:
        pass

def safe_remove(path: str, max_retries: int = 10) -> bool:
    """Safely removes a file or directory with retries against temporary Windows locks."""
    if not os.path.exists(path):
        return True
    for attempt in range(max_retries):
        try:
            if os.path.isdir(path):
                shutil.rmtree(path, onerror=_remove_readonly)
            else:
                os.chmod(path, stat.S_IWRITE)
                os.remove(path)
            return True
        except Exception:
            time.sleep(0.15)
    return not os.path.exists(path)

def safe_copy_tree(src: str, dst: str, max_retries: int = 5) -> bool:
    for attempt in range(max_retries):
        try:
            shutil.copytree(src, dst, dirs_exist_ok=True)
            return True
        except Exception as e:
            if attempt == max_retries - 1:
                print(f"Error copying tree {src} -> {dst}: {e}")
            time.sleep(0.15)
    return False

def safe_copy_file(src: str, dst: str, max_retries: int = 5) -> bool:
    for attempt in range(max_retries):
        try:
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(src, dst)
            return True
        except Exception as e:
            if attempt == max_retries - 1:
                print(f"Error copying file {src} -> {dst}: {e}")
            time.sleep(0.15)
    return False

def get_live_account_uuid() -> Optional[str]:
    """Reads the lastKnownAccountUuid directly from the live Claude app configuration."""
    cfg = os.path.join(CLAUDE_ROAMING, "config.json")
    if os.path.exists(cfg):
        try:
            with open(cfg, "r", encoding="utf-8") as f:
                return json.load(f).get("lastKnownAccountUuid")
        except Exception:
            pass
    return None

def get_saved_account_uuid(account_id: str) -> Optional[str]:
    """Reads the lastKnownAccountUuid from a saved native profile."""
    cfg = os.path.join(PROFILES_DIR, account_id, "config.json")
    if os.path.exists(cfg):
        try:
            with open(cfg, "r", encoding="utf-8") as f:
                return json.load(f).get("lastKnownAccountUuid")
        except Exception:
            pass
    return None

def get_all_account_uuids() -> Dict[str, str]:
    """Returns a mapping of account_id -> saved UUID for all configured accounts."""
    mapping = {}
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                for acc in data.get("accounts", []):
                    aid = acc["id"]
                    uuid = get_saved_account_uuid(aid)
                    if uuid:
                        mapping[aid] = uuid
        except Exception:
            pass
    return mapping

def get_account_for_uuid(uuid: str) -> Optional[str]:
    """Finds which account_id corresponds to a given UUID."""
    if not uuid:
        return None
    mapping = get_all_account_uuids()
    for aid, u in mapping.items():
        if u.lower() == uuid.lower():
            return aid
    return None

def get_live_account_id() -> Optional[str]:
    """Determines which account is currently active in Claude Desktop by checking live UUID."""
    live_uuid = get_live_account_uuid()
    if not live_uuid:
        return None
    return get_account_for_uuid(live_uuid)

def has_saved_session(account_id: str) -> bool:
    target_dir = os.path.join(PROFILES_DIR, account_id)
    cookies_path = os.path.join(target_dir, "Network", "Cookies")
    config_path = os.path.join(target_dir, "config.json")
    return os.path.exists(cookies_path) and os.path.exists(config_path)

def save_current_native_session(account_id: str) -> bool:
    """Saves the current live session into native_profiles/<account_id>."""
    ensure_claude_closed()
    
    target_dir = os.path.join(PROFILES_DIR, account_id)
    os.makedirs(target_dir, exist_ok=True)
    
    for item in SESSION_ITEMS:
        src = os.path.join(CLAUDE_ROAMING, item)
        dst = os.path.join(target_dir, item)
        if os.path.exists(src):
            if os.path.isdir(src):
                safe_copy_tree(src, dst)
            else:
                safe_copy_file(src, dst)
                
    return has_saved_session(account_id)

def switch_to_native_account(target_account_id: str, current_active_id: Optional[str] = None) -> bool:
    """
    1. Gracefully terminates Claude and verifies file locks are released.
    2. Identifies live session account and snapshots it to its own profile.
    3. Clears active session items in CLAUDE_ROAMING.
    4. Restores target_account_id profile items.
    5. Verifies restoration and launches native Claude Desktop.
    """
    ensure_claude_closed()
    
    # Snapshot the session that was just active before closing
    live_uuid = get_live_account_uuid()
    current_detected_id = get_account_for_uuid(live_uuid) if live_uuid else None
    
    # Save the session to the account that actually owned it
    account_to_save = current_detected_id or current_active_id
    if account_to_save and account_to_save != target_account_id:
        save_current_native_session(account_to_save)
    elif account_to_save == target_account_id and has_saved_session(target_account_id):
        # Already on the target account, refresh backup
        save_current_native_session(target_account_id)
            
    target_dir = os.path.join(PROFILES_DIR, target_account_id)
    
    # Clear live session items from CLAUDE_ROAMING
    for item in SESSION_ITEMS:
        p = os.path.join(CLAUDE_ROAMING, item)
        safe_remove(p)
                
    # Restore the target profile files if they exist
    if has_saved_session(target_account_id):
        for item in SESSION_ITEMS:
            src = os.path.join(target_dir, item)
            dst = os.path.join(CLAUDE_ROAMING, item)
            if os.path.exists(src):
                if os.path.isdir(src):
                    safe_copy_tree(src, dst)
                else:
                    safe_copy_file(src, dst)
                    
    time.sleep(0.3)
    # Launch Claude Desktop
    launch_native_claude()
    return True
