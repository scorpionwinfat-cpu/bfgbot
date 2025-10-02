import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from zcb_client import _find_first, OGRN_KEYS


def test_find_first_prefers_matching_segment_over_date():
    body = {
        "egrip": {
            "ogrn": "123456789012345",
            "ogrn_date": "2020-01-01",
        }
    }

    assert _find_first(body, OGRN_KEYS) == "123456789012345"


def test_find_first_matches_egrip_ogrnip():
    body = {
        "body": {
            "egrip": {
                "ogrnip": "314159265358979",
                "ogrn_date": "2030-12-31",
            }
        }
    }

    assert _find_first(body, OGRN_KEYS) == "314159265358979"
