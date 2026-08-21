from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from src.aegis.system_health import SystemHealthMonitor


class SystemHealthMonitorTests(unittest.TestCase):
    def test_reads_cpu_memory_and_temperature(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            stat = root / "stat"
            memory = root / "meminfo"
            temperature = root / "temp"
            stat.write_text("cpu  100 0 100 800 0 0 0 0\n", encoding="ascii")
            memory.write_text(
                "MemTotal: 1000 kB\nMemAvailable: 600 kB\n", encoding="ascii"
            )
            temperature.write_text("52500\n", encoding="ascii")
            monitor = SystemHealthMonitor(stat, memory, temperature)

            first = monitor.read()
            self.assertIsNone(first.cpu_percent)
            self.assertEqual(first.memory_percent, 40.0)
            self.assertEqual(first.temperature_c, 52.5)

            stat.write_text("cpu  150 0 150 900 0 0 0 0\n", encoding="ascii")
            second = monitor.read()
            self.assertAlmostEqual(second.cpu_percent, 50.0)

    def test_missing_sources_return_unavailable(self) -> None:
        monitor = SystemHealthMonitor(
            Path("missing-stat"), Path("missing-memory"), Path("missing-temp")
        )
        health = monitor.read()
        self.assertIsNone(health.cpu_percent)
        self.assertIsNone(health.memory_percent)
        self.assertIsNone(health.temperature_c)


if __name__ == "__main__":
    unittest.main()
