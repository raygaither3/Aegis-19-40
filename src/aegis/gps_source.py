"""Local GPS receiver backed by gpsd's JSON socket protocol."""

from dataclasses import dataclass
import json
import socket
import threading
import time


@dataclass(frozen=True)
class GpsFix:
    latitude: float
    longitude: float
    altitude_m: float | None = None
    speed_mps: float | None = None
    track_degrees: float | None = None
    horizontal_error_m: float | None = None
    fix_time: str | None = None


class GpsdSource:
    """Continuously retain the newest usable TPV report from local gpsd."""

    def __init__(self, host: str = "127.0.0.1", port: int = 2947) -> None:
        self.host, self.port = host, port
        self._socket: socket.socket | None = None
        self._thread: threading.Thread | None = None
        self._stop_event: threading.Event | None = None
        self._lock = threading.Lock()
        self._fix: GpsFix | None = None
        self._received_at: float | None = None
        self._error: str | None = None

    def start(self) -> None:
        # Always build a fresh session. A previous reader can still be winding
        # down briefly after its socket closes; reusing its stop event can make
        # a quick GPS off/on cycle appear active without a live connection.
        self.stop()
        connection = socket.create_connection((self.host, self.port), timeout=3)
        connection.settimeout(1.0)
        connection.sendall(b'?WATCH={"enable":true,"json":true};\n')
        stop_event = threading.Event()
        self._socket = connection
        self._stop_event = stop_event
        with self._lock:
            self._fix = None
            self._received_at = None
            self._error = None
        self._thread = threading.Thread(
            target=self._run,
            args=(connection, stop_event),
            name="aegis-gpsd",
            daemon=True,
        )
        self._thread.start()

    def latest(self, max_age_seconds: float = 5.0) -> GpsFix | None:
        with self._lock:
            if self._received_at is None or time.monotonic() - self._received_at > max_age_seconds:
                return None
            return self._fix

    @property
    def error(self) -> str | None:
        with self._lock:
            return self._error

    def stop(self) -> None:
        stop_event, self._stop_event = self._stop_event, None
        if stop_event is not None:
            stop_event.set()
        connection, self._socket = self._socket, None
        if connection is not None:
            try:
                connection.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            connection.close()
        thread, self._thread = self._thread, None
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=1.5)

    def _run(
        self, connection: socket.socket, stop_event: threading.Event
    ) -> None:
        buffer = b""
        try:
            while not stop_event.is_set():
                try:
                    chunk = connection.recv(4096)
                except socket.timeout:
                    continue
                if not chunk:
                    raise ConnectionError("gpsd closed the connection")
                buffer += chunk
                while b"\n" in buffer:
                    line, buffer = buffer.split(b"\n", 1)
                    self._accept_report(line)
        except (OSError, ConnectionError, ValueError) as error:
            if not stop_event.is_set():
                with self._lock:
                    self._error = str(error)

    def _accept_report(self, raw: bytes) -> None:
        try:
            report = json.loads(raw)
        except (UnicodeDecodeError, json.JSONDecodeError):
            return
        fix = parse_tpv(report)
        if fix is not None:
            with self._lock:
                self._fix = fix
                self._received_at = time.monotonic()
                self._error = None


def parse_tpv(report: object) -> GpsFix | None:
    if not isinstance(report, dict) or report.get("class") != "TPV":
        return None
    if int(report.get("mode", 0) or 0) < 2:
        return None
    lat, lon = _number(report.get("lat")), _number(report.get("lon"))
    if lat is None or lon is None or not -90 <= lat <= 90 or not -180 <= lon <= 180:
        return None
    return GpsFix(lat, lon, _number(report.get("altMSL", report.get("alt"))),
                  _number(report.get("speed")), _number(report.get("track")),
                  _number(report.get("epx")),
                  report.get("time") if isinstance(report.get("time"), str) else None)


def _number(value: object) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if result == result and abs(result) != float("inf") else None
