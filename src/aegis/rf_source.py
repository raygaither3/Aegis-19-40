"""Receive-only live spectrum acquisition using rtl_power."""

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import shutil
import subprocess
import threading

import numpy as np


@dataclass(frozen=True)
class SpectrumSweep:
    """One measured power spectrum assembled from rtl_power CSV rows."""

    observed_at: datetime
    frequencies_hz: np.ndarray
    power_db: np.ndarray


def parse_rtl_power_row(line: str) -> tuple[datetime, np.ndarray, np.ndarray]:
    """Parse one rtl_power CSV row and return its bin centers and powers."""

    fields = [field.strip() for field in line.split(",")]
    if len(fields) < 7:
        raise ValueError("rtl_power row has too few fields")
    observed_at = datetime.strptime(
        f"{fields[0]} {fields[1]}", "%Y-%m-%d %H:%M:%S"
    ).replace(tzinfo=timezone.utc)
    start_hz = float(fields[2])
    stop_hz = float(fields[3])
    step_hz = float(fields[4])
    powers = np.asarray([float(value) for value in fields[6:]], dtype=float)
    if powers.size < 2 or step_hz <= 0 or stop_hz <= start_hz:
        raise ValueError("rtl_power row contains an invalid frequency range")
    frequencies = start_hz + np.arange(powers.size, dtype=float) * step_hz
    return observed_at, frequencies, powers


class RtlPowerSource:
    """Own an rtl_power process and publish complete, thread-safe sweeps."""

    def __init__(
        self,
        start_hz: float = 902_000_000,
        stop_hz: float = 928_000_000,
        bin_width_hz: float = 100_000,
        interval_seconds: int = 1,
        gain_db: str = "auto",
    ) -> None:
        if start_hz <= 0 or stop_hz <= start_hz or bin_width_hz <= 0:
            raise ValueError("invalid RF scan range")
        self.start_hz = start_hz
        self.stop_hz = stop_hz
        self.bin_width_hz = bin_width_hz
        self.interval_seconds = interval_seconds
        self.gain_db = gain_db
        self.process: subprocess.Popen | None = None
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self._latest: SpectrumSweep | None = None
        self._sequence = 0
        self._error: str | None = None

    @staticmethod
    def find_binary() -> Path | None:
        installed = shutil.which("rtl_power")
        return Path(installed) if installed else None

    @property
    def error(self) -> str | None:
        with self._lock:
            return self._error

    def start(self) -> None:
        if self.process is not None and self.process.poll() is None:
            return
        binary = self.find_binary()
        if binary is None:
            raise FileNotFoundError(
                "rtl_power was not found. Install rtl-sdr and ensure rtl_power "
                "is on PATH."
            )
        command = [
            str(binary), "-f",
            f"{int(self.start_hz)}:{int(self.stop_hz)}:{int(self.bin_width_hz)}",
            "-i", str(self.interval_seconds),
        ]
        if self.gain_db != "auto":
            command.extend(("-g", self.gain_db))
        command.append("-")
        with self._lock:
            self._error = None
        self.process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            bufsize=1,
        )
        self._thread = threading.Thread(target=self._read_output, daemon=True)
        self._thread.start()

    def latest(self, after_sequence: int = 0) -> tuple[int, SpectrumSweep | None]:
        with self._lock:
            if self._sequence <= after_sequence:
                return self._sequence, None
            return self._sequence, self._latest

    def stop(self) -> None:
        process, self.process = self.process, None
        if process is not None and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=2)
        thread, self._thread = self._thread, None
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=1)

    def _read_output(self) -> None:
        process = self.process
        if process is None or process.stdout is None:
            return
        batch_time: datetime | None = None
        frequency_parts: list[np.ndarray] = []
        power_parts: list[np.ndarray] = []
        try:
            for line in process.stdout:
                try:
                    observed_at, frequencies, powers = parse_rtl_power_row(line)
                except (ValueError, OverflowError):
                    continue
                if batch_time is not None and observed_at != batch_time:
                    self._publish(batch_time, frequency_parts, power_parts)
                    frequency_parts, power_parts = [], []
                batch_time = observed_at
                frequency_parts.append(frequencies)
                power_parts.append(powers)
            if batch_time is not None:
                self._publish(batch_time, frequency_parts, power_parts)
            if self.process is process and process.poll() not in (None, 0, -15):
                with self._lock:
                    self._error = "rtl_power stopped unexpectedly"
        except OSError as error:
            if self.process is process:
                with self._lock:
                    self._error = str(error)

    def _publish(
        self,
        observed_at: datetime,
        frequency_parts: list[np.ndarray],
        power_parts: list[np.ndarray],
    ) -> None:
        frequencies = np.concatenate(frequency_parts)
        powers = np.concatenate(power_parts)
        order = np.argsort(frequencies)
        sweep = SpectrumSweep(observed_at, frequencies[order], powers[order])
        with self._lock:
            self._latest = sweep
            self._sequence += 1
