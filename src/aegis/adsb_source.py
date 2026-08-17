"""Local readsb adapter for measured ADS-B aircraft observations."""

from dataclasses import dataclass
import json
from pathlib import Path
import shutil
import subprocess
import time


@dataclass(frozen=True)
class AdsbAircraft:
    icao: str
    flight: str | None
    latitude: float | None
    longitude: float | None
    altitude_ft: int | None
    speed_knots: float | None
    track_degrees: float | None
    messages: int
    seen_seconds: float

    @property
    def has_position(self) -> bool:
        return self.latitude is not None and self.longitude is not None


def parse_aircraft_json(data: dict) -> tuple[AdsbAircraft, ...]:
    """Parse readsb aircraft.json while tolerating absent measurements."""

    result: list[AdsbAircraft] = []
    for item in data.get("aircraft", []):
        if not isinstance(item, dict) or not item.get("hex"):
            continue
        altitude = item.get("alt_baro", item.get("alt_geom"))
        if not isinstance(altitude, (int, float)):
            altitude = None
        result.append(
            AdsbAircraft(
                icao=str(item["hex"]).upper(),
                flight=_clean_text(item.get("flight")),
                latitude=_number(item.get("lat")),
                longitude=_number(item.get("lon")),
                altitude_ft=int(altitude) if altitude is not None else None,
                speed_knots=_number(item.get("gs")),
                track_degrees=_number(item.get("track")),
                messages=int(item.get("messages", 0)),
                seen_seconds=float(item.get("seen", 999.0)),
            )
        )
    return tuple(sorted(result, key=lambda aircraft: aircraft.seen_seconds))


class ReadsbSource:
    """Own a readsb subprocess and expose its atomically-written JSON output."""

    def __init__(self, data_directory: Path | None = None) -> None:
        self.data_directory = data_directory or (
            Path.home() / ".cache" / "aegis" / "readsb"
        )
        self.process: subprocess.Popen | None = None

    @staticmethod
    def find_binary() -> Path | None:
        installed = shutil.which("readsb")
        candidates = (
            Path.home() / "readsb-rtl" / "readsb",
            Path(installed) if installed else None,
        )
        for candidate in candidates:
            if candidate is not None and candidate.is_file():
                return candidate
        return None

    def start(self) -> None:
        if self.process is not None and self.process.poll() is None:
            return
        binary = self.find_binary()
        if binary is None:
            raise FileNotFoundError(
                "RTL-enabled readsb was not found at ~/readsb-rtl/readsb"
            )
        self.data_directory.mkdir(parents=True, exist_ok=True)
        aircraft_file = self.data_directory / "aircraft.json"
        if aircraft_file.exists():
            aircraft_file.unlink()
        self.process = subprocess.Popen(
            [
                str(binary),
                "--device-type", "rtlsdr",
                "--device", "0",
                "--gain", "auto",
                "--net",
                f"--write-json={self.data_directory}",
                "--write-json-every=1",
                "--quiet",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
        )
        time.sleep(0.25)
        if self.process.poll() is not None:
            error = self.process.stderr.read().strip() if self.process.stderr else ""
            self.process = None
            raise RuntimeError(error or "readsb exited before starting")

    def read(self) -> tuple[AdsbAircraft, ...]:
        if self.process is not None and self.process.poll() is not None:
            error = self.process.stderr.read().strip() if self.process.stderr else ""
            self.process = None
            raise RuntimeError(error or "readsb stopped unexpectedly")
        path = self.data_directory / "aircraft.json"
        if not path.exists():
            return ()
        try:
            with path.open("r", encoding="utf-8") as stream:
                return parse_aircraft_json(json.load(stream))
        except (OSError, json.JSONDecodeError):
            return ()

    def stop(self) -> None:
        process, self.process = self.process, None
        if process is None or process.poll() is not None:
            return
        process.terminate()
        try:
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=2)


def _number(value: object) -> float | None:
    return float(value) if isinstance(value, (int, float)) else None


def _clean_text(value: object) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    return value.strip()
