import unittest

from src.aegis.adsb_source import parse_aircraft_json
from src.aegis.online_map import geo_to_world


class AdsbSourceTests(unittest.TestCase):
    def test_parses_positioned_and_unpositioned_aircraft(self) -> None:
        aircraft = parse_aircraft_json({"aircraft": [
            {"hex": "abc123", "flight": " UAL12 ", "lat": 41.9,
             "lon": -87.9, "alt_baro": 12000, "gs": 280.5,
             "track": 90, "messages": 42, "seen": 0.3},
            {"hex": "def456", "seen": 2.0},
        ]})
        self.assertEqual(aircraft[0].icao, "ABC123")
        self.assertEqual(aircraft[0].flight, "UAL12")
        self.assertTrue(aircraft[0].has_position)
        self.assertFalse(aircraft[1].has_position)

    def test_web_mercator_places_east_to_the_right(self) -> None:
        origin_x, origin_y = geo_to_world(0, 0, 4)
        east_x, east_y = geo_to_world(0, 1, 4)
        self.assertGreater(east_x, origin_x)
        self.assertAlmostEqual(east_y, origin_y)


if __name__ == "__main__":
    unittest.main()
