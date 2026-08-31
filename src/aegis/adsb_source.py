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
    registration: str | None
    type_designator: str | None
    model: str | None
    owner_operator: str | None
    aircraft_class: str
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
                registration=_clean_text(item.get("r")),
                type_designator=_clean_text(item.get("t")),
                model=_aircraft_model(item),
                owner_operator=_clean_text(item.get("ownOp")),
                aircraft_class=classify_aircraft(item),
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


# Common ICAO type designators. readsb's aircraft database supplies the code;
# this compact fallback makes the most frequently observed types human-readable.
_TYPE_NAMES = {
    "A20N": "Airbus A320neo", "A21N": "Airbus A321neo",
    "A319": "Airbus A319", "A320": "Airbus A320", "A321": "Airbus A321",
    "A332": "Airbus A330-200", "A333": "Airbus A330-300",
    "A359": "Airbus A350-900", "A35K": "Airbus A350-1000",
    "B38M": "Boeing 737 MAX 8", "B39M": "Boeing 737 MAX 9",
    "B733": "Boeing 737-300", "B734": "Boeing 737-400",
    "B735": "Boeing 737-500", "B736": "Boeing 737-600",
    "B737": "Boeing 737-700", "B738": "Boeing 737-800",
    "B739": "Boeing 737-900/900ER", "B752": "Boeing 757-200",
    "B753": "Boeing 757-300", "B763": "Boeing 767-300",
    "B772": "Boeing 777-200", "B77W": "Boeing 777-300ER",
    "B788": "Boeing 787-8", "B789": "Boeing 787-9",
    "B78X": "Boeing 787-10", "C172": "Cessna 172",
    "C182": "Cessna 182", "C25A": "Cessna Citation CJ2",
    "C25B": "Cessna Citation CJ3", "C25C": "Cessna Citation CJ4",
    "CRJ2": "Bombardier CRJ-200", "CRJ7": "Bombardier CRJ-700",
    "CRJ9": "Bombardier CRJ-900", "E170": "Embraer E170",
    "E175": "Embraer E175", "E190": "Embraer E190",
    "E195": "Embraer E195", "E75L": "Embraer E175 (long wing)",
    "GLF4": "Gulfstream IV", "GLF5": "Gulfstream V",
    "GLF6": "Gulfstream G650", "LJ35": "Learjet 35",
    "PC12": "Pilatus PC-12", "SR22": "Cirrus SR22",
}

_AIRLINER_TYPES = {
    code for code in _TYPE_NAMES
    if code.startswith(("A2", "A3", "B3", "B7", "CRJ", "E17", "E19", "E75"))
}
_PRIVATE_TYPES = {"C172", "C182", "C25A", "C25B", "C25C", "GLF4", "GLF5",
                  "GLF6", "LJ35", "PC12", "SR22"}


def classify_aircraft(item: dict) -> str:
    """Return an evidence-qualified operational class for a readsb record."""

    flags = item.get("dbFlags", 0)
    if isinstance(flags, int) and flags & 1:
        return "MILITARY"
    designator = (_clean_text(item.get("t")) or "").upper()
    if designator in _PRIVATE_TYPES:
        return "PRIVATE/GENERAL (LIKELY)"
    if designator in _AIRLINER_TYPES and _clean_text(item.get("flight")):
        return "COMMERCIAL (LIKELY)"
    return "UNKNOWN"


def _aircraft_model(item: dict) -> str | None:
    designator = (_clean_text(item.get("t")) or "").upper()
    return _TYPE_NAMES.get(designator) or _clean_text(item.get("desc")) or designator or None


class ReadsbSource:
    """Own a readsb subprocess and expose its atomically-written JSON output."""

    def __init__(self, data_directory: Path | None = None,
                 database_file: Path | None = None) -> None:
        self.data_directory = data_directory or (
            Path.home() / ".cache" / "aegis" / "readsb"
        )
        self.database_file = database_file
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

    @staticmethod
    def find_database() -> Path | None:
        candidates = (
            Path.home() / ".cache" / "aegis" / "aircraft.csv.gz",
            Path.home() / "readsb-rtl" / "aircraft.csv.gz",
            Path("/usr/local/share/tar1090/aircraft.csv.gz"),
            Path("/usr/share/tar1090/aircraft.csv.gz"),
        )
        return next((path for path in candidates if path.is_file()), None)

    @staticmethod
    def build_command(binary: Path, data_directory: Path,
                      database_file: Path | None = None) -> list[str]:
        command = [
            str(binary),
            "--device-type", "rtlsdr",
            "--device", "0",
            "--gain", "auto",
            "--net",
            f"--write-json={data_directory}",
            "--write-json-every=1",
            "--quiet",
        ]
        if database_file is not None:
            command.extend(("--db-file", str(database_file), "--db-file-lt"))
        return command

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
        database_file = self.database_file or self.find_database()
        self.process = subprocess.Popen(
            self.build_command(binary, self.data_directory, database_file),
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
