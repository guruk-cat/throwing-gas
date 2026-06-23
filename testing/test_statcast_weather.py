import datetime as dt
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent / 'main'))
from statcast_to_config import _reshape_height, _pick_hour


def test_reshape_height():
    assert _reshape_height("""5' 10\"""") == "5 ft 10 in"
    assert _reshape_height("""6' 4\"""") == "6 ft 4 in"
    assert _reshape_height("6' 0") == "6 ft 0 in"


def test_pick_hour():
    hourly = {
        'time': ['2026-04-24T21:00', '2026-04-24T22:00', '2026-04-24T23:00'],
        'temperature_2m':    [14.0, 15.1, 16.0],
        'surface_pressure':  [1011.0, 1012.0, 1013.0],
        'relative_humidity_2m': [70, 68, 66],
    }
    # 22:05 UTC floors to the 22:00 hour.
    when = dt.datetime(2026, 4, 24, 22, 5, tzinfo=dt.timezone.utc)
    assert _pick_hour(hourly, when) == (15.1, 1012.0, 68)


if __name__ == '__main__':
    test_reshape_height()
    test_pick_hour()
    print("ok")
