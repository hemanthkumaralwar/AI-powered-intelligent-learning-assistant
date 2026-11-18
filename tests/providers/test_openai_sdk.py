import httpx2
import openai
import pytest

from app.providers.openai_sdk import parse_retry_after

HTTP_REQUEST = httpx2.Request("POST", "https://api.openai.com/v1/chat/completions")


def rate_limit_error(headers: dict) -> openai.RateLimitError:
    response = httpx2.Response(429, headers=headers, request=HTTP_REQUEST)
    return openai.RateLimitError("error", response=response, body=None)


@pytest.mark.parametrize(("header", "expected"), [("2.5", 2.5), ("soon", None), (None, None)])
def test_parse_retry_after(header: str | None, expected: float | None) -> None:
    headers = {"retry-after": header} if header is not None else {}

    assert parse_retry_after(rate_limit_error(headers)) == expected
