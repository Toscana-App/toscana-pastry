from datetime import UTC, date, datetime, timedelta

import pytest

from domain.dashboard import (
    DEFAULT_PERIOD_DAYS,
    MAX_PERIOD_DAYS,
    DashboardPeriod,
    Granularity,
    InvalidDashboardPeriodError,
    bucket_start,
    bucket_starts,
    local_today,
    period_bounds,
)


class TestDashboardPeriod:
    def test_valid_period_keeps_bounds(self):
        period = DashboardPeriod(date(2026, 1, 1), date(2026, 1, 31))
        assert period.date_from == date(2026, 1, 1)
        assert period.date_to == date(2026, 1, 31)

    def test_single_day_period_is_valid(self):
        period = DashboardPeriod(date(2026, 1, 1), date(2026, 1, 1))
        assert period.days == 1

    def test_from_after_to_is_rejected(self):
        with pytest.raises(InvalidDashboardPeriodError) as exc:
            DashboardPeriod(date(2026, 2, 1), date(2026, 1, 1))
        assert exc.value.code == "date_from_after_date_to"

    def test_span_over_max_is_rejected(self):
        start = date(2025, 1, 1)
        end = date.fromordinal(start.toordinal() + MAX_PERIOD_DAYS)
        with pytest.raises(InvalidDashboardPeriodError) as exc:
            DashboardPeriod(start, end)
        assert exc.value.code == "period_too_long"

    def test_span_exactly_max_is_valid(self):
        start = date(2025, 1, 1)
        end = date.fromordinal(start.toordinal() + MAX_PERIOD_DAYS - 1)
        assert DashboardPeriod(start, end).days == MAX_PERIOD_DAYS

    def test_resolve_defaults_to_last_thirty_days_inclusive_of_today(self):
        today = date(2026, 3, 31)
        period = DashboardPeriod.resolve(None, None, today)
        assert period.date_to == today
        assert period.days == DEFAULT_PERIOD_DAYS
        assert period.date_from == date(2026, 3, 2)

    def test_resolve_only_date_to_goes_back_default_days(self):
        period = DashboardPeriod.resolve(None, date(2026, 1, 31), date(2026, 6, 1))
        assert period.date_to == date(2026, 1, 31)
        assert period.days == DEFAULT_PERIOD_DAYS

    def test_resolve_only_date_from_ends_today(self):
        period = DashboardPeriod.resolve(date(2026, 3, 1), None, date(2026, 3, 10))
        assert period.date_from == date(2026, 3, 1)
        assert period.date_to == date(2026, 3, 10)

    def test_resolve_explicit_bounds(self):
        period = DashboardPeriod.resolve(
            date(2026, 1, 1), date(2026, 1, 5), date(2026, 6, 1)
        )
        assert (period.date_from, period.date_to) == (date(2026, 1, 1), date(2026, 1, 5))

    def test_resolve_invalid_explicit_bounds_rejected(self):
        with pytest.raises(InvalidDashboardPeriodError):
            DashboardPeriod.resolve(date(2026, 2, 1), date(2026, 1, 1), date(2026, 6, 1))


class TestBusinessDay:
    def test_local_today_is_previous_day_before_03_utc(self):
        now = datetime(2026, 5, 10, 2, 30, tzinfo=UTC)
        assert local_today(now) == date(2026, 5, 9)

    def test_local_today_matches_utc_date_from_03_utc(self):
        now = datetime(2026, 5, 10, 3, 0, tzinfo=UTC)
        assert local_today(now) == date(2026, 5, 10)

    def test_period_bounds_start_at_local_midnight(self):
        start, end = period_bounds(DashboardPeriod(date(2026, 5, 10), date(2026, 5, 10)))
        assert start == datetime(2026, 5, 10, 3, 0, tzinfo=UTC)
        assert end == datetime(2026, 5, 11, 3, 0, tzinfo=UTC)

    def test_period_bounds_are_timezone_aware(self):
        start, end = period_bounds(DashboardPeriod(date(2026, 5, 1), date(2026, 5, 31)))
        assert start.utcoffset() is not None and end.utcoffset() is not None
        assert end - start == timedelta(days=31)


class TestBuckets:
    def test_day_bucket_is_the_date(self):
        assert bucket_start(date(2026, 5, 13), Granularity.DAY) == date(2026, 5, 13)

    def test_week_bucket_is_monday(self):
        assert bucket_start(date(2026, 5, 13), Granularity.WEEK) == date(2026, 5, 11)

    def test_month_bucket_is_first_day(self):
        assert bucket_start(date(2026, 5, 13), Granularity.MONTH) == date(2026, 5, 1)

    def test_day_buckets_cover_every_day(self):
        period = DashboardPeriod(date(2026, 5, 1), date(2026, 5, 4))
        assert bucket_starts(period, Granularity.DAY) == [
            date(2026, 5, 1),
            date(2026, 5, 2),
            date(2026, 5, 3),
            date(2026, 5, 4),
        ]

    def test_week_buckets_start_on_monday_of_first_day(self):
        period = DashboardPeriod(date(2026, 5, 13), date(2026, 5, 26))
        assert bucket_starts(period, Granularity.WEEK) == [
            date(2026, 5, 11),
            date(2026, 5, 18),
            date(2026, 5, 25),
        ]

    def test_month_buckets_cross_year_boundary(self):
        period = DashboardPeriod(date(2025, 11, 20), date(2026, 2, 3))
        assert bucket_starts(period, Granularity.MONTH) == [
            date(2025, 11, 1),
            date(2025, 12, 1),
            date(2026, 1, 1),
            date(2026, 2, 1),
        ]
