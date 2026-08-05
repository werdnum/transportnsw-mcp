"""Offline tests for Sydney timezone conversion in api.py.

These tests do not hit the network and do not require OPEN_TRANSPORT_API_KEY.
`requests.get` is monkeypatched wherever a function makes an HTTP call, and
`datetime.datetime.now()` is frozen (by monkeypatching the `datetime` module's
`datetime` attribute, which api.py's function-local `from datetime import
datetime` picks up on every call) so tests are deterministic regardless of
the machine's system timezone or wall-clock time.
"""
import sys
import os
import datetime as datetime_module
from datetime import timezone
from unittest.mock import Mock

import pytest

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import api
from api import (
    SYDNEY_TZ,
    _format_api_time,
    _parse_api_time,
    _format_journeys,
    get_departure_monitor,
    plan_trip,
)


class _FrozenDateTime(datetime_module.datetime):
    """datetime.datetime subclass whose now() returns a fixed, injected instant."""

    _frozen = None

    @classmethod
    def now(cls, tz=None):
        frozen = cls._frozen
        if tz is not None:
            return frozen.astimezone(tz)
        return frozen.replace(tzinfo=None)


@pytest.fixture
def freeze_time():
    """Freeze `datetime.datetime.now()` as observed by api.py.

    api.py imports `datetime` locally inside each function (`from datetime
    import datetime, ...`), so patching the `datetime` module's `datetime`
    attribute here is picked up on the next call without needing to patch
    api.py's namespace directly.
    """
    original = datetime_module.datetime

    def _freeze(frozen_utc):
        _FrozenDateTime._frozen = frozen_utc
        datetime_module.datetime = _FrozenDateTime

    yield _freeze
    datetime_module.datetime = original
    _FrozenDateTime._frozen = None


def _mock_response(json_data, status_code=200):
    resp = Mock()
    resp.status_code = status_code
    resp.json.return_value = json_data
    resp.text = ''
    return resp


# ---------------------------------------------------------------------------
# _format_api_time / _parse_api_time
# ---------------------------------------------------------------------------

def test_format_api_time_winter_aest():
    """Non-DST period: Sydney is AEST = UTC+10."""
    assert _format_api_time('2026-07-15T04:30:00Z') == '2026-07-15 14:30'


def test_format_api_time_summer_aedt():
    """DST period: Sydney is AEDT = UTC+11."""
    assert _format_api_time('2026-01-15T04:30:00Z') == '2026-01-15 15:30'


def test_format_api_time_date_rollover():
    """A late-UTC timestamp should roll over to the next Sydney calendar date."""
    # 2026-01-15T14:30:00Z + 11h (AEDT) = 2026-01-16 01:30 local
    assert _format_api_time('2026-01-15T14:30:00Z') == '2026-01-16 01:30'


def test_format_api_time_empty_input():
    assert _format_api_time('') == ''
    assert _format_api_time(None) == ''


def test_parse_api_time_empty_input():
    assert _parse_api_time('') is None
    assert _parse_api_time(None) is None


def test_parse_api_time_is_utc_aware():
    parsed = _parse_api_time('2026-07-15T04:30:00Z')
    assert parsed is not None
    assert parsed.tzinfo == timezone.utc
    assert (parsed.year, parsed.month, parsed.day, parsed.hour, parsed.minute) == (2026, 7, 15, 4, 30)


# ---------------------------------------------------------------------------
# get_departure_monitor
# ---------------------------------------------------------------------------

def test_departure_monitor_local_display_and_raw_passthrough(monkeypatch, freeze_time):
    # Freeze "now" during AEST (winter): 2026-07-15T03:00:00Z == 13:00 Sydney
    freeze_time(datetime_module.datetime(2026, 7, 15, 3, 0, 0, tzinfo=timezone.utc))

    captured = {}

    def fake_get(url, params=None, headers=None):
        captured['params'] = params
        return _mock_response({
            'stopEvents': [
                {
                    'departureTimePlanned': '2026-07-15T04:30:00Z',
                    'departureTimeEstimated': '2026-07-15T04:35:00Z',
                    'transportation': {
                        'number': 'T1',
                        'description': 'Test Line',
                        'destination': {'name': 'Test Dest'},
                        'operator': {'name': 'Test Op'},
                    },
                    'location': {'name': 'Test Stop'},
                    'properties': {'WheelchairAccess': 'true'},
                }
            ]
        })

    monkeypatch.setattr(api.requests, 'get', fake_get)

    result = get_departure_monitor('123456')

    assert result is not None
    assert len(result) == 1
    stop = result[0]

    # local_departure_time must be Sydney local (+10 in winter), not UTC or host tz
    assert stop['local_departure_time'] == '2026-07-15 14:30:00'

    # Raw UTC passthrough fields must be preserved verbatim (original "...Z" strings)
    assert stop['planned_departure'] == '2026-07-15T04:30:00Z'
    assert stop['estimated_departure'] == '2026-07-15T04:35:00Z'

    # Default itdDate/itdTime must reflect Sydney local "now" (13:00), not UTC (03:00)
    assert captured['params']['itdDate'] == '20260715'
    assert captured['params']['itdTime'] == '1300'


def test_departure_monitor_default_params_date_rollover(monkeypatch, freeze_time):
    """UTC and Sydney dates differ around the UTC evening/Sydney-next-day boundary."""
    # 2026-07-14 23:00 UTC == 2026-07-15 09:00 Sydney (AEST +10)
    freeze_time(datetime_module.datetime(2026, 7, 14, 23, 0, 0, tzinfo=timezone.utc))

    captured = {}

    def fake_get(url, params=None, headers=None):
        captured['params'] = params
        return _mock_response({'stopEvents': []})

    monkeypatch.setattr(api.requests, 'get', fake_get)

    get_departure_monitor('123456')

    assert captured['params']['itdDate'] == '20260715'  # Sydney date, not '20260714' (UTC)
    assert captured['params']['itdTime'] == '0900'


def test_departure_monitor_closest_time_target_uses_sydney_now(monkeypatch, freeze_time):
    """target_time filtering must compare against Sydney local time, not host/system tz."""
    freeze_time(datetime_module.datetime(2026, 7, 15, 3, 0, 0, tzinfo=timezone.utc))  # 13:00 Sydney

    def fake_get(url, params=None, headers=None):
        return _mock_response({
            'stopEvents': [
                {
                    # Close to the requested target (14:00 Sydney)
                    'departureTimePlanned': '2026-07-15T04:05:00Z',  # 14:05 Sydney
                    'transportation': {'number': 'A'},
                    'location': {'name': 'Near'},
                },
                {
                    # Far from the requested target
                    'departureTimePlanned': '2026-07-15T09:00:00Z',  # 19:00 Sydney
                    'transportation': {'number': 'B'},
                    'location': {'name': 'Far'},
                },
            ]
        })

    monkeypatch.setattr(api.requests, 'get', fake_get)

    result = get_departure_monitor('123456', time='14:00', max_results=1)

    assert result is not None
    assert len(result) == 1
    assert result[0]['route_number'] == 'A'


# ---------------------------------------------------------------------------
# plan_trip / _execute_trip_request default params
# ---------------------------------------------------------------------------

def test_plan_trip_default_params_date_rollover(monkeypatch, freeze_time):
    # 2026-07-14 23:00 UTC == 2026-07-15 09:00 Sydney (AEST +10)
    freeze_time(datetime_module.datetime(2026, 7, 14, 23, 0, 0, tzinfo=timezone.utc))

    captured = {}

    def fake_get(url, params=None, headers=None):
        captured['params'] = params
        return _mock_response({'journeys': []})

    monkeypatch.setattr(api.requests, 'get', fake_get)

    # Use origin_type/destination_type='stop' to skip name-resolution network calls
    plan_trip('200060', '200070', origin_type='stop', destination_type='stop')

    assert captured['params']['itdDate'] == '20260715'  # Sydney date, not '20260714' (UTC)
    assert captured['params']['itdTime'] == '0900'


# ---------------------------------------------------------------------------
# plan_trip leg/journey output formatting (_format_journeys)
# ---------------------------------------------------------------------------

def test_format_journeys_converts_legs_and_journey_to_sydney_time():
    journeys = [
        {
            'legs': [
                {
                    'origin': {
                        'name': 'Central Station',
                        'departureTimePlanned': '2026-07-15T04:30:00Z',
                        'departureTimeEstimated': '2026-07-15T04:32:00Z',
                    },
                    'destination': {
                        'name': 'Town Hall Station',
                        'arrivalTimePlanned': '2026-07-15T04:40:00Z',
                        'arrivalTimeEstimated': '2026-07-15T04:41:00Z',
                    },
                    'transportation': {
                        'product': {'name': 'Train', 'class': 1},
                        'number': 'T1',
                        'destination': {'name': 'Town Hall'},
                        'operator': {'name': 'Sydney Trains'},
                    },
                    'duration': 600,
                    'isRealtimeControlled': True,
                    'stopSequence': [{}, {}, {}],
                }
            ]
        }
    ]

    result = _format_journeys(journeys)

    assert len(result) == 1
    leg = result[0]['legs'][0]

    # AEST = UTC+10 in July
    assert leg['departure_planned'] == '2026-07-15 14:30'
    assert leg['arrival_planned'] == '2026-07-15 14:40'
    assert leg['departure_estimated'] == '2026-07-15 14:32'
    assert leg['arrival_estimated'] == '2026-07-15 14:41'

    assert result[0]['depart'] == '2026-07-15 14:30'
    assert result[0]['arrive'] == '2026-07-15 14:40'


def test_format_journeys_converts_to_aedt_in_summer():
    journeys = [
        {
            'legs': [
                {
                    'origin': {
                        'name': 'Central Station',
                        'departureTimePlanned': '2026-01-15T04:30:00Z',
                    },
                    'destination': {
                        'name': 'Town Hall Station',
                        'arrivalTimePlanned': '2026-01-15T04:40:00Z',
                    },
                    'transportation': {'product': {'name': 'Train', 'class': 1}},
                    'duration': 600,
                }
            ]
        }
    ]

    result = _format_journeys(journeys)
    leg = result[0]['legs'][0]

    # AEDT = UTC+11 in January
    assert leg['departure_planned'] == '2026-01-15 15:30'
    assert leg['arrival_planned'] == '2026-01-15 15:40'
    assert result[0]['depart'] == '2026-01-15 15:30'
    assert result[0]['arrive'] == '2026-01-15 15:40'
