"""Geocoder ranking tests.

Autocomplete is the first thing a reviewer touches, and the provider's raw
ordering is not useful for trip planning: a bare city query used to come back as
state-level administrative areas (typing "Nashville" offered "TN", which then
geocodes to the middle of Tennessee). These tests pin the corrected behaviour.
"""

from django.test import SimpleTestCase

from eld.services.geocoding import Geocoder, Place, _rank_places


def _photon(name, osm_value, state, *, city=None, lat=36.16, lng=-86.78, countrycode="us"):
    """A minimal Photon feature, shaped like the real payload."""
    props = {
        "name": name,
        "osm_key": "place",
        "osm_value": osm_value,
        "state": state,
        "state_code": state,
        "countrycode": countrycode,
        "country": "United States",
    }
    if city:
        props["city"] = city
    return {"geometry": {"coordinates": [lng, lat]}, "properties": props}


def _place(label, city, state, rank):
    """A candidate with only the fields the ranking cares about."""
    return Place(label=label, lat=0.0, lng=0.0, city=city, state=state, rank=rank)


class PhotonFeatureTests(SimpleTestCase):
    def setUp(self):
        self.geocoder = Geocoder()

    def test_a_city_match_recovers_its_name_from_the_feature(self):
        """Photon leaves `city` empty when the match *is* the city."""
        place = self.geocoder._from_photon(_photon("Nashville", "city", "TN"))
        self.assertIsNotNone(place)
        self.assertEqual(place.city, "Nashville")
        self.assertEqual(place.label, "Nashville, TN")
        self.assertEqual(place.short_label, "Nashville, TN")
        self.assertFalse(place.weak)

    def test_a_state_match_is_never_promoted_to_a_city(self):
        place = self.geocoder._from_photon(_photon("Tennessee", "state", "TN"))
        self.assertIsNotNone(place)
        self.assertEqual(place.city, "")
        # Photon reports the state's own `name` as the code.
        self.assertEqual(place.label, "TN")

    def test_results_outside_north_america_are_dropped(self):
        feature = _photon("Paris", "city", "TX", countrycode="fr")
        self.assertIsNone(self.geocoder._from_photon(feature))


class RankingTests(SimpleTestCase):
    def test_a_real_city_outranks_a_state_row_and_the_state_row_is_dropped(self):
        ranked = _rank_places(
            [
                _place("TN", "", "TN", 10),
                _place("Nashville, TN", "Nashville", "TN", 100),
            ],
            "Nashville",
        )
        self.assertEqual(ranked[0].short_label, "Nashville, TN")
        self.assertEqual(len(ranked), 1, "the unusable state row should be dropped")

    def test_the_state_in_the_query_breaks_a_tie_between_same_named_cities(self):
        places = [
            _place("Nashville, IL", "Nashville", "IL", 100),
            _place("Nashville, TN", "Nashville", "TN", 100),
        ]
        self.assertEqual(_rank_places(places, "Nashville, TN")[0].state, "TN")

    def test_an_exact_name_match_beats_a_longer_one(self):
        places = [
            _place("Nashville-Davidson, TN", "Nashville-Davidson", "TN", 100),
            _place("Nashville, TN", "Nashville", "TN", 100),
        ]
        self.assertEqual(_rank_places(places, "Nashville")[0].city, "Nashville")

    def test_administrative_results_survive_when_nothing_better_exists(self):
        places = [_place("WI", "", "WI", 10)]
        self.assertEqual(len(_rank_places(places, "Wisconsin")), 1)
