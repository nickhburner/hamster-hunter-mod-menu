# Hamster Hunter Mod Menu
# Imports

import threading
import tkinter as tk

import customtkinter as ctk
import pymem
import pymem.process

try:
    from pynput import keyboard as pynput_kb, mouse as pynput_mouse
    PYNPUT_OK = True
except Exception:
    pynput_kb = pynput_mouse = None
    PYNPUT_OK = False


# Constants

APP_SIZE  = "560x640"
WAIT_SIZE = "340x140"
FONT      = ("Montserrat ExtraBold", 13)
FONT_SM   = ("Montserrat ExtraBold", 11)


# Pointer Offsets
# GameAssembly.dll (money, info, blocks)

MONEY_BASE_OFFSET  = 0x04169C80
MONEY_PTR_OFFSETS  = [0xB8, 0x0,  0x20]

INFO_BASE_OFFSET   = 0x0412BF70
INFO_PTR_OFFSETS   = [0xB8, 0x20, 0x4C]

BLOCKS_BASE_OFFSET = 0x0415B000
BLOCKS_PTR_OFFSETS = [0xB8, 0x0,  0x1A8]

# UnityPlayer.dll (FPV drone)

FPV_MODULE        = "UnityPlayer.dll"
FPV_BASE_OFFSET   = 0x01F591C0
FPV_CHAIN_OFFSETS = [0x0, 0xE00, 0x240, 0x50, 0x0]

FPV_FIELDS = {
    "thrustSpeed":   0x20,
    "strafeSpeed":   0x24,
    "verticalSpeed": 0x28,
    "acceleration":  0x30,
    "deceleration":  0x34,
    "currentPitch":  0x1DC,
    "currentYaw":    0x1E0,
}


# Process state — populated on successful game attach

pm                = None
gameassembly_base = None
unityplayer_base  = None


# Memory Helpers

def _read_ptr(addr: int) -> int:
    return pm.read_longlong(addr)

def _resolve_ptr_chain(module_base: int, base_off: int, offs: list[int]) -> int:
    addr = module_base + base_off
    for off in offs:
        addr = _read_ptr(addr) + off
    return addr

def _resolve_fpv_field_address(field: str) -> int:
    addr = _read_ptr(unityplayer_base + FPV_BASE_OFFSET)
    if addr == 0:
        raise RuntimeError("FPV base pointer is null (enter drone mode first)")
    for off in FPV_CHAIN_OFFSETS:
        addr = _read_ptr(addr + off)
        if addr == 0:
            raise RuntimeError("FPV pointer chain resolved to null")
    return addr + FPV_FIELDS[field]

def _read_fpv_safe(field: str, default: float) -> float:
    try:
        return pm.read_float(_resolve_fpv_field_address(field))
    except Exception:
        return default


# Value Setters

def set_money(v: float):
    a = _resolve_ptr_chain(gameassembly_base, MONEY_BASE_OFFSET, MONEY_PTR_OFFSETS)
    pm.write_float(a, float(v))
    rb = pm.read_float(a)
    return f"Money → {rb} @ {hex(a)}", "lightgreen"

def set_info(v: float):
    a = _resolve_ptr_chain(gameassembly_base, INFO_BASE_OFFSET, INFO_PTR_OFFSETS)
    pm.write_int(a, int(v))
    rb = pm.read_int(a)
    return f"Info → {rb} @ {hex(a)}", "lightgreen"

def set_blocks(v: float):
    a = _resolve_ptr_chain(gameassembly_base, BLOCKS_BASE_OFFSET, BLOCKS_PTR_OFFSETS)
    pm.write_int(a, int(v))
    rb = pm.read_int(a)
    return f"Blocks → {rb} @ {hex(a)}", "lightgreen"

def _set_fpv_field(field: str, v: float):
    a = _resolve_fpv_field_address(field)
    pm.write_float(a, float(v))
    rb = pm.read_float(a)
    return f"{field} {rb} @ {hex(a)}", "lightgreen"

def set_thrust_speed(v: float):    return _set_fpv_field("thrustSpeed",   v)
def set_strafe_speed(v: float):    return _set_fpv_field("strafeSpeed",   v)
def set_vertical_speed(v: float):  return _set_fpv_field("verticalSpeed", v)
def set_acceleration(v: float):    return _set_fpv_field("acceleration",  v)
def set_deceleration(v: float):    return _set_fpv_field("deceleration",  v)
def set_current_pitch(v: float):   return _set_fpv_field("currentPitch",  v)
def set_current_yaw(v: float):     return _set_fpv_field("currentYaw",    v)


# GUI Initialization

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

app = ctk.CTk()
app.title("Hamster Hunter Mod Menu")
app.geometry(WAIT_SIZE)
app.attributes("-topmost", True)
app.resizable(False, False)


# Tooltip

class _Tooltip:
    def __init__(self, widget, text: str):
        self._text   = text
        self._window = None
        widget.bind("<Enter>", self._show)
        widget.bind("<Leave>", self._hide)

    def _show(self, event):
        x = event.widget.winfo_rootx() + 20
        y = event.widget.winfo_rooty() + 24
        self._window = tw = tk.Toplevel()
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        tw.attributes("-topmost", True)
        tk.Label(
            tw, text=self._text, justify="left",
            background="#2b2b2b", foreground="white",
            font=("Montserrat ExtraBold", 11),
            relief="solid", borderwidth=1,
            padx=8, pady=5, wraplength=240,
        ).pack()

    def _hide(self, *_):
        if self._window:
            self._window.destroy()
            self._window = None

def _add_info_icon(parent_frame, tooltip_text: str):
    lbl = ctk.CTkLabel(parent_frame, text="?", width=18, font=FONT_SM,
                        text_color="gray", cursor="question_arrow")
    lbl.pack(side="left", padx=(6, 0))
    _Tooltip(lbl, tooltip_text)


# Waiting Screen

_wait_frame = ctk.CTkFrame(app, fg_color="transparent")
_wait_frame.pack(expand=True, fill="both")

ctk.CTkLabel(_wait_frame, text="Hamster Hunter Mod Menu", font=("Montserrat ExtraBold", 16)).pack(pady=(24, 8))

_wait_status = ctk.StringVar(value="Waiting for Hamster Hunter")
ctk.CTkLabel(_wait_frame, textvariable=_wait_status, font=FONT, text_color="gray").pack()

_dot_count = 0

def _animate_dots():
    global _dot_count
    _dot_count = (_dot_count + 1) % 4
    _wait_status.set("Waiting for Hamster Hunter" + "." * _dot_count)
    app.after(500, _animate_dots)


# Game Attach & Poll

def _attach_to_game():
    global pm, gameassembly_base, unityplayer_base
    pm = pymem.Pymem("Hamster Hunter.exe")
    gameassembly_base = pymem.process.module_from_name(
        pm.process_handle, "GameAssembly.dll"
    ).lpBaseOfDll
    unityplayer_base = pymem.process.module_from_name(
        pm.process_handle, FPV_MODULE
    ).lpBaseOfDll

def _poll_for_game():
    try:
        _attach_to_game()
    except Exception:
        app.after(1000, _poll_for_game)
        return
    _wait_frame.pack_forget()
    app.geometry(APP_SIZE)
    app.resizable(True, True)
    _build_main_ui()


# Always-on-Top Toggle (tilde key)

_topmost      = True
_topmost_hint = None  # StringVar, created inside _build_main_ui

def _toggle_topmost():
    global _topmost
    _topmost = not _topmost
    app.attributes("-topmost", _topmost)
    if _topmost_hint is not None:
        _topmost_hint.set("Press ~ to unlock from top" if _topmost else "Press ~ to lock on top")


# Hotkey Helper

_RECORDABLE_MOUSE_BUTTONS = (
    {pynput_mouse.Button.x1, pynput_mouse.Button.x2} if PYNPUT_OK else set()
)

def _key_name(key) -> str:
    if PYNPUT_OK and isinstance(key, pynput_mouse.Button):
        return {
            pynput_mouse.Button.x1: "Mouse X1",
            pynput_mouse.Button.x2: "Mouse X2",
        }.get(key, f"mouse:{key.name}")
    char = getattr(key, "char", None)
    if char:
        return char
    name = getattr(key, "name", None)
    if name:
        return name
    return str(key)


# Binding Section

_active_recorder = None

class BindingSection:

    def __init__(self, parent, label: str, action_func,
                 value_placeholder: str = "value", tooltip: str = None):
        self.action_func  = action_func
        self.bindings     = []
        self.recorded_key = None
        self.is_recording = False

        header = ctk.CTkFrame(parent, fg_color="transparent")
        header.pack(fill="x", pady=(12, 2))
        ctk.CTkLabel(header, text=label, font=FONT).pack(side="left")
        if tooltip:
            _add_info_icon(header, tooltip)

        self.bindings_frame = ctk.CTkFrame(parent, fg_color="transparent")

        self._add_row = ctk.CTkFrame(parent, fg_color="transparent")
        self._add_row.pack(fill="x", pady=(4, 0))

        self.record_btn = ctk.CTkButton(
            self._add_row, text="Record", width=80, font=FONT, command=self._toggle_record,
        )
        self.record_btn.pack(side="left", padx=(0, 6))

        self.key_label = ctk.CTkLabel(self._add_row, text="—", width=90, font=FONT, anchor="w")
        self.key_label.pack(side="left", padx=(0, 6))

        self.value_entry = ctk.CTkEntry(self._add_row, placeholder_text=value_placeholder)
        self.value_entry.pack(side="left", fill="x", expand=True, padx=(0, 6))

        self.add_btn = ctk.CTkButton(
            self._add_row, text="Add", width=60, font=FONT,
            state="disabled", command=self._add_binding,
        )
        self.add_btn.pack(side="right")

    def _toggle_record(self):
        if self.is_recording:
            self._stop_recording()
        else:
            self._start_recording()

    def _start_recording(self):
        global _active_recorder
        if not PYNPUT_OK:
            status.set("Hotkeys unavailable: run  pip install pynput")
            status_label.configure(text_color="yellow")
            return
        app.focus_set()
        _active_recorder  = self
        self.is_recording = True
        self.recorded_key = None
        self.record_btn.configure(text="Stop")
        self.key_label.configure(text="listening…")
        self.add_btn.configure(state="disabled")
        status.set("Recording — press a key or mouse side button")
        status_label.configure(text_color="yellow")

    def _stop_recording(self):
        global _active_recorder
        if _active_recorder is self:
            _active_recorder = None
        self.is_recording = False
        self.record_btn.configure(text="Record")
        if self.recorded_key is None:
            self.key_label.configure(text="—")
            status.set("Recording cancelled")
            status_label.configure(text_color="yellow")
        else:
            self.key_label.configure(text=_key_name(self.recorded_key))
            status.set(f"Recorded: {_key_name(self.recorded_key)}")
            status_label.configure(text_color="lightgreen")

    def on_key_recorded(self, key):
        global _active_recorder
        _active_recorder  = None
        self.is_recording = False
        self.recorded_key = key
        self.record_btn.configure(text="Record")
        self.key_label.configure(text=_key_name(key))
        self.add_btn.configure(state="normal")
        status.set(f"Recorded: {_key_name(key)}")
        status_label.configure(text_color="lightgreen")

    def _add_binding(self):
        if self.recorded_key is None:
            return
        try:
            value = float(self.value_entry.get() or 0.0)
        except ValueError:
            status.set("Invalid number")
            status_label.configure(text_color="yellow")
            return

        key     = self.recorded_key
        name    = _key_name(key)
        binding = {"key": key, "value": value, "frame": None}

        if not self.bindings:
            self.bindings_frame.pack(fill="x", before=self._add_row)

        row = ctk.CTkFrame(self.bindings_frame, fg_color="transparent")
        row.pack(fill="x", pady=2)
        binding["frame"] = row

        ctk.CTkLabel(row, text=name,       width=90, font=FONT, anchor="w").pack(side="left", padx=(0, 6))
        ctk.CTkLabel(row, text=str(value),           font=FONT, anchor="w").pack(side="left", fill="x", expand=True)
        ctk.CTkButton(
            row, text="Remove", width=70, font=FONT,
            fg_color="#8B0000", hover_color="#5C0000",
            command=lambda b=binding: self._remove_binding(b),
        ).pack(side="right")

        self.bindings.append(binding)

        self.recorded_key = None
        self.key_label.configure(text="—")
        self.value_entry.delete(0, "end")
        self.add_btn.configure(state="disabled")
        status.set(f"Binding added: {name} → {value}")
        status_label.configure(text_color="lightgreen")

    def _remove_binding(self, binding):
        if binding in self.bindings:
            self.bindings.remove(binding)
        binding["frame"].destroy()
        if not self.bindings:
            self.bindings_frame.pack_forget()
        status.set("Binding removed")
        status_label.configure(text_color="yellow")

    def fire_if_match(self, key):
        for b in list(self.bindings):
            if b["key"] == key:
                try:
                    self.action_func(b["value"])
                except Exception:
                    pass


# Auto-Click Section

class AutoClickSection:

    def __init__(self, parent, label: str, tooltip: str = None):
        self.bindings     = []
        self.recorded_key = None
        self.is_recording = False

        header = ctk.CTkFrame(parent, fg_color="transparent")
        header.pack(fill="x", pady=(12, 2))
        ctk.CTkLabel(header, text=label, font=FONT).pack(side="left")
        if tooltip:
            _add_info_icon(header, tooltip)

        self.bindings_frame = ctk.CTkFrame(parent, fg_color="transparent")

        self._add_row = ctk.CTkFrame(parent, fg_color="transparent")
        self._add_row.pack(fill="x", pady=(4, 0))

        self.record_btn = ctk.CTkButton(
            self._add_row, text="Record", width=80, font=FONT, command=self._toggle_record,
        )
        self.record_btn.pack(side="left", padx=(0, 6))

        self.key_label = ctk.CTkLabel(self._add_row, text="—", width=90, font=FONT, anchor="w")
        self.key_label.pack(side="left", padx=(0, 6))

        self.value_entry = ctk.CTkEntry(self._add_row, placeholder_text="delay ms, ex 100")
        self.value_entry.pack(side="left", fill="x", expand=True, padx=(0, 6))

        self.add_btn = ctk.CTkButton(
            self._add_row, text="Add", width=60, font=FONT,
            state="disabled", command=self._add_binding,
        )
        self.add_btn.pack(side="right")

    def _toggle_record(self):
        if self.is_recording:
            self._stop_recording()
        else:
            self._start_recording()

    def _start_recording(self):
        global _active_recorder
        if not PYNPUT_OK:
            status.set("Hotkeys unavailable: run pip install pynput")
            status_label.configure(text_color="yellow")
            return
        app.focus_set()
        _active_recorder  = self
        self.is_recording = True
        self.recorded_key = None
        self.record_btn.configure(text="Stop")
        self.key_label.configure(text="listening…")
        self.add_btn.configure(state="disabled")
        status.set("Recording — press a key or mouse side button")
        status_label.configure(text_color="yellow")

    def _stop_recording(self):
        global _active_recorder
        if _active_recorder is self:
            _active_recorder = None
        self.is_recording = False
        self.record_btn.configure(text="Record")
        if self.recorded_key is None:
            self.key_label.configure(text="—")
            status.set("Recording cancelled")
            status_label.configure(text_color="yellow")
        else:
            self.key_label.configure(text=_key_name(self.recorded_key))
            status.set(f"Recorded: {_key_name(self.recorded_key)}")
            status_label.configure(text_color="lightgreen")

    def on_key_recorded(self, key):
        global _active_recorder
        _active_recorder  = None
        self.is_recording = False
        self.recorded_key = key
        self.record_btn.configure(text="Record")
        self.key_label.configure(text=_key_name(key))
        self.add_btn.configure(state="normal")
        status.set(f"Recorded: {_key_name(key)}")
        status_label.configure(text_color="lightgreen")

    def _add_binding(self):
        if self.recorded_key is None:
            return
        try:
            delay_ms = float(self.value_entry.get() or 0.0)
            if delay_ms <= 0:
                raise ValueError
        except ValueError:
            status.set("Enter a positive number for delay")
            status_label.configure(text_color="yellow")
            return

        key     = self.recorded_key
        name    = _key_name(key)
        binding = {"key": key, "delay_ms": delay_ms, "running": False,
                   "stop_event": None, "thread": None, "frame": None, "state_label": None}

        if not self.bindings:
            self.bindings_frame.pack(fill="x", before=self._add_row)

        row = ctk.CTkFrame(self.bindings_frame, fg_color="transparent")
        row.pack(fill="x", pady=2)
        binding["frame"] = row

        ctk.CTkLabel(row, text=name,              width=90, font=FONT, anchor="w").pack(side="left", padx=(0, 6))
        ctk.CTkLabel(row, text=f"{delay_ms:g}ms",          font=FONT, anchor="w").pack(side="left", fill="x", expand=True)

        state_lbl = ctk.CTkLabel(row, text="Stopped", width=70, font=FONT, text_color="gray", anchor="e")
        state_lbl.pack(side="left", padx=(0, 6))
        binding["state_label"] = state_lbl

        ctk.CTkButton(
            row, text="Remove", width=70, font=FONT,
            fg_color="#8B0000", hover_color="#5C0000",
            command=lambda b=binding: self._remove_binding(b),
        ).pack(side="right")

        self.bindings.append(binding)

        self.recorded_key = None
        self.key_label.configure(text="—")
        self.value_entry.delete(0, "end")
        self.add_btn.configure(state="disabled")
        status.set(f"Auto-clicker added: {name} @ {delay_ms:g}ms")
        status_label.configure(text_color="lightgreen")

    def _remove_binding(self, binding):
        self._stop_clicker(binding)
        if binding in self.bindings:
            self.bindings.remove(binding)
        binding["frame"].destroy()
        if not self.bindings:
            self.bindings_frame.pack_forget()
        status.set("Auto-clicker removed")
        status_label.configure(text_color="yellow")

    def _start_clicker(self, binding):
        stop_event = threading.Event()
        binding["stop_event"] = stop_event
        binding["running"]    = True
        binding["state_label"].configure(text="Running", text_color="lightgreen")

        delay_s = binding["delay_ms"] / 1000.0

        def _loop():
            if not PYNPUT_OK:
                return
            controller = pynput_mouse.Controller()
            while True:
                controller.click(pynput_mouse.Button.left)
                if stop_event.wait(delay_s):
                    break

        t = threading.Thread(target=_loop, daemon=True)
        binding["thread"] = t
        t.start()
        status.set(f"Auto-clicker started: {_key_name(binding['key'])} @ {binding['delay_ms']:g}ms")
        status_label.configure(text_color="lightgreen")

    def _stop_clicker(self, binding):
        binding["running"] = False
        if binding.get("stop_event"):
            binding["stop_event"].set()
            binding["stop_event"] = None
        if binding.get("state_label"):
            binding["state_label"].configure(text="Stopped", text_color="gray")
        status.set(f"Auto-clicker stopped: {_key_name(binding['key'])}")
        status_label.configure(text_color="yellow")

    def fire_if_match(self, key):
        for b in list(self.bindings):
            if b["key"] == key:
                if b["running"]:
                    app.after(0, lambda b=b: self._stop_clicker(b))
                else:
                    app.after(0, lambda b=b: self._start_clicker(b))

    def stop_all(self):
        for b in self.bindings:
            if b["running"]:
                b["running"] = False
                if b.get("stop_event"):
                    b["stop_event"].set()


# GUI Row Builder

def _build_float_setter_row(parent, label_text: str, placeholder: str,
                             setter_func, initial_val=None, tooltip: str = None, default_val=None):
    header = ctk.CTkFrame(parent, fg_color="transparent")
    header.pack(fill="x", pady=(6, 0))
    ctk.CTkLabel(header, text=label_text, font=FONT).pack(side="left")
    if tooltip:
        _add_info_icon(header, tooltip)

    if initial_val is not None:
        current_label = ctk.CTkLabel(
            header, text=f"Current: {initial_val:g}", font=FONT, text_color="lightgreen",
        )
        current_label.pack(side="left", padx=(8, 0))
        reset_val = default_val if default_val is not None else initial_val
        _on_reconnect_callbacks.append(
            lambda lbl=current_label, v=reset_val: lbl.configure(text=f"Current: {v:g}")
        )
    else:
        current_label = None

    row = ctk.CTkFrame(parent, fg_color="transparent")
    row.pack(fill="x", pady=6)

    entry = ctk.CTkEntry(row, placeholder_text=placeholder)
    entry.pack(side="left", fill="x", expand=True, padx=(0, 8))

    def _on_confirm():
        try:
            value = float(entry.get() or 0.0)
            msg, color = setter_func(value)
            status.set(msg)
            status_label.configure(text_color=color)
            if current_label is not None:
                current_label.configure(text=f"Current: {value:g}")
        except ValueError:
            status.set("Invalid number")
            status_label.configure(text_color="yellow")
        except Exception as e:
            status.set(str(e))
            status_label.configure(text_color="red")

    ctk.CTkButton(row, text="Confirm", font=FONT, command=_on_confirm).pack(side="right")


# Main UI Builder — called once the game process is detected

status                  = None
status_label            = None
autoclick_section       = None
pitch_section           = None
yaw_section             = None
kb_listener             = None
mouse_listener          = None
_game_connected         = False
_on_reconnect_callbacks = []

def _build_main_ui():
    global status, status_label, autoclick_section, pitch_section, yaw_section
    global _topmost_hint, kb_listener, mouse_listener, _game_connected

    frame = ctk.CTkScrollableFrame(app)
    frame.pack(pady=20, padx=20, fill="both", expand=True)

    # Status bar
    status = ctk.StringVar(value="Ready")
    status_label = ctk.CTkLabel(frame, textvariable=status, font=FONT, text_color="lightgreen")
    status_label.pack(anchor="w", pady=(10, 2))

    # Topmost hint
    _topmost_hint = ctk.StringVar(value="Press ~ to unlock from top")
    ctk.CTkLabel(frame, textvariable=_topmost_hint, font=FONT, text_color="gray").pack(anchor="w", pady=(0, 4))

    # Opacity slider
    opacity_row = ctk.CTkFrame(frame, fg_color="transparent")
    opacity_row.pack(fill="x", pady=(0, 8))
    ctk.CTkLabel(opacity_row, text="Opacity", font=FONT).pack(side="left")
    opacity_val = ctk.CTkLabel(opacity_row, text="100%", width=44, font=FONT, anchor="e")
    opacity_val.pack(side="right")

    def _on_opacity(val):
        app.attributes("-alpha", val)
        opacity_val.configure(text=f"{int(val * 100)}%")

    ctk.CTkSlider(
        opacity_row, from_=0.2, to=1.0, number_of_steps=80,
        command=_on_opacity,
    ).pack(side="left", fill="x", expand=True, padx=(10, 8))

    # Auto Clicker
    autoclick_section = AutoClickSection(
        frame, "Auto Clicker",
        tooltip="Simulates left mouse clicks at the set interval. Press the bound key to start or stop.",
    )

    # Money
    _build_float_setter_row(frame, "Money", "Enter amount, ex 999.0", set_money)

    # Info
    _build_float_setter_row(
        frame, "Info", "Enter amount, ex 500", set_info,
        tooltip="Info points. You must collect at least one info point in-game before editing this value.",
    )

    # Blocks
    _build_float_setter_row(
        frame, "Blocks", "Enter amount, ex 999", set_blocks,
        tooltip="Building blocks. You must place or pick up at least one block in-game before editing this value.",
    )

    # FPV Drone — collapsible section
    _fpv_visible = [True]

    toggle_btn = ctk.CTkButton(
        frame, text="▼  FPV Drone", font=FONT, anchor="w",
        fg_color="#1f538d", hover_color="#174070",
        command=lambda: _toggle_fpv(),
    )
    toggle_btn.pack(fill="x", pady=(16, 0))

    fpv_frame = ctk.CTkFrame(frame, fg_color="transparent")
    fpv_frame.pack(fill="x")

    def _toggle_fpv():
        if _fpv_visible[0]:
            fpv_frame.pack_forget()
            toggle_btn.configure(text="▶  FPV Drone")
            _fpv_visible[0] = False
        else:
            fpv_frame.pack(fill="x")
            toggle_btn.configure(text="▼  FPV Drone")
            _fpv_visible[0] = True

    pitch_section = BindingSection(
        fpv_frame, "Pitch Hotkeys", set_current_pitch,
        value_placeholder="ex -90 for up, 90 for down, 0 for level",
        tooltip="Sets a hotkey to set the drone's vertical tilt. Useful for aligning the drone when building. -90 = straight up, 90 = straight down, 0 = level.",
    )
    yaw_section = BindingSection(
        fpv_frame, "Yaw Hotkeys", set_current_yaw,
        value_placeholder="ex. 0 for north, 90 for east",
        tooltip="Sets a hotkey to set the direction the drone faces. 0 = North, 90 = East, 180 = South, 270 = West.",
    )

    _build_float_setter_row(fpv_frame, "Thrust Speed",   "Default: 10", set_thrust_speed,
                            _read_fpv_safe("thrustSpeed",   10), default_val=10,
                            tooltip="How fast the drone moves forward and backward. (bigger number = faster)")
    _build_float_setter_row(fpv_frame, "Strafe Speed",   "Default: 8",  set_strafe_speed,
                            _read_fpv_safe("strafeSpeed",   8),  default_val=8,
                            tooltip="How fast the drone moves left and right. (bigger number = faster)")
    _build_float_setter_row(fpv_frame, "Vertical Speed", "Default: 5",  set_vertical_speed,
                            _read_fpv_safe("verticalSpeed", 5),  default_val=5,
                            tooltip="How fast the drone moves up and down. (bigger number = faster)")
    _build_float_setter_row(fpv_frame, "Acceleration",   "Default: 2",  set_acceleration,
                            _read_fpv_safe("acceleration",  2),  default_val=2,
                            tooltip="How quickly the drone reaches full speed when input is applied. (bigger number = speeds up faster)")
    _build_float_setter_row(fpv_frame, "Deceleration",   "Default: 1",  set_deceleration,
                            _read_fpv_safe("deceleration",  1),  default_val=1,
                            tooltip="How quickly the drone slows to a stop when input is released. (bigger number = slows down faster)")

    if not PYNPUT_OK:
        status.set("Hotkeys unavailable. Run: pip install pynput")
        status_label.configure(text_color="yellow")

    # Start pynput listeners now that all sections exist
    if PYNPUT_OK:
        kb_listener    = pynput_kb.Listener(on_press=_on_global_key_press)
        mouse_listener = pynput_mouse.Listener(on_click=_on_global_mouse_click)
        kb_listener.start()
        mouse_listener.start()

    # Begin health monitoring
    _game_connected = True
    app.after(3000, _connection_check)


# Global pynput Listeners

def _on_global_key_press(key):
    global _active_recorder

    if getattr(key, "char", None) in ("`", "~"):
        app.after(0, _toggle_topmost)
        return

    if _active_recorder is not None:
        recorder         = _active_recorder
        _active_recorder = None
        app.after(0, lambda: recorder.on_key_recorded(key))
        return

    if autoclick_section: autoclick_section.fire_if_match(key)
    if pitch_section:     pitch_section.fire_if_match(key)
    if yaw_section:       yaw_section.fire_if_match(key)

def _on_global_mouse_click(_x, _y, button, pressed):
    if not pressed:
        return
    global _active_recorder

    if _active_recorder is not None and button in _RECORDABLE_MOUSE_BUTTONS:
        recorder         = _active_recorder
        _active_recorder = None
        app.after(0, lambda: recorder.on_key_recorded(button))
        return

    if autoclick_section: autoclick_section.fire_if_match(button)
    if pitch_section:     pitch_section.fire_if_match(button)
    if yaw_section:       yaw_section.fire_if_match(button)


# Connection Health Check

def _connection_check():
    global _game_connected
    try:
        _read_ptr(gameassembly_base + MONEY_BASE_OFFSET)
        app.after(3000, _connection_check)
    except Exception:
        _game_connected = False
        if autoclick_section:
            autoclick_section.stop_all()
        if status:
            status.set("Game closed — waiting to reconnect...")
            status_label.configure(text_color="yellow")
        app.after(3000, _reconnect_poll)

def _reconnect_poll():
    global _game_connected
    try:
        _attach_to_game()
        _game_connected = True
        for cb in _on_reconnect_callbacks:
            cb()
        if status:
            status.set("Reconnected — values reset to game defaults")
            status_label.configure(text_color="lightgreen")
        app.after(3000, _connection_check)
    except Exception:
        app.after(3000, _reconnect_poll)


# Window Close Handler

def _on_close():
    if autoclick_section:
        autoclick_section.stop_all()
    if PYNPUT_OK:
        try: kb_listener.stop()
        except Exception: pass
        try: mouse_listener.stop()
        except Exception: pass
    app.destroy()

app.protocol("WM_DELETE_WINDOW", _on_close)


# Start dot animation, begin polling, enter main loop

_animate_dots()
app.after(500, _poll_for_game)
app.mainloop()
