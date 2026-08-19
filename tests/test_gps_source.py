import unittest

from src.aegis.gps_source import GpsFix, parse_tpv


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


if __name__ == "__main__":
    unittest.main()
