import unittest
from unittest.mock import patch
import socket
import time

from src.aegis.gps_source import GpsFix, GpsdSource, parse_tpv


class _FakeGpsdSocket:
    def __init__(self) -> None:
        self.closed = False
        self.sent = b""

    def settimeout(self, _timeout: float) -> None:
        pass

    def sendall(self, data: bytes) -> None:
        self.sent += data

    def recv(self, _size: int) -> bytes:
        time.sleep(0.005)
        if self.closed:
            return b""
        raise socket.timeout

    def shutdown(self, _how: int) -> None:
        self.closed = True

    def close(self) -> None:
        self.closed = True


class GpsSourceTests(unittest.TestCase):
    def test_parses_usable_tpv_fix(self) -> None:
        self.assertEqual(
            parse_tpv({"class": "TPV", "mode": 3, "lat": 41.1, "lon": -87.2,
                       "altMSL": 190.5, "speed": 2.4, "track": 12.0}),
            GpsFix(41.1, -87.2, 190.5, 2.4, 12.0),
        )

    def test_ignores_reports_without_position_fix(self) -> None:
        self.assertIsNone(parse_tpv({"class": "TPV", "mode": 1}))
        self.assertIsNone(parse_tpv({"class": "SKY", "lat": 41, "lon": -87}))

    def test_rejects_invalid_coordinates(self) -> None:
        self.assertIsNone(parse_tpv({"class": "TPV", "mode": 2, "lat": 91, "lon": 0}))

    def test_source_can_stop_and_start_a_fresh_session(self) -> None:
        connections = [_FakeGpsdSocket(), _FakeGpsdSocket()]
        with patch("src.aegis.gps_source.socket.create_connection",
                   side_effect=connections) as connect:
            source = GpsdSource()
            source.start()
            source.stop()
            source.start()
            source.stop()

        self.assertEqual(connect.call_count, 2)
        self.assertTrue(all(connection.closed for connection in connections))
        self.assertTrue(all(b'"enable":true' in connection.sent
                            for connection in connections))


if __name__ == "__main__":
    unittest.main()
