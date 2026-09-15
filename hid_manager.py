"""
ASSHOLE DECK
HID Script Manager + Device Capture Hub

Features
--------
HID:
    - Enable / Disable HID manager
    - Save HID scripts
    - Edit HID scripts
    - Delete HID scripts
    - Run HID scripts
    - JSON macro format
    - Safe Rubber-Ducky-style text parser

Device Capture:
    - Windows camera detection
    - Microphone detection
    - Multiple display detection
    - Camera recording
    - Microphone recording
    - Screen recording
    - Simultaneous capture
    - Capture configuration
    - Runtime capture status

Required optional packages
--------------------------
pyautogui
opencv-python
mss
numpy
sounddevice
"""

import json
import os
import re
import threading
import time
from pathlib import Path


# ============================================================
# OPTIONAL DEPENDENCIES
# ============================================================

try:
    import pyautogui
except ImportError:
    pyautogui = None

try:
    import cv2
except ImportError:
    cv2 = None

try:
    import mss
except ImportError:
    mss = None

try:
    import numpy as np
except ImportError:
    np = None

try:
    import sounddevice as sd
except ImportError:
    sd = None


# ============================================================
# GLOBAL STATE
# ============================================================

_LOCK = threading.RLock()

_CONFIG = {}

_BUNDLE_DIR = os.path.abspath(".")

_ENABLED = False

_CAPTURE_STOP = threading.Event()

_CAPTURE_THREADS = []

_CAPTURE_STATE = {
    "camera": False,
    "microphone": False,
    "screen": False,
    "started_at": None,
    "files": [],
    "error": None,
}


# ============================================================
# CONSTANTS
# ============================================================

_NAME_RE = re.compile(
    r"^[A-Za-z0-9 _.-]{1,80}$"
)


# ============================================================
# CONFIGURATION
# ============================================================

def _defaults():
    return {
        "enabled": False,

        "scripts_path": os.path.join(
            _BUNDLE_DIR,
            "hid_scripts"
        ),

        "capture": {
            "camera_enabled": False,
            "microphone_enabled": False,
            "screen_enabled": False,

            "camera_device": 0,

            "microphone_device": "default",

            "screen_device": 0,

            "screen_display": 0,

            "output_path": os.path.join(
                os.path.expanduser("~"),
                "ASSHOLE_DECK_Captures"
            ),
        },
    }


def configure(config=None, bundle_dir=None, **kwargs):
    """
    Configure HID manager.

    Compatible with:
        configure(config)
        configure(config, bundle_dir)
        configure(enabled=True)
        configure(script_path="...")
        configure(capture_config={...})
    """

    global _CONFIG
    global _BUNDLE_DIR
    global _ENABLED

    with _LOCK:

        incoming = dict(config or {})

        # ----------------------------------------------------
        # Keyword compatibility
        # ----------------------------------------------------

        if "enabled" in kwargs:
            incoming["enabled"] = bool(
                kwargs["enabled"]
            )

        if "script_path" in kwargs:
            incoming["scripts_path"] = (
                kwargs["script_path"]
            )

        if "scripts_path" in kwargs:
            incoming["scripts_path"] = (
                kwargs["scripts_path"]
            )

        cap = kwargs.get(
            "capture_config",
            kwargs.get("capture")
        )

        if isinstance(cap, dict):
            incoming.setdefault(
                "capture",
                {}
            ).update(cap)

        # ----------------------------------------------------
        # Nested HID compatibility
        # ----------------------------------------------------

        hid = incoming.get("hid")

        if isinstance(hid, dict):

            if hid.get("script_path"):
                incoming["scripts_path"] = (
                    hid["script_path"]
                )

            elif hid.get("scripts_path"):
                incoming["scripts_path"] = (
                    hid["scripts_path"]
                )

            if "enabled" in hid:
                incoming["enabled"] = bool(
                    hid["enabled"]
                )

        _CONFIG = incoming

        _BUNDLE_DIR = os.path.abspath(
            bundle_dir or _BUNDLE_DIR
        )

        _normalize_config()

        _ENABLED = bool(
            _CONFIG.get(
                "enabled",
                _ENABLED
            )
        )

        _ensure_dirs()


def _cfg():
    """
    Return normalized configuration.
    """

    d = _defaults()

    incoming = _CONFIG or {}

    # --------------------------------------------------------
    # Scripts path
    # --------------------------------------------------------

    nested_hid = (
        incoming.get("hid")
        if isinstance(
            incoming.get("hid"),
            dict
        )
        else {}
    )

    if incoming.get("scripts_path"):
        d["scripts_path"] = (
            incoming["scripts_path"]
        )

    elif nested_hid.get("script_path"):
        d["scripts_path"] = (
            nested_hid["script_path"]
        )

    elif nested_hid.get("scripts_path"):
        d["scripts_path"] = (
            nested_hid["scripts_path"]
        )

    # --------------------------------------------------------
    # Top-level settings
    # --------------------------------------------------------

    for key, value in incoming.items():

        if key not in (
            "capture",
            "hid",
            "scripts_path",
        ):
            d[key] = value

    # --------------------------------------------------------
    # Capture
    # --------------------------------------------------------

    cap = dict(
        d["capture"]
    )

    incoming_cap = (
        incoming.get("capture")
        or {}
    )

    if isinstance(
        incoming_cap,
        dict
    ):
        cap.update(
            incoming_cap
        )

    # Frontend compatibility.
    if (
        "screen_device" not in incoming_cap
        and
        "screen_display" in incoming_cap
    ):
        cap["screen_device"] = (
            incoming_cap["screen_display"]
        )

    if "screen_display" not in cap:
        cap["screen_display"] = (
            cap.get(
                "screen_device",
                0
            )
        )

    d["capture"] = cap

    return d


def _normalize_config():
    cfg = _cfg()

    _CONFIG["scripts_path"] = (
        cfg["scripts_path"]
    )

    _CONFIG.setdefault(
        "capture",
        {}
    ).update(
        cfg["capture"]
    )


def _ensure_dirs():
    cfg = _cfg()

    Path(
        cfg["scripts_path"]
    ).expanduser().mkdir(
        parents=True,
        exist_ok=True
    )

    Path(
        cfg["capture"]["output_path"]
    ).expanduser().mkdir(
        parents=True,
        exist_ok=True
    )


# ============================================================
# HID ENABLE / DISABLE
# ============================================================

def enable():
    global _ENABLED

    with _LOCK:

        _ENABLED = True

        _ensure_dirs()

    return True


def disable():
    global _ENABLED

    with _LOCK:
        _ENABLED = False

    stop_capture()

    return True


def is_enabled():

    with _LOCK:
        return bool(_ENABLED)


# ============================================================
# STATUS
# ============================================================

def status():

    with _LOCK:

        state = dict(
            _CAPTURE_STATE
        )

        state["files"] = list(
            _CAPTURE_STATE.get(
                "files",
                []
            )
        )

        active = any(
            state.get(key, False)
            for key in (
                "camera",
                "microphone",
                "screen",
            )
        )

        return {
            "enabled": bool(
                _ENABLED
            ),

            "capture_active": active,

            "capture": state,

            "capture_config":
                capture_config(),

            "dependencies": {
                "pyautogui":
                    pyautogui is not None,

                "opencv":
                    cv2 is not None,

                "mss":
                    mss is not None,

                "numpy":
                    np is not None,

                "sounddevice":
                    sd is not None,
            },
        }


# ============================================================
# HID SCRIPT PATHS
# ============================================================

def _script_dir():

    path = Path(
        _cfg()["scripts_path"]
    ).expanduser().resolve()

    path.mkdir(
        parents=True,
        exist_ok=True
    )

    return path


def _safe_script_path(name):

    if not isinstance(
        name,
        str
    ):
        raise ValueError(
            "Invalid script name."
        )

    name = name.strip()

    if not name:
        raise ValueError(
            "Script name is required."
        )

    if not _NAME_RE.fullmatch(
        name
    ):
        raise ValueError(
            "Script name may contain "
            "letters, numbers, spaces, "
            "_, -, and . only."
        )

    if not name.lower().endswith(
        ".json"
    ):
        name += ".json"

    root = _script_dir()

    path = (
        root / name
    ).resolve()

    if os.path.commonpath(
        [
            str(path),
            str(root)
        ]
    ) != str(root):

        raise ValueError(
            "Invalid script path."
        )

    return path


# ============================================================
# HID SCRIPT LIST
# ============================================================

def list_scripts():

    root = _script_dir()

    result = []

    for p in sorted(
        root.glob("*.json"),
        key=lambda x:
        x.name.lower()
    ):

        try:

            data = json.loads(
                p.read_text(
                    encoding="utf-8"
                )
            )

            actions = data.get(
                "actions",
                []
            )

            valid = isinstance(
                actions,
                list
            )

            result.append({
                "name":
                    data.get(
                        "name"
                    ) or p.stem,

                "file":
                    p.name,

                "actions":
                    len(actions)
                    if valid
                    else 0,

                "valid":
                    valid,

                "content":
                    data.get(
                        "source"
                    )
                    or
                    actions_to_ducky(
                        actions
                        if valid
                        else []
                    ),
            })

        except Exception as exc:

            result.append({
                "name":
                    p.stem,

                "file":
                    p.name,

                "actions":
                    0,

                "invalid":
                    True,

                "error":
                    str(exc),
            })

    return result


def get_script(name):

    path = _safe_script_path(
        name
    )

    if not path.is_file():
        raise FileNotFoundError(
            "Script not found."
        )

    data = json.loads(
        path.read_text(
            encoding="utf-8"
        )
    )

    actions = _validate_actions(
        data.get(
            "actions",
            []
        )
    )

    return {
        "name":
            data.get(
                "name",
                path.stem
            ),

        "actions":
            actions,

        "file":
            path.name,

        "content":
            data.get(
                "source"
            )
            or
            actions_to_ducky(
                actions
            ),
    }


# ============================================================
# HID ACTION VALIDATION
# ============================================================

def _validate_actions(actions):

    if not isinstance(
        actions,
        list
    ):
        raise ValueError(
            "actions must be a list."
        )

    if len(actions) > 500:
        raise ValueError(
            "A script may contain "
            "at most 500 actions."
        )

    allowed = {
        "press",
        "write",
        "hotkey",
        "wait",
    }

    clean = []

    for action in actions:

        if (
            not isinstance(
                action,
                dict
            )
            or
            action.get("type")
            not in allowed
        ):
            raise ValueError(
                "Unsupported HID action."
            )

        typ = action["type"]

        # ----------------------------------------------------
        # PRESS
        # ----------------------------------------------------

        if typ == "press":

            key = str(
                action.get(
                    "key",
                    ""
                )
            ).strip().lower()

            if (
                not key
                or len(key) > 40
            ):
                raise ValueError(
                    "Invalid key."
                )

            clean.append({
                "type": "press",
                "key": key,
            })

        # ----------------------------------------------------
        # WRITE
        # ----------------------------------------------------

        elif typ == "write":

            text = str(
                action.get(
                    "text",
                    ""
                )
            )

            if len(text) > 4000:
                raise ValueError(
                    "write text is too long."
                )

            clean.append({
                "type": "write",
                "text": text,
            })

        # ----------------------------------------------------
        # HOTKEY
        # ----------------------------------------------------

        elif typ == "hotkey":

            keys = action.get(
                "keys",
                []
            )

            if (
                not isinstance(
                    keys,
                    list
                )
                or
                not 1 <= len(keys) <= 8
            ):
                raise ValueError(
                    "Invalid hotkey."
                )

            clean_keys = [
                str(k)
                .strip()
                .lower()
                for k in keys
            ]

            if any(
                not k or len(k) > 40
                for k in clean_keys
            ):
                raise ValueError(
                    "Invalid hotkey key."
                )

            clean.append({
                "type": "hotkey",
                "keys": clean_keys,
            })

        # ----------------------------------------------------
        # WAIT
        # ----------------------------------------------------

        elif typ == "wait":

            try:
                seconds = float(
                    action.get(
                        "seconds",
                        0
                    )
                )
            except Exception:
                raise ValueError(
                    "Invalid wait value."
                )

            if (
                seconds < 0
                or
                seconds > 60
            ):
                raise ValueError(
                    "wait must be between "
                    "0 and 60 seconds."
                )

            clean.append({
                "type": "wait",
                "seconds": seconds,
            })

    return clean


# ============================================================
# RUBBER DUCKY PARSER
# ============================================================

_RUBBER_KEY_MAP = {

    "ENTER": "enter",
    "RETURN": "enter",

    "TAB": "tab",

    "ESC": "esc",
    "ESCAPE": "esc",

    "BACKSPACE": "backspace",

    "DELETE": "delete",
    "DEL": "delete",

    "SPACE": "space",

    "UP": "up",
    "DOWN": "down",
    "LEFT": "left",
    "RIGHT": "right",

    "HOME": "home",
    "END": "end",

    "INSERT": "insert",

    "PAGEUP": "pageup",
    "PAGEDOWN": "pagedown",

    "CAPSLOCK": "capslock",
    "NUMLOCK": "numlock",
    "SCROLLLOCK": "scrolllock",

    "PRINTSCREEN": "printscreen",

    "WIN": "win",
    "WINDOWS": "win",
    "GUI": "win",

    "ALT": "alt",

    "CTRL": "ctrl",
    "CONTROL": "ctrl",

    "SHIFT": "shift",

    "F1": "f1",
    "F2": "f2",
    "F3": "f3",
    "F4": "f4",
    "F5": "f5",
    "F6": "f6",
    "F7": "f7",
    "F8": "f8",
    "F9": "f9",
    "F10": "f10",
    "F11": "f11",
    "F12": "f12",
}


def parse_rubber_ducky(text):

    if not isinstance(
        text,
        str
    ):
        raise ValueError(
            "Script content must be text."
        )

    if len(text) > 12000:
        raise ValueError(
            "Script content is too long."
        )

    actions = []

    for line_no, raw in enumerate(
        text.splitlines(),
        1
    ):

        line = raw.strip()

        if not line:
            continue

        if (
            line.startswith("REM ")
            or
            line.startswith("#")
        ):
            continue

        parts = line.split(
            None,
            1
        )

        command = parts[0].upper()

        arg = (
            parts[1]
            if len(parts) > 1
            else ""
        )

        # ----------------------------------------------------
        # DELAY
        # ----------------------------------------------------

        if command == "DELAY":

            try:
                ms = float(arg)
            except Exception:

                raise ValueError(
                    f"Line {line_no}: "
                    "DELAY requires "
                    "milliseconds."
                )

            if (
                ms < 0
                or
                ms > 60000
            ):
                raise ValueError(
                    f"Line {line_no}: "
                    "DELAY must be "
                    "0-60000 ms."
                )

            actions.append({
                "type": "wait",
                "seconds": ms / 1000.0,
            })

        # ----------------------------------------------------
        # STRING
        # ----------------------------------------------------

        elif command == "STRING":

            actions.append({
                "type": "write",
                "text": arg,
            })

        # ----------------------------------------------------
        # STRINGLN
        # ----------------------------------------------------

        elif command == "STRINGLN":

            actions.append({
                "type": "write",
                "text": arg,
            })

            actions.append({
                "type": "press",
                "key": "enter",
            })

        # ----------------------------------------------------
        # CTRL / ALT / SHIFT / GUI
        # ----------------------------------------------------

        elif command in (
            "CTRL",
            "CONTROL",
            "ALT",
            "SHIFT",
            "GUI",
            "WINDOWS",
            "WIN",
        ):

            key = _RUBBER_KEY_MAP[
                command
            ]

            if not arg:

                actions.append({
                    "type": "press",
                    "key": key,
                })

            else:

                combo = [key]

                for token in re.split(
                    r"[ +]+",
                    arg.strip()
                ):

                    if not token:
                        continue

                    combo.append(
                        _RUBBER_KEY_MAP.get(
                            token.upper(),
                            token.lower()
                        )
                    )

                if len(combo) < 2:

                    raise ValueError(
                        f"Line {line_no}: "
                        "invalid hotkey."
                    )

                actions.append({
                    "type": "hotkey",
                    "keys": combo,
                })

        # ----------------------------------------------------
        # HOTKEY
        # ----------------------------------------------------

        elif command == "HOTKEY":

            tokens = re.split(
                r"[ +]+",
                arg.strip()
            )

            if (
                not tokens
                or
                not all(tokens)
            ):

                raise ValueError(
                    f"Line {line_no}: "
                    "HOTKEY requires keys."
                )

            keys = [
                _RUBBER_KEY_MAP.get(
                    token.upper(),
                    token.lower()
                )
                for token in tokens
            ]

            actions.append({
                "type": "hotkey",
                "keys": keys,
            })

        # ----------------------------------------------------
        # NORMAL KEY
        # ----------------------------------------------------

        elif command in _RUBBER_KEY_MAP:

            actions.append({
                "type": "press",
                "key":
                    _RUBBER_KEY_MAP[
                        command
                    ],
            })

        # ----------------------------------------------------
        # WAIT
        # ----------------------------------------------------

        elif command == "WAIT":

            try:
                seconds = float(arg)
            except Exception:

                raise ValueError(
                    f"Line {line_no}: "
                    "WAIT requires seconds."
                )

            if (
                seconds < 0
                or
                seconds > 60
            ):

                raise ValueError(
                    f"Line {line_no}: "
                    "WAIT must be "
                    "0-60 seconds."
                )

            actions.append({
                "type": "wait",
                "seconds": seconds,
            })

        else:

            raise ValueError(
                f"Line {line_no}: "
                f"unsupported command "
                f"'{command}'."
            )

    return _validate_actions(
        actions
    )


# ============================================================
# ACTIONS -> DUCKY
# ============================================================

def actions_to_ducky(actions):

    names = {

        "enter": "ENTER",
        "tab": "TAB",
        "esc": "ESC",

        "backspace":
            "BACKSPACE",

        "delete":
            "DELETE",

        "space":
            "SPACE",

        "up": "UP",
        "down": "DOWN",
        "left": "LEFT",
        "right": "RIGHT",

        "home": "HOME",
        "end": "END",

        "insert":
            "INSERT",

        "pageup":
            "PAGEUP",

        "pagedown":
            "PAGEDOWN",

        "capslock":
            "CAPSLOCK",

        "numlock":
            "NUMLOCK",

        "scrolllock":
            "SCROLLLOCK",

        "printscreen":
            "PRINTSCREEN",

        "pause":
            "PAUSE",
    }

    lines = []

    for action in actions or []:

        typ = action.get(
            "type"
        )

        if typ == "wait":

            lines.append(
                "DELAY "
                + str(
                    int(
                        round(
                            float(
                                action.get(
                                    "seconds",
                                    0
                                )
                            )
                            * 1000
                        )
                    )
                )
            )

        elif typ == "write":

            lines.append(
                "STRING "
                + str(
                    action.get(
                        "text",
                        ""
                    )
                )
            )

        elif typ == "press":

            key = str(
                action.get(
                    "key",
                    ""
                )
            ).lower()

            lines.append(
                names.get(
                    key,
                    key.upper()
                )
            )

        elif typ == "hotkey":

            keys = [
                str(k).lower()
                for k in action.get(
                    "keys",
                    []
                )
            ]

            if (
                len(keys) == 2
                and
                keys[0] in (
                    "ctrl",
                    "alt",
                    "shift",
                    "win",
                )
            ):

                lines.append(
                    keys[0].upper()
                    + " "
                    +
                    names.get(
                        keys[1],
                        keys[1].upper()
                    )
                )

            else:

                lines.append(
                    "HOTKEY "
                    +
                    " ".join(keys)
                )

    return "\n".join(
        lines
    )


# ============================================================
# SAVE SCRIPT
# ============================================================

def save_script(
    name,
    content=None,
    actions=None
):

    path = _safe_script_path(
        name
    )

    if content is not None:

        if not isinstance(
            content,
            str
        ):
            raise ValueError(
                "content must be text."
            )

        text = content.strip()

        if not text:

            raise ValueError(
                "Script content cannot "
                "be empty."
            )

        # ----------------------------------------------------
        # JSON first
        # ----------------------------------------------------

        try:

            parsed = json.loads(
                text
            )

            if not isinstance(
                parsed,
                dict
            ):
                raise ValueError

            data = parsed

            source = (
                data.get("source")
                or
                actions_to_ducky(
                    data.get(
                        "actions",
                        []
                    )
                )
            )

        # ----------------------------------------------------
        # Ducky text
        # ----------------------------------------------------

        except (
            json.JSONDecodeError,
            ValueError,
        ):

            data = {
                "name":
                    path.stem,

                "actions":
                    parse_rubber_ducky(
                        content
                    ),
            }

            source = content

    else:

        data = {
            "name":
                Path(name).stem,

            "actions":
                actions or [],
        }

        source = actions_to_ducky(
            data["actions"]
        )

    script_name = str(
        data.get(
            "name"
        )
        or
        path.stem
    ).strip()

    if not script_name:

        raise ValueError(
            "Script name is required."
        )

    if len(script_name) > 80:

        raise ValueError(
            "Script name is too long."
        )

    clean_actions = _validate_actions(
        data.get(
            "actions",
            []
        )
    )

    payload = {
        "name":
            script_name,

        "actions":
            clean_actions,

        "source":
            source
            or
            actions_to_ducky(
                clean_actions
            ),
    }

    path.write_text(
        json.dumps(
            payload,
            indent=4,
            ensure_ascii=False
        ),
        encoding="utf-8"
    )

    return {
        "name":
            script_name,

        "file":
            path.name,

        "actions":
            len(clean_actions),

        "content":
            payload["source"],
    }


# ============================================================
# DELETE SCRIPT
# ============================================================

def delete_script(name):

    path = _safe_script_path(
        name
    )

    if not path.is_file():

        raise FileNotFoundError(
            "Script not found."
        )

    path.unlink()

    return True


# ============================================================
# RUN ACTIONS
# ============================================================

def _run_actions(actions):

    if pyautogui is None:

        raise RuntimeError(
            "pyautogui is not installed."
        )

    for action in actions:

        if not is_enabled():

            raise RuntimeError(
                "HID Manager is disabled."
            )

        typ = action["type"]

        if typ == "press":

            pyautogui.press(
                action["key"]
            )

        elif typ == "write":

            pyautogui.write(
                action["text"],
                interval=0.01
            )

        elif typ == "hotkey":

            pyautogui.hotkey(
                *action["keys"]
            )

        elif typ == "wait":

            time.sleep(
                action["seconds"]
            )


def run_script(name):

    if not is_enabled():

        raise RuntimeError(
            "HID Manager is disabled. "
            "Enable it first."
        )

    script = get_script(
        name
    )

    _run_actions(
        script["actions"]
    )

    return {
        "name":
            script["name"],

        "actions":
            len(
                script["actions"]
            ),

        "status":
            "completed",
    }


# ============================================================
# CAPTURE CONFIG
# ============================================================

def capture_config():

    cfg = dict(
        _cfg()["capture"]
    )

    # --------------------------------------------------------
    # Camera
    # --------------------------------------------------------

    try:
        cfg["camera_device"] = int(
            cfg.get(
                "camera_device",
                0
            )
        )
    except Exception:
        cfg["camera_device"] = 0

    # --------------------------------------------------------
    # Screen
    # --------------------------------------------------------

    try:

        cfg["screen_device"] = max(
            0,
            int(
                cfg.get(
                    "screen_device",
                    cfg.get(
                        "screen_display",
                        0
                    )
                )
            )
        )

    except Exception:

        cfg["screen_device"] = 0

    cfg["screen_display"] = (
        cfg["screen_device"]
    )

    return cfg


def set_capture_config(data):

    if not isinstance(
        data,
        dict
    ):
        raise ValueError(
            "Capture configuration "
            "must be an object."
        )

    current = dict(
        _cfg()["capture"]
    )

    allowed = {
        "camera_enabled",
        "microphone_enabled",
        "screen_enabled",

        "camera_device",
        "microphone_device",

        "screen_device",
        "screen_display",

        "output_path",
    }

    for key in allowed:

        if key in data:
            current[key] = data[key]

    # --------------------------------------------------------
    # Screen compatibility
    # --------------------------------------------------------

    if (
        "screen_device" not in data
        and
        "screen_display" in data
    ):

        current["screen_device"] = (
            data["screen_display"]
        )

    current["screen_display"] = (
        current.get(
            "screen_device",
            current.get(
                "screen_display",
                0
            )
        )
    )

    # --------------------------------------------------------
    # Boolean values
    # --------------------------------------------------------

    current["camera_enabled"] = bool(
        current.get(
            "camera_enabled",
            False
        )
    )

    current["microphone_enabled"] = bool(
        current.get(
            "microphone_enabled",
            False
        )
    )

    current["screen_enabled"] = bool(
        current.get(
            "screen_enabled",
            False
        )
    )

    # --------------------------------------------------------
    # Camera
    # --------------------------------------------------------

    try:

        current["camera_device"] = int(
            current.get(
                "camera_device",
                0
            )
        )

    except Exception:

        current["camera_device"] = 0

    # --------------------------------------------------------
    # Screen
    # --------------------------------------------------------

    try:

        current["screen_device"] = max(
            0,
            int(
                current.get(
                    "screen_device",
                    0
                )
            )
        )

    except Exception:

        current["screen_device"] = 0

    current["screen_display"] = (
        current["screen_device"]
    )

    # --------------------------------------------------------
    # Microphone
    # --------------------------------------------------------

    mic = current.get(
        "microphone_device",
        "default"
    )

    if (
        mic is None
        or
        str(mic).strip() == ""
    ):

        mic = "default"

    elif (
        isinstance(
            mic,
            str
        )
        and
        mic.strip().isdigit()
    ):

        mic = int(
            mic.strip()
        )

    elif (
        isinstance(
            mic,
            float
        )
        and
        mic.is_integer()
    ):

        mic = int(mic)

    current["microphone_device"] = mic

    # --------------------------------------------------------
    # Output path
    # --------------------------------------------------------

    output = str(
        current.get(
            "output_path",
            ""
        )
    ).strip()

    if not output:

        raise ValueError(
            "Capture output path "
            "cannot be empty."
        )

    current["output_path"] = (
        os.path.abspath(
            os.path.expanduser(
                output
            )
        )
    )

    Path(
        current["output_path"]
    ).mkdir(
        parents=True,
        exist_ok=True
    )

    _CONFIG.setdefault(
        "capture",
        {}
    ).update(
        current
    )

    return current


# ============================================================
# CAMERA ENUMERATION
# ============================================================

def _camera_name(index):

    return f"Camera {index}"


def _camera_test(index, backend):

    """
    Test whether a camera index actually opens.
    """

    cap = None

    try:

        cap = cv2.VideoCapture(
            index,
            backend
        )

        if cap is None:
            return False

        # Small buffer.
        try:
            cap.set(
                cv2.CAP_PROP_BUFFERSIZE,
                1
            )
        except Exception:
            pass

        if not cap.isOpened():
            return False

        return True

    except Exception:

        return False

    finally:

        try:
            if cap is not None:
                cap.release()
        except Exception:
            pass


# ============================================================
# DEVICE ENUMERATION
# ============================================================

def list_capture_devices():

    """
    Detect actual PC-side:

        Camera
        Microphone
        Display

    Returns backend IDs that can directly be used
    by the capture workers.
    """

    cameras = []
    microphones = []
    screens = []

    errors = {
        "camera": None,
        "microphone": None,
        "screen": None,
    }

    # ========================================================
    # CAMERA
    # ========================================================

    if cv2 is None:

        errors["camera"] = (
            "opencv-python is not installed."
        )

    else:

        try:

            seen = set()

            backends = []

            if os.name == "nt":

                if hasattr(
                    cv2,
                    "CAP_DSHOW"
                ):

                    backends.append(
                        (
                            "DirectShow",
                            cv2.CAP_DSHOW
                        )
                    )

                if hasattr(
                    cv2,
                    "CAP_MSMF"
                ):

                    backends.append(
                        (
                            "Media Foundation",
                            cv2.CAP_MSMF
                        )
                    )

            backends.append(
                (
                    "Auto",
                    cv2.CAP_ANY
                )
            )

            # Test camera indexes.
            for index in range(10):

                found = False
                working_backend = "Auto"

                for backend_name, backend_id in backends:

                    if _camera_test(
                        index,
                        backend_id
                    ):

                        found = True
                        working_backend = (
                            backend_name
                        )
                        break

                if (
                    found
                    and
                    index not in seen
                ):

                    seen.add(index)

                    cameras.append({
                        "id":
                            index,

                        "index":
                            index,

                        "device":
                            index,

                        "name":
                            _camera_name(
                                index
                            ),

                        "backend":
                            working_backend,
                    })

        except Exception as exc:

            errors["camera"] = str(
                exc
            )

    # ========================================================
    # MICROPHONE
    # ========================================================

    if sd is None:

        errors["microphone"] = (
            "sounddevice is not installed."
        )

    else:

        try:

            devices = sd.query_devices()

            default_input = None

            # ------------------------------------------------
            # Default microphone
            # ------------------------------------------------

            try:

                default_info = (
                    sd.default.device
                )

                if isinstance(
                    default_info,
                    (
                        list,
                        tuple
                    )
                ):

                    default_input = (
                        default_info[0]
                    )

                else:

                    default_input = (
                        default_info
                    )

            except Exception:

                default_input = None

            # ------------------------------------------------
            # Enumerate input devices
            # ------------------------------------------------

            for index, dev in enumerate(
                devices
            ):

                try:

                    input_channels = int(
                        dev.get(
                            "max_input_channels",
                            0
                        )
                    )

                except Exception:

                    input_channels = 0

                # Ignore playback-only devices.
                if input_channels <= 0:
                    continue

                name = str(
                    dev.get(
                        "name"
                    )
                    or
                    f"Microphone {index}"
                ).strip()

                try:

                    samplerate = int(
                        float(
                            dev.get(
                                "default_samplerate",
                                44100
                            )
                        )
                    )

                except Exception:

                    samplerate = 44100

                is_default = (
                    default_input is not None
                    and
                    str(index)
                    ==
                    str(default_input)
                )

                microphones.append({
                    "id":
                        index,

                    "index":
                        index,

                    "device":
                        index,

                    "name":
                        name,

                    "channels":
                        input_channels,

                    "samplerate":
                        samplerate,

                    "default":
                        is_default,
                })

        except Exception as exc:

            errors["microphone"] = str(
                exc
            )

    # ========================================================
    # SCREENS / DISPLAYS
    # ========================================================

    if mss is None:

        errors["screen"] = (
            "mss is not installed."
        )

    else:

        try:

            with mss.mss() as sct:

                # MSS monitor 0 = virtual desktop.
                # Real displays start from monitor 1.
                monitors = list(
                    sct.monitors[1:]
                )

                if not monitors:

                    errors["screen"] = (
                        "No Windows display detected."
                    )

                for index, monitor in enumerate(
                    monitors
                ):

                    width = int(
                        monitor.get(
                            "width",
                            0
                        )
                    )

                    height = int(
                        monitor.get(
                            "height",
                            0
                        )
                    )

                    left = int(
                        monitor.get(
                            "left",
                            0
                        )
                    )

                    top = int(
                        monitor.get(
                            "top",
                            0
                        )
                    )

                    screens.append({
                        "id":
                            index,

                        "index":
                            index,

                        "device":
                            index,

                        "monitor":
                            index + 1,

                        "name":
                            f"Display {index + 1}",

                        "width":
                            width,

                        "height":
                            height,

                        "left":
                            left,

                        "top":
                            top,
                    })

        except Exception as exc:

            errors["screen"] = str(
                exc
            )

    # ========================================================
    # RETURN
    # ========================================================

    return {

        "cameras":
            cameras,

        "microphones":
            microphones,

        "screens":
            screens,

        # Compatibility aliases.
        "camera":
            cameras,

        "microphone":
            microphones,

        "screen":
            screens,

        # Diagnostic errors.
        "errors":
            errors,

        # Device counts.
        "counts": {
            "camera":
                len(cameras),

            "microphone":
                len(microphones),

            "screen":
                len(screens),
        },

        "available":
            bool(
                cameras
                or
                microphones
                or
                screens
            ),
    }


# ============================================================
# BACKWARD COMPATIBILITY
# ============================================================

def devices():

    return list_capture_devices()


# ============================================================
# CAPTURE HELPERS
# ============================================================

def _timestamp():

    return time.strftime(
        "%Y%m%d_%H%M%S"
    )


def _add_file(path):

    with _LOCK:

        absolute = os.path.abspath(
            path
        )

        if absolute not in (
            _CAPTURE_STATE["files"]
        ):

            _CAPTURE_STATE[
                "files"
            ].append(
                absolute
            )


def _set_capture_error(message):

    with _LOCK:

        _CAPTURE_STATE[
            "error"
        ] = str(message)


# ============================================================
# CAMERA WORKER
# ============================================================

def _camera_worker(
    device,
    output_dir
):

    cap = None
    writer = None

    try:

        if cv2 is None:

            raise RuntimeError(
                "Camera recording requires "
                "opencv-python."
            )

        # ----------------------------------------------------
        # Choose Windows backend
        # ----------------------------------------------------

        backend = (
            cv2.CAP_DSHOW
            if (
                os.name == "nt"
                and
                hasattr(
                    cv2,
                    "CAP_DSHOW"
                )
            )
            else cv2.CAP_ANY
        )

        cap = cv2.VideoCapture(
            int(device),
            backend
        )

        if (
            cap is None
            or
            not cap.isOpened()
        ):

            raise RuntimeError(
                f"Camera {device} "
                "could not be opened."
            )

        # ----------------------------------------------------
        # Resolution
        # ----------------------------------------------------

        width = int(
            cap.get(
                cv2.CAP_PROP_FRAME_WIDTH
            )
            or
            640
        )

        height = int(
            cap.get(
                cv2.CAP_PROP_FRAME_HEIGHT
            )
            or
            480
        )

        if width <= 0:
            width = 640

        if height <= 0:
            height = 480

        # ----------------------------------------------------
        # FPS
        # ----------------------------------------------------

        fps = float(
            cap.get(
                cv2.CAP_PROP_FPS
            )
            or
            20.0
        )

        if (
            fps <= 1
            or
            fps > 120
        ):

            fps = 20.0

        # ----------------------------------------------------
        # Output
        # ----------------------------------------------------

        path = os.path.join(
            output_dir,
            f"camera_{_timestamp()}.mp4"
        )

        writer = cv2.VideoWriter(
            path,
            cv2.VideoWriter_fourcc(
                *"mp4v"
            ),
            fps,
            (
                width,
                height
            )
        )

        if (
            writer is None
            or
            not writer.isOpened()
        ):

            raise RuntimeError(
                "Could not create "
                "camera recording file."
            )

        _add_file(path)

        with _LOCK:
            _CAPTURE_STATE[
                "camera"
            ] = True

        # ----------------------------------------------------
        # Recording loop
        # ----------------------------------------------------

        while not _CAPTURE_STOP.is_set():

            ok, frame = cap.read()

            if not ok:

                _set_capture_error(
                    f"Camera {device} "
                    "stopped returning frames."
                )

                break

            writer.write(frame)

    except Exception as exc:

        _set_capture_error(
            f"Camera: {exc}"
        )

    finally:

        try:

            if writer is not None:
                writer.release()

        except Exception:
            pass

        try:

            if cap is not None:
                cap.release()

        except Exception:
            pass

        with _LOCK:

            _CAPTURE_STATE[
                "camera"
            ] = False


# ============================================================
# SCREEN WORKER
# ============================================================

def _screen_worker(
    display_index,
    output_dir
):

    writer = None

    try:

        if mss is None:

            raise RuntimeError(
                "Screen recording requires mss."
            )

        if cv2 is None:

            raise RuntimeError(
                "Screen recording requires "
                "opencv-python."
            )

        if np is None:

            raise RuntimeError(
                "Screen recording requires numpy."
            )

        with mss.mss() as sct:

            monitors = list(
                sct.monitors[1:]
            )

            if not monitors:

                raise RuntimeError(
                    "No display detected."
                )

            display_index = int(
                display_index
            )

            # The public device list uses zero-based display IDs.
            # Older configs could contain screen_display=1 even on a
            # single-monitor PC; treat that legacy value as Display 1.
            if (
                display_index == 1
                and len(monitors) == 1
            ):
                display_index = 0

            if (
                display_index < 0
                or
                display_index >= len(
                    monitors
                )
            ):

                raise RuntimeError(
                    f"Selected display {display_index + 1} is not available. "
                    f"Detected {len(monitors)} display(s)."
                )

            mon = monitors[
                display_index
            ]

            width = int(
                mon["width"]
            )

            height = int(
                mon["height"]
            )

            if width <= 0 or height <= 0:

                raise RuntimeError(
                    "Invalid display resolution."
                )

            path = os.path.join(
                output_dir,
                f"screen_{_timestamp()}.mp4"
            )

            writer = cv2.VideoWriter(
                path,
                cv2.VideoWriter_fourcc(
                    *"mp4v"
                ),
                20.0,
                (
                    width,
                    height
                )
            )

            if (
                writer is None
                or
                not writer.isOpened()
            ):

                raise RuntimeError(
                    "Could not create "
                    "screen recording file."
                )

            _add_file(path)

            with _LOCK:
                _CAPTURE_STATE[
                    "screen"
                ] = True

            # ------------------------------------------------
            # Recording loop
            # ------------------------------------------------

            while not _CAPTURE_STOP.is_set():

                frame = np.array(
                    sct.grab(mon)
                )

                frame = cv2.cvtColor(
                    frame,
                    cv2.COLOR_BGRA2BGR
                )

                writer.write(
                    frame
                )

                time.sleep(
                    0.02
                )

    except Exception as exc:

        _set_capture_error(
            f"Screen: {exc}"
        )

    finally:

        try:

            if writer is not None:
                writer.release()

        except Exception:
            pass

        with _LOCK:

            _CAPTURE_STATE[
                "screen"
            ] = False


# ============================================================
# MICROPHONE WORKER
# ============================================================

def _microphone_worker(
    device,
    output_dir
):

    wf = None

    try:

        if sd is None:

            raise RuntimeError(
                "Microphone recording "
                "requires sounddevice."
            )

        if np is None:

            raise RuntimeError(
                "Microphone recording "
                "requires numpy."
            )

        # ----------------------------------------------------
        # Query selected input device
        # ----------------------------------------------------

        info = sd.query_devices(
            device,
            "input"
        )

        channels = max(
            1,
            min(
                2,
                int(
                    info.get(
                        "max_input_channels",
                        1
                    )
                )
            )
        )

        samplerate = int(
            float(
                info.get(
                    "default_samplerate",
                    44100
                )
            )
        )

        if samplerate <= 0:
            samplerate = 44100

        # ----------------------------------------------------
        # Output
        # ----------------------------------------------------

        path = os.path.join(
            output_dir,
            f"microphone_{_timestamp()}.wav"
        )

        import wave

        wf = wave.open(
            path,
            "wb"
        )

        wf.setnchannels(
            channels
        )

        wf.setsampwidth(
            2
        )

        wf.setframerate(
            samplerate
        )

        _add_file(path)

        with _LOCK:

            _CAPTURE_STATE[
                "microphone"
            ] = True

        # ----------------------------------------------------
        # Audio callback
        # ----------------------------------------------------

        def callback(
            indata,
            frames,
            callback_time,
            status
        ):

            try:

                if status:

                    _set_capture_error(
                        f"Microphone: "
                        f"{status}"
                    )

                if wf is not None:

                    audio = (
                        np.asarray(
                            indata
                        )
                        * 32767
                    )

                    audio = np.clip(
                        audio,
                        -32768,
                        32767
                    ).astype(
                        np.int16
                    )

                    wf.writeframes(
                        audio.tobytes()
                    )

            except Exception as exc:

                _set_capture_error(
                    f"Microphone callback: "
                    f"{exc}"
                )

        # ----------------------------------------------------
        # Start input stream
        # ----------------------------------------------------

        with sd.InputStream(
            device=device,
            samplerate=samplerate,
            channels=channels,
            dtype="float32",
            callback=callback,
        ):

            while not _CAPTURE_STOP.is_set():

                time.sleep(
                    0.1
                )

    except Exception as exc:

        _set_capture_error(
            f"Microphone: {exc}"
        )

    finally:

        try:

            if wf is not None:
                wf.close()

        except Exception:
            pass

        with _LOCK:

            _CAPTURE_STATE[
                "microphone"
            ] = False


# ============================================================
# START CAPTURE
# ============================================================

def start_capture():

    if not is_enabled():

        raise RuntimeError(
            "HID & Device Manager is "
            "disabled. Enable it first."
        )

    # --------------------------------------------------------
    # Already running?
    # --------------------------------------------------------

    if status()[
        "capture_active"
    ]:

        return status()[
            "capture"
        ]

    cfg = _cfg()[
        "capture"
    ]

    selected = {

        "camera":
            bool(
                cfg.get(
                    "camera_enabled",
                    False
                )
            ),

        "microphone":
            bool(
                cfg.get(
                    "microphone_enabled",
                    False
                )
            ),

        "screen":
            bool(
                cfg.get(
                    "screen_enabled",
                    False
                )
            ),
    }

    # --------------------------------------------------------
    # At least one device
    # --------------------------------------------------------

    if not any(
        selected.values()
    ):

        raise RuntimeError(
            "Enable at least one "
            "capture device first."
        )

    # --------------------------------------------------------
    # Dependency validation
    # --------------------------------------------------------

    if (
        selected["camera"]
        and
        cv2 is None
    ):

        raise RuntimeError(
            "Camera recording requires "
            "opencv-python."
        )

    if (
        selected["screen"]
        and
        (
            mss is None
            or
            cv2 is None
            or
            np is None
        )
    ):

        raise RuntimeError(
            "Screen recording requires "
            "mss, opencv-python "
            "and numpy."
        )

    if (
        selected["microphone"]
        and
        (
            sd is None
            or
            np is None
        )
    ):

        raise RuntimeError(
            "Microphone recording requires "
            "sounddevice and numpy."
        )

    # --------------------------------------------------------
    # Output directory
    # --------------------------------------------------------

    output_dir = os.path.abspath(
        os.path.expanduser(
            cfg.get(
                "output_path",
                os.path.join(
                    os.path.expanduser("~"),
                    "ASSHOLE_DECK_Captures"
                )
            )
        )
    )

    Path(
        output_dir
    ).mkdir(
        parents=True,
        exist_ok=True
    )

    # --------------------------------------------------------
    # Reset stop event
    # --------------------------------------------------------

    _CAPTURE_STOP.clear()

    # --------------------------------------------------------
    # Reset state
    # --------------------------------------------------------

    with _LOCK:

        _CAPTURE_STATE.update({

            "camera":
                False,

            "microphone":
                False,

            "screen":
                False,

            "started_at":
                time.time(),

            "files":
                [],

            "error":
                None,
        })

    # --------------------------------------------------------
    # Create workers
    # --------------------------------------------------------

    threads = []

    if selected["camera"]:

        camera_device = cfg.get(
            "camera_device",
            0
        )

        threads.append(
            threading.Thread(
                target=_camera_worker,
                args=(
                    camera_device,
                    output_dir,
                ),
                daemon=True,
                name="Capture-Camera",
            )
        )

    if selected["microphone"]:

        microphone_device = cfg.get(
            "microphone_device",
            "default"
        )

        threads.append(
            threading.Thread(
                target=_microphone_worker,
                args=(
                    microphone_device,
                    output_dir,
                ),
                daemon=True,
                name="Capture-Microphone",
            )
        )

    if selected["screen"]:

        screen_device = int(
            cfg.get(
                "screen_device",
                cfg.get(
                    "screen_display",
                    0
                )
            )
        )

        threads.append(
            threading.Thread(
                target=_screen_worker,
                args=(
                    screen_device,
                    output_dir,
                ),
                daemon=True,
                name="Capture-Screen",
            )
        )

    # --------------------------------------------------------
    # Store threads
    # --------------------------------------------------------

    global _CAPTURE_THREADS

    _CAPTURE_THREADS = threads

    # --------------------------------------------------------
    # Start threads
    # --------------------------------------------------------

    for thread in threads:

        thread.start()

    # Give workers a short startup period.
    time.sleep(
        0.25
    )

    return status()[
        "capture"
    ]


# ============================================================
# STOP CAPTURE
# ============================================================

def stop_capture():

    _CAPTURE_STOP.set()

    threads = list(
        _CAPTURE_THREADS
    )

    for thread in threads:

        if thread.is_alive():

            thread.join(
                timeout=2.0
            )

    with _LOCK:

        _CAPTURE_STATE[
            "camera"
        ] = False

        _CAPTURE_STATE[
            "microphone"
        ] = False

        _CAPTURE_STATE[
            "screen"
        ] = False

    return status()[
        "capture"
    ]


# ============================================================
# MODULE INITIALIZATION
# ============================================================

try:
    _normalize_config()
    _ensure_dirs()
except Exception:
    pass