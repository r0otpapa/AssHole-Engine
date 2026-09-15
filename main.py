import os
import sys
import json
import time
import ctypes
import socket
import threading
import subprocess
import webbrowser
import mimetypes
import urllib.parse
try:
    from zoneinfo import available_timezones
except ImportError:
    def available_timezones():
        return set()
import pyautogui

try:
    import hid_manager
    HID_MANAGER_AVAILABLE = True
except ImportError:
    hid_manager = None
    HID_MANAGER_AVAILABLE = False
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    psutil = None
    PSUTIL_AVAILABLE = False
try:
    import pystray
    PYSTRAY_AVAILABLE = True
except ImportError:
    pystray = None
    PYSTRAY_AVAILABLE = False
try:
    import pynvml
    pynvml.nvmlInit()
    PYNVML_AVAILABLE = True
except Exception:
    pynvml = None
    PYNVML_AVAILABLE = False
try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    cv2 = None
    CV2_AVAILABLE = False
import qrcode
import screen_brightness_control as sbc

try:
    import pygame
    PYGAME_AVAILABLE = True
except ImportError:
    pygame = None
    PYGAME_AVAILABLE = False
import tkinter as tk
from tkinter import filedialog, ttk, messagebox
from PIL import ImageTk, Image, ImageDraw, ImageGrab
from flask import Flask, jsonify, request, send_from_directory, send_file
from werkzeug.utils import secure_filename
from flask_socketio import SocketIO

# Root path resolver for PyInstaller bundle directory
def get_bundle_dir():
    if getattr(sys, 'frozen', False):
        return getattr(sys, '_MEIPASS', os.path.dirname(sys.executable))
    return os.path.abspath(".")

BUNDLE_DIR = get_bundle_dir()

# Flask & SocketIO setup
app = Flask(__name__, static_folder=BUNDLE_DIR, template_folder=BUNDLE_DIR)
app.config['SECRET_KEY'] = 'secret!'
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading', logger=False, engineio_logger=False)

CONFIG_FILE = "config.json"

DEFAULT_CONFIG = {
    "screenshot_path": r"C:\Users\PanicButton\Pictures\Screenshots",
    "soundboard_path": r"C:\Users\Public\Music",
    "soundboard_volume": 80,
    "webui_timezone": "",
    "upload_folder": os.path.join(os.path.expanduser("~"), "Downloads"),
    "auto_start": False,
    "minimize_to_tray_on_close": True,
    "media_folders": [
        {"path": r"C:\Users\Public\Videos", "enabled": True}
    ],
    "custom_apps": [
        {"name": "Task Manager", "path": "C:\\Windows\\System32\\taskmgr.exe", "is_link": False, "enabled": True},
        {"name": "Notepad", "path": "notepad.exe", "is_link": False, "enabled": True},
        {"name": "Calculator", "path": "calc.exe", "is_link": False, "enabled": True},
        {"name": "Google", "path": "https://www.google.com", "is_link": True, "enabled": True}
    ],
    "workspaces": [],
    "custom_shortcuts": [
        {"name": "Win + Tab", "keys": ["win", "tab"], "category": "Windows", "icon": "🔀", "enabled": True},
        {"name": "Sound output devices", "keys": ["win", "ctrl", "v"], "category": "Windows", "icon": "🔊", "enabled": True},
        {"name": "Taskbar apps", "keys": ["win", "t"], "category": "Windows", "icon": "🖥️", "enabled": True},
        {"name": "Enter", "keys": ["enter"], "category": "Windows", "icon": "↩️", "enabled": True}
    ],
    "hid": {
        "enabled": False,
        "script_path": "hid_scripts"
    },
    "capture": {
        "enabled": False,
        "camera_enabled": False,
        "microphone_enabled": False,
        "screen_enabled": False,
        "camera_device": 0,
        "microphone_device": "default",
        "screen_display": 0,
        "screen_device": 0,
        "output_path": "captures",
        "visible_recording_indicator": True
    },
    "built_in_controls": [
        {"id": "play_pause", "name": "Play/Pause", "category": "Media", "enabled": True},
        {"id": "vol_up", "name": "Volume Up", "category": "Media", "enabled": True},
        {"id": "vol_down", "name": "Volume Down", "category": "Media", "enabled": True},
        {"id": "mute", "name": "Mute", "category": "Media", "enabled": True},
        {"id": "arrow_up", "name": "Up Arrow", "category": "Navigation", "enabled": True},
        {"id": "arrow_down", "name": "Down Arrow", "category": "Navigation", "enabled": True},
        {"id": "arrow_left", "name": "Left Arrow", "category": "Navigation", "enabled": True},
        {"id": "arrow_right", "name": "Right Arrow", "category": "Navigation", "enabled": True},
        {"id": "screenshot", "name": "Screenshot", "category": "Capture", "enabled": True},
        {"id": "record_screen", "name": "Record Screen", "category": "Capture", "enabled": True},
        {"id": "bright_up", "name": "Brightness Up", "category": "System", "enabled": True},
        {"id": "bright_down", "name": "Brightness Down", "category": "System", "enabled": True},
        {"id": "lock_pc", "name": "Lock PC", "category": "System", "enabled": True},
        {"id": "sleep_pc", "name": "Sleep PC", "category": "System", "enabled": True},
        {"id": "restart_pc", "name": "Restart PC", "category": "System", "enabled": True},
        {"id": "shutdown_pc", "name": "Shutdown PC", "category": "System", "enabled": True}
    ]
}

def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                data = json.load(f)
                # Ensure all default top-level keys exist
                for key in DEFAULT_CONFIG:
                    if key not in data:
                        data[key] = DEFAULT_CONFIG[key]
                # Backward compatibility fix for media_folders string list
                if data["media_folders"] and isinstance(data["media_folders"][0], str):
                    data["media_folders"] = [{"path": p, "enabled": True} for p in data["media_folders"]]
                return data
        except Exception as e:
            print("Config Load Error:", e)
    return DEFAULT_CONFIG

def save_config():
    try:
        with open(CONFIG_FILE, "w") as f:
            json.dump(CONFIG, f, indent=4)
    except Exception as e:
        print("Config Save Error:", e)

CONFIG = load_config()

# ---------------- MULTI-DEVICE ACTIVITY LOG ----------------
# Records which connected device (phone/browser) triggered which action,
# so that if several devices control the PC at once, there is a file-based
# trail of "who did what, when".

ACTIVITY_LOG_DIR = "logs"
ACTIVITY_LOG_FILE = os.path.join(ACTIVITY_LOG_DIR, "activity_log.jsonl")
_activity_log_lock = threading.Lock()


def _client_device_label():
    """Best-effort device identifier (IP + short platform hint) for the log."""
    try:
        ip = request.remote_addr or "unknown"
        ua = request.headers.get("User-Agent", "")
        platform_hint = "Device"
        for token in ("iPhone", "Android", "iPad", "Windows", "Macintosh", "Linux"):
            if token in ua:
                platform_hint = token
                break
        return f"{ip} ({platform_hint})"
    except Exception:
        return "unknown"


def log_activity(action, meta=None, device=None):
    """Append one entry to the multi-device activity log file (JSON Lines)."""
    try:
        os.makedirs(ACTIVITY_LOG_DIR, exist_ok=True)
        entry = {
            "time": time.strftime("%Y-%m-%d %H:%M:%S"),
            "device": device or _client_device_label(),
            "action": action,
            "meta": meta or {}
        }
        with _activity_log_lock:
            with open(ACTIVITY_LOG_FILE, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception as e:
        print("Activity Log Error:", e)


def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


# ---------------- AUTO-START (Windows Registry Run key) ----------------

AUTO_START_APP_NAME = "ASSHOLE_ENGINE"


def _autostart_exe_path():
    if getattr(sys, "frozen", False):
        return sys.executable
    return os.path.abspath(sys.argv[0])


def is_auto_start_enabled():
    if os.name != "nt":
        return False
    try:
        import winreg
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_READ) as key:
            winreg.QueryValueEx(key, AUTO_START_APP_NAME)
            return True
    except Exception:
        return False


def set_auto_start(enabled):
    """Add/remove the app from the Windows Startup (Run key). Returns True on success."""
    if os.name != "nt":
        return False
    try:
        import winreg
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        exe_path = _autostart_exe_path()
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE) as key:
            if enabled:
                winreg.SetValueEx(key, AUTO_START_APP_NAME, 0, winreg.REG_SZ, f'"{exe_path}"')
            else:
                try:
                    winreg.DeleteValue(key, AUTO_START_APP_NAME)
                except FileNotFoundError:
                    pass
        return True
    except Exception as e:
        print("Auto-start registry error:", e)
        return False


# ---------------- SYSTEM TRAY ----------------

_tray_icon_ref = {"icon": None}


def _make_tray_image():
    img = Image.new("RGB", (64, 64), "#ff4757")
    draw = ImageDraw.Draw(img)
    draw.ellipse((14, 14, 50, 50), fill="#ffffff")
    draw.ellipse((24, 24, 40, 40), fill="#ff4757")
    return img


def setup_system_tray(root):
    """Create the tray icon (runs its own loop in a daemon thread)."""
    if not PYSTRAY_AVAILABLE:
        return None

    def restore_window():
        root.deiconify()
        root.lift()
        root.focus_force()

    def on_open(icon, item):
        root.after(0, restore_window)

    def on_exit(icon, item):
        icon.stop()
        root.after(0, root.destroy)

    menu = pystray.Menu(
        pystray.MenuItem("Open ASSHOLE ENGINE", on_open, default=True),
        pystray.MenuItem("Exit", on_exit)
    )
    icon = pystray.Icon("asshole_engine", _make_tray_image(), "ASSHOLE ENGINE", menu)
    threading.Thread(target=icon.run, daemon=True).start()
    return icon


def minimize_to_tray(root):
    """Hide the window and (re)start the tray icon if needed."""
    root.withdraw()
    if _tray_icon_ref["icon"] is None:
        _tray_icon_ref["icon"] = setup_system_tray(root)


MEDIA_EXTS = (
    '.mp4', '.mkv', '.avi', '.mov', '.wmv', '.webm', '.m4v',
    '.mp3', '.wav', '.flac', '.m4a', '.aac', '.ogg', '.wma', '.opus',
    '.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.svg',
    '.ppt', '.pptx', '.doc', '.docx', '.xls', '.xlsx', '.pdf',
    '.txt', '.csv'
)

def build_tree_structure(path, mode="media"):
    """Build a folder tree. 'media' keeps the original supported-media behavior;
    'all' exposes every regular file inside the configured folder."""
    items = []
    try:
        entries = sorted(
            os.scandir(path),
            key=lambda e: (not e.is_dir(follow_symlinks=False), e.name.lower())
        )
        for entry in entries:
            try:
                if entry.is_dir(follow_symlinks=False):
                    children = build_tree_structure(entry.path, mode)
                    if children:
                        items.append({
                            "name": entry.name,
                            "type": "folder",
                            "children": children
                        })
                elif entry.is_file(follow_symlinks=False):
                    if mode == "all" or entry.name.lower().endswith(MEDIA_EXTS):
                        try:
                            size = entry.stat(follow_symlinks=False).st_size
                        except OSError:
                            size = 0
                        items.append({
                            "name": entry.name,
                            "type": "file",
                            "path": entry.path,
                            "size": size,
                            "extension": os.path.splitext(entry.name)[1].lower(),
                            "mime": mimetypes.guess_type(entry.name)[0] or "application/octet-stream"
                        })
            except (PermissionError, OSError):
                continue
    except (PermissionError, OSError) as e:
        print("Scan Error:", e)
    return items


SOUNDBOARD_EXTS = (
    '.mp3', '.wav', '.flac', '.m4a', '.aac', '.ogg', '.wma', '.opus'
)


def build_soundboard_tree(path):
    """Build a folder/file tree containing audio files only."""
    items = []
    try:
        entries = sorted(
            os.scandir(path),
            key=lambda e: (not e.is_dir(), e.name.lower())
        )
        for entry in entries:
            try:
                if entry.is_dir():
                    children = build_soundboard_tree(entry.path)
                    if children:
                        items.append({
                            "name": entry.name,
                            "type": "folder",
                            "children": children
                        })
                elif entry.is_file() and entry.name.lower().endswith(SOUNDBOARD_EXTS):
                    items.append({
                        "name": entry.name,
                        "type": "file",
                        "path": entry.path
                    })
            except (PermissionError, OSError):
                continue
    except (PermissionError, OSError) as e:
        print("Soundboard Scan Error:", e)
    return items


def is_path_inside(child_path, parent_path):
    """Prevent soundboard file API from reading outside configured folder."""
    try:
        child = os.path.realpath(child_path)
        parent = os.path.realpath(parent_path)
        return os.path.commonpath([child, parent]) == parent
    except (ValueError, OSError):
        return False


def get_configured_roots():
    """Return real paths that the remote file APIs are allowed to access."""
    roots = []
    for item in CONFIG.get("media_folders", []):
        if item.get("enabled", True):
            path = item.get("path", "")
            if path and os.path.isdir(path):
                roots.append(os.path.realpath(path))
    sound_path = CONFIG.get("soundboard_path", "")
    if sound_path and os.path.isdir(sound_path):
        roots.append(os.path.realpath(sound_path))
    return roots


def is_allowed_remote_path(path):
    """Allow access only inside folders configured in the dashboard."""
    if not path:
        return False
    real = os.path.realpath(path)
    for root in get_configured_roots():
        try:
            if os.path.commonpath([real, root]) == root:
                return True
        except ValueError:
            continue
    return False


class SoundPlayer:
    """Local PC audio player. Audio is rendered by the PC app, never by the phone browser."""
    def __init__(self):
        self.enabled = PYGAME_AVAILABLE
        self.current_path = None
        self.volume = max(0, min(100, int(CONFIG.get("soundboard_volume", 80))))
        self.paused = False
        self.root = None
        if self.enabled:
            try:
                pygame.mixer.init()
                pygame.mixer.music.set_volume(self.volume / 100.0)
            except Exception as e:
                print("SoundPlayer Init Error:", e)
                self.enabled = False

    def attach_root(self, root):
        self.root = root

    def set_volume(self, value):
        try:
            self.volume = max(0, min(100, int(float(value))))
            CONFIG["soundboard_volume"] = self.volume
            save_config()
            if self.enabled:
                pygame.mixer.music.set_volume(self.volume / 100.0)
            return True
        except Exception as e:
            print("SoundPlayer Volume Error:", e)
            return False

    def play(self, path):
        if not self.enabled:
            return False, "pygame is not installed. Install it with: pip install pygame"
        if not path or not os.path.isfile(path):
            return False, "Audio file not found."
        if not is_path_inside(path, CONFIG.get("soundboard_path", "")):
            return False, "Audio file is outside the configured soundboard folder."
        if not path.lower().endswith(SOUNDBOARD_EXTS):
            return False, "Unsupported audio file."
        try:
            pygame.mixer.music.load(path)
            pygame.mixer.music.set_volume(self.volume / 100.0)
            pygame.mixer.music.play()
            self.current_path = os.path.realpath(path)
            self.paused = False
            return True, "Playing"
        except Exception as e:
            print("SoundPlayer Play Error:", e)
            return False, str(e)

    def pause_toggle(self):
        if not self.enabled:
            return False
        try:
            if self.paused:
                pygame.mixer.music.unpause()
                self.paused = False
            else:
                pygame.mixer.music.pause()
                self.paused = True
            return True
        except Exception as e:
            print("SoundPlayer Pause Error:", e)
            return False

    def stop(self):
        if not self.enabled:
            return False
        try:
            pygame.mixer.music.stop()
            self.paused = False
            return True
        except Exception as e:
            print("SoundPlayer Stop Error:", e)
            return False


SOUND_PLAYER = SoundPlayer()

# Custom Center-Aligned Multi-Input Dark Dialog
class DarkMultiInputDialog(tk.Toplevel):
    def __init__(self, parent, title, fields):
        super().__init__(parent)
        self.title(title)
        self.configure(bg="#090d16")
        self.resizable(False, False)
        self.results = None
        self.entries = {}

        self.transient(parent)
        self.grab_set()

        tk.Label(self, text=title, font=("Segoe UI", 11, "bold"), fg="#ff4757", bg="#090d16", pady=10).pack()

        form_frame = tk.Frame(self, bg="#090d16", padx=20)
        form_frame.pack(fill="x", expand=True)

        for label_text, key in fields:
            f_frame = tk.Frame(form_frame, bg="#090d16")
            f_frame.pack(fill="x", pady=6)
            
            lbl = tk.Label(f_frame, text=label_text, font=("Segoe UI", 9), fg="#94a3b8", bg="#090d16", anchor="w")
            lbl.pack(fill="x")

            entry = tk.Entry(f_frame, bg="#162032", fg="#ffffff", insertbackground="#ff4757", relief="flat", font=("Segoe UI", 10))
            entry.pack(fill="x", ipady=4, pady=2)
            self.entries[key] = entry

        btn_frame = tk.Frame(self, bg="#090d16")
        btn_frame.pack(fill="x", pady=15)

        tk.Button(btn_frame, text="OK", command=self.on_ok, bg="#ff4757", fg="#ffffff", font=("Segoe UI", 9, "bold"), relief="flat", width=10, pady=4, cursor="hand2").pack(side="left", padx=30)
        tk.Button(btn_frame, text="Cancel", command=self.destroy, bg="#162032", fg="#94a3b8", font=("Segoe UI", 9), relief="flat", width=10, pady=4, cursor="hand2").pack(side="right", padx=30)

        self.update_idletasks()
        dialog_width = 380
        dialog_height = self.winfo_reqheight()
        parent_x = parent.winfo_x()
        parent_y = parent.winfo_y()
        parent_w = parent.winfo_width()
        parent_h = parent.winfo_height()

        pos_x = parent_x + (parent_w // 2) - (dialog_width // 2)
        pos_y = parent_y + (parent_h // 2) - (dialog_height // 2)

        self.geometry(f"{dialog_width}x{dialog_height}+{pos_x}+{pos_y}")

        self.bind("<Return>", lambda e: self.on_ok())
        self.bind("<Escape>", lambda e: self.destroy())
        
        if self.entries:
            list(self.entries.values())[0].focus_set()

        self.wait_window()

    def on_ok(self):
        res = {}
        for key, entry in self.entries.items():
            val = entry.get().strip()
            if not val:
                return
            res[key] = val
        self.results = res
        self.destroy()

@app.route('/')
def index():
    return send_from_directory(BUNDLE_DIR, 'index.html')

@app.route('/<path:filename>')
def serve_static(filename):
    return send_from_directory(BUNDLE_DIR, filename)

@app.route('/api/media_sources', methods=['GET'])
def get_media_sources():
    sources = []
    for index, item in enumerate(CONFIG.get("media_folders", [])):
        if item.get("enabled", True):
            path = item.get("path", "")
            if os.path.isdir(path):
                sources.append({
                    "id": index,
                    "name": os.path.basename(os.path.normpath(path)) or path,
                    "path": path
                })
    return jsonify(sources)


@app.route('/api/media_tree', methods=['GET'])
def get_media_tree():
    mode = request.args.get("mode", "media").lower()
    if mode not in ("media", "all"):
        mode = "media"

    requested_index = request.args.get("source")
    root_nodes = []

    for index, item in enumerate(CONFIG.get("media_folders", [])):
        if not item.get("enabled", True):
            continue
        if requested_index not in (None, "", str(index)):
            continue

        path = item.get("path", "")
        if os.path.isdir(path):
            folder_name = os.path.basename(os.path.normpath(path)) or path
            children = build_tree_structure(path, mode=mode)
            root_nodes.append({
                "name": folder_name,
                "type": "folder",
                "path": path,
                "source_id": index,
                "children": children
            })
    return jsonify(root_nodes)

@app.route('/api/soundboard_tree', methods=['GET'])
def get_soundboard_tree():
    """Return the configured soundboard folder as an audio-only tree."""
    configured_path = CONFIG.get("soundboard_path", "").strip()

    if not configured_path:
        return jsonify({
            "root": None,
            "items": [],
            "error": "Soundboard folder is not configured."
        })

    if not os.path.isdir(configured_path):
        return jsonify({
            "root": configured_path,
            "items": [],
            "error": "Soundboard folder does not exist."
        })

    root_name = os.path.basename(os.path.normpath(configured_path)) or configured_path
    return jsonify({
        "root": {
            "name": root_name,
            "path": configured_path
        },
        "items": build_soundboard_tree(configured_path)
    })


@app.route('/api/soundboard_file', methods=['GET'])
def get_soundboard_file():
    """
    Stream one configured soundboard audio file.
    The requested path must be inside soundboard_path and have an audio extension.
    """
    requested_path = request.args.get("path", "").strip()
    configured_path = CONFIG.get("soundboard_path", "").strip()

    if not requested_path or not configured_path:
        return jsonify({"status": "error", "message": "Invalid soundboard path."}), 400

    if not os.path.isdir(configured_path):
        return jsonify({"status": "error", "message": "Soundboard folder does not exist."}), 404

    if not is_path_inside(requested_path, configured_path):
        return jsonify({"status": "error", "message": "Access denied."}), 403

    if not os.path.isfile(requested_path):
        return jsonify({"status": "error", "message": "Audio file not found."}), 404

    if not requested_path.lower().endswith(SOUNDBOARD_EXTS):
        return jsonify({"status": "error", "message": "Unsupported audio file."}), 415

    try:
        return send_from_directory(
            os.path.dirname(requested_path),
            os.path.basename(requested_path),
            as_attachment=False,
            conditional=True
        )
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/download_file', methods=['GET'])
def download_file():
    requested_path = request.args.get("path", "").strip()
    if not requested_path or not is_allowed_remote_path(requested_path):
        return jsonify({"status": "error", "message": "Access denied."}), 403
    if not os.path.isfile(requested_path):
        return jsonify({"status": "error", "message": "File not found."}), 404

    try:
        log_activity("download_file", {"file": os.path.basename(requested_path)})
        return send_file(
            os.path.realpath(requested_path),
            as_attachment=True,
            download_name=os.path.basename(requested_path),
            conditional=True
        )
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/open_file', methods=['POST'])
def open_file_on_pc():
    data = request.get_json(silent=True) or {}
    requested_path = str(data.get("path", "")).strip()

    if not requested_path or not is_allowed_remote_path(requested_path):
        return jsonify({"status": "error", "message": "Access denied."}), 403
    if not os.path.isfile(requested_path):
        return jsonify({"status": "error", "message": "File not found."}), 404

    try:
        if os.name == "nt":
            os.startfile(requested_path)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", requested_path])
        else:
            subprocess.Popen(["xdg-open", requested_path])
        log_activity("open_file", {"file": os.path.basename(requested_path)})
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/soundboard_play', methods=['POST'])
def soundboard_play_http():
    data = request.get_json(silent=True) or {}
    path = str(data.get("path", "")).strip()
    ok, message = SOUND_PLAYER.play(path)
    if ok:
        log_activity("soundboard_play", {"file": os.path.basename(path)})
    try:
        socketio.emit("soundboard_status", {
            "status": "playing" if ok else "error",
            "message": message,
            "path": SOUND_PLAYER.current_path if ok else path
        })
    except Exception:
        pass
    return jsonify({"status": "success" if ok else "error", "message": message}), (200 if ok else 400)


@app.route('/api/soundboard_control', methods=['POST'])
def soundboard_control_http():
    data = request.get_json(silent=True) or {}
    action = data.get("action")
    if action == "pause":
        ok = SOUND_PLAYER.pause_toggle()
    elif action == "stop":
        ok = SOUND_PLAYER.stop()
    else:
        return jsonify({"status": "error", "message": "Unknown player action."}), 400
    if ok:
        log_activity("soundboard_" + action)
    try:
        socketio.emit("soundboard_status", {
            "status": "success" if ok else "error",
            "path": SOUND_PLAYER.current_path
        })
    except Exception:
        pass
    return jsonify({"status": "success" if ok else "error"}), (200 if ok else 400)



# ---------------- WORKSPACE WEB API ----------------
# Mirrors the desktop "Workspace Manager" (create/delete/pin/launch) so the
# Web UI can manage and launch workspaces too. The desktop Tkinter UI itself
# is untouched.

def _find_workspace_by_identifier(identifier):
    """Look up a workspace by name first, falling back to numeric index."""
    workspaces = CONFIG.get("workspaces", [])
    if identifier is None:
        return None, None

    for idx, ws in enumerate(workspaces):
        if ws.get("name", "") == identifier:
            return idx, ws

    identifier_str = str(identifier).strip()
    if identifier_str.isdigit():
        idx = int(identifier_str)
        if 0 <= idx < len(workspaces):
            return idx, workspaces[idx]

    return None, None


@app.route('/api/webui_settings', methods=['GET'])
def get_webui_settings():
    return jsonify({
        "timezone": CONFIG.get("webui_timezone", "")
    })


_net_io_snapshot = {"time": None, "sent": 0, "recv": 0}


def _get_net_speed_kbps():
    """Best-effort upload/download speed in KB/s, based on a delta between calls."""
    global _net_io_snapshot
    if not PSUTIL_AVAILABLE:
        return None, None
    try:
        counters = psutil.net_io_counters()
        now = time.time()

        if _net_io_snapshot["time"] is None:
            _net_io_snapshot = {"time": now, "sent": counters.bytes_sent, "recv": counters.bytes_recv}
            return 0.0, 0.0

        elapsed = max(now - _net_io_snapshot["time"], 0.001)
        up_kbps = max((counters.bytes_sent - _net_io_snapshot["sent"]) / elapsed / 1024, 0)
        down_kbps = max((counters.bytes_recv - _net_io_snapshot["recv"]) / elapsed / 1024, 0)

        _net_io_snapshot = {"time": now, "sent": counters.bytes_sent, "recv": counters.bytes_recv}
        return round(up_kbps, 1), round(down_kbps, 1)
    except Exception:
        return None, None


def _get_gpu_percent():
    if not PYNVML_AVAILABLE:
        return None
    try:
        handle = pynvml.nvmlDeviceGetHandleByIndex(0)
        util = pynvml.nvmlDeviceGetUtilizationRates(handle)
        return round(util.gpu)
    except Exception:
        return None


def _get_cpu_temp():
    if not PSUTIL_AVAILABLE or not hasattr(psutil, "sensors_temperatures"):
        return None
    try:
        temps = psutil.sensors_temperatures()
        if not temps:
            return None
        for entries in temps.values():
            if entries:
                return round(entries[0].current)
    except Exception:
        pass
    return None


@app.route('/api/system_stats', methods=['GET'])
def get_system_stats():
    """Battery / CPU / GPU / RAM / Temp / Net mini-stats for the WebUI clock popup."""
    cpu_percent = None
    ram_percent = None
    battery_percent = None
    battery_plugged = None

    if PSUTIL_AVAILABLE:
        try:
            cpu_percent = round(psutil.cpu_percent(interval=0.1))
        except Exception:
            cpu_percent = None
        try:
            ram_percent = round(psutil.virtual_memory().percent)
        except Exception:
            ram_percent = None
        try:
            battery = psutil.sensors_battery()
            if battery is not None:
                battery_percent = round(battery.percent)
                battery_plugged = bool(battery.power_plugged)
        except Exception:
            battery_percent = None

    gpu_percent = _get_gpu_percent()
    cpu_temp = _get_cpu_temp()
    net_up_kbps, net_down_kbps = _get_net_speed_kbps()

    return jsonify({
        "cpu_percent": cpu_percent,
        "ram_percent": ram_percent,
        "battery_percent": battery_percent,
        "battery_plugged": battery_plugged,
        "gpu_percent": gpu_percent,
        "cpu_temp_c": cpu_temp,
        "net_up_kbps": net_up_kbps,
        "net_down_kbps": net_down_kbps,
        "psutil_available": PSUTIL_AVAILABLE,
        "gpu_available": PYNVML_AVAILABLE
    })


@app.route('/api/upload_file', methods=['POST'])
def upload_file_from_mobile():
    """Receive a file from a phone/browser and save it into whichever
    folder is selected in the File Explorer (falls back to the configured
    upload folder / Downloads if none is selected)."""
    if 'file' not in request.files:
        return jsonify({"status": "error", "message": "No file provided."}), 400

    uploaded = request.files['file']
    if not uploaded or not uploaded.filename:
        return jsonify({"status": "error", "message": "No file selected."}), 400

    upload_folder = CONFIG.get("upload_folder") or os.path.join(os.path.expanduser("~"), "Downloads")

    source_index = request.form.get("source", "").strip()
    if source_index != "":
        try:
            idx = int(source_index)
            media_folders = CONFIG.get("media_folders", [])
            if 0 <= idx < len(media_folders):
                candidate = media_folders[idx].get("path", "")
                if candidate and os.path.isdir(candidate):
                    upload_folder = candidate
        except (TypeError, ValueError):
            pass

    try:
        os.makedirs(upload_folder, exist_ok=True)

        safe_name = secure_filename(uploaded.filename) or "upload"
        dest_path = os.path.join(upload_folder, safe_name)

        # Avoid overwriting an existing file with the same name.
        base, ext = os.path.splitext(safe_name)
        counter = 1
        while os.path.exists(dest_path):
            dest_path = os.path.join(upload_folder, f"{base}_{counter}{ext}")
            counter += 1

        uploaded.save(dest_path)
        log_activity("upload_file", {"file": os.path.basename(dest_path), "folder": upload_folder})

        return jsonify({
            "status": "success",
            "saved_as": os.path.basename(dest_path),
            "folder": upload_folder
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/play_alert', methods=['POST'])
def play_alert_sound():
    """Play a short alert sound on the PC's speakers (e.g. timer finished)."""
    try:
        if os.name == "nt":
            import winsound
            winsound.Beep(880, 200)
            winsound.Beep(1046, 250)
        else:
            print("\a", end="", flush=True)
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/capture_photo', methods=['POST'])
def capture_photo():
    """Take a single still photo from the configured camera device
    (independent of the video/audio recording pipeline in hid_manager)."""
    if not CV2_AVAILABLE:
        return jsonify({
            "status": "error",
            "message": "Camera support not installed. Run: pip install opencv-python"
        }), 503

    cap_cfg = CONFIG.get("capture", {})
    device_index = cap_cfg.get("camera_device", 0)
    output_path = cap_cfg.get("output_path") or CONFIG.get("screenshot_path") or os.getcwd()

    camera = None
    try:
        os.makedirs(output_path, exist_ok=True)

        camera = cv2.VideoCapture(device_index)
        if not camera.isOpened():
            return jsonify({
                "status": "error",
                "message": f"Could not open camera device {device_index}."
            }), 500

        # Warm-up reads — the first frame or two from many webcams is dark/blurry.
        for _ in range(3):
            camera.read()

        ok, frame = camera.read()
        if not ok or frame is None:
            return jsonify({"status": "error", "message": "Could not read a frame from the camera."}), 500

        filename = f"photo_{time.strftime('%Y%m%d_%H%M%S')}.jpg"
        filepath = os.path.join(output_path, filename)
        cv2.imwrite(filepath, frame)

        log_activity("capture_photo", {"file": filename})
        return jsonify({"status": "success", "file": filename, "folder": output_path})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        if camera is not None:
            camera.release()


@app.route('/api/activity_log', methods=['GET'])
def get_activity_log():
    """Return the most recent multi-device activity log entries."""
    limit = request.args.get("limit", 50, type=int)
    limit = max(1, min(limit, 500))

    entries = []
    try:
        if os.path.isfile(ACTIVITY_LOG_FILE):
            with open(ACTIVITY_LOG_FILE, "r", encoding="utf-8") as f:
                lines = f.readlines()[-limit:]
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                try:
                    entries.append(json.loads(line))
                except Exception:
                    continue
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

    entries.reverse()
    return jsonify(entries)


@app.route('/api/fetch_workspaces', methods=['GET'])
def fetch_workspaces():
    workspaces = CONFIG.get("workspaces", [])
    result = []
    for idx, ws in enumerate(workspaces):
        result.append({
            "index": idx,
            "name": ws.get("name", "Workspace"),
            "enabled": ws.get("enabled", True),
            "items": ws.get("items", [])
        })
    return jsonify(result)


@app.route('/api/workspace/toggle', methods=['POST'])
def toggle_workspace_pin():
    """Pin/unpin (enable/disable) a workspace from the Web UI."""
    data = request.get_json(silent=True) or {}
    identifier = data.get("name", data.get("index"))
    idx, ws = _find_workspace_by_identifier(identifier)
    if ws is None:
        return jsonify({"status": "error", "message": "Workspace not found."}), 404

    ws["enabled"] = not ws.get("enabled", True)
    save_config()
    return jsonify({"status": "success", "enabled": ws["enabled"]})


@app.route('/api/workspace/delete', methods=['POST'])
def delete_workspace_web():
    """Delete a workspace from the Web UI."""
    data = request.get_json(silent=True) or {}
    identifier = data.get("name", data.get("index"))
    idx, ws = _find_workspace_by_identifier(identifier)
    if ws is None:
        return jsonify({"status": "error", "message": "Workspace not found."}), 404

    CONFIG["workspaces"].pop(idx)
    save_config()
    return jsonify({"status": "success"})


@app.route('/api/launch_workspace', methods=['POST'])
def launch_workspace_web():
    """Open every enabled item (.exe / link) inside a workspace."""
    data = request.get_json(silent=True) or {}
    identifier = data.get("name", data.get("index"))
    idx, ws = _find_workspace_by_identifier(identifier)
    if ws is None:
        return jsonify({"status": "error", "message": "Workspace not found."}), 404

    if not ws.get("enabled", True):
        return jsonify({"status": "error", "message": "This workspace is unpinned/disabled."}), 400

    launched = 0
    errors = []
    for item in ws.get("items", []):
        if not item.get("enabled", True):
            continue
        path = str(item.get("path", "")).strip()
        if not path:
            continue
        try:
            if item.get("is_link", False):
                webbrowser.open(path)
            elif os.name == "nt":
                os.startfile(path)
            else:
                subprocess.Popen([path])
            launched += 1
        except Exception as exc:
            errors.append(f"{item.get('name', path)}: {exc}")

    if launched == 0 and errors:
        return jsonify({"status": "error", "message": "; ".join(errors[:5])}), 500

    log_activity("launch_workspace", {"workspace": ws.get("name"), "launched": launched})
    return jsonify({"status": "success", "launched": launched, "errors": errors})


@app.route('/api/workspace/item/toggle', methods=['POST'])
def toggle_workspace_item_web():
    """Pin/unpin (enable/disable) a single link/app inside a workspace."""
    data = request.get_json(silent=True) or {}
    identifier = data.get("workspace")
    item_index = data.get("item_index")

    idx, ws = _find_workspace_by_identifier(identifier)
    if ws is None:
        return jsonify({"status": "error", "message": "Workspace not found."}), 404

    items = ws.get("items", [])
    try:
        item_index = int(item_index)
    except (TypeError, ValueError):
        return jsonify({"status": "error", "message": "Invalid item."}), 400

    if not (0 <= item_index < len(items)):
        return jsonify({"status": "error", "message": "Item not found."}), 404

    items[item_index]["enabled"] = not items[item_index].get("enabled", True)
    save_config()
    return jsonify({"status": "success", "enabled": items[item_index]["enabled"]})


@app.route('/api/workspace/item/delete', methods=['POST'])
def delete_workspace_item_web():
    """Remove a single link/app from inside a workspace."""
    data = request.get_json(silent=True) or {}
    identifier = data.get("workspace")
    item_index = data.get("item_index")

    idx, ws = _find_workspace_by_identifier(identifier)
    if ws is None:
        return jsonify({"status": "error", "message": "Workspace not found."}), 404

    items = ws.get("items", [])
    try:
        item_index = int(item_index)
    except (TypeError, ValueError):
        return jsonify({"status": "error", "message": "Invalid item."}), 400

    if not (0 <= item_index < len(items)):
        return jsonify({"status": "error", "message": "Item not found."}), 404

    items.pop(item_index)
    save_config()
    return jsonify({"status": "success"})


@app.route('/api/fetch_apps', methods=['GET'])
def fetch_apps():
    active_apps = [a for a in CONFIG["custom_apps"] if a.get("enabled", True)]
    return jsonify(active_apps)

@app.route('/api/fetch_shortcuts', methods=['GET'])
def fetch_shortcuts():
    active_shortcuts = [s for s in CONFIG["custom_shortcuts"] if s.get("enabled", True)]
    return jsonify(active_shortcuts)

@app.route('/api/fetch_controls', methods=['GET'])
def fetch_controls():
    active_controls = [c for c in CONFIG.get("built_in_controls", []) if c.get("enabled", True)]
    return jsonify(active_controls)

@app.route('/api/launch_app', methods=['POST'])
def launch_app():
    data = request.json
    app_path = data.get('path')
    is_link = data.get('is_link', False)
    
    if app_path:
        try:
            if is_link:
                webbrowser.open(app_path)
            else:
                os.startfile(app_path) if os.name == 'nt' else subprocess.Popen(app_path)
            log_activity("launch_app", {"path": app_path, "is_link": is_link})
            return jsonify({"status": "success"})
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)}), 500
    return jsonify({"status": "error"}), 400

def _hid_enabled():
    return bool(CONFIG.get("hid", {}).get("enabled", False))


def _sync_hid_config():
    """Keep the separate HID manager synchronized with main.py config."""
    if not HID_MANAGER_AVAILABLE:
        return
    try:
        hid_manager.configure(
            enabled=_hid_enabled(),
            script_path=CONFIG.get("hid", {}).get("script_path", "hid_scripts"),
            capture_config=CONFIG.get("capture", {})
        )
    except Exception as e:
        print("HID Manager Sync Error:", e)


_sync_hid_config()


@app.route('/api/hid/status', methods=['GET'])
def hid_status():
    if not HID_MANAGER_AVAILABLE:
        return jsonify({"status": "error", "message": "hid_manager.py not found."}), 503
    try:
        return jsonify(hid_manager.status())
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/hid/toggle', methods=['POST'])
def hid_toggle():
    data = request.get_json(silent=True) or {}
    enabled = bool(data.get("enabled", False))
    CONFIG.setdefault("hid", {})["enabled"] = enabled
    save_config()
    _sync_hid_config()
    try:
        if HID_MANAGER_AVAILABLE:
            hid_manager.enable() if enabled else hid_manager.disable()
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
    return jsonify({"status": "success", "enabled": enabled})


@app.route('/api/hid/scripts', methods=['GET'])
def hid_scripts():
    if not HID_MANAGER_AVAILABLE:
        return jsonify([])
    try:
        return jsonify(hid_manager.list_scripts())
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/hid/script', methods=['GET'])
def hid_script_get():
    if not HID_MANAGER_AVAILABLE:
        return jsonify({"status": "error", "message": "hid_manager.py not found."}), 503
    name = request.args.get('name', '')
    try:
        return jsonify(hid_manager.get_script(name))
    except FileNotFoundError as e:
        return jsonify({"status": "error", "message": str(e)}), 404
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/hid/script', methods=['POST'])
def hid_script_save():
    if not HID_MANAGER_AVAILABLE:
        return jsonify({"status": "error", "message": "hid_manager.py not found."}), 503
    data = request.get_json(silent=True) or {}
    try:
        result = hid_manager.save_script(data.get("name", ""), data.get("content", ""))
        return jsonify(result)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/hid/script', methods=['DELETE'])
def hid_script_delete():
    if not HID_MANAGER_AVAILABLE:
        return jsonify({"status": "error", "message": "hid_manager.py not found."}), 503
    data = request.get_json(silent=True) or {}
    try:
        return jsonify(hid_manager.delete_script(data.get("name", "")))
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/hid/run', methods=['POST'])
def hid_script_run():
    if not HID_MANAGER_AVAILABLE:
        return jsonify({"status": "error", "message": "hid_manager.py not found."}), 503
    if not _hid_enabled():
        return jsonify({"status": "error", "message": "HID Manager is disabled."}), 403
    data = request.get_json(silent=True) or {}
    try:
        return jsonify(hid_manager.run_script(data.get("name", "")))
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/hid/devices', methods=['GET'])
def hid_devices():
    if not HID_MANAGER_AVAILABLE:
        return jsonify({"camera": [], "microphone": [], "screen": []})
    try:
        return jsonify(hid_manager.devices())
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/hid/capture/config', methods=['POST'])
def hid_capture_config():
    data = request.get_json(silent=True) or {}
    cap = CONFIG.setdefault("capture", {})
    for key in ("enabled", "camera_enabled", "microphone_enabled", "screen_enabled", "visible_recording_indicator"):
        if key in data:
            cap[key] = bool(data[key])
    for key in ("camera_device", "microphone_device", "screen_device", "screen_display", "output_path"):
        if key in data:
            cap[key] = data[key]
    save_config()
    _sync_hid_config()
    return jsonify({"status": "success", "capture": cap})


@app.route('/api/hid/capture/start', methods=['POST'])
def hid_capture_start():
    if not HID_MANAGER_AVAILABLE:
        return jsonify({"status": "error", "message": "hid_manager.py not found."}), 503
    if not _hid_enabled():
        return jsonify({"status": "error", "message": "HID Manager is disabled."}), 403
    CONFIG.setdefault("capture", {})["enabled"] = True
    save_config()
    _sync_hid_config()
    try:
        return jsonify(hid_manager.start_capture())
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/hid/capture/stop', methods=['POST'])
def hid_capture_stop():
    if not HID_MANAGER_AVAILABLE:
        return jsonify({"status": "error", "message": "hid_manager.py not found."}), 503
    try:
        result = hid_manager.stop_capture()
        CONFIG.setdefault("capture", {})["enabled"] = False
        save_config()
        return jsonify(result)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/open_url', methods=['POST'])
def open_url_on_pc():
    data = request.get_json(silent=True) or {}
    url = str(data.get("url", "")).strip()
    if not url:
        return jsonify({"status": "error", "message": "URL is required."}), 400
    if not url.lower().startswith(("http://", "https://")):
        url = "https://" + url
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return jsonify({"status": "error", "message": "Invalid HTTP/HTTPS URL."}), 400
    try:
        webbrowser.open(url)
        return jsonify({"status": "success", "url": url})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@socketio.on('media_control')
def handle_media(data):
    action = data.get('action')
    log_activity("media_control", {"action": action}, device=_client_device_label())
    matched = False
    for sc in CONFIG["custom_shortcuts"]:
        if sc.get("enabled", True) and sc["name"] == action:
            keys = sc["keys"]
            try:
                if len(keys) == 1:
                    pyautogui.press(keys[0])
                else:
                    for key in keys:
                        pyautogui.keyDown(key)
                        time.sleep(0.05)
                    for key in reversed(keys):
                        pyautogui.keyUp(key)
                        time.sleep(0.05)
            except Exception as e:
                print(f"Shortcut Error ({sc['name']}):", e)
            matched = True
            break
            
    if matched:
        return

    try:
        if action == 'play_pause': pyautogui.press('playpause')
        elif action == 'vol_up': pyautogui.press('volumeup')
        elif action == 'vol_down': pyautogui.press('volumedown')
        elif action == 'mute': pyautogui.press('volumemute')
        elif action == 'switch_audio': pyautogui.press('b')
        elif action == 'switch_subtitle': pyautogui.press('v')
        elif action == 'arrow_up': pyautogui.press('up')
        elif action == 'arrow_down': pyautogui.press('down')
        elif action == 'arrow_left': pyautogui.press('left')
        elif action == 'arrow_right': pyautogui.press('right')
        elif action == 'ctrl_up': pyautogui.hotkey('ctrl', 'up')
        elif action == 'ctrl_down': pyautogui.hotkey('ctrl', 'down')
        elif action == 'ctrl_left': pyautogui.hotkey('ctrl', 'left')
        elif action == 'ctrl_right': pyautogui.hotkey('ctrl', 'right')
        elif action == 'minimize_all': pyautogui.hotkey('win', 'd')
        elif action == 'close_app': pyautogui.hotkey('alt', 'f4')
        elif action == 'screenshot':
            target_dir = CONFIG.get("screenshot_path", r"C:\Users\PanicButton\Pictures\Screenshots")
            if not os.path.exists(target_dir):
                os.makedirs(target_dir, exist_ok=True)
                
            screenshot = ImageGrab.grab(all_screens=True)
            save_path = os.path.join(target_dir, f"ASSHOLE_Screenshot_{int(time.time())}.png")
            screenshot.save(save_path)
            print(f"Screenshot Saved: {save_path}")
        elif action == 'record_screen':
            pyautogui.hotkey('win', 'alt', 'r')
        elif action == 'bright_up':
            curr = sbc.get_brightness()[0]
            sbc.set_brightness(min(100, curr + 10))
        elif action == 'bright_down':
            curr = sbc.get_brightness()[0]
            sbc.set_brightness(max(0, curr - 10))
        elif action == 'lock_pc' and os.name == 'nt':
            ctypes.windll.user32.LockWorkStation()
        elif action == 'sleep_pc' and os.name == 'nt':
            os.system("rundll32.exe powrprof.dll,SetSuspendState 0,1,0")
        elif action == 'restart_pc' and os.name == 'nt':
            os.system("shutdown /r /t 1")
        elif action == 'shutdown_pc' and os.name == 'nt':
            os.system("shutdown /s /t 1")
    except Exception as e:
        print("Control Execution Error:", e)

@socketio.on('soundboard_play')
def handle_soundboard_play(data):
    path = str((data or {}).get("path", "")).strip()
    ok, message = SOUND_PLAYER.play(path)
    socketio.emit("soundboard_status", {
        "status": "playing" if ok else "error",
        "message": message,
        "path": SOUND_PLAYER.current_path if ok else path
    })


@socketio.on('soundboard_control')
def handle_soundboard_control(data):
    action = (data or {}).get("action")
    if action == "pause":
        ok = SOUND_PLAYER.pause_toggle()
        message = "Paused/Resumed"
    elif action == "stop":
        ok = SOUND_PLAYER.stop()
        message = "Stopped"
    else:
        ok = False
        message = "Unknown player action"
    socketio.emit("soundboard_status", {
        "status": "ok" if ok else "error",
        "message": message,
        "path": SOUND_PLAYER.current_path
    })


@socketio.on('keyboard_action')
def handle_keyboard_action(data):
    action_type = data.get('type')
    payload = data.get('payload')
    try:
        if action_type == 'press': pyautogui.press(payload)
        elif action_type == 'write': pyautogui.write(payload)
    except Exception as e:
        print("Keyboard Action Error:", e)

@socketio.on('mouse_action')
def handle_mouse_action(data):
    action = data.get('action')
    try:
        if action == 'move':
            pyautogui.moveRel(data.get('dx', 0), data.get('dy', 0))
        elif action == 'click': pyautogui.click()
        elif action == 'right_click': pyautogui.rightClick()
        elif action == 'double_click': pyautogui.doubleClick()
        elif action == 'scroll': pyautogui.scroll(data.get('clicks', 0))
    except Exception as e:
        print("Mouse Action Error:", e)

def run_flask():
    socketio.run(app, host='0.0.0.0', port=5000, debug=False, use_reloader=False)

def start_pc_dashboard():
    root = tk.Tk()
    root.title("ASSHOLE DECK")
    root.geometry("540x780")
    root.configure(bg="#090d16")
    root.minsize(480, 560)
    root.resizable(True, True)

    # Windows taskbar/app identity + icon fix.
    if os.name == "nt":
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                "r0otpapa.ASSHOLEDECK"
            )
        except Exception:
            pass
    SOUND_PLAYER.attach_root(root)

    icon_path = os.path.join(BUNDLE_DIR, "icon.ico")
    if os.path.isfile(icon_path):
        try:
            root.iconbitmap(default=icon_path)
            root.iconbitmap(icon_path)
        except Exception as e:
            print("ICO load warning:", e)

    # Optional PNG fallback for Tk/Windows environments where ICO scaling fails.
    icon_png = os.path.join(BUNDLE_DIR, "icon.png")
    if os.path.isfile(icon_png):
        try:
            icon_img = Image.open(icon_png)
            root_icon = ImageTk.PhotoImage(icon_img)
            root.iconphoto(True, root_icon)
            root._app_icon_image = root_icon
        except Exception as e:
            print("PNG icon fallback warning:", e)

    header_frame = tk.Frame(root, bg="#0e1420", pady=12)
    header_frame.pack(fill="x")
    
    tk.Label(header_frame, text="⚡ ASSHOLE DECK", font=("Segoe UI", 15, "bold"), fg="#ff4757", bg="#0e1420").pack()
    tk.Label(header_frame, text="One Hole Infinite Control", font=("Segoe UI", 9), fg="#64748b", bg="#0e1420").pack()

    footer_frame = tk.Frame(root, bg="#060910", pady=8)
    footer_frame.pack(side="bottom", fill="x")

    tk.Label(footer_frame, text="Created by r0otpapa", font=("Segoe UI", 8, "bold"), fg="#64748b", bg="#060910").pack(side="left", padx=15)
    
    github_btn = tk.Button(footer_frame, text="🌐 GitHub Repo", command=lambda: webbrowser.open("https://github.com/r0otpapa/AssHole-Engine"), font=("Segoe UI", 8, "bold"), bg="#162032", fg="#38bdf8", relief="flat", padx=8, pady=2, cursor="hand2")
    github_btn.pack(side="right", padx=15)

    content_frame = tk.Frame(root, bg="#090d16", padx=20, pady=10)
    content_frame.pack(fill="both", expand=True)

    qr_label = tk.Label(content_frame, bg="#090d16")
    qr_label.pack(pady=2)

    url_label = tk.Label(content_frame, text="", font=("Segoe UI", 11, "bold"), fg="#34d399", bg="#090d16")
    url_label.pack(pady=2)

    def update_qr_and_ip():
        ip = get_local_ip()
        url = f"http://{ip}:5000"
        
        qr = qrcode.QRCode(box_size=3, border=2)
        qr.add_data(url)
        qr.make(fit=True)
        qr_img = qr.make_image(fill_color="#ff4757", back_color="#090d16")
        
        qr_path = os.path.join(os.path.expanduser("~"), "qr_code_temp.png")
        qr_img.save(qr_path)

        img = Image.open(qr_path)
        tk_img = ImageTk.PhotoImage(img)
        qr_label.configure(image=tk_img)
        qr_label.image = tk_img
        url_label.configure(text=url)

    btn_panel = tk.Frame(content_frame, bg="#090d16")
    btn_panel.pack(fill="x", pady=5)

    tk.Button(btn_panel, text="🔄 Refresh Connection", command=update_qr_and_ip, bg="#162032", fg="#38bdf8", font=("Segoe UI", 9, "bold"), relief="flat", padx=10, pady=6, cursor="hand2").pack(side="left", expand=True, fill="x", padx=4)
    tk.Button(btn_panel, text="🌐 Open Local Web UI", command=lambda: webbrowser.open("http://127.0.0.1:5000"), bg="#162032", fg="#34d399", font=("Segoe UI", 9, "bold"), relief="flat", padx=10, pady=6, cursor="hand2").pack(side="right", expand=True, fill="x", padx=4)

    notebook = ttk.Notebook(content_frame)
    notebook.pack(fill="both", expand=True, pady=5)

    style = ttk.Style()
    style.theme_use('default')
    style.configure('TNotebook', background='#090d16', borderwidth=0)
    style.configure('TNotebook.Tab', background='#162032', foreground='#94a3b8', padding=[8, 4], font=('Segoe UI', 8, 'bold'))
    style.map('TNotebook.Tab', background=[('selected', '#ff4757')], foreground=[('selected', '#ffffff')])

    # Helper for Reordering Items
    def move_item(listbox, item_list, direction):
        sel = listbox.curselection()
        if not sel:
            return
        idx = sel[0]
        new_idx = idx + direction
        if 0 <= new_idx < len(item_list):
            item_list[idx], item_list[new_idx] = item_list[new_idx], item_list[idx]
            save_config()
            return new_idx
        return None

    # ================= 📂 FOLDERS TAB =================
    tab_folders = tk.Frame(notebook, bg="#121923")
    notebook.add(tab_folders, text="📂 Folders")
    
    list_folders = tk.Listbox(tab_folders, bg="#162032", fg="#fff", selectbackground="#ff4757", borderwidth=0, font=("Segoe UI", 9))
    list_folders.pack(fill="both", expand=True, padx=6, pady=6)

    def refresh_folder_list():
        list_folders.delete(0, tk.END)
        for folder in CONFIG["media_folders"]:
            status = "📌 [Pinned]" if folder.get("enabled", True) else "⚪ [Unpinned]"
            list_folders.insert(tk.END, f"{status} {folder['path']}")

    def toggle_pin_folder():
        sel = list_folders.curselection()
        if sel:
            idx = sel[0]
            current_state = CONFIG["media_folders"][idx].get("enabled", True)
            CONFIG["media_folders"][idx]["enabled"] = not current_state
            save_config()
            refresh_folder_list()

    def move_folder(direction):
        new_idx = move_item(list_folders, CONFIG["media_folders"], direction)
        if new_idx is not None:
            refresh_folder_list()
            list_folders.selection_set(new_idx)
            list_folders.see(new_idx)

    def add_media_folder():
        folder = filedialog.askdirectory()
        if folder and not any(m["path"] == folder for m in CONFIG["media_folders"]):
            CONFIG["media_folders"].append({"path": folder, "enabled": True})
            save_config()
            refresh_folder_list()
            new_idx = len(CONFIG["media_folders"]) - 1
            list_folders.selection_set(new_idx)
            list_folders.see(new_idx)

    def delete_media_folder():
        sel = list_folders.curselection()
        if sel:
            CONFIG["media_folders"].pop(sel[0])
            save_config()
            refresh_folder_list()

    f_btns = tk.Frame(tab_folders, bg="#121923")
    f_btns.pack(fill="x", padx=6, pady=6)

    tk.Button(f_btns, text="📌 Toggle Pin", command=toggle_pin_folder, bg="#1e293b", fg="#34d399", relief="flat", padx=4, pady=3, cursor="hand2").pack(side="left", padx=2)
    tk.Button(f_btns, text="➕ Add", command=add_media_folder, bg="#1e293b", fg="#fff", relief="flat", padx=4, pady=3, cursor="hand2").pack(side="left", padx=2)
    tk.Button(f_btns, text="⬆️", command=lambda: move_folder(-1), bg="#1e293b", fg="#fff", relief="flat", padx=5, pady=3, cursor="hand2").pack(side="left", padx=2)
    tk.Button(f_btns, text="⬇️", command=lambda: move_folder(1), bg="#1e293b", fg="#fff", relief="flat", padx=5, pady=3, cursor="hand2").pack(side="left", padx=2)
    tk.Button(f_btns, text="🗑️ Delete", command=delete_media_folder, bg="#7f1d1d", fg="#fff", relief="flat", padx=4, pady=3, cursor="hand2").pack(side="right", padx=2)

    # ================= 🚀 APPS & LINKS TAB =================
    tab_apps = tk.Frame(notebook, bg="#121923")
    notebook.add(tab_apps, text="🚀 Apps & Links")

    list_apps = tk.Listbox(tab_apps, bg="#162032", fg="#fff", selectbackground="#ff4757", borderwidth=0, font=("Segoe UI", 9))
    list_apps.pack(fill="both", expand=True, padx=6, pady=6)

    def refresh_app_list():
        list_apps.delete(0, tk.END)
        for item in CONFIG.get("custom_apps", []):
            status = "📌 [Pinned]" if item.get("enabled", True) else "⚪ [Unpinned]"
            icon = "🌐" if item.get("is_link") else "🚀"
            list_apps.insert(tk.END, f"{status} {icon} {item['name']}")

        workspaces = CONFIG.get("workspaces", [])
        if workspaces:
            list_apps.insert(tk.END, "")
            list_apps.insert(tk.END, "──────── 🗂 WORKSPACES ────────")
            for ws in workspaces:
                count = len(ws.get("items", []))
                enabled = ws.get("enabled", True)
                status = "📌" if enabled else "⚪"
                list_apps.insert(tk.END, f"{status} 🗂 {ws.get('name', 'Workspace')} [{count} items]")

    def toggle_pin_app():
        sel = list_apps.curselection()
        if not sel:
            return
        idx = sel[0]
        if idx >= len(CONFIG.get("custom_apps", [])):
            return
        current_state = CONFIG["custom_apps"][idx].get("enabled", True)
        CONFIG["custom_apps"][idx]["enabled"] = not current_state
        save_config()
        refresh_app_list()

    def add_custom_link():
        dialog = DarkMultiInputDialog(root, "Add Web Link", [("Enter Link Name:", "name"), ("Enter URL (e.g. google.com):", "url")])
        if dialog.results:
            name = dialog.results.get("name")
            url = dialog.results.get("url")
            if not url.startswith(("http://", "https://")):
                url = "https://" + url
            CONFIG.setdefault("custom_apps", []).append({"name": name, "path": url, "is_link": True, "enabled": True})
            save_config()
            refresh_app_list()

    def move_app(direction):
        sel = list_apps.curselection()
        if not sel:
            return
        idx = sel[0]
        custom_apps = CONFIG.get("custom_apps", [])
        workspaces = CONFIG.get("workspaces", [])

        if idx < len(custom_apps):
            new_idx = move_item(list_apps, custom_apps, direction)
            if new_idx is not None:
                refresh_app_list()
                list_apps.selection_set(new_idx)
            return

        # Workspace rows are appended after custom_apps + 2 header rows
        # (a blank spacer row and the "──── WORKSPACES ────" label row).
        ws_start = len(custom_apps) + 2
        ws_idx = idx - ws_start
        if 0 <= ws_idx < len(workspaces):
            new_ws_idx = ws_idx + direction
            if 0 <= new_ws_idx < len(workspaces):
                workspaces[ws_idx], workspaces[new_ws_idx] = workspaces[new_ws_idx], workspaces[ws_idx]
                save_config()
                refresh_app_list()
                list_apps.selection_set(ws_start + new_ws_idx)

    # ---------------- WORKSPACE MANAGER ----------------
    def open_workspace_manager():
        CONFIG.setdefault("workspaces", [])
        win = tk.Toplevel(root)
        win.title("Workspace Manager")
        win.configure(bg="#090d16")
        win.geometry("680x500")
        win.minsize(560, 400)
        win.resizable(True, True)
        win.transient(root)
        win.grab_set()

        tk.Label(win, text="🗂 Workspace Manager", font=("Segoe UI", 13, "bold"), fg="#ff4757", bg="#090d16").pack(pady=(12, 2))
        tk.Label(win, text="Group multiple EXE files and web links into one-click launch buttons.", font=("Segoe UI", 8), fg="#64748b", bg="#090d16").pack(pady=(0, 10))

        body = tk.Frame(win, bg="#090d16")
        body.pack(fill="both", expand=True, padx=10, pady=5)

        left = tk.Frame(body, bg="#121923", width=190)
        left.pack(side="left", fill="y", padx=(0, 6))
        left.pack_propagate(False)
        right = tk.Frame(body, bg="#121923")
        right.pack(side="left", fill="both", expand=True)

        tk.Label(left, text="WORKSPACES", font=("Segoe UI", 8, "bold"), fg="#94a3b8", bg="#121923").pack(anchor="w", padx=8, pady=8)
        ws_list = tk.Listbox(left, bg="#162032", fg="#fff", selectbackground="#ff4757", selectforeground="#fff", exportselection=False, borderwidth=0, font=("Segoe UI", 9))
        ws_list.pack(fill="both", expand=True, padx=6, pady=(0, 6))

        tk.Label(right, text="ITEMS", font=("Segoe UI", 8, "bold"), fg="#94a3b8", bg="#121923").pack(anchor="w", padx=8, pady=8)
        item_list = tk.Listbox(right, bg="#162032", fg="#fff", selectbackground="#ff4757", selectforeground="#fff", exportselection=False, borderwidth=0, font=("Segoe UI", 9))
        item_list.pack(fill="both", expand=True, padx=6, pady=(0, 6))

        def selected_workspace():
            sel = ws_list.curselection()
            if not sel:
                return None
            return CONFIG["workspaces"][sel[0]]

        def refresh_ws():
            ws_list.delete(0, tk.END)
            for ws in CONFIG["workspaces"]:
                icon = "📌" if ws.get("enabled", True) else "⚪"
                ws_list.insert(tk.END, f"{icon} {ws.get('name', 'Workspace')}")
            if CONFIG["workspaces"] and not ws_list.curselection():
                ws_list.selection_set(0)
            refresh_items()

        def refresh_items(event=None):
            item_list.delete(0, tk.END)
            ws = selected_workspace()
            if not ws:
                return
            for item in ws.get("items", []):
                pin_icon = "📌" if item.get("enabled", True) else "⚪"
                type_icon = "🌐" if item.get("is_link") else "🚀"
                item_list.insert(tk.END, f"{pin_icon} {type_icon} {item.get('name', 'Item')}  —  {item.get('path', '')}")

        def create_workspace():
            dialog = DarkMultiInputDialog(win, "New Workspace", [("Workspace Name:", "name")])
            if dialog.results:
                name = dialog.results["name"]
                if any(w.get("name", "").lower() == name.lower() for w in CONFIG["workspaces"]):
                    messagebox.showwarning("Workspace", "A workspace with this name already exists.", parent=win)
                    return
                CONFIG["workspaces"].append({"name": name, "enabled": True, "items": []})
                save_config()
                refresh_ws()
                ws_list.selection_clear(0, tk.END)
                ws_list.selection_set(tk.END)
                refresh_items()
                refresh_app_list()

        def delete_workspace():
            sel = ws_list.curselection()
            if not sel:
                return
            CONFIG["workspaces"].pop(sel[0])
            save_config()
            refresh_ws()
            refresh_app_list()

        def toggle_workspace():
            ws = selected_workspace()
            if ws is None:
                return
            ws["enabled"] = not ws.get("enabled", True)
            save_config()
            refresh_ws()
            refresh_app_list()

        def add_workspace_exe():
            ws = selected_workspace()
            if ws is None:
                messagebox.showwarning("Workspace", "Create/select a workspace first.", parent=win)
                return
            path = filedialog.askopenfilename(parent=win, filetypes=[("Executables", "*.exe"), ("All files", "*.*")])
            if path:
                name = os.path.splitext(os.path.basename(path))[0]
                ws.setdefault("items", []).append({"name": name, "path": path, "is_link": False, "enabled": True})
                save_config()
                refresh_items()
                refresh_app_list()

        def add_workspace_url():
            ws = selected_workspace()
            if ws is None:
                messagebox.showwarning("Workspace", "Create/select a workspace first.", parent=win)
                return
            dialog = DarkMultiInputDialog(win, "Add Workspace Link", [("Link Name:", "name"), ("URL:", "url")])
            if dialog.results:
                url = dialog.results["url"]
                if not url.startswith(("http://", "https://")):
                    url = "https://" + url
                ws.setdefault("items", []).append({"name": dialog.results["name"], "path": url, "is_link": True, "enabled": True})
                save_config()
                refresh_items()
                refresh_app_list()

        def toggle_workspace_item():
            ws = selected_workspace()
            sel = item_list.curselection()
            if ws is None or not sel:
                return
            items = ws.get("items", [])
            if sel[0] >= len(items):
                return
            items[sel[0]]["enabled"] = not items[sel[0]].get("enabled", True)
            save_config()
            refresh_items()
            item_list.selection_set(sel[0])
            refresh_app_list()

        def remove_workspace_item():
            ws = selected_workspace()
            sel = item_list.curselection()
            if ws is None or not sel:
                return
            ws["items"].pop(sel[0])
            save_config()
            refresh_items()
            refresh_app_list()

        def launch_workspace():
            ws = selected_workspace()
            if ws is None:
                return
            if not ws.get("enabled", True):
                messagebox.showwarning("Workspace", "This workspace is disabled/unpinned.", parent=win)
                return
            errors = []
            launched = 0
            for item in ws.get("items", []):
                if not item.get("enabled", True):
                    continue
                path = str(item.get("path", "")).strip()
                try:
                    if not path:
                        continue
                    if item.get("is_link", False):
                        webbrowser.open(path)
                    elif os.name == "nt":
                        os.startfile(path)
                    else:
                        subprocess.Popen([path])
                    launched += 1
                except Exception as exc:
                    errors.append(f"{item.get('name', path)}: {exc}")
            if errors:
                messagebox.showwarning("Workspace Launch", f"Opened {launched} item(s).\n\n" + "\n".join(errors[:8]), parent=win)

        ws_list.bind("<<ListboxSelect>>", refresh_items)

        controls = tk.Frame(win, bg="#090d16")
        controls.pack(fill="x", padx=10, pady=(5, 10))
        tk.Button(controls, text="➕ Workspace", command=create_workspace, bg="#1e293b", fg="#fff", relief="flat", padx=7, pady=4).pack(side="left", padx=2)
        tk.Button(controls, text="📌 Enable", command=toggle_workspace, bg="#1e293b", fg="#34d399", relief="flat", padx=7, pady=4).pack(side="left", padx=2)
        tk.Button(controls, text="➕ .exe", command=add_workspace_exe, bg="#1e293b", fg="#fff", relief="flat", padx=7, pady=4).pack(side="left", padx=2)
        tk.Button(controls, text="🌐 URL", command=add_workspace_url, bg="#1e293b", fg="#38bdf8", relief="flat", padx=7, pady=4).pack(side="left", padx=2)
        tk.Button(controls, text="📌 Pin Item", command=toggle_workspace_item, bg="#1e293b", fg="#34d399", relief="flat", padx=7, pady=4).pack(side="left", padx=2)
        tk.Button(controls, text="🗑 Item", command=remove_workspace_item, bg="#1e293b", fg="#fca5a5", relief="flat", padx=7, pady=4).pack(side="left", padx=2)
        tk.Button(controls, text="🗑 Workspace", command=delete_workspace, bg="#7f1d1d", fg="#fff", relief="flat", padx=7, pady=4).pack(side="left", padx=2)
        tk.Button(controls, text="🚀 Open All", command=launch_workspace, bg="#ff4757", fg="#fff", font=("Segoe UI", 9, "bold"), relief="flat", padx=10, pady=4).pack(side="right", padx=2)

        refresh_ws()

    a_btns = tk.Frame(tab_apps, bg="#121923")
    a_btns.pack(fill="x", padx=6, pady=6)

    tk.Button(a_btns, text="📌 Toggle Pin", command=toggle_pin_app, bg="#1e293b", fg="#34d399", relief="flat", padx=4, pady=3, cursor="hand2").pack(side="left", padx=2)
    tk.Button(a_btns, text="➕ .exe", command=lambda: [CONFIG["custom_apps"].append({"name": os.path.basename(f).replace('.exe', '').capitalize(), "path": f, "is_link": False, "enabled": True}) if (f:=filedialog.askopenfilename(filetypes=[("Executables", "*.exe")])) else None, save_config(), refresh_app_list()], bg="#1e293b", fg="#fff", relief="flat", padx=4, pady=3, cursor="hand2").pack(side="left", padx=2)
    tk.Button(a_btns, text="🌐 URL", command=add_custom_link, bg="#1e293b", fg="#38bdf8", relief="flat", padx=4, pady=3, cursor="hand2").pack(side="left", padx=2)
    tk.Button(a_btns, text="🗂 Workspace", command=open_workspace_manager, bg="#1e293b", fg="#fbbf24", relief="flat", padx=5, pady=3, cursor="hand2").pack(side="left", padx=2)
    tk.Button(a_btns, text="⬆️", command=lambda: move_app(-1), bg="#1e293b", fg="#fff", relief="flat", padx=4, pady=3, cursor="hand2").pack(side="left", padx=2)
    tk.Button(a_btns, text="⬇️", command=lambda: move_app(1), bg="#1e293b", fg="#fff", relief="flat", padx=4, pady=3, cursor="hand2").pack(side="left", padx=2)
    tk.Button(a_btns, text="🗑️ Delete", command=lambda: [CONFIG["custom_apps"].pop(sel[0]) if (sel:=list_apps.curselection()) and sel[0] < len(CONFIG.get("custom_apps", [])) else None, save_config(), refresh_app_list()], bg="#7f1d1d", fg="#fff", relief="flat", padx=4, pady=3, cursor="hand2").pack(side="right", padx=2)

    # ================= ⚡ SHORTCUTS TAB =================
    tab_sc = tk.Frame(notebook, bg="#121923")
    notebook.add(tab_sc, text="⚡ Shortcuts")

    list_sc = tk.Listbox(tab_sc, bg="#162032", fg="#fff", selectbackground="#ff4757", borderwidth=0, font=("Segoe UI", 9))
    list_sc.pack(fill="both", expand=True, padx=6, pady=6)

    def refresh_sc_list():
        list_sc.delete(0, tk.END)
        for sc in CONFIG["custom_shortcuts"]:
            status = "📌 [Pinned]" if sc.get("enabled", True) else "⚪ [Unpinned]"
            list_sc.insert(tk.END, f"{status} {sc.get('icon', '⭐')} {sc['name']} [{'+'.join(sc['keys']).upper()}]")

    def toggle_pin_shortcut():
        sel = list_sc.curselection()
        if sel:
            idx = sel[0]
            current_state = CONFIG["custom_shortcuts"][idx].get("enabled", True)
            CONFIG["custom_shortcuts"][idx]["enabled"] = not current_state
            save_config()
            refresh_sc_list()

    def add_custom_shortcut():
        dialog = DarkMultiInputDialog(root, "Add Shortcut", [("Enter Shortcut Name:", "name"), ("Enter Keys (comma separated, e.g. ctrl,r):", "keys")])
        if dialog.results:
            name = dialog.results.get("name")
            keys_str = dialog.results.get("keys")
            keys = [k.strip().lower() for k in keys_str.split(",")]
            CONFIG["custom_shortcuts"].append({"name": name, "keys": keys, "category": "Custom", "icon": "⚡", "enabled": True})
            save_config()
            refresh_sc_list()

    def move_sc(direction):
        new_idx = move_item(list_sc, CONFIG["custom_shortcuts"], direction)
        if new_idx is not None:
            refresh_sc_list()
            list_sc.selection_set(new_idx)

    sc_btns = tk.Frame(tab_sc, bg="#121923")
    sc_btns.pack(fill="x", padx=6, pady=6)
    tk.Button(sc_btns, text="📌 Toggle Pin", command=toggle_pin_shortcut, bg="#1e293b", fg="#34d399", relief="flat", padx=4, pady=3, cursor="hand2").pack(side="left", padx=2)
    tk.Button(sc_btns, text="➕ Add", command=add_custom_shortcut, bg="#1e293b", fg="#fff", relief="flat", padx=4, pady=3, cursor="hand2").pack(side="left", padx=2)
    tk.Button(sc_btns, text="⬆️", command=lambda: move_sc(-1), bg="#1e293b", fg="#fff", relief="flat", padx=4, pady=3, cursor="hand2").pack(side="left", padx=2)
    tk.Button(sc_btns, text="⬇️", command=lambda: move_sc(1), bg="#1e293b", fg="#fff", relief="flat", padx=4, pady=3, cursor="hand2").pack(side="left", padx=2)
    tk.Button(sc_btns, text="🗑️ Delete", command=lambda: [CONFIG["custom_shortcuts"].pop(sel[0]) if (sel:=list_sc.curselection()) else None, save_config(), refresh_sc_list()], bg="#7f1d1d", fg="#fff", relief="flat", padx=4, pady=3, cursor="hand2").pack(side="right", padx=2)

    # ================= 🔊 SOUND PLAYER TAB =================
    tab_player = tk.Frame(notebook, bg="#121923")
    notebook.add(tab_player, text="🔊 Player")

    player_status = tk.Label(
        tab_player, text="Soundboard Player",
        font=("Segoe UI", 11, "bold"),
        fg="#a78bfa", bg="#121923"
    )
    player_status.pack(anchor="w", padx=10, pady=(10, 5))

    player_current = tk.Label(
        tab_player, text="No sound selected",
        font=("Segoe UI", 9),
        fg="#94a3b8", bg="#121923",
        wraplength=470, justify="left"
    )
    player_current.pack(fill="x", padx=10, pady=5)

    player_list = tk.Listbox(
        tab_player, bg="#162032", fg="#fff",
        selectbackground="#a855f7", borderwidth=0,
        font=("Segoe UI", 9)
    )
    player_list.pack(fill="both", expand=True, padx=8, pady=6)

    player_paths = []

    def refresh_player_list():
        player_list.delete(0, tk.END)
        player_paths.clear()
        sound_root = CONFIG.get("soundboard_path", "").strip()
        if not os.path.isdir(sound_root):
            player_list.insert(tk.END, "Soundboard folder does not exist.")
            return
        def walk_audio(path):
            try:
                entries = sorted(os.scandir(path), key=lambda e: e.name.lower())
                for entry in entries:
                    try:
                        if entry.is_dir(follow_symlinks=False):
                            walk_audio(entry.path)
                        elif entry.is_file(follow_symlinks=False) and entry.name.lower().endswith(SOUNDBOARD_EXTS):
                            player_paths.append(entry.path)
                            rel = os.path.relpath(entry.path, sound_root)
                            player_list.insert(tk.END, rel)
                    except (PermissionError, OSError):
                        continue
            except (PermissionError, OSError):
                pass
        walk_audio(sound_root)

    def play_selected_sound():
        sel = player_list.curselection()
        if not sel or sel[0] >= len(player_paths):
            return
        path = player_paths[sel[0]]
        ok, message = SOUND_PLAYER.play(path)
        player_current.configure(text=os.path.basename(path) if ok else message)

    def stop_sound():
        SOUND_PLAYER.stop()
        player_current.configure(text="Stopped")

    def pause_sound():
        SOUND_PLAYER.pause_toggle()
        player_current.configure(text="Paused / Resumed")

    player_btns = tk.Frame(tab_player, bg="#121923")
    player_btns.pack(fill="x", padx=8, pady=5)

    tk.Button(
        player_btns, text="▶ Play", command=play_selected_sound,
        bg="#7c3aed", fg="#fff", relief="flat", padx=10, pady=5
    ).pack(side="left", padx=2)
    tk.Button(
        player_btns, text="⏯ Pause", command=pause_sound,
        bg="#1e293b", fg="#fff", relief="flat", padx=10, pady=5
    ).pack(side="left", padx=2)
    tk.Button(
        player_btns, text="⏹ Stop", command=stop_sound,
        bg="#7f1d1d", fg="#fff", relief="flat", padx=10, pady=5
    ).pack(side="left", padx=2)
    tk.Button(
        player_btns, text="🔄 Refresh", command=refresh_player_list,
        bg="#1e293b", fg="#38bdf8", relief="flat", padx=10, pady=5
    ).pack(side="right", padx=2)

    volume_frame = tk.Frame(tab_player, bg="#121923")
    volume_frame.pack(fill="x", padx=8, pady=(4, 10))
    tk.Label(volume_frame, text="Volume", fg="#94a3b8", bg="#121923").pack(side="left")
    volume_scale = tk.Scale(
        volume_frame, from_=0, to=100, orient="horizontal",
        bg="#121923", fg="#fff", highlightthickness=0,
        troughcolor="#162032", command=lambda value: SOUND_PLAYER.set_volume(value)
    )
    volume_scale.set(SOUND_PLAYER.volume)
    volume_scale.pack(side="left", fill="x", expand=True, padx=8)

    # ================= ⚙️ SETTINGS TAB (scrollable) =================
    tab_settings_outer = tk.Frame(notebook, bg="#121923")
    notebook.add(tab_settings_outer, text="⚙️ Settings")

    settings_canvas = tk.Canvas(tab_settings_outer, bg="#121923", highlightthickness=0)
    settings_scrollbar = tk.Scrollbar(tab_settings_outer, orient="vertical", command=settings_canvas.yview)
    settings_canvas.configure(yscrollcommand=settings_scrollbar.set)

    settings_scrollbar.pack(side="right", fill="y")
    settings_canvas.pack(side="left", fill="both", expand=True)

    tab_settings = tk.Frame(settings_canvas, bg="#121923", padx=10, pady=10)
    settings_window_id = settings_canvas.create_window((0, 0), window=tab_settings, anchor="nw")

    def _on_settings_frame_configure(event=None):
        settings_canvas.configure(scrollregion=settings_canvas.bbox("all"))

    def _on_settings_canvas_configure(event):
        settings_canvas.itemconfig(settings_window_id, width=event.width)

    tab_settings.bind("<Configure>", _on_settings_frame_configure)
    settings_canvas.bind("<Configure>", _on_settings_canvas_configure)

    def _on_settings_mousewheel(event):
        settings_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def _bind_settings_mousewheel(event):
        settings_canvas.bind_all("<MouseWheel>", _on_settings_mousewheel)

    def _unbind_settings_mousewheel(event):
        settings_canvas.unbind_all("<MouseWheel>")

    settings_canvas.bind("<Enter>", _bind_settings_mousewheel)
    settings_canvas.bind("<Leave>", _unbind_settings_mousewheel)

    tk.Label(
        tab_settings,
        text="📸 Camera / Screenshot Directory:",
        font=("Segoe UI", 9, "bold"),
        fg="#38bdf8",
        bg="#121923"
    ).pack(anchor="w", pady=(5, 2))

    path_frame = tk.Frame(tab_settings, bg="#121923")
    path_frame.pack(fill="x", pady=5)

    path_entry = tk.Entry(
        path_frame,
        bg="#162032",
        fg="#ffffff",
        insertbackground="#ff4757",
        relief="flat",
        font=("Segoe UI", 9)
    )
    path_entry.pack(side="left", fill="x", expand=True, ipady=4, padx=(0, 5))
    path_entry.insert(
        0,
        CONFIG.get("screenshot_path", r"C:\Users\PanicButton\Pictures\Screenshots")
    )

    def browse_cam_dir():
        dir_selected = filedialog.askdirectory()
        if dir_selected:
            path_entry.delete(0, tk.END)
            path_entry.insert(0, dir_selected)

    tk.Button(
        path_frame,
        text="📁 Browse",
        command=browse_cam_dir,
        bg="#1e293b",
        fg="#fff",
        relief="flat",
        padx=8,
        cursor="hand2"
    ).pack(side="right")

    # ================= ⌨ HID SETTINGS =================
    tk.Label(
        tab_settings,
        text="⌨ HID Script Directory:",
        font=("Segoe UI", 9, "bold"),
        fg="#38bdf8",
        bg="#121923"
    ).pack(anchor="w", pady=(15, 2))

    hid_path_frame = tk.Frame(tab_settings, bg="#121923")
    hid_path_frame.pack(fill="x", pady=5)

    hid_path_entry = tk.Entry(
        hid_path_frame,
        bg="#162032",
        fg="#ffffff",
        insertbackground="#ff4757",
        relief="flat",
        font=("Segoe UI", 9)
    )
    hid_path_entry.pack(side="left", fill="x", expand=True, ipady=4, padx=(0, 5))
    hid_path_entry.insert(
        0,
        CONFIG.get("hid", {}).get("script_path", "hid_scripts")
    )

    def browse_hid_dir():
        dir_selected = filedialog.askdirectory()
        if dir_selected:
            hid_path_entry.delete(0, tk.END)
            hid_path_entry.insert(0, dir_selected)

    tk.Button(
        hid_path_frame,
        text="📁 Browse",
        command=browse_hid_dir,
        bg="#1e293b",
        fg="#fff",
        relief="flat",
        padx=8,
        cursor="hand2"
    ).pack(side="right")

    tk.Label(
        tab_settings,
        text="Scripts are saved here and shown in the Web UI HID manager.",
        font=("Segoe UI", 8),
        fg="#64748b",
        bg="#121923"
    ).pack(anchor="w", pady=(0, 2))

    # ================= 🎥 CAPTURE SETTINGS =================
    tk.Label(
        tab_settings,
        text="🎥 Capture Output Directory:",
        font=("Segoe UI", 9, "bold"),
        fg="#34d399",
        bg="#121923"
    ).pack(anchor="w", pady=(12, 2))

    capture_path_frame = tk.Frame(tab_settings, bg="#121923")
    capture_path_frame.pack(fill="x", pady=5)

    capture_path_entry = tk.Entry(
        capture_path_frame,
        bg="#162032",
        fg="#ffffff",
        insertbackground="#ff4757",
        relief="flat",
        font=("Segoe UI", 9)
    )
    capture_path_entry.pack(side="left", fill="x", expand=True, ipady=4, padx=(0, 5))
    capture_path_entry.insert(
        0,
        CONFIG.get("capture", {}).get("output_path", "captures")
    )

    def browse_capture_dir():
        dir_selected = filedialog.askdirectory()
        if dir_selected:
            capture_path_entry.delete(0, tk.END)
            capture_path_entry.insert(0, dir_selected)

    tk.Button(
        capture_path_frame,
        text="📁 Browse",
        command=browse_capture_dir,
        bg="#1e293b",
        fg="#fff",
        relief="flat",
        padx=8,
        cursor="hand2"
    ).pack(side="right")

    tk.Label(
        tab_settings,
        text="Camera, microphone and screen recordings will be saved here.",
        font=("Segoe UI", 8),
        fg="#64748b",
        bg="#121923"
    ).pack(anchor="w", pady=(0, 2))

    tk.Label(
        tab_settings,
        text="🔊 Soundboard / Sound Effects Directory:",
        font=("Segoe UI", 9, "bold"),
        fg="#a78bfa",
        bg="#121923"
    ).pack(anchor="w", pady=(15, 2))

    sound_frame = tk.Frame(tab_settings, bg="#121923")
    sound_frame.pack(fill="x", pady=5)

    sound_path_entry = tk.Entry(
        sound_frame,
        bg="#162032",
        fg="#ffffff",
        insertbackground="#ff4757",
        relief="flat",
        font=("Segoe UI", 9)
    )
    sound_path_entry.pack(side="left", fill="x", expand=True, ipady=4, padx=(0, 5))
    sound_path_entry.insert(
        0,
        CONFIG.get("soundboard_path", r"C:\Users\Public\Music")
    )

    def browse_soundboard_dir():
        dir_selected = filedialog.askdirectory()
        if dir_selected:
            sound_path_entry.delete(0, tk.END)
            sound_path_entry.insert(0, dir_selected)

    tk.Button(
        sound_frame,
        text="📁 Browse",
        command=browse_soundboard_dir,
        bg="#1e293b",
        fg="#fff",
        relief="flat",
        padx=8,
        cursor="hand2"
    ).pack(side="right")

    tk.Label(
        tab_settings,
        text="Supported: MP3, WAV, FLAC, M4A, AAC, OGG, WMA, OPUS",
        font=("Segoe UI", 8),
        fg="#64748b",
        bg="#121923"
    ).pack(anchor="w", pady=(2, 0))

    # ================= 🕐 WEBUI CLOCK TIMEZONE =================
    tk.Label(
        tab_settings,
        text="🕐 WebUI Clock Timezone:",
        font=("Segoe UI", 9, "bold"),
        fg="#fbbf24",
        bg="#121923"
    ).pack(anchor="w", pady=(15, 2))

    tz_frame = tk.Frame(tab_settings, bg="#121923")
    tz_frame.pack(fill="x", pady=5)

    tz_values = ["Auto (Browser / PC Local)"] + sorted(available_timezones())
    tz_combo = ttk.Combobox(
        tz_frame,
        values=tz_values,
        state="readonly",
        font=("Segoe UI", 9)
    )
    tz_combo.pack(fill="x", ipady=3)

    current_tz = CONFIG.get("webui_timezone", "")
    tz_combo.set(current_tz if current_tz in tz_values else "Auto (Browser / PC Local)")

    tk.Label(
        tab_settings,
        text="Used by the WebUI clock/focus popup. Auto uses the viewing device's own timezone.",
        font=("Segoe UI", 8),
        fg="#64748b",
        bg="#121923"
    ).pack(anchor="w", pady=(2, 0))

    # ================= 🚀 AUTO-START / SYSTEM TRAY =================
    tk.Label(
        tab_settings,
        text="🚀 Startup & Tray:",
        font=("Segoe UI", 9, "bold"),
        fg="#fbbf24",
        bg="#121923"
    ).pack(anchor="w", pady=(15, 2))

    autostart_var = tk.BooleanVar(value=is_auto_start_enabled())
    tray_close_var = tk.BooleanVar(value=CONFIG.get("minimize_to_tray_on_close", True))

    def on_autostart_toggle():
        ok = set_auto_start(autostart_var.get())
        if not ok and os.name != "nt":
            messagebox.showwarning("Not Supported", "Auto-start is only supported on Windows.")
            autostart_var.set(False)
        elif not ok:
            messagebox.showerror("Error", "Could not update the Windows Startup entry.")
            autostart_var.set(not autostart_var.get())
        CONFIG["auto_start"] = autostart_var.get()
        save_config()

    def on_tray_close_toggle():
        CONFIG["minimize_to_tray_on_close"] = tray_close_var.get()
        save_config()
        if tray_close_var.get() and not PYSTRAY_AVAILABLE:
            messagebox.showwarning(
                "pystray not installed",
                "Install it with:  pip install pystray\n\nUntil then, closing the window will exit the app."
            )

    tk.Checkbutton(
        tab_settings,
        text="Start with Windows (auto-start on login)",
        variable=autostart_var,
        command=on_autostart_toggle,
        font=("Segoe UI", 9),
        fg="#e2e8f0",
        bg="#121923",
        selectcolor="#162032",
        activebackground="#121923",
        activeforeground="#fff"
    ).pack(anchor="w", pady=(4, 0))

    tk.Checkbutton(
        tab_settings,
        text="Minimize to system tray when window is closed (⚫ instead of quitting)",
        variable=tray_close_var,
        command=on_tray_close_toggle,
        font=("Segoe UI", 9),
        fg="#e2e8f0",
        bg="#121923",
        selectcolor="#162032",
        activebackground="#121923",
        activeforeground="#fff"
    ).pack(anchor="w", pady=(2, 0))

    if not PYSTRAY_AVAILABLE:
        tk.Label(
            tab_settings,
            text="⚠ 'pystray' not installed — tray icon disabled until you run: pip install pystray",
            font=("Segoe UI", 8),
            fg="#fca5a5",
            bg="#121923",
            wraplength=460,
            justify="left"
        ).pack(anchor="w", pady=(2, 0))

    def save_settings():
        new_screenshot_path = path_entry.get().strip()
        new_hid_path = hid_path_entry.get().strip()
        new_capture_path = capture_path_entry.get().strip()
        new_soundboard_path = sound_path_entry.get().strip()
        new_tz = tz_combo.get().strip()

        if not new_screenshot_path:
            messagebox.showwarning("Invalid Path", "Screenshot directory cannot be empty.")
            return

        if not new_hid_path:
            messagebox.showwarning("Invalid Path", "HID script directory cannot be empty.")
            return

        if not new_capture_path:
            messagebox.showwarning("Invalid Path", "Capture output directory cannot be empty.")
            return

        if not new_soundboard_path:
            messagebox.showwarning("Invalid Path", "Soundboard directory cannot be empty.")
            return

        CONFIG["screenshot_path"] = new_screenshot_path
        CONFIG.setdefault("hid", {})["script_path"] = new_hid_path
        CONFIG.setdefault("capture", {})["output_path"] = new_capture_path
        CONFIG["soundboard_path"] = new_soundboard_path
        CONFIG["webui_timezone"] = "" if new_tz.startswith("Auto") else new_tz
        save_config()
        _sync_hid_config()

        messagebox.showinfo(
            "Success",
            "Settings saved successfully.\n\n"
            "HID scripts and Capture recordings will use the new paths."
        )

    tk.Button(
        tab_settings,
        text="💾 Save Settings",
        command=save_settings,
        bg="#ff4757",
        fg="#fff",
        font=("Segoe UI", 9, "bold"),
        relief="flat",
        pady=4,
        cursor="hand2"
    ).pack(fill="x", pady=15)

    # Initial Refresh
    refresh_folder_list()
    refresh_app_list()
    refresh_sc_list()
    refresh_player_list()
    update_qr_and_ip()

    def on_root_close():
        if CONFIG.get("minimize_to_tray_on_close", True) and PYSTRAY_AVAILABLE:
            minimize_to_tray(root)
        else:
            root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_root_close)

    # Auto-launch the tray icon at startup too, so it's there even before
    # the user closes the window for the first time.
    if CONFIG.get("minimize_to_tray_on_close", True) and PYSTRAY_AVAILABLE:
        _tray_icon_ref["icon"] = setup_system_tray(root)

    root.mainloop()

if __name__ == '__main__':
    t = threading.Thread(target=run_flask, daemon=True)
    t.start()
    start_pc_dashboard()
