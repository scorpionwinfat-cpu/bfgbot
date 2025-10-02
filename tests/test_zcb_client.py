from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parents[1]))

import zcb_client as zcb


def test_find_first_uses_egrip_fio_full_for_name():
    body = {"egrip": {"fio": {"full": "Иванов Иван Иванович"}}}

    assert zcb._find_first(body, zcb.NAME_KEYS) == "Иванов Иван Иванович"


def test_find_first_builds_name_from_structured_fio():
    body = {
        "egrip": {
            "fio": {
                "last": "Иванов",
                "first": "Иван",
                "middle": "Иванович",
            }
        }
    }

    assert zcb._find_first(body, zcb.NAME_KEYS) == "Иванов Иван Иванович"
