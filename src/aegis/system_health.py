"""Low-overhead Linux system health readings for the Aegis dashboard."""

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SystemHealth:
    cpu_percent: float | None
    memory_percent: float | None
    temperature_c: float | None


class SystemHealthMonitor:
    """Sample Raspberry Pi health data without an external dependency."""

    def __init__(
        self,
        stat_path: Path = Path("/proc/stat"),
        meminfo_path: Path = Path("/proc/meminfo"),
        temperature_path: Path = Path("/sys/class/thermal/thermal_zone0/temp"),
    ) -> None:
        self.stat_path = stat_path
        self.meminfo_path = meminfo_path
        self.temperature_path = temperature_path
        self._previous_cpu: tuple[int, int] | None = None

    def read(self) -> SystemHealth:
        return SystemHealth(
            cpu_percent=self._read_cpu(),
            memory_percent=self._read_memory(),
            temperature_c=self._read_temperature(),
        )

    def _read_cpu(self) -> float | None:
        try:
            fields = self.stat_path.read_text(encoding="ascii").splitlines()[0].split()
            values = [int(value) for value in fields[1:]]
            idle = values[3] + (values[4] if len(values) > 4 else 0)
            total = sum(values)
        except (OSError, ValueError, IndexError):
            return None
        previous, self._previous_cpu = self._previous_cpu, (total, idle)
        if previous is None:
            return None
        total_delta = total - previous[0]
        idle_delta = idle - previous[1]
        if total_delta <= 0:
            return None
        return max(0.0, min(100.0, 100.0 * (1.0 - idle_delta / total_delta)))

    def _read_memory(self) -> float | None:
        try:
            values = {}
            for line in self.meminfo_path.read_text(encoding="ascii").splitlines():
                name, value = line.split(":", 1)
                values[name] = int(value.strip().split()[0])
            total = values["MemTotal"]
            available = values["MemAvailable"]
        except (OSError, ValueError, KeyError, IndexError):
            return None
        if total <= 0:
            return None
        return max(0.0, min(100.0, 100.0 * (total - available) / total))

    def _read_temperature(self) -> float | None:
        try:
            value = float(self.temperature_path.read_text(encoding="ascii").strip())
        except (OSError, ValueError):
            return None
        # Linux thermal zones normally expose millidegrees Celsius.
        temperature = value / 1000.0 if abs(value) > 500 else value
        return temperature if -50 <= temperature <= 150 else None

