"""Small OpenStreetMap tile renderer for Aegis's Tk canvas."""

from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
import math
from pathlib import Path
import urllib.request

from PIL import Image, ImageTk


TILE_SIZE = 256


def geo_to_world(latitude: float, longitude: float, zoom: int) -> tuple[float, float]:
    latitude = max(-85.05112878, min(85.05112878, latitude))
    scale = TILE_SIZE * (2 ** zoom)
    x = (longitude + 180.0) / 360.0 * scale
    sine = math.sin(math.radians(latitude))
    y = (0.5 - math.log((1 + sine) / (1 - sine)) / (4 * math.pi)) * scale
    return x, y


class OnlineMap:
    def __init__(self, root, canvas) -> None:
        self.root = root
        self.canvas = canvas
        self.cache = Path.home() / ".cache" / "aegis" / "map_tiles"
        self.executor = ThreadPoolExecutor(max_workers=3, thread_name_prefix="map-tile")
        self.pending: set[tuple[int, int, int]] = set()
        self.ready: dict[tuple[int, int, int], bytes | None] = {}
        self.images: dict[tuple[int, int, int], ImageTk.PhotoImage] = {}
        self.redraw = None

    def draw(self, center_lat: float, center_lon: float, zoom: int = 10) -> None:
        self._consume_ready()
        canvas = self.canvas
        canvas.delete("all")
        width = max(canvas.winfo_width(), 320)
        height = max(canvas.winfo_height(), 230)
        center_x, center_y = geo_to_world(center_lat, center_lon, zoom)
        left, top = center_x - width / 2, center_y - height / 2
        first_x, last_x = math.floor(left / TILE_SIZE), math.floor((left + width) / TILE_SIZE)
        first_y, last_y = math.floor(top / TILE_SIZE), math.floor((top + height) / TILE_SIZE)
        tile_limit = 2 ** zoom
        for tile_y in range(first_y, last_y + 1):
            if not 0 <= tile_y < tile_limit:
                continue
            for raw_x in range(first_x, last_x + 1):
                tile_x = raw_x % tile_limit
                key = (zoom, tile_x, tile_y)
                x = raw_x * TILE_SIZE - left
                y = tile_y * TILE_SIZE - top
                image = self.images.get(key)
                if image is not None:
                    canvas.create_image(x, y, image=image, anchor="nw")
                else:
                    canvas.create_rectangle(x, y, x + TILE_SIZE, y + TILE_SIZE,
                                            fill="#102128", outline="#28404d")
                    self._request(key)
        canvas.create_text(width - 6, height - 5,
                           text="© OpenStreetMap contributors",
                           fill="#dce8ed", anchor="se", font=("Sans", 7))

    def project(self, latitude: float, longitude: float, center_lat: float,
                center_lon: float, zoom: int = 10) -> tuple[float, float]:
        width = max(self.canvas.winfo_width(), 320)
        height = max(self.canvas.winfo_height(), 230)
        cx, cy = geo_to_world(center_lat, center_lon, zoom)
        x, y = geo_to_world(latitude, longitude, zoom)
        return width / 2 + x - cx, height / 2 + y - cy

    def _request(self, key: tuple[int, int, int]) -> None:
        if key in self.pending:
            return
        self.pending.add(key)
        future = self.executor.submit(self._load, key)
        future.add_done_callback(lambda result: self._ready(key, result))

    def _load(self, key: tuple[int, int, int]) -> bytes | None:
        zoom, x, y = key
        path = self.cache / str(zoom) / str(x) / f"{y}.png"
        try:
            if path.exists():
                return path.read_bytes()
            request = urllib.request.Request(
                f"https://tile.openstreetmap.org/{zoom}/{x}/{y}.png",
                headers={"User-Agent": "Project-Aegis/0.4 local ADS-B display"},
            )
            with urllib.request.urlopen(request, timeout=8) as response:
                data = response.read()
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
            return data
        except (OSError, ValueError):
            return None

    def _ready(self, key, future) -> None:
        self.pending.discard(key)
        try:
            self.ready[key] = future.result()
        except Exception:
            self.ready[key] = None

    def _consume_ready(self) -> None:
        ready, self.ready = self.ready, {}
        for key, data in ready.items():
            if not data:
                continue
            try:
                image = Image.open(BytesIO(data)).convert("RGB")
                self.images[key] = ImageTk.PhotoImage(image)
            except OSError:
                continue

    def close(self) -> None:
        self.executor.shutdown(wait=False, cancel_futures=True)
