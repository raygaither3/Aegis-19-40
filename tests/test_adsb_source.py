import unittest

from src.aegis.adsb_source import classify_aircraft, parse_aircraft_json
from src.aegis.online_map import geo_to_world, world_to_geo


class AdsbSourceTests(unittest.TestCase):
    def test_web_mercator_round_trip(self) -> None:
        world = geo_to_world(41.881832, -87.623177, 11)
        latitude, longitude = world_to_geo(*world, 11)
        self.assertAlmostEqual(latitude, 41.881832)
        self.assertAlmostEqual(longitude, -87.623177)

    def test_parses_positioned_and_unpositioned_aircraft(self) -> None:
        aircraft = parse_aircraft_json({"aircraft": [
            {"hex": "abc123", "flight": " UAL12 ", "r": "N12345",
             "t": "B739", "ownOp": "United Airlines", "lat": 41.9,
             "lon": -87.9, "alt_baro": 12000, "gs": 280.5,
             "track": 90, "messages": 42, "seen": 0.3},
            {"hex": "def456", "seen": 2.0},
        ]})
        self.assertEqual(aircraft[0].icao, "ABC123")
        self.assertEqual(aircraft[0].flight, "UAL12")
        self.assertEqual(aircraft[0].registration, "N12345")
        self.assertEqual(aircraft[0].model, "Boeing 737-900/900ER")
        self.assertEqual(aircraft[0].aircraft_class, "COMMERCIAL (LIKELY)")
        self.assertTrue(aircraft[0].has_position)
        self.assertFalse(aircraft[1].has_position)

    def test_military_database_flag_takes_priority(self) -> None:
        item = {"hex": "ae1234", "t": "B738", "flight": "RCH123", "dbFlags": 1}
        self.assertEqual(classify_aircraft(item), "MILITARY")

    def test_web_mercator_places_east_to_the_right(self) -> None:
        origin_x, origin_y = geo_to_world(0, 0, 4)
        east_x, east_y = geo_to_world(0, 1, 4)
        self.assertGreater(east_x, origin_x)
        self.assertAlmostEqual(east_y, origin_y)


if __name__ == "__main__":
    unittest.main()
