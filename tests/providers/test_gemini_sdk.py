from typing import Any

import pytest

from app.providers.gemini_sdk import parse_retry_delay


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
