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
import pyautogui
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
from PIL import ImageTk, Image, ImageGrab
from flask import Flask, jsonify, request, send_from_directory, send_file
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
    "media_folders": [
        {"path": r"C:\Users\Public\Videos", "enabled": True}
    ],
    "custom_apps": [
        {"name": "Task Manager", "path": "C:\\Windows\\System32\\taskmgr.exe", "is_link": False, "enabled": True},
        {"name": "Notepad", "path": "notepad.exe", "is_link": False, "enabled": True},
        {"name": "Calculator", "path": "calc.exe", "is_link": False, "enabled": True},
        {"name": "Google", "path": "https://www.google.com", "is_link": True, "enabled": True}
    ],
    "custom_shortcuts": [
        {"name": "Win + Tab", "keys": ["win", "tab"], "category": "Windows", "icon": "🔀", "enabled": True},
        {"name": "Sound output devices", "keys": ["win", "ctrl", "v"], "category": "Windows", "icon": "🔊", "enabled": True},
        {"name": "Taskbar apps", "keys": ["win", "t"], "category": "Windows", "icon": "🖥️", "enabled": True},
        {"name": "Enter", "keys": ["enter"], "category": "Windows", "icon": "↩️", "enabled": True}
    ],
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

def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

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
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/soundboard_play', methods=['POST'])
def soundboard_play_http():
    data = request.get_json(silent=True) or {}
    path = str(data.get("path", "")).strip()
    ok, message = SOUND_PLAYER.play(path)
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
    return jsonify({"status": "success" if ok else "error"}), (200 if ok else 400)


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
            return jsonify({"status": "success"})
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)}), 500
    return jsonify({"status": "error"}), 400

@socketio.on('media_control')
def handle_media(data):
    action = data.get('action')
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
    root.geometry("540x720")
    root.configure(bg="#090d16")
    root.resizable(False, False)

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
        for item in CONFIG["custom_apps"]:
            status = "📌 [Pinned]" if item.get("enabled", True) else "⚪ [Unpinned]"
            icon = "🌐" if item.get('is_link') else "🚀"
            list_apps.insert(tk.END, f"{status} {icon} {item['name']}")

    def toggle_pin_app():
        sel = list_apps.curselection()
        if sel:
            idx = sel[0]
            current_state = CONFIG["custom_apps"][idx].get("enabled", True)
            CONFIG["custom_apps"][idx]["enabled"] = not current_state
            save_config()
            refresh_app_list()

    def add_custom_link():
        dialog = DarkMultiInputDialog(root, "Add Web Link", [("Enter Link Name:", "name"), ("Enter URL (e.g. google.com):", "url")])
        if dialog.results:
            name = dialog.results.get("name")
            url = dialog.results.get("url")
            if not url.startswith("http://") and not url.startswith("https://"):
                url = "https://" + url
            CONFIG["custom_apps"].append({"name": name, "path": url, "is_link": True, "enabled": True})
            save_config()
            refresh_app_list()

    def move_app(direction):
        new_idx = move_item(list_apps, CONFIG["custom_apps"], direction)
        if new_idx is not None:
            refresh_app_list()
            list_apps.selection_set(new_idx)

    a_btns = tk.Frame(tab_apps, bg="#121923")
    a_btns.pack(fill="x", padx=6, pady=6)
    
    tk.Button(a_btns, text="📌 Toggle Pin", command=toggle_pin_app, bg="#1e293b", fg="#34d399", relief="flat", padx=4, pady=3, cursor="hand2").pack(side="left", padx=2)
    tk.Button(a_btns, text="➕ .exe", command=lambda: [CONFIG["custom_apps"].append({"name": os.path.basename(f).replace('.exe', '').capitalize(), "path": f, "is_link": False, "enabled": True}) if (f:=filedialog.askopenfilename(filetypes=[("Executables", "*.exe")])) else None, save_config(), refresh_app_list()], bg="#1e293b", fg="#fff", relief="flat", padx=4, pady=3, cursor="hand2").pack(side="left", padx=2)
    tk.Button(a_btns, text="🌐 URL", command=add_custom_link, bg="#1e293b", fg="#38bdf8", relief="flat", padx=4, pady=3, cursor="hand2").pack(side="left", padx=2)
    tk.Button(a_btns, text="⬆️", command=lambda: move_app(-1), bg="#1e293b", fg="#fff", relief="flat", padx=4, pady=3, cursor="hand2").pack(side="left", padx=2)
    tk.Button(a_btns, text="⬇️", command=lambda: move_app(1), bg="#1e293b", fg="#fff", relief="flat", padx=4, pady=3, cursor="hand2").pack(side="left", padx=2)
    tk.Button(a_btns, text="🗑️ Delete", command=lambda: [CONFIG["custom_apps"].pop(sel[0]) if (sel:=list_apps.curselection()) else None, save_config(), refresh_app_list()], bg="#7f1d1d", fg="#fff", relief="flat", padx=4, pady=3, cursor="hand2").pack(side="right", padx=2)

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

    # ================= ⚙️ SETTINGS TAB =================
    tab_settings = tk.Frame(notebook, bg="#121923", padx=10, pady=10)
    notebook.add(tab_settings, text="⚙️ Settings")

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

    def save_settings():
        new_screenshot_path = path_entry.get().strip()
        new_soundboard_path = sound_path_entry.get().strip()

        if not new_screenshot_path:
            messagebox.showwarning("Invalid Path", "Screenshot directory cannot be empty.")
            return

        if not new_soundboard_path:
            messagebox.showwarning("Invalid Path", "Soundboard directory cannot be empty.")
            return

        CONFIG["screenshot_path"] = new_screenshot_path
        CONFIG["soundboard_path"] = new_soundboard_path
        save_config()

        messagebox.showinfo(
            "Success",
            "Settings saved successfully.\n\n"
            "The Web UI Sound Effects page will use the new soundboard path."
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

    root.mainloop()

if __name__ == '__main__':
    t = threading.Thread(target=run_flask, daemon=True)
    t.start()
    start_pc_dashboard()