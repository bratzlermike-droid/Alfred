"""
Alfred's Live Dashboard
Real-time system stats, weather, news, and upcoming events.
Embedded panel in the desktop app.
"""
import tkinter as tk
import threading
import time
import datetime
import psutil
from collections import deque

# Keep history for mini graphs
_cpu_history = deque(maxlen=30)
_ram_history = deque(maxlen=30)


class LiveDashboard:
    """Full-featured dashboard window with live stats and info."""

    def __init__(self, parent=None):
        self.root = tk.Toplevel(parent) if parent else tk.Tk()
        self.root.title("Alfred Dashboard")
        self.root.geometry("340x520")
        self.root.configure(bg='#060a10')
        self.root.attributes('-topmost', True)
        self.root.resizable(False, False)

        # Position: left side of screen
        self.root.geometry("+10+80")

        self.visible = True
        self._build()
        self._update_loop()

        # External data (updated by main app)
        self._weather_text = ""
        self._news_items = []
        self._next_event = ""
        self._unread_emails = 0

    def _build(self):
        bg = '#060a10'
        panel = '#0a1020'
        cyan = '#00d0e0'
        dim = '#3a5a6a'
        text = '#8ab0c0'
        border = '#0a3040'

        # Title bar
        title_frame = tk.Frame(self.root, bg=panel)
        title_frame.pack(fill='x')
        tk.Label(title_frame, text=" A L F R E D   D A S H B O A R D",
                 font=("Consolas", 9, "bold"), fg=cyan, bg=panel).pack(side='left', padx=8, pady=6)
        tk.Button(title_frame, text="✕", font=("Consolas", 8), fg=dim, bg=panel,
                  bd=0, command=self.toggle, activebackground=panel).pack(side='right', padx=8)

        # Main container
        main = tk.Frame(self.root, bg=bg, padx=12, pady=8)
        main.pack(fill='both', expand=True)

        # ── Clock Section ──
        self.clock_label = tk.Label(main, text="", font=("Consolas", 28, "bold"),
                                     fg=cyan, bg=bg)
        self.clock_label.pack(anchor='w')
        self.date_label = tk.Label(main, text="", font=("Consolas", 10),
                                    fg=dim, bg=bg)
        self.date_label.pack(anchor='w')

        self._separator(main)

        # ── System Stats ──
        tk.Label(main, text="SYSTEM", font=("Consolas", 8, "bold"),
                 fg=dim, bg=bg).pack(anchor='w')

        stats_frame = tk.Frame(main, bg=bg)
        stats_frame.pack(fill='x', pady=(2, 0))

        # CPU
        cpu_frame = tk.Frame(stats_frame, bg=bg)
        cpu_frame.pack(fill='x')
        tk.Label(cpu_frame, text="CPU", font=("Consolas", 9), fg=dim, bg=bg, width=5, anchor='w').pack(side='left')
        self.cpu_bar = tk.Canvas(cpu_frame, width=180, height=12, bg='#0a1428', highlightthickness=0)
        self.cpu_bar.pack(side='left', padx=(4, 4))
        self.cpu_val = tk.Label(cpu_frame, text="0%", font=("Consolas", 9, "bold"), fg=text, bg=bg, width=5, anchor='e')
        self.cpu_val.pack(side='right')

        # RAM
        ram_frame = tk.Frame(stats_frame, bg=bg)
        ram_frame.pack(fill='x', pady=(2, 0))
        tk.Label(ram_frame, text="RAM", font=("Consolas", 9), fg=dim, bg=bg, width=5, anchor='w').pack(side='left')
        self.ram_bar = tk.Canvas(ram_frame, width=180, height=12, bg='#0a1428', highlightthickness=0)
        self.ram_bar.pack(side='left', padx=(4, 4))
        self.ram_val = tk.Label(ram_frame, text="0%", font=("Consolas", 9, "bold"), fg=text, bg=bg, width=5, anchor='e')
        self.ram_val.pack(side='right')

        # Disk
        disk_frame = tk.Frame(stats_frame, bg=bg)
        disk_frame.pack(fill='x', pady=(2, 0))
        tk.Label(disk_frame, text="DISK", font=("Consolas", 9), fg=dim, bg=bg, width=5, anchor='w').pack(side='left')
        self.disk_bar = tk.Canvas(disk_frame, width=180, height=12, bg='#0a1428', highlightthickness=0)
        self.disk_bar.pack(side='left', padx=(4, 4))
        self.disk_val = tk.Label(disk_frame, text="0%", font=("Consolas", 9, "bold"), fg=text, bg=bg, width=5, anchor='e')
        self.disk_val.pack(side='right')

        # Network
        net_frame = tk.Frame(stats_frame, bg=bg)
        net_frame.pack(fill='x', pady=(2, 0))
        tk.Label(net_frame, text="NET", font=("Consolas", 9), fg=dim, bg=bg, width=5, anchor='w').pack(side='left')
        self.net_label = tk.Label(net_frame, text="", font=("Consolas", 9), fg=text, bg=bg)
        self.net_label.pack(side='left', padx=(4, 0))

        self._separator(main)

        # ── Weather ──
        tk.Label(main, text="WEATHER", font=("Consolas", 8, "bold"),
                 fg=dim, bg=bg).pack(anchor='w')
        self.weather_label = tk.Label(main, text="Loading...", font=("Consolas", 9),
                                       fg=text, bg=bg, anchor='w', wraplength=300, justify='left')
        self.weather_label.pack(anchor='w')

        self._separator(main)

        # ── Next Event ──
        tk.Label(main, text="NEXT EVENT", font=("Consolas", 8, "bold"),
                 fg=dim, bg=bg).pack(anchor='w')
        self.event_label = tk.Label(main, text="None", font=("Consolas", 9),
                                     fg=text, bg=bg, anchor='w', wraplength=300, justify='left')
        self.event_label.pack(anchor='w')

        self._separator(main)

        # ── Quick Info ──
        tk.Label(main, text="STATUS", font=("Consolas", 8, "bold"),
                 fg=dim, bg=bg).pack(anchor='w')
        self.status_frame = tk.Frame(main, bg=bg)
        self.status_frame.pack(fill='x')

        self.email_label = tk.Label(self.status_frame, text="Email: —",
                                     font=("Consolas", 9), fg=text, bg=bg)
        self.email_label.pack(anchor='w')
        self.uptime_label = tk.Label(self.status_frame, text="Uptime: —",
                                      font=("Consolas", 9), fg=text, bg=bg)
        self.uptime_label.pack(anchor='w')

        self._separator(main)

        # ── News Ticker ──
        tk.Label(main, text="HEADLINES", font=("Consolas", 8, "bold"),
                 fg=dim, bg=bg).pack(anchor='w')
        self.news_label = tk.Label(main, text="Loading...", font=("Consolas", 8),
                                    fg=dim, bg=bg, anchor='w', wraplength=300, justify='left')
        self.news_label.pack(anchor='w')

    def _separator(self, parent):
        tk.Frame(parent, bg='#0a3040', height=1).pack(fill='x', pady=6)

    def _color_for_pct(self, pct):
        if pct > 90: return '#ff3050'
        if pct > 70: return '#ffaa00'
        return '#00d0e0'

    def _draw_bar(self, canvas, pct):
        canvas.delete('all')
        color = self._color_for_pct(pct)
        width = int(180 * pct / 100)
        canvas.create_rectangle(0, 0, width, 12, fill=color, outline='')

    def toggle(self, event=None):
        if self.visible:
            self.root.withdraw()
            self.visible = False
        else:
            self.root.deiconify()
            self.visible = True

    def update_weather(self, text):
        try:
            self.weather_label.config(text=text)
        except:
            pass

    def update_news(self, items):
        try:
            self._news_items = items[:4]
            text = "\n".join("• " + n[:60] for n in self._news_items)
            self.news_label.config(text=text if text else "No news available")
        except:
            pass

    def update_event(self, text):
        try:
            self.event_label.config(text=text)
        except:
            pass

    def update_emails(self, count):
        try:
            self.email_label.config(text="Email: " + str(count) + " unread")
        except:
            pass

    def _update_loop(self):
        try:
            now = datetime.datetime.now()
            self.clock_label.config(text=now.strftime("%I:%M:%S %p"))
            self.date_label.config(text=now.strftime("%A, %B %d, %Y"))

            # System stats
            cpu = psutil.cpu_percent(interval=0)
            ram = psutil.virtual_memory().percent
            disk = psutil.disk_usage('C:\\').percent
            net = psutil.net_io_counters()

            self._draw_bar(self.cpu_bar, cpu)
            self.cpu_val.config(text=str(cpu) + "%", fg=self._color_for_pct(cpu))
            self._draw_bar(self.ram_bar, ram)
            self.ram_val.config(text=str(ram) + "%", fg=self._color_for_pct(ram))
            self._draw_bar(self.disk_bar, disk)
            self.disk_val.config(text=str(disk) + "%", fg=self._color_for_pct(disk))

            sent = round(net.bytes_sent / (1024**2))
            recv = round(net.bytes_recv / (1024**2))
            self.net_label.config(text="↑ " + str(sent) + " MB  ↓ " + str(recv) + " MB")

            # Uptime
            boot = datetime.datetime.fromtimestamp(psutil.boot_time())
            uptime = str(now - boot).split('.')[0]
            self.uptime_label.config(text="Uptime: " + uptime)

        except:
            pass

        self.root.after(1000, self._update_loop)
