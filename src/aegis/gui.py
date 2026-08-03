import math
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from src.aegis.mission import (
    MissionController,
    MissionFrame,
    MissionMode,
)
from src.aegis.scenario_simulator import ContactSnapshot


class AegisApp:
    BG = "#071018"
    PANEL = "#0c1822"
    PANEL_2 = "#101f2b"
    BORDER = "#28404d"
    TEXT = "#dce8ed"
    MUTED = "#78909c"
    CYAN = "#62c7e8"
    GREEN = "#72dc78"
    AMBER = "#f0b83f"
    RED = "#ef5b5b"
    PURPLE = "#a980e8"

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.controller = MissionController()
        self._auto_job: str | None = None
        self._auto_running = False
        self._contacts_by_row: dict[str, ContactSnapshot] = {}

        root.title("Project Aegis - Situational Awareness")
        root.geometry("1400x820")
        root.minsize(1100, 680)
        root.configure(bg=self.BG)

        self._configure_styles()
        self._build_dashboard()
        self._show_ready_state()

    def _configure_styles(self) -> None:
        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure("Bg.TFrame", background=self.BG)
        style.configure("Panel.TFrame", background=self.PANEL)
        style.configure("Panel2.TFrame", background=self.PANEL_2)
        style.configure(
            "Title.TLabel",
            background=self.BG,
            foreground=self.TEXT,
            font=("Segoe UI Semibold", 20),
        )
        style.configure(
            "Section.TLabel",
            background=self.PANEL,
            foreground=self.CYAN,
            font=("Segoe UI Semibold", 9),
        )
        style.configure(
            "Text.TLabel",
            background=self.PANEL,
            foreground=self.TEXT,
            font=("Segoe UI", 9),
        )
        style.configure(
            "Muted.TLabel",
            background=self.PANEL,
            foreground=self.MUTED,
            font=("Segoe UI", 8),
        )
        style.configure(
            "Aegis.TButton",
            background=self.PANEL_2,
            foreground=self.TEXT,
            bordercolor=self.BORDER,
            padding=(12, 7),
            font=("Segoe UI Semibold", 9),
        )
        style.map("Aegis.TButton", background=[("active", "#183344")])
        style.configure(
            "Accent.TButton",
            background="#17475b",
            foreground=self.CYAN,
            bordercolor=self.CYAN,
            padding=(12, 7),
            font=("Segoe UI Semibold", 9),
        )
        style.map("Accent.TButton", background=[("active", "#205f78")])
        style.configure(
            "Treeview",
            background=self.PANEL,
            fieldbackground=self.PANEL,
            foreground=self.TEXT,
            rowheight=30,
            borderwidth=0,
            font=("Consolas", 9),
        )
        style.configure(
            "Treeview.Heading",
            background=self.PANEL_2,
            foreground=self.MUTED,
            borderwidth=0,
            padding=(5, 7),
            font=("Segoe UI Semibold", 8),
        )
        style.map("Treeview", background=[("selected", "#17475b")])

    def _build_dashboard(self) -> None:
        shell = ttk.Frame(self.root, style="Bg.TFrame", padding=(16, 12, 16, 8))
        shell.pack(fill="both", expand=True)
        self._build_header(shell)

        body = ttk.Frame(shell, style="Bg.TFrame")
        body.pack(fill="both", expand=True, pady=(10, 8))
        body.columnconfigure(0, weight=18, minsize=190)
        body.columnconfigure(1, weight=52, minsize=500)
        body.columnconfigure(2, weight=30, minsize=320)
        body.rowconfigure(0, weight=1)

        self._build_status_column(body)
        self._build_center_column(body)
        self._build_analysis_column(body)
        self._build_footer(shell)

    def _build_header(self, parent: ttk.Frame) -> None:
        header = ttk.Frame(parent, style="Bg.TFrame")
        header.pack(fill="x")
        title_group = ttk.Frame(header, style="Bg.TFrame")
        title_group.pack(side="left")
        ttk.Label(title_group, text="AEGIS", style="Title.TLabel").pack(
            side="left"
        )
        self.unit_label = tk.Label(
            title_group,
            text="  UNIT 01 / READY",
            bg=self.BG,
            fg=self.MUTED,
            font=("Consolas", 10),
        )
        self.unit_label.pack(side="left", pady=(7, 0))

        controls = ttk.Frame(header, style="Bg.TFrame")
        controls.pack(side="right")
        self.mode_label = tk.Label(
            controls,
            text="●  OFFLINE / SECURE",
            bg=self.BG,
            fg=self.GREEN,
            font=("Consolas", 9),
        )
        self.mode_label.pack(side="left", padx=(0, 18))
        ttk.Button(
            controls,
            text="START SIM",
            style="Aegis.TButton",
            command=self.start_simulation,
        ).pack(side="left", padx=(0, 6))
        ttk.Button(
            controls,
            text="RECORD",
            style="Aegis.TButton",
            command=self.start_recording,
        ).pack(side="left", padx=(0, 6))
        ttk.Button(
            controls,
            text="OPEN",
            style="Aegis.TButton",
            command=self.open_recording,
        ).pack(side="left", padx=(0, 6))
        ttk.Button(
            controls,
            text="STOP",
            style="Aegis.TButton",
            command=self.stop_mission,
        ).pack(side="left", padx=(0, 6))
        self.auto_button = ttk.Button(
            controls,
            text="PLAY",
            style="Aegis.TButton",
            command=self.toggle_auto,
        )
        self.auto_button.pack(side="left", padx=(0, 6))
        self.next_button = ttk.Button(
            controls,
            text="NEXT",
            style="Accent.TButton",
            command=self.next_scan,
        )
        self.next_button.pack(side="left")

    def _build_status_column(self, parent: ttk.Frame) -> None:
        column = ttk.Frame(parent, style="Panel.TFrame", padding=12)
        column.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        self._section_title(column, "STATUS OVERVIEW")
        self.status_values: dict[str, tk.Label] = {}
        for name, value, color in (
            ("System Status", "ONLINE", self.GREEN),
            ("Input Source", "SIMULATOR", self.CYAN),
            ("RF Activity", "0 ACTIVE", self.AMBER),
            ("Alerts", "0 NEW", self.RED),
            ("GPS", "SIMULATED", self.GREEN),
            ("Scan", "0 / 0", self.TEXT),
        ):
            row = tk.Frame(column, bg=self.PANEL)
            row.pack(fill="x", pady=5)
            tk.Label(
                row, text=name, bg=self.PANEL, fg=self.MUTED,
                font=("Segoe UI", 8),
            ).pack(side="left")
            label = tk.Label(
                row, text=value, bg=self.PANEL, fg=color,
                font=("Consolas", 8),
            )
            label.pack(side="right")
            self.status_values[name] = label

        self._divider(column)
        self._section_title(column, "SENSOR STATUS")
        for sensor, state in (
            ("RF Scanner", "SIM"),
            ("Direction Finder", "STANDBY"),
            ("Camera System", "STANDBY"),
            ("Acoustic Sensor", "STANDBY"),
            ("GPS Receiver", "SIM"),
        ):
            row = tk.Frame(column, bg=self.PANEL)
            row.pack(fill="x", pady=5)
            tk.Label(
                row, text=sensor, bg=self.PANEL, fg=self.TEXT,
                font=("Segoe UI", 8),
            ).pack(side="left")
            active = state == "SIM"
            tk.Label(
                row,
                text=f"● {state}",
                bg=self.PANEL,
                fg=self.GREEN if active else self.MUTED,
                font=("Consolas", 7),
            ).pack(side="right")

        self._divider(column)
        self._section_title(column, "SYSTEM HEALTH")
        for label, value in (("CPU", "--"), ("MEMORY", "--"), ("TEMP", "--")):
            row = tk.Frame(column, bg=self.PANEL)
            row.pack(fill="x", pady=4)
            tk.Label(row, text=label, bg=self.PANEL, fg=self.MUTED,
                     font=("Consolas", 8)).pack(side="left")
            tk.Label(row, text=value, bg=self.PANEL, fg=self.CYAN,
                     font=("Consolas", 8)).pack(side="right")

    def _build_center_column(self, parent: ttk.Frame) -> None:
        column = ttk.Frame(parent, style="Bg.TFrame")
        column.grid(row=0, column=1, sticky="nsew", padx=(0, 8))
        column.rowconfigure(0, weight=54)
        column.rowconfigure(1, weight=46)
        column.columnconfigure(0, weight=1)

        situational = ttk.Frame(column, style="Panel.TFrame", padding=10)
        situational.grid(row=0, column=0, sticky="nsew", pady=(0, 8))
        self._section_title(situational, "LIVE SITUATIONAL DISPLAY")
        self.map_canvas = tk.Canvas(
            situational, bg="#09151a", highlightthickness=1,
            highlightbackground=self.BORDER,
        )
        self.map_canvas.pack(fill="both", expand=True, pady=(7, 0))
        self.map_canvas.bind("<Configure>", lambda _: self._draw_map())

        contacts = ttk.Frame(column, style="Panel.TFrame", padding=10)
        contacts.grid(row=1, column=0, sticky="nsew")
        self._section_title(contacts, "ACTIVE CONTACTS")
        columns = ("id", "frequency", "confidence", "state", "seen", "missed")
        self.contact_table = ttk.Treeview(
            contacts, columns=columns, show="headings", selectmode="browse",
        )
        config = (
            ("id", "ID", 48),
            ("frequency", "FREQUENCY", 125),
            ("confidence", "CONFIDENCE", 95),
            ("state", "STATE", 95),
            ("seen", "SEEN", 58),
            ("missed", "MISSED", 62),
        )
        for key, title, width in config:
            self.contact_table.heading(key, text=title)
            self.contact_table.column(key, width=width, anchor="center")
        self.contact_table.tag_configure("confirmed", foreground=self.GREEN)
        self.contact_table.tag_configure("tentative", foreground=self.AMBER)
        self.contact_table.tag_configure("fading", foreground=self.RED)
        self.contact_table.pack(fill="both", expand=True, pady=(7, 0))
        self.contact_table.bind("<<TreeviewSelect>>", self._on_contact_selected)

    def _build_analysis_column(self, parent: ttk.Frame) -> None:
        column = ttk.Frame(parent, style="Bg.TFrame")
        column.grid(row=0, column=2, sticky="nsew")
        column.rowconfigure(0, weight=42)
        column.rowconfigure(1, weight=58)
        column.columnconfigure(0, weight=1)

        signal = ttk.Frame(column, style="Panel.TFrame", padding=10)
        signal.grid(row=0, column=0, sticky="nsew", pady=(0, 8))
        self._section_title(signal, "SIGNAL ANALYSIS")
        self.signal_canvas = tk.Canvas(
            signal, bg="#07151c", highlightthickness=1,
            highlightbackground=self.BORDER,
        )
        self.signal_canvas.pack(fill="both", expand=True, pady=(7, 0))
        self.signal_canvas.bind("<Configure>", lambda _: self._draw_signal())

        detail = ttk.Frame(column, style="Panel.TFrame", padding=12)
        detail.grid(row=1, column=0, sticky="nsew")
        self._section_title(detail, "CONTACT DETAILS")
        self.detail_title = tk.Label(
            detail, text="NO CONTACT SELECTED", bg=self.PANEL, fg=self.MUTED,
            font=("Segoe UI Semibold", 13), anchor="w",
        )
        self.detail_title.pack(fill="x", pady=(10, 3))
        self.detail_state = tk.Label(
            detail, text="Advance the simulator to acquire contacts.",
            bg=self.PANEL, fg=self.MUTED, font=("Segoe UI", 8), anchor="w",
        )
        self.detail_state.pack(fill="x")
        self.confidence_canvas = tk.Canvas(
            detail, height=12, bg=self.PANEL_2, highlightthickness=0,
        )
        self.confidence_canvas.pack(fill="x", pady=(12, 14))
        self.detail_fields: dict[str, tk.Label] = {}
        for name in (
            "Center Frequency", "Bandwidth", "Peak Power",
            "Detections", "Missed Scans", "Aircraft ID",
            "Distance", "Bearing", "Heading", "Altitude",
        ):
            row = tk.Frame(detail, bg=self.PANEL)
            row.pack(fill="x", pady=4)
            tk.Label(
                row, text=name, bg=self.PANEL, fg=self.MUTED,
                font=("Segoe UI", 8),
            ).pack(side="left")
            value = tk.Label(
                row, text="--", bg=self.PANEL, fg=self.TEXT,
                font=("Consolas", 8),
            )
            value.pack(side="right")
            self.detail_fields[name] = value
        self.classification_note = tk.Label(
            detail,
            text="Remote ID trajectory is simulated and not a live observation",
            bg=self.PANEL,
            fg=self.MUTED,
            font=("Segoe UI", 8, "italic"),
            anchor="w",
        )
        self.classification_note.pack(fill="x", side="bottom")

    def _build_footer(self, parent: ttk.Frame) -> None:
        footer = ttk.Frame(parent, style="Panel.TFrame", padding=(12, 7))
        footer.pack(fill="x")
        for index, name in enumerate(
            ("DASHBOARD", "MAP", "CONTACTS", "SIGNALS", "RECORDINGS", "SETTINGS")
        ):
            tk.Label(
                footer,
                text=name,
                bg=self.PANEL,
                fg=self.CYAN if index == 0 else self.MUTED,
                font=("Consolas", 8, "bold" if index == 0 else "normal"),
                padx=18,
            ).pack(side="left")
        self.footer_status = tk.Label(
            footer, text="SIMULATOR READY", bg=self.PANEL, fg=self.GREEN,
            font=("Consolas", 8),
        )
        self.footer_status.pack(side="right")

    def _section_title(self, parent: ttk.Frame, text: str) -> None:
        ttk.Label(parent, text=text, style="Section.TLabel").pack(anchor="w")

    def _divider(self, parent: ttk.Frame) -> None:
        tk.Frame(parent, height=1, bg=self.BORDER).pack(fill="x", pady=12)

    def next_scan(self) -> None:
        frame = self.controller.next_frame()
        if frame is None:
            self._stop_auto()
            self.footer_status.configure(text="MISSION COMPLETE", fg=self.AMBER)
            return
        self._render(frame)
        if not self.controller.has_next:
            self.next_button.configure(state="disabled")
            self._stop_auto()

    def reset(self) -> None:
        self._stop_auto()
        self.controller.reset()
        self.next_button.configure(state="normal")
        self._show_ready_state()

    def start_simulation(self) -> None:
        self._stop_auto()
        self.controller.start_simulation()
        self.next_button.configure(state="normal")
        self._show_ready_state()
        self._set_mode(MissionMode.SIMULATED)

    def start_recording(self) -> None:
        parent = filedialog.askdirectory(
            title="Choose where to save the Aegis recording"
        )
        if not parent:
            return
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        recording_path = Path(parent) / f"aegis-mission-{timestamp}"
        try:
            self.controller.start_simulation(recording_path)
        except (OSError, ValueError) as error:
            messagebox.showerror("Recording Error", str(error))
            return
        self.next_button.configure(state="normal")
        self._show_ready_state()
        self._set_mode(MissionMode.RECORDING)
        self.footer_status.configure(
            text=f"RECORDING TO {recording_path.name}", fg=self.RED
        )

    def open_recording(self) -> None:
        directory = filedialog.askdirectory(
            title="Open an Aegis recording directory"
        )
        if not directory:
            return
        try:
            self.controller.open_recording(directory)
        except (OSError, ValueError) as error:
            messagebox.showerror("Playback Error", str(error))
            return
        self.next_button.configure(state="normal")
        self._show_ready_state()
        self._set_mode(MissionMode.REPLAY)
        if self.controller.issues:
            messagebox.showwarning(
                "Recording Recovered",
                f"Loaded with {len(self.controller.issues)} reported issue(s).",
            )

    def stop_mission(self) -> None:
        self._stop_auto()
        self.controller.stop()
        self.next_button.configure(state="disabled")
        self.footer_status.configure(text="MISSION STOPPED", fg=self.AMBER)

    def toggle_auto(self) -> None:
        if self._auto_running:
            self._stop_auto()
            return
        if self.controller.mode is MissionMode.READY:
            self.start_simulation()
        if not self.controller.has_next:
            return
        self._auto_running = True
        self.auto_button.configure(text="PAUSE")
        self._auto_step()

    def _auto_step(self) -> None:
        if not self._auto_running:
            return
        self.next_scan()
        if self._auto_running and self.controller.has_next:
            self._auto_job = self.root.after(1400, self._auto_step)

    def _stop_auto(self) -> None:
        self._auto_running = False
        self.auto_button.configure(text="PLAY")
        if self._auto_job is not None:
            self.root.after_cancel(self._auto_job)
            self._auto_job = None

    def _show_ready_state(self) -> None:
        self._set_mode(self.controller.mode)
        self.status_values["RF Activity"].configure(text="0 ACTIVE")
        self.status_values["Alerts"].configure(text="0 NEW")
        self.status_values["Scan"].configure(
            text=f"0 / {self.controller.total_frames}"
        )
        if self.controller.mode is MissionMode.READY:
            self.footer_status.configure(text="MISSION READY", fg=self.GREEN)
        self._clear_contacts()
        self._clear_details()
        self._draw_map()
        self._draw_signal()

    def _render(self, frame: MissionFrame) -> None:
        result = frame.scan_result
        confirmed = sum(c.state.value == "confirmed" for c in result.contacts)
        fading = sum(c.state.value == "fading" for c in result.contacts)
        self.status_values["RF Activity"].configure(
            text=f"{len(result.contacts)} ACTIVE"
        )
        self.status_values["Alerts"].configure(
            text=f"{fading} NEW", fg=self.RED if fading else self.GREEN
        )
        self.status_values["Scan"].configure(
            text=f"{result.scan_number} / {self.controller.total_frames}"
        )
        self._set_mode(frame.mode)
        self.footer_status.configure(
            text=(
                f"{frame.mode.value.upper()}  |  SCAN {result.scan_number}  |  "
                f"{confirmed} CONFIRMED"
            ),
            fg=self.CYAN,
        )
        self._clear_contacts()
        for contact in result.contacts:
            row = self.contact_table.insert(
                "", "end",
                values=(
                    f"#{contact.signal_id}",
                    f"{contact.center_frequency_hz / 1e6:.3f} MHz",
                    f"{contact.confidence:.0f}%",
                    contact.state.value.upper(),
                    contact.detection_count,
                    contact.missed_scans,
                ),
                tags=(contact.state.value,),
            )
            self._contacts_by_row[row] = contact
        rows = self.contact_table.get_children()
        if rows:
            self.contact_table.selection_set(rows[0])
            self.contact_table.focus(rows[0])
            self._show_contact(self._contacts_by_row[rows[0]])
        self._show_trajectory(frame)
        self._draw_map()
        self._draw_signal()

    def _set_mode(self, mode: MissionMode) -> None:
        colors = {
            MissionMode.READY: self.MUTED,
            MissionMode.SIMULATED: self.AMBER,
            MissionMode.RECORDING: self.RED,
            MissionMode.REPLAY: self.PURPLE,
        }
        label = mode.value.upper()
        self.unit_label.configure(text=f"  UNIT 01 / {label}")
        self.mode_label.configure(text=f"MODE: {label}", fg=colors[mode])
        self.status_values["Input Source"].configure(text=label)

    def _clear_contacts(self) -> None:
        self._contacts_by_row.clear()
        for row in self.contact_table.get_children():
            self.contact_table.delete(row)

    def _on_contact_selected(self, _: object) -> None:
        selected = self.contact_table.selection()
        if selected and selected[0] in self._contacts_by_row:
            self._show_contact(self._contacts_by_row[selected[0]])

    def _show_contact(self, contact: ContactSnapshot) -> None:
        colors = {
            "confirmed": self.GREEN,
            "tentative": self.AMBER,
            "fading": self.RED,
        }
        color = colors[contact.state.value]
        self.detail_title.configure(
            text=f"CONTACT #{contact.signal_id}", fg=color
        )
        self.detail_state.configure(
            text=f"{contact.state.value.upper()}  |  CONFIDENCE {contact.confidence:.0f}%"
        )
        values = {
            "Center Frequency": f"{contact.center_frequency_hz / 1e6:.6f} MHz",
            "Bandwidth": f"{contact.bandwidth_hz / 1e3:.1f} kHz",
            "Peak Power": f"{contact.peak_power_db:.1f} dB",
            "Detections": str(contact.detection_count),
            "Missed Scans": str(contact.missed_scans),
        }
        for name, value in values.items():
            self.detail_fields[name].configure(text=value)
        self.confidence_canvas.delete("all")
        self.confidence_canvas.update_idletasks()
        width = max(self.confidence_canvas.winfo_width(), 1)
        self.confidence_canvas.create_rectangle(
            0, 0, width * contact.confidence / 100, 12,
            fill=color, outline="",
        )

    def _show_trajectory(self, frame: MissionFrame) -> None:
        altitude = (
            frame.aircraft_position.altitude_m
            if frame.aircraft_position is not None
            else None
        )
        values = {
            "Aircraft ID": frame.aircraft_id or "UNAVAILABLE",
            "Distance": (
                f"{frame.distance_m:.1f} m"
                if frame.distance_m is not None
                else "UNAVAILABLE"
            ),
            "Bearing": (
                f"{frame.bearing_degrees:.1f} deg"
                if frame.bearing_degrees is not None
                else "UNAVAILABLE"
            ),
            "Heading": (
                f"{frame.heading_degrees:.1f} deg"
                if frame.heading_degrees is not None
                else "UNAVAILABLE"
            ),
            "Altitude": (
                f"{altitude:.1f} m" if altitude is not None else "UNAVAILABLE"
            ),
        }
        for name, value in values.items():
            self.detail_fields[name].configure(text=value)

    def _clear_details(self) -> None:
        self.detail_title.configure(text="NO CONTACT SELECTED", fg=self.MUTED)
        self.detail_state.configure(
            text="Advance the simulator to acquire contacts."
        )
        for label in self.detail_fields.values():
            label.configure(text="--")
        self.confidence_canvas.delete("all")

    def _draw_map(self) -> None:
        canvas = self.map_canvas
        canvas.delete("all")
        width = max(canvas.winfo_width(), 320)
        height = max(canvas.winfo_height(), 230)
        for x in range(0, width, 40):
            canvas.create_line(x, 0, x, height, fill="#10262c")
        for y in range(0, height, 40):
            canvas.create_line(0, y, width, y, fill="#10262c")
        cx, cy = width / 2, height * 0.58
        for radius in (35, 70, 105, 140):
            canvas.create_oval(
                cx - radius, cy - radius, cx + radius, cy + radius,
                outline="#1a5360",
            )
        canvas.create_line(cx, 0, cx, height, fill="#245462", dash=(3, 5))
        canvas.create_line(0, cy, width, cy, fill="#245462", dash=(3, 5))
        canvas.create_oval(cx - 8, cy - 8, cx + 8, cy + 8,
                           fill=self.CYAN, outline="#b8efff")
        canvas.create_text(cx, cy + 20, text="AEGIS", fill=self.CYAN,
                           font=("Consolas", 8, "bold"))
        frame = self.controller.current
        if frame is None:
            canvas.create_text(
                cx, 24, text="AWAITING MISSION EVENTS",
                fill=self.MUTED, font=("Consolas", 9),
            )
            return
        result = frame.scan_result
        if frame.bearing_degrees is not None and frame.distance_m is not None:
            angle = math.radians(frame.bearing_degrees - 90.0)
            radius = min(140.0, 35.0 + frame.distance_m * 0.32)
            x = cx + math.cos(angle) * radius
            y = cy + math.sin(angle) * radius
            color = self.GREEN
            canvas.create_line(cx, cy, x, y, fill=color, dash=(4, 4))
            canvas.create_oval(
                x - 8, y - 8, x + 8, y + 8, outline=color, width=2
            )
            canvas.create_text(
                x + 11,
                y - 10,
                text=(
                    f"{frame.aircraft_id}  {frame.distance_m:.0f} m  "
                    f"{frame.bearing_degrees:.0f} deg"
                ),
                fill=color, anchor="w", font=("Consolas", 8, "bold"),
            )
        confidence = result.contacts[0].confidence if result.contacts else 0.0
        canvas.create_text(
            8,
            height - 8,
            text=f"RF CONTACT CONFIDENCE: {confidence:.0f}%",
            fill=self.AMBER,
            anchor="sw",
            font=("Consolas", 7),
        )
        canvas.create_text(8, 8, text="FICTIONAL REMOTE ID TRAJECTORY",
                           fill=self.MUTED, anchor="nw", font=("Consolas", 7))

    def _draw_signal(self) -> None:
        canvas = self.signal_canvas
        canvas.delete("all")
        width = max(canvas.winfo_width(), 280)
        height = max(canvas.winfo_height(), 180)
        split = int(height * 0.48)
        for x in range(0, width, 45):
            canvas.create_line(x, 0, x, split, fill="#13303a")
        for y in range(0, split, 30):
            canvas.create_line(0, y, width, y, fill="#13303a")
        scan = (
            self.controller.current.scan_result.scan_number
            if self.controller.current
            else 0
        )
        points: list[float] = []
        for x in range(width):
            base = split * 0.72
            wave = 8 * math.sin(x * 0.11 + scan) + 4 * math.sin(x * 0.37)
            spike = 0.0
            for center in (0.24, 0.53, 0.81):
                distance = abs(x / width - center)
                if distance < 0.018:
                    spike += (1 - distance / 0.018) * 42
            points.extend((x, base - wave - spike))
        canvas.create_line(*points, fill="#2bd4a7", width=1)
        canvas.create_text(6, 5, text="2.400 GHz", fill=self.MUTED,
                           anchor="nw", font=("Consolas", 7))
        canvas.create_text(width - 6, 5, text="2.500 GHz", fill=self.MUTED,
                           anchor="ne", font=("Consolas", 7))
        waterfall_top = split + 8
        palette = ("#071b27", "#0b3442", "#126b70", "#24a887", "#d5b447")
        rows = 18
        cell_h = max((height - waterfall_top) / rows, 1)
        for row in range(rows):
            for col in range(70):
                value = (col * 17 + row * 13 + scan * 19) % 31
                level = 0
                if value > 20:
                    level = 1
                if any(abs(col / 70 - peak) < 0.025 for peak in (0.24, 0.53, 0.81)):
                    level = 3 + ((row + col + scan) % 2)
                x1 = col * width / 70
                x2 = (col + 1) * width / 70 + 1
                y1 = waterfall_top + row * cell_h
                y2 = y1 + cell_h + 1
                canvas.create_rectangle(x1, y1, x2, y2,
                                        fill=palette[level], outline="")
        canvas.create_line(0, split, width, split, fill=self.BORDER)


def main() -> None:
    root = tk.Tk()
    AegisApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
