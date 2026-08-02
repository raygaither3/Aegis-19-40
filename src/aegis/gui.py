import tkinter as tk
from tkinter import ttk

from src.aegis.scenario_simulator import (
    ScanResult,
    build_demo_scenario,
    run_scenario,
)


class ScenarioController:
    """Provide sequential access to simulator results for any interface."""

    def __init__(self) -> None:
        self._results = run_scenario(build_demo_scenario())
        self._index = -1

    @property
    def current(self) -> ScanResult | None:
        if self._index < 0:
            return None
        return self._results[self._index]

    @property
    def has_next(self) -> bool:
        return self._index + 1 < len(self._results)

    @property
    def total_scans(self) -> int:
        return len(self._results)

    def next_scan(self) -> ScanResult | None:
        if not self.has_next:
            return None
        self._index += 1
        return self.current

    def reset(self) -> None:
        self._index = -1


class AegisApp:
    BACKGROUND = "#0b1220"
    PANEL = "#111c2e"
    BORDER = "#26364d"
    TEXT = "#e6edf7"
    MUTED = "#8ea0b8"
    ACCENT = "#38bdf8"
    GREEN = "#34d399"
    AMBER = "#fbbf24"
    RED = "#fb7185"

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.controller = ScenarioController()
        self._auto_job: str | None = None
        self._auto_running = False

        self.root.title("Project Aegis - Contact Monitor")
        self.root.geometry("1060x650")
        self.root.minsize(850, 500)
        self.root.configure(bg=self.BACKGROUND)

        self._configure_styles()
        self._build_layout()
        self._show_ready_state()

    def _configure_styles(self) -> None:
        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure("Aegis.TFrame", background=self.BACKGROUND)
        style.configure("Panel.TFrame", background=self.PANEL)
        style.configure(
            "Title.TLabel",
            background=self.BACKGROUND,
            foreground=self.TEXT,
            font=("Segoe UI Semibold", 22),
        )
        style.configure(
            "Subtitle.TLabel",
            background=self.BACKGROUND,
            foreground=self.MUTED,
            font=("Segoe UI", 10),
        )
        style.configure(
            "Metric.TLabel",
            background=self.PANEL,
            foreground=self.TEXT,
            font=("Segoe UI Semibold", 16),
        )
        style.configure(
            "MetricName.TLabel",
            background=self.PANEL,
            foreground=self.MUTED,
            font=("Segoe UI", 9),
        )
        style.configure(
            "Aegis.TButton",
            background=self.BORDER,
            foreground=self.TEXT,
            borderwidth=0,
            padding=(14, 8),
            font=("Segoe UI Semibold", 10),
        )
        style.map("Aegis.TButton", background=[("active", "#334968")])
        style.configure(
            "Accent.TButton",
            background=self.ACCENT,
            foreground="#04131d",
            borderwidth=0,
            padding=(14, 8),
            font=("Segoe UI Semibold", 10),
        )
        style.map("Accent.TButton", background=[("active", "#7dd3fc")])
        style.configure(
            "Treeview",
            background=self.PANEL,
            fieldbackground=self.PANEL,
            foreground=self.TEXT,
            rowheight=34,
            borderwidth=0,
            font=("Consolas", 10),
        )
        style.configure(
            "Treeview.Heading",
            background="#18263b",
            foreground=self.MUTED,
            borderwidth=0,
            padding=(8, 9),
            font=("Segoe UI Semibold", 9),
        )
        style.map("Treeview", background=[("selected", "#1f4d68")])

    def _build_layout(self) -> None:
        main = ttk.Frame(self.root, style="Aegis.TFrame", padding=24)
        main.pack(fill="both", expand=True)

        header = ttk.Frame(main, style="Aegis.TFrame")
        header.pack(fill="x")
        ttk.Label(
            header,
            text="PROJECT AEGIS",
            style="Title.TLabel",
        ).pack(anchor="w")
        ttk.Label(
            header,
            text="Simulated RF contact monitoring | Confidence engine v0.3",
            style="Subtitle.TLabel",
        ).pack(anchor="w", pady=(2, 0))

        controls = ttk.Frame(header, style="Aegis.TFrame")
        controls.place(relx=1.0, rely=0.5, anchor="e")
        self.reset_button = ttk.Button(
            controls,
            text="Reset",
            style="Aegis.TButton",
            command=self.reset,
        )
        self.reset_button.pack(side="left", padx=(0, 8))
        self.auto_button = ttk.Button(
            controls,
            text="Auto Play",
            style="Aegis.TButton",
            command=self.toggle_auto,
        )
        self.auto_button.pack(side="left", padx=(0, 8))
        self.next_button = ttk.Button(
            controls,
            text="Next Scan",
            style="Accent.TButton",
            command=self.next_scan,
        )
        self.next_button.pack(side="left")

        metrics = ttk.Frame(main, style="Aegis.TFrame")
        metrics.pack(fill="x", pady=(26, 16))
        self.scan_value = self._metric_card(metrics, "SCAN", 0)
        self.contact_value = self._metric_card(metrics, "ACTIVE CONTACTS", 1)
        self.confirmed_value = self._metric_card(metrics, "CONFIRMED", 2)
        self.fading_value = self._metric_card(metrics, "FADING", 3)

        scenario_panel = ttk.Frame(main, style="Panel.TFrame", padding=(16, 12))
        scenario_panel.pack(fill="x", pady=(0, 12))
        self.scenario_label = ttk.Label(
            scenario_panel,
            background=self.PANEL,
            foreground=self.TEXT,
            font=("Segoe UI Semibold", 11),
        )
        self.scenario_label.pack(anchor="w")
        self.status_label = ttk.Label(
            scenario_panel,
            background=self.PANEL,
            foreground=self.MUTED,
            font=("Segoe UI", 9),
        )
        self.status_label.pack(anchor="w", pady=(3, 0))

        table_panel = ttk.Frame(main, style="Panel.TFrame", padding=1)
        table_panel.pack(fill="both", expand=True)
        columns = (
            "id",
            "frequency",
            "bandwidth",
            "power",
            "confidence",
            "state",
            "seen",
            "missed",
        )
        self.contact_table = ttk.Treeview(
            table_panel,
            columns=columns,
            show="headings",
            selectmode="browse",
        )
        headings = {
            "id": "ID",
            "frequency": "FREQUENCY",
            "bandwidth": "BANDWIDTH",
            "power": "PEAK POWER",
            "confidence": "CONFIDENCE",
            "state": "STATE",
            "seen": "SEEN",
            "missed": "MISSED",
        }
        widths = {
            "id": 55,
            "frequency": 145,
            "bandwidth": 115,
            "power": 110,
            "confidence": 115,
            "state": 115,
            "seen": 70,
            "missed": 75,
        }
        for column in columns:
            self.contact_table.heading(column, text=headings[column])
            self.contact_table.column(
                column,
                width=widths[column],
                anchor="center",
                stretch=True,
            )
        self.contact_table.tag_configure("confirmed", foreground=self.GREEN)
        self.contact_table.tag_configure("tentative", foreground=self.AMBER)
        self.contact_table.tag_configure("fading", foreground=self.RED)
        self.contact_table.pack(fill="both", expand=True)

    def _metric_card(
        self,
        parent: ttk.Frame,
        name: str,
        column: int,
    ) -> ttk.Label:
        card = ttk.Frame(parent, style="Panel.TFrame", padding=(16, 12))
        card.grid(row=0, column=column, sticky="ew", padx=(0, 10))
        parent.columnconfigure(column, weight=1)
        value = ttk.Label(card, text="0", style="Metric.TLabel")
        value.pack(anchor="w")
        ttk.Label(card, text=name, style="MetricName.TLabel").pack(anchor="w")
        return value

    def next_scan(self) -> None:
        result = self.controller.next_scan()
        if result is None:
            self._stop_auto()
            self.status_label.configure(text="Scenario complete. Reset to replay.")
            return
        self._render(result)
        if not self.controller.has_next:
            self.next_button.configure(state="disabled")
            self._stop_auto()

    def reset(self) -> None:
        self._stop_auto()
        self.controller.reset()
        self.next_button.configure(state="normal")
        self._show_ready_state()

    def toggle_auto(self) -> None:
        if self._auto_running:
            self._stop_auto()
            return
        self._auto_running = True
        self.auto_button.configure(text="Pause")
        self._auto_step()

    def _auto_step(self) -> None:
        if not self._auto_running:
            return
        self.next_scan()
        if self._auto_running and self.controller.has_next:
            self._auto_job = self.root.after(1200, self._auto_step)

    def _stop_auto(self) -> None:
        self._auto_running = False
        self.auto_button.configure(text="Auto Play")
        if self._auto_job is not None:
            self.root.after_cancel(self._auto_job)
            self._auto_job = None

    def _show_ready_state(self) -> None:
        self.scan_value.configure(text=f"0 / {self.controller.total_scans}")
        self.contact_value.configure(text="0")
        self.confirmed_value.configure(text="0")
        self.fading_value.configure(text="0")
        self.scenario_label.configure(text="Simulator ready")
        self.status_label.configure(
            text="Select Next Scan or Auto Play to begin monitoring."
        )
        self._clear_table()

    def _render(self, result: ScanResult) -> None:
        confirmed = sum(
            contact.state.value == "confirmed" for contact in result.contacts
        )
        fading = sum(
            contact.state.value == "fading" for contact in result.contacts
        )
        self.scan_value.configure(
            text=f"{result.scan_number} / {self.controller.total_scans}"
        )
        self.contact_value.configure(text=str(len(result.contacts)))
        self.confirmed_value.configure(text=str(confirmed))
        self.fading_value.configure(text=str(fading))
        self.scenario_label.configure(
            text=f"Scan {result.scan_number}: {result.name}"
        )
        self.status_label.configure(
            text=f"Simulation time {result.timestamp:.1f}s"
        )
        self._clear_table()

        for contact in result.contacts:
            self.contact_table.insert(
                "",
                "end",
                values=(
                    f"#{contact.signal_id}",
                    f"{contact.center_frequency_hz / 1e6:.3f} MHz",
                    f"{contact.bandwidth_hz / 1e3:.1f} kHz",
                    f"{contact.peak_power_db:.1f} dB",
                    f"{contact.confidence:.1f}%",
                    contact.state.value.upper(),
                    contact.detection_count,
                    contact.missed_scans,
                ),
                tags=(contact.state.value,),
            )

    def _clear_table(self) -> None:
        for item in self.contact_table.get_children():
            self.contact_table.delete(item)


def main() -> None:
    root = tk.Tk()
    AegisApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
