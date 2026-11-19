from typing import Any

import pytest
from google.genai import errors

from app.providers.errors import RateLimitedError
from app.providers.gemini_sdk import is_daily_quota, map_api_error, parse_retry_delay


@pytest.mark.parametrize(
    "details",
    [
        None,
        "text body",
        {"error": "flat"},
        {"error": {"details": "not a list"}},
        {"error": {"details": [{"@type": "type.googleapis.com/google.rpc.RetryInfo"}]}},
        {
            "error": {
                "details": [
                    {"@type": "type.googleapis.com/google.rpc.RetryInfo", "retryDelay": "soon"}
                ]
            }
        },
    ],
)
def test_parse_retry_delay_tolerates_unexpected_shapes(details: Any) -> None:
    assert parse_retry_delay(details) is None


def test_parse_retry_delay_reads_fractional_seconds() -> None:
    details = {
        "error": {
            "details": [{"@type": "type.googleapis.com/google.rpc.RetryInfo", "retryDelay": "1.5s"}]
        }
    }

    assert parse_retry_delay(details) == 1.5


def quota_body(quota_id: str) -> dict:
    return {
        "error": {
            "details": [
                {
                    "@type": "type.googleapis.com/google.rpc.QuotaFailure",
                    "violations": [{"quotaId": quota_id}],
                }
            ]
        }
    }


@pytest.mark.parametrize(
    ("details", "daily"),
    [
        (quota_body("EmbedContentRequestsPerDayPerUserPerProjectPerModel-FreeTier"), True),
        (quota_body("EmbedContentRequestsPerMinutePerUserPerProjectPerModel-FreeTier"), False),
        ({"error": {"details": [{"@type": "x.QuotaFailure", "violations": "junk"}]}}, False),
        ({"error": {"details": "not a list"}}, False),
        (None, False),
    ],
)
def test_daily_quota_is_recognised(details, daily: bool) -> None:
    assert is_daily_quota(details) is daily


def test_429_carries_the_daily_flag() -> None:
    error = map_api_error(errors.ClientError(429, quota_body("RequestsPerDayPerProject")))

    assert isinstance(error, RateLimitedError) and error.daily is True
