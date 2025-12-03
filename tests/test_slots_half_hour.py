from datetime import datetime, time, timedelta, timezone

from bot.utils.time_utils import generate_half_hour_slots


def conflict_exists(st_utc, et_utc, busy_utc):
    return any((st_utc < b_end and et_utc > b_start) for b_start, b_end in busy_utc)


def to_utc_local(dt: datetime):
    # Treat naive as local Europe/Saratov (+4) for test; convert to UTC
    # For simplicity in unit test, assume fixed offset +4
    return (dt - timedelta(hours=4)).replace(tzinfo=timezone.utc)


def test_half_hour_slots_generation():
    day = datetime(2025, 12, 3)
    starts = generate_half_hour_slots(time(10, 0), time(12, 0), day)
    assert starts[0] == datetime(2025, 12, 3, 10, 0)
    assert starts[1] == datetime(2025, 12, 3, 10, 30)
    assert starts[2] == datetime(2025, 12, 3, 11, 0)
    assert starts[3] == datetime(2025, 12, 3, 11, 30)
    assert len(starts) == 4
    assert starts[-1] == datetime(2025, 12, 3, 11, 30)


def test_conflict_with_30_min_service():
    day = datetime(2025, 12, 3)
    # Existing appointment 11:30-12:00 (local), convert to UTC
    busy_local = [(datetime(2025, 12, 3, 11, 30), datetime(2025, 12, 3, 12, 0))]
    busy_utc = [(to_utc_local(s), to_utc_local(e)) for s, e in busy_local]

    # Candidate 30-min service at 11:30
    st = datetime(2025, 12, 3, 11, 30)
    et = st + timedelta(minutes=30)
    st_utc, et_utc = to_utc_local(st), to_utc_local(et)
    assert conflict_exists(st_utc, et_utc, busy_utc) is True

    # Candidate 30-min at 11:00 should be free
    st = datetime(2025, 12, 3, 11, 0)
    et = st + timedelta(minutes=30)
    st_utc, et_utc = to_utc_local(st), to_utc_local(et)
    assert conflict_exists(st_utc, et_utc, busy_utc) is False


def test_conflict_with_60_min_service():
    day = datetime(2025, 12, 3)
    busy_local = [(datetime(2025, 12, 3, 11, 30), datetime(2025, 12, 3, 12, 0))]
    busy_utc = [(to_utc_local(s), to_utc_local(e)) for s, e in busy_local]

    # Candidate 60-min service starting at 11:00 overlaps 11:30 existing
    st = datetime(2025, 12, 3, 11, 0)
    et = st + timedelta(minutes=60)
    st_utc, et_utc = to_utc_local(st), to_utc_local(et)
    assert conflict_exists(st_utc, et_utc, busy_utc) is True

    # Candidate 60-min at 10:30 should be free within 10:30-11:30
    st = datetime(2025, 12, 3, 10, 30)
    et = st + timedelta(minutes=60)
    st_utc, et_utc = to_utc_local(st), to_utc_local(et)
    assert conflict_exists(st_utc, et_utc, busy_utc) is False
