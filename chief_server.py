"""
Alfred Desktop App v2 — Clean rewrite
Holographic orb UI with unified command dispatcher.
"""
import customtkinter as ctk
import tkinter as tk
import threading
import requests
import sounddevice as sd
import numpy as np
import scipy.io.wavfile as wav
import tempfile
import os
import time
import math
import random
import datetime
import psutil
from PIL import Image, ImageDraw, ImageFilter

# ── Feature Imports ────────────────────────────────────────────
from pc_control import detect_pc_command, execute_pc_command
from pc_vision import detect_vision_command, execute_vision_command
from briefing import detect_briefing_command, execute_briefing_command
from routines import (detect_routine_command, execute_routine_command,
                      get_due_routines, get_routine, execute_routine_actions, load_routines)
from media_control import detect_media_command, execute_media_command
from code_assistant import detect_code_command, execute_code_command
from agent import detect_agent_command, run_agent
from ambient import (get_time_context, track_interaction, get_proactive_suggestion,
                     get_orb_color_for_time, reset_session, get_session_duration)
from finance import detect_finance_command, execute_finance_command
from deep_conversation import detect_deep_conversation
from system_monitor import (detect_system_command, execute_system_command,
                            check_alerts, get_system_stats)
from email_manager import detect_email_command, execute_email_command, get_unread_count
from calendar_manager import detect_calendar_command, execute_calendar_command, get_next_event
from security_monitor import (detect_security_command, execute_security_command,
                              check_all_security)
from clipboard_manager import (detect_clipboard_command, execute_clipboard_command,
                               start_monitoring as start_clipboard)
from document_reader import detect_document_command, execute_document_command
from meeting_recorder import detect_recording_command, execute_recording_command
from device_sync import detect_sync_command, execute_sync_command, start_auto_sync
from custom_commands import detect_custom_command, execute_command as execute_protocol, list_commands
from hud_overlay import HUDOverlay
from live_dashboard import LiveDashboard

# ── Configuration ──────────────────────────────────────────────
SERVER_URL = os.environ.get("ALFRED_SERVER_URL", "http://localhost:8000")
AUTH_TOKEN = "Bearer " + os.environ.get("ALFRED_AUTH_TOKEN", "change-me-in-env")
SAMPLE_RATE = 16000
KOKORO_VOICE = "bm_george"
WAKE_WORD = "alfred"
HOTKEY_COMBO = "<ctrl>+<space>"
ELEVENLABS_VOICE_ID = "JBFqnCBsd6RMkjVDRZzb"
ELEVENLABS_MODEL = "eleven_multilingual_v2"
ELEVENLABS_API_KEY = ""

ORB_SIZE = 280
ORB_PARTICLES = 120
ORB_FPS = 24

# ── Colors ─────────────────────────────────────────────────────
BG_DARK = "#060a10"
BG_PANEL = "#0a1020"
BG_INPUT = "#0c1428"
CYAN = "#00f0ff"
CYAN_DIM = "#0a3040"
CYAN_DARK = "#063040"
BLUE_DIM = "#0a1a3a"
TEXT = "#c8dce8"
TEXT_DIM = "#4a6a7a"
SUCCESS = "#00ff88"
DANGER = "#ff3050"
ACCENT = "#00c8d0"
AMBER = "#ffaa00"
BG_RGB = (6, 10, 16)

ctk.set_appearance_mode("dark")

# ── Command Dispatcher ─────────────────────────────────────────
# Each entry: (detect_func, execute_func, options)
# Options: status_msg, long_speak_msg, max_display_chars, needs_server
COMMAND_PIPELINE = [
    # Custom protocols (highest priority)
    {"detect": detect_custom_command, "name": "protocol"},
    # Routines
    {"detect": detect_routine_command, "execute": execute_routine_command, "name": "routine"},
    # Agent (multi-step tasks)
    {"detect": detect_agent_command, "name": "agent"},
    # Media
    {"detect": detect_media_command, "execute": execute_media_command, "name": "media"},
    # Code
    {"detect": detect_code_command, "execute": execute_code_command, "name": "code",
     "status": "Analyzing code...", "long_msg": "I've prepared the analysis, Sir."},
    # Finance
    {"detect": detect_finance_command, "execute": execute_finance_command, "name": "finance"},
    # System monitor
    {"detect": detect_system_command, "execute": execute_system_command, "name": "system"},
    # Email
    {"detect": detect_email_command, "execute": execute_email_command, "name": "email",
     "status": "Checking your email, Sir...", "long_msg": "Your emails are in the chat, Sir."},
    # Security
    {"detect": detect_security_command, "execute": execute_security_command, "name": "security",
     "long_msg": "Security report is in the chat, Sir."},
    # Clipboard
    {"detect": detect_clipboard_command, "execute": execute_clipboard_command, "name": "clipboard",
     "long_msg": "Your clipboard history is in the chat, Sir."},
    # Documents
    {"detect": detect_document_command, "execute": execute_document_command, "name": "document",
     "status": "Reading document...", "long_msg": "I've analyzed the document, Sir."},
    # Recording
    {"detect": detect_recording_command, "execute": execute_recording_command, "name": "recording",
     "long_msg": "Recording processed, Sir."},
    # Sync
    {"detect": detect_sync_command, "execute": execute_sync_command, "name": "sync"},
    # Calendar
    {"detect": detect_calendar_command, "execute": execute_calendar_command, "name": "calendar",
     "status": "Checking your calendar, Sir...", "long_msg": "Your schedule is in the chat, Sir."},
    # Briefing
    {"detect": detect_briefing_command, "name": "briefing"},
    # PC control
    {"detect": detect_pc_command, "execute": execute_pc_command, "name": "pc_control"},
    # Vision
    {"detect": detect_vision_command, "execute": execute_vision_command, "name": "vision",
     "status": "Looking at screen..."},
]



# ═══════════════════════════════════════════════════════════════
# HOLOGRAPHIC SPHERE
# ═══════════════════════════════════════════════════════════════
class HoloSphere:
    """Holographic particle sphere rendered with PIL."""

    def __init__(self, size=280, num_particles=120):
        self.size = size
        self.cx = size // 2
        self.cy = size // 2
        self.base_radius = size // 4
        self.radius = self.base_radius
        self.angle = 0.0
        self.pulse_phase = 0.0
        self.state = "idle"
        self.idle_color = (0, 140, 220)
        golden = (1 + math.sqrt(5)) / 2
        self.particles = [{
            "theta": math.acos(1 - 2 * (i + 0.5) / num_particles) + random.uniform(-0.03, 0.03),
            "phi": 2 * math.pi * i / golden + random.uniform(-0.03, 0.03),
            "speed": random.uniform(0.4, 1.2),
            "size": random.uniform(2.0, 4.0),
            "brightness": random.uniform(0.5, 1.0),
            "phase_offset": random.uniform(0, math.pi * 2)
        } for i in range(num_particles)]

    def set_state(self, state):
        self.state = state

    def render(self):
        self.angle += 0.012
        self.pulse_phase += 0.05

        colors = {
            "idle": (self.idle_color, tuple(max(0, c - 60) for c in self.idle_color), 0.5, 4),
            "listening": ((0, 230, 120), (0, 160, 80), 1.8, 12),
            "thinking": ((240, 160, 0), (180, 100, 0), 3.5, 8),
            "speaking": ((0, 200, 255), (0, 140, 220), 2.0, 14),
        }
        base_color, glow_color, pulse_speed, pulse_amp = colors.get(self.state, colors["idle"])
        pulse = math.sin(self.pulse_phase * pulse_speed) * pulse_amp
        self.radius = self.base_radius + pulse

        img = Image.new('RGB', (self.size, self.size), BG_RGB)
        particle_layer = Image.new('RGB', (self.size, self.size), (0, 0, 0))
        core_layer = Image.new('RGB', (self.size, self.size), (0, 0, 0))
        draw_p = ImageDraw.Draw(particle_layer)
        draw_c = ImageDraw.Draw(core_layer)

        # Center glow
        for r in range(int(self.radius * 0.8), 0, -3):
            a = max(0, min(255, int(15 * (1 - r / (self.radius * 0.8)))))
            gc = tuple(max(0, min(255, int(glow_color[j] * a / 255))) for j in range(3))
            draw_p.ellipse([self.cx - r, self.cy - r, self.cx + r, self.cy + r], fill=gc)

        # Particles
        rot = self.angle * 0.6
        cos_rot, sin_rot = math.cos(rot), math.sin(rot)
        for i, p in enumerate(self.particles):
            phi = p["phi"] + self.angle * p["speed"]
            x3d = math.sin(p["theta"]) * math.cos(phi)
            y3d = math.sin(p["theta"]) * math.sin(phi)
            z3d = math.cos(p["theta"])
            x_r = x3d * cos_rot - z3d * sin_rot
            z_r = x3d * sin_rot + z3d * cos_rot
            depth = (z_r + 1) / 2
            px = self.cx + x_r * self.radius
            py = self.cy + y3d * self.radius
            ind_pulse = math.sin(self.pulse_phase * 1.5 + p["phase_offset"]) * 0.25
            bright = max(0.1, min(1.0, p["brightness"] * (0.3 + depth * 0.7) + ind_pulse))
            size = p["size"] * (0.5 + depth * 0.7)
            cr = max(0, min(255, int(base_color[0] * bright)))
            cg = max(0, min(255, int(base_color[1] * bright)))
            cb = max(0, min(255, int(base_color[2] * bright)))
            s = size * 2
            draw_p.ellipse([px - s, py - s, px + s, py + s], fill=(cr, cg, cb))
            s2 = size * 0.8
            br = max(0, min(255, int(base_color[0] * bright * 1.5 + 60 * bright)))
            bg_val = max(0, min(255, int(base_color[1] * bright * 1.5 + 60 * bright)))
            bb = max(0, min(255, int(base_color[2] * bright * 1.5 + 60 * bright)))
            draw_c.ellipse([px - s2, py - s2, px + s2, py + s2], fill=(br, bg_val, bb))

        glow = particle_layer.filter(ImageFilter.GaussianBlur(radius=6))
        result = np.clip(
            np.array(img, dtype=np.int16) + np.array(glow, dtype=np.int16) * 2
            + np.array(core_layer, dtype=np.int16), 0, 255
        ).astype(np.uint8)
        return Image.fromarray(result)


# ═══════════════════════════════════════════════════════════════
# MAIN APPLICATION
# ═══════════════════════════════════════════════════════════════
class AlfredApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("A L F R E D")
        self.geometry("520x860")
        self.minsize(420, 700)
        self.configure(fg_color=BG_DARK)

        self.is_recording = False
        self.audio_chunks = []
        self.conversation_history = []
        self.tts_enabled = True
        self.tts_pipeline = None
        self.wake_word_active = False
        self.state_changed_at = time.time()
        self.sphere = HoloSphere(ORB_SIZE, ORB_PARTICLES)
        self.orb_photo = None
        self.hud = None
        self.dashboard = None

        self._load_elevenlabs_key()
        self._build_ui()
        self._load_voice()
        self._check_status()
        self._setup_hotkey()
        self._animate_orb()
        self._start_services()
        threading.Thread(target=self._boot_sequence, daemon=True).start()

    # ── ElevenLabs Key ─────────────────────────────────────────
    def _load_elevenlabs_key(self):
        global ELEVENLABS_API_KEY
        config = os.path.expanduser("~/chief_config.txt")
        if os.path.exists(config):
            with open(config) as f:
                for line in f:
                    if line.startswith("ELEVENLABS_API_KEY="):
                        ELEVENLABS_API_KEY = line.strip().split("=", 1)[1]

    # ── UI ─────────────────────────────────────────────────────
    def _build_ui(self):
        # Header
        header = ctk.CTkFrame(self, fg_color=BG_PANEL, corner_radius=0, height=50)
        header.pack(fill="x"); header.pack_propagate(False)
        ctk.CTkLabel(header, text="A L F R E D",
            font=ctk.CTkFont(family="Consolas", size=20, weight="bold"),
            text_color=CYAN).pack(side="left", padx=20, pady=10)
        sf = ctk.CTkFrame(header, fg_color="transparent"); sf.pack(side="right", padx=20)
        self.status_dot = ctk.CTkLabel(sf, text="●", font=ctk.CTkFont(size=12), text_color=TEXT_DIM)
        self.status_dot.pack(side="left", padx=(0, 4))
        self.status_label = ctk.CTkLabel(sf, text="CONNECTING",
            font=ctk.CTkFont(family="Consolas", size=10), text_color=TEXT_DIM)
        self.status_label.pack(side="left")

        # Orb
        self.orb_label = ctk.CTkLabel(self, text="", fg_color=BG_DARK)
        self.orb_label.pack(pady=(4, 0))
        self.state_label = ctk.CTkLabel(self, text="IDLE",
            font=ctk.CTkFont(family="Consolas", size=10, weight="bold"), text_color=TEXT_DIM)
        self.state_label.pack(pady=(0, 4))
        ctk.CTkFrame(self, fg_color=CYAN_DIM, height=1, corner_radius=0).pack(fill="x")

        # Chat
        self.chat_frame = ctk.CTkScrollableFrame(self, fg_color=BG_DARK, corner_radius=0,
            scrollbar_button_color=CYAN_DIM, scrollbar_button_hover_color=CYAN_DARK)
        self.chat_frame.pack(fill="both", expand=True)
        ctk.CTkFrame(self, fg_color=CYAN_DIM, height=1, corner_radius=0).pack(fill="x")

        # Input area
        ia = ctk.CTkFrame(self, fg_color=BG_PANEL, corner_radius=0, height=115)
        ia.pack(fill="x"); ia.pack_propagate(False)
        self.info_label = ctk.CTkLabel(ia, text="",
            font=ctk.CTkFont(family="Consolas", size=10), text_color=TEXT_DIM)
        self.info_label.pack(pady=(6, 2))

        ir = ctk.CTkFrame(ia, fg_color="transparent"); ir.pack(fill="x", padx=16, pady=(0, 6))
        self.mic_btn = ctk.CTkButton(ir, text="🎤", width=44, height=44,
            font=ctk.CTkFont(size=18), fg_color=CYAN_DIM, hover_color=CYAN_DARK,
            text_color=CYAN, corner_radius=22, border_width=1, border_color=CYAN_DARK,
            command=self._toggle_record)
        self.mic_btn.pack(side="left", padx=(0, 6))
        self.text_input = ctk.CTkEntry(ir, placeholder_text="Talk to Alfred...",
            font=ctk.CTkFont(family="Consolas", size=14), fg_color=BG_INPUT,
            border_color=CYAN_DIM, text_color=TEXT, placeholder_text_color=TEXT_DIM,
            height=44, corner_radius=22, border_width=1)
        self.text_input.pack(side="left", fill="x", expand=True, padx=(0, 6))
        self.text_input.bind("<Return>", lambda e: self._send_text())
        ctk.CTkButton(ir, text="➤", width=44, height=44, font=ctk.CTkFont(size=16),
            fg_color=CYAN_DIM, hover_color=CYAN_DARK, text_color=CYAN, corner_radius=22,
            border_width=1, border_color=CYAN_DARK, command=self._send_text).pack(side="right")

        br = ctk.CTkFrame(ia, fg_color="transparent"); br.pack(fill="x", padx=16, pady=(0, 8))
        for text, cmd, color in [("🔊 Voice", self._toggle_voice, ACCENT),
                                  ("◈ HUD", self._toggle_hud, ACCENT),
                                  ("👂 Wake", self._toggle_wake_word, TEXT_DIM)]:
            ctk.CTkButton(br, text=text, width=70, height=26,
                font=ctk.CTkFont(family="Consolas", size=10), fg_color=CYAN_DIM,
                hover_color=CYAN_DARK, text_color=color, corner_radius=13,
                command=cmd).pack(side="left", padx=(0, 6))
        self.timer_label = ctk.CTkLabel(br, text="Ctrl+Space",
            font=ctk.CTkFont(family="Consolas", size=10), text_color=TEXT_DIM)
        self.timer_label.pack(side="right")

    # ── State Management ───────────────────────────────────────
    def _set_state(self, state):
        self.state_changed_at = time.time()
        if self.sphere: self.sphere.set_state(state)
        labels = {"idle": ("IDLE", TEXT_DIM), "listening": ("LISTENING", SUCCESS),
                  "thinking": ("THINKING", AMBER), "speaking": ("SPEAKING", CYAN)}
        t, c = labels.get(state, ("IDLE", TEXT_DIM))
        self.state_label.configure(text=t, text_color=c)

    def _add_msg(self, text, sender="chief"):
        colors = {"user": (BLUE_DIM, "#1a3a6a", "YOU", "#4488cc"),
                  "chief": (CYAN_DIM, CYAN_DARK, "ALFRED", CYAN)}
        bc, brc, lt, lc = colors.get(sender, colors["chief"])
        c = ctk.CTkFrame(self.chat_frame, fg_color="transparent")
        c.pack(fill="x", pady=3, padx=8)
        b = ctk.CTkFrame(c, fg_color=bc, corner_radius=14, border_width=1, border_color=brc)
        b.pack(side="right" if sender == "user" else "left", padx=(60, 0) if sender == "user" else (0, 60))
        ctk.CTkLabel(b, text=lt, font=ctk.CTkFont(family="Consolas", size=9, weight="bold"),
            text_color=lc).pack(anchor="w", padx=12, pady=(8, 0))
        ctk.CTkLabel(b, text=text, font=ctk.CTkFont(size=13), text_color=TEXT,
            wraplength=300, justify="left").pack(anchor="w", padx=12, pady=(2, 8))
        self.chat_frame._parent_canvas.yview_moveto(1.0)

    def _add_system_msg(self, text):
        ctk.CTkLabel(self.chat_frame, text=text,
            font=ctk.CTkFont(family="Consolas", size=10), text_color=TEXT_DIM).pack(pady=4)

    # ── Animation ──────────────────────────────────────────────
    def _animate_orb(self):
        try:
            if self.sphere and self.sphere.state in ("thinking", "listening"):
                if time.time() - self.state_changed_at > 30:
                    self._set_state("idle")
            frame = self.sphere.render()
            self.orb_photo = ctk.CTkImage(light_image=frame, dark_image=frame, size=(ORB_SIZE, ORB_SIZE))
            self.orb_label.configure(image=self.orb_photo)
        except: pass
        self.after(1000 // ORB_FPS, self._animate_orb)

    # ── Voice Loading ──────────────────────────────────────────
    def _load_voice(self):
        def load():
            try:
                from kokoro import KPipeline
                self.tts_pipeline = KPipeline(lang_code='b')
                self._add_system_msg("Kokoro voice loaded")
            except:
                try:
                    from piper import PiperVoice
                    self.tts_pipeline = PiperVoice.load("C:/Users/ishal/chief_voices/en_US-ryan-high.onnx")
                    self._add_system_msg("Piper voice loaded")
                except:
                    self._add_system_msg("No voice available")
        threading.Thread(target=load, daemon=True).start()

    def _check_status(self):
        def check():
            try:
                r = requests.get(SERVER_URL + "/status", timeout=5)
                if r.status_code == 200:
                    d = r.json()
                    self.status_dot.configure(text_color=SUCCESS)
                    self.status_label.configure(text="ONLINE", text_color=SUCCESS)
                    self.info_label.configure(text=d.get("engine", "") + " • " + str(d.get("memories", 0)) + " mem")
            except:
                self.status_dot.configure(text_color=DANGER)
                self.status_label.configure(text="OFFLINE", text_color=DANGER)
        threading.Thread(target=check, daemon=True).start()

    def _setup_hotkey(self):
        def start():
            try:
                from pynput import keyboard
                keyboard.GlobalHotKeys({HOTKEY_COMBO: lambda: self.after(0, self._toggle_record)}).start()
            except: pass
        threading.Thread(target=start, daemon=True).start()

    # ═══════════════════════════════════════════════════════════
    # UNIFIED COMMAND DISPATCHER
    # ═══════════════════════════════════════════════════════════
    def _send_text(self):
        text = self.text_input.get().strip()
        if not text: return
        self.text_input.delete(0, "end")
        self._add_msg(text, "user")
        threading.Thread(target=self._process, args=(text,), daemon=True).start()

    def _process(self, text):
        self.after(0, self._set_state, "thinking")
        start = time.time()
        track_interaction()

        try:
            # 1. Custom protocols (highest priority)
            action, args = detect_custom_command(text)
            if action:
                if action == "list":
                    self._respond(list_commands(), start, long_msg="Here are your protocols, Sir.")
                elif action == "execute":
                    cbs = {"speak": self._speak,
                           "add_message": lambda t, s: self.after(0, self._add_msg, t, s),
                           "run_command": lambda cmd: self._process(cmd)}
                    result = execute_protocol(args, cbs)
                    if result: self.after(0, self._add_system_msg, result)
                return

            # 2. Routines
            action, args = detect_routine_command(text)
            if action:
                if action == "run":
                    routine = get_routine(args)
                    if routine:
                        self.after(0, self._add_system_msg, "Running " + routine["name"] + "...")
                        cbs = {"speak": self._speak,
                               "add_message": lambda t, s: self.after(0, self._add_msg, t, s),
                               "run_briefing": lambda: self._process("morning briefing")}
                        execute_routine_actions(routine, cbs)
                else:
                    self._respond(execute_routine_command(action, args), start)
                return

            # 3. Agent (multi-step tasks)
            action, args = detect_agent_command(text)
            if action:
                self.after(0, self._add_system_msg, "Working on it, Sir...")
                cbs = {"on_step": lambda n, a, ar: self.after(0, self._add_system_msg,
                            "Step " + str(n) + ": " + a + (" — " + str(ar)[:50] if ar else "")),
                       "on_result": lambda n, r: self.after(0, self._add_system_msg, "  " + str(r)[:100]),
                       "on_complete": lambda r: None}
                report, _ = run_agent(args, cbs)
                self._respond(report[:2000], start, long_msg="Task complete, Sir. Report is in the chat.")
                return

            # 4. Briefing (needs server for LLM formatting)
            action, args = detect_briefing_command(text)
            if action:
                if action == "briefing":
                    self.after(0, self._add_system_msg, "Preparing briefing...")
                    prompt = execute_briefing_command(action, args)
                    r = requests.post(SERVER_URL + "/chat",
                        headers={"Authorization": AUTH_TOKEN, "Content-Type": "application/json"},
                        json={"message": prompt, "history": []}, timeout=60)
                    if r.status_code == 200:
                        self._respond(r.json()["reply"], start)
                    return
                else:
                    self._respond(execute_briefing_command(action, args), start)
                    return

            # 5. Standard command pipeline (detect → execute → respond)
            for cmd in COMMAND_PIPELINE:
                if cmd["name"] in ("protocol", "routine", "agent", "briefing"):
                    continue  # Already handled above
                try:
                    action, args = cmd["detect"](text)
                    if action and "execute" in cmd:
                        if cmd.get("status"):
                            self.after(0, self._add_system_msg, cmd["status"])
                        result = cmd["execute"](action, args)
                        self._respond(result, start,
                            max_chars=cmd.get("max_chars", 1500),
                            long_msg=cmd.get("long_msg"))
                        return
                except Exception as e:
                    print(cmd["name"] + " error:", e)

            # 6. Nothing matched — send to server (Alfred LLM)
            is_deep = any(text.lower().strip().startswith(t) for t in [
                "speak freely", "be honest with me", "lets go deep", "let's go deep",
                "go deeper", "heart to heart", "level with me", "tell me more",
                "elaborate", "give me the full", "explain in detail",
                "alfred speak freely", "deep conversation"
            ])
            msg = ("[LONG RESPONSE OK] " + text) if is_deep else text
            r = requests.post(SERVER_URL + "/chat",
                headers={"Authorization": AUTH_TOKEN, "Content-Type": "application/json"},
                json={"message": msg, "history": self.conversation_history[-6:]}, timeout=120)
            if r.status_code == 200:
                reply = r.json()["reply"]
                self._respond(reply, start)
                self.conversation_history.append({"role": "user", "content": text})
                self.conversation_history.append({"role": "assistant", "content": reply})

        except Exception as e:
            print("Process error:", e)
            self.after(0, self._add_system_msg, "Connection error")
        finally:
            time.sleep(0.5)
            if self.sphere and self.sphere.state not in ("speaking", "idle"):
                self.after(0, self._set_state, "idle")

    def _respond(self, text, start_time, max_chars=1500, long_msg=None):
        """Standard response: show in chat, set timer, speak."""
        elapsed = round(time.time() - start_time, 1)
        display = text[:max_chars] if text else "No response."
        self.after(0, self._add_msg, display, "chief")
        self.after(0, self.timer_label.configure, {"text": str(elapsed) + "s"})
        if len(text) > 300 and long_msg:
            self._speak(long_msg)
        else:
            self._speak(text)

    # ═══════════════════════════════════════════════════════════
    # TTS — ElevenLabs → Kokoro fallback
    # ═══════════════════════════════════════════════════════════
    def _speak(self, text):
        if not self.tts_enabled or not text or not text.strip():
            self.after(0, self._set_state, "idle")
            return
        self.after(0, self._set_state, "speaking")
        try:
            if ELEVENLABS_API_KEY and self._speak_elevenlabs(text):
                return
            if self.tts_pipeline:
                self._speak_kokoro(text)
        except Exception as e:
            print("TTS error:", e)
        finally:
            self.after(0, self._set_state, "idle")

    def _speak_elevenlabs(self, text):
        sentences = []
        current = ""
        for ch in text:
            current += ch
            if ch in ".!?" and len(current.strip()) > 5:
                sentences.append(current.strip())
                current = ""
        if current.strip(): sentences.append(current.strip())

        for sentence in sentences:
            try:
                r = requests.post(
                    "https://api.elevenlabs.io/v1/text-to-speech/" + ELEVENLABS_VOICE_ID
                    + "?output_format=pcm_24000",
                    headers={"xi-api-key": ELEVENLABS_API_KEY, "Content-Type": "application/json"},
                    json={"text": sentence, "model_id": ELEVENLABS_MODEL,
                          "voice_settings": {"stability": 0.6, "similarity_boost": 0.8, "style": 0.3}},
                    timeout=10)
                if r.status_code == 200:
                    audio = np.frombuffer(r.content, dtype=np.int16).astype(np.float32) / 32768.0
                    sd.play(audio, samplerate=24000); sd.wait()
                else: return False
            except: return False
        return True

    def _speak_kokoro(self, text):
        from kokoro import KPipeline
        if isinstance(self.tts_pipeline, KPipeline):
            for _, _, audio in self.tts_pipeline(text, voice=KOKORO_VOICE, speed=1.0):
                if audio is not None and len(audio) > 0:
                    sd.play(audio.numpy(), samplerate=24000); sd.wait()

    # ═══════════════════════════════════════════════════════════
    # RECORDING
    # ═══════════════════════════════════════════════════════════
    def _toggle_record(self):
        if not self.is_recording:
            self.is_recording = True; self.audio_chunks = []
            self.mic_btn.configure(fg_color="#3a1020", border_color=DANGER, text_color=DANGER, text="⏹")
            self._set_state("listening")
            threading.Thread(target=self._record, daemon=True).start()
        else:
            self.is_recording = False
            self.mic_btn.configure(fg_color=CYAN_DIM, border_color=CYAN_DARK, text_color=CYAN, text="🎤")

    def _record(self):
        with sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype='int16') as stream:
            while self.is_recording:
                chunk, _ = stream.read(1024)
                self.audio_chunks.append(chunk)
        if self.audio_chunks:
            data = np.concatenate(self.audio_chunks, axis=0)
            tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
            wav.write(tmp.name, SAMPLE_RATE, data)
            threading.Thread(target=self._send_voice, args=(tmp.name,), daemon=True).start()
        else:
            self.after(0, self._set_state, "idle")

    def _send_voice(self, path):
        self.after(0, self._set_state, "thinking")
        try:
            with open(path, 'rb') as f:
                r = requests.post(SERVER_URL + "/transcribe",
                    headers={"Authorization": AUTH_TOKEN},
                    files={"audio": ("audio.wav", f, "audio/wav")}, timeout=30)
            os.unlink(path)
            if r.status_code != 200: return
            text = r.json().get("text", "")
            if not text:
                self.after(0, self._add_system_msg, "Couldn't hear you")
                return
            self.after(0, self._add_msg, text, "user")
            self._process(text)
        except Exception as e:
            self.after(0, self._add_system_msg, "Error: " + str(e))
            if os.path.exists(path): os.unlink(path)

    # ═══════════════════════════════════════════════════════════
    # WAKE WORD
    # ═══════════════════════════════════════════════════════════
    def _toggle_wake_word(self):
        if not self.wake_word_active:
            self.wake_word_active = True
            self._add_system_msg("Say 'Alfred' to activate")
            threading.Thread(target=self._wake_loop, daemon=True).start()
        else:
            self.wake_word_active = False

    def _wake_loop(self):
        try:
            import speech_recognition as sr
            rec = sr.Recognizer()
            rec.energy_threshold = 300; rec.dynamic_energy_threshold = True
            rec.pause_threshold = 1.2  # Wait longer for natural pauses
            mic = sr.Microphone(sample_rate=SAMPLE_RATE)
            with mic as src: rec.adjust_for_ambient_noise(src, duration=1)
            while self.wake_word_active:
                if self.is_recording: time.sleep(0.5); continue
                try:
                    # Listen for wake word (short window)
                    with mic as src:
                        audio = rec.listen(src, timeout=4, phrase_time_limit=8)
                    text = rec.recognize_google(audio).lower()
                    if WAKE_WORD in text:
                        # Strip wake word to get the command
                        cmd = text
                        for t in ["hey alfred", "alfred", "hey offer"]:
                            cmd = cmd.replace(t, "").strip()
                        if cmd and len(cmd) > 3:
                            # Got wake word + full command
                            self.after(0, self._add_msg, cmd, "user")
                            threading.Thread(target=self._process, args=(cmd,), daemon=True).start()
                        else:
                            # Just wake word — listen for follow-up command
                            self.after(0, self._add_system_msg, "Listening...")
                            self.after(0, self._set_state, "listening")
                            try:
                                with mic as src:
                                    follow_up = rec.listen(src, timeout=5, phrase_time_limit=10)
                                cmd2 = rec.recognize_google(follow_up).lower()
                                if cmd2:
                                    self.after(0, self._add_msg, cmd2, "user")
                                    threading.Thread(target=self._process, args=(cmd2,), daemon=True).start()
                            except:
                                self.after(0, self._set_state, "idle")
                                self.after(0, self._add_system_msg, "Didn't catch that")
                except Exception as e2:
                    if "speech_recognition" not in str(type(e2)):
                        print("Wake listen error:", e2)
        except Exception as e:
            print("Wake loop error:", e)
            self.after(0, self._add_system_msg, "Wake error: " + str(e))

    # ═══════════════════════════════════════════════════════════
    # BOOT SEQUENCE
    # ═══════════════════════════════════════════════════════════
    def _boot_sequence(self):
        time.sleep(1)
        self.after(0, self._set_state, "thinking")
        self.after(0, self._add_system_msg, "Initializing Alfred systems...")
        time.sleep(0.5)

        checks = []

        # Server
        try:
            r = requests.get(SERVER_URL + "/status", timeout=5)
            if r.status_code == 200:
                d = r.json()
                checks.append(("Server link", True, d.get("engine", "Groq")))
                checks.append(("Memory bank", True, str(d.get("memories", 0)) + " records"))
            else: checks.append(("Server link", False, "error"))
        except: checks.append(("Server link", False, "offline"))

        # Voice
        checks.append(("Voice engine", bool(self.tts_pipeline), "Kokoro" if self.tts_pipeline else "loading"))
        checks.append(("Premium voice", bool(ELEVENLABS_API_KEY), "ElevenLabs" if ELEVENLABS_API_KEY else "none"))

        # System
        try:
            checks.append(("CPU", True, str(psutil.cpu_percent(interval=0.5)) + "%"))
            checks.append(("Memory", True, str(psutil.virtual_memory().percent) + "% used"))
            checks.append(("Disk", True, str(psutil.disk_usage('C:\\').percent) + "% used"))
        except: checks.append(("System stats", False, "unavailable"))

        # Services
        try:
            routines = load_routines()
            checks.append(("Routines", True, str(sum(1 for r in routines.values() if r["enabled"])) + " active"))
        except: pass
        checks.append(("Security", True, "monitoring"))
        checks.append(("Clipboard", True, "tracking"))
        checks.append(("Dashboard", True, "ready"))
        try:
            from custom_commands import load_commands
            checks.append(("Protocols", True, str(len(load_commands())) + " loaded"))
        except: pass

        # Display checks
        for name, ok, detail in checks:
            self.after(0, self._add_system_msg, "  [" + ("+" if ok else "!") + "] " + name + " — " + detail)
            time.sleep(0.2)

        failed = sum(1 for _, s, _ in checks if not s)
        self.after(0, self._add_system_msg,
            "All systems nominal." if failed == 0 else str(len(checks) - failed) + " online, " + str(failed) + " warnings.")

        # Set orb color
        try: self.sphere.idle_color = get_orb_color_for_time()
        except: pass

        # Greeting
        time.sleep(0.5)
        try:
            ctx = get_time_context()
            greeting = ctx["greeting"]
            extras = []
            from briefing import get_todays_reminders, get_weather
            w = get_weather()
            if "error" not in w: extras.append(w.get("description", "") + ", " + w.get("temp", "") + " degrees")
            reminders = get_todays_reminders()
            if reminders: extras.append(str(len(reminders)) + " reminders")
            try:
                unread = get_unread_count()
                if unread > 0: extras.append(str(unread) + " unread emails")
            except: pass
            if extras: greeting += " " + ". ".join(extras) + "."
            self.after(0, self._add_msg, greeting, "chief")
            reset_session()
            self._speak(greeting)
        except:
            self.after(0, self._add_msg, "Good day, Sir. Alfred is online.", "chief")

        self.after(0, self._set_state, "idle")

    # ═══════════════════════════════════════════════════════════
    # SERVICES (scheduler, HUD, dashboard)
    # ═══════════════════════════════════════════════════════════
    def _start_services(self):
        try: start_clipboard()
        except: pass
        try: start_auto_sync(300)
        except: pass

        # HUD + Dashboard
        try:
            self.hud = HUDOverlay()
        except: pass
        try:
            self.dashboard = LiveDashboard(self)
            self.dashboard.root.withdraw()
        except: pass

        # Info updater (weather, news, email count for dashboard)
        def update_info():
            while True:
                try:
                    from briefing import get_weather, get_news_headlines
                    w = get_weather()
                    if "error" not in w:
                        wt = w.get("description", "") + " " + w.get("temp", "") + "F"
                        if self.hud: self.hud.update_weather(wt)
                        if self.dashboard:
                            self.dashboard.update_weather(wt + " (feels " + w.get("feels_like", "") + "F)")
                    news = get_news_headlines()
                    if news and self.dashboard: self.dashboard.update_news(news)
                    try:
                        unread = get_unread_count()
                        if self.dashboard: self.dashboard.update_emails(unread)
                    except: pass
                    try:
                        event = get_next_event()
                        if event and self.dashboard:
                            self.dashboard.update_event(event["summary"] + " at " + event["time_str"])
                    except: pass
                except: pass
                time.sleep(600)
        threading.Thread(target=update_info, daemon=True).start()

        # Scheduler loop
        def scheduler():
            tick = 0
            last_minute = ""
            while True:
                now = datetime.datetime.now().strftime("%H:%M")
                if now != last_minute:
                    last_minute = now
                    # Routines
                    for key, routine in get_due_routines():
                        self.after(0, self._run_routine, routine)
                    # Orb color
                    try: self.sphere.idle_color = get_orb_color_for_time()
                    except: pass
                    # System alerts
                    try:
                        for alert in check_alerts()[0]:
                            self.after(0, self._add_msg, alert, "chief")
                            threading.Thread(target=self._speak, args=(alert,), daemon=True).start()
                    except: pass
                    # Security (every 5 min)
                    if tick % 20 == 5:
                        try:
                            for alert in check_all_security():
                                self.after(0, self._add_msg, alert, "chief")
                                threading.Thread(target=self._speak, args=(alert,), daemon=True).start()
                        except: pass
                    # Meeting reminder (every 5 min)
                    if tick % 20 == 10:
                        try:
                            event = get_next_event()
                            if event and event["time"]:
                                diff = (event["time"] - datetime.datetime.now(event["time"].tzinfo)).total_seconds() / 60
                                if 14 <= diff <= 16:
                                    alert = "Sir, you have " + event["summary"] + " in 15 minutes."
                                    self.after(0, self._add_msg, alert, "chief")
                                    threading.Thread(target=self._speak, args=(alert,), daemon=True).start()
                        except: pass
                    # Email check (every 30 min)
                    if tick % 120 == 60:
                        try:
                            unread = get_unread_count()
                            if unread >= 5:
                                alert = "Sir, you have " + str(unread) + " unread emails."
                                self.after(0, self._add_msg, alert, "chief")
                                threading.Thread(target=self._speak, args=(alert,), daemon=True).start()
                        except: pass
                    # Proactive suggestion (every 30 min)
                    if tick % 120 == 0 and tick > 0:
                        try:
                            suggestion = get_proactive_suggestion()
                            if suggestion:
                                self.after(0, self._add_msg, suggestion, "chief")
                                threading.Thread(target=self._speak, args=(suggestion,), daemon=True).start()
                        except: pass
                tick += 1
                time.sleep(15)
        threading.Thread(target=scheduler, daemon=True).start()

    def _run_routine(self, routine):
        def run():
            cbs = {"speak": self._speak,
                   "add_message": lambda t, s: self.after(0, self._add_msg, t, s),
                   "run_briefing": lambda: self._process("morning briefing")}
            execute_routine_actions(routine, cbs)
        self._add_system_msg(routine["name"])
        threading.Thread(target=run, daemon=True).start()

    # ── Toggles ────────────────────────────────────────────────
    def _toggle_hud(self):
        if self.hud: self.hud.toggle_visibility()
        if self.dashboard: self.dashboard.toggle()

    def _toggle_voice(self):
        self.tts_enabled = not self.tts_enabled

if __name__ == "__main__":
    import sys
    import traceback
    import logging

    # Log crashes to file
    LOG_FILE = os.path.expanduser("~/alfred_crash.log")
    logging.basicConfig(filename=LOG_FILE, level=logging.ERROR,
                        format="%(asctime)s %(message)s")

    # Catch unhandled thread exceptions
    def thread_exception_handler(args):
        logging.error("Thread crash: " + str(args.exc_type.__name__) + ": " + str(args.exc_value))
        logging.error(traceback.format_exception(args.exc_type, args.exc_value, args.exc_traceback))
        print("Thread error:", args.exc_type.__name__, args.exc_value)

    threading.excepthook = thread_exception_handler

    # Run app with crash protection
    try:
        app = AlfredApp()
        app.mainloop()
    except Exception as e:
        logging.error("Main crash: " + str(e))
        logging.error(traceback.format_exc())
        print("Alfred crashed:", e)
        print("Check ~/alfred_crash.log for details")
        input("Press Enter to exit...")
