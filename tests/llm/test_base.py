import pytest
from pydantic import ValidationError

from app.llm.base import ChatMessage, GenerationOptions


def test_message_rejects_empty_content() -> None:
    with pytest.raises(ValidationError):
        ChatMessage(role="user", content="")


def test_message_rejects_unknown_role() -> None:
    with pytest.raises(ValidationError):
        ChatMessage(role="tool", content="hi")


@pytest.mark.parametrize(
    "kwargs",
    [
        {"temperature": -0.1},
        {"temperature": 2.1},
        {"max_output_tokens": 0},
        {"max_output_tokens": 8193},
    ],
)
def test_options_reject_out_of_range_values(kwargs: dict) -> None:
    with pytest.raises(ValidationError):
        GenerationOptions(**kwargs)


def test_options_accept_boundaries() -> None:
    options = GenerationOptions(temperature=2.0, max_output_tokens=8192)

    assert options.temperature == 2.0
    assert options.max_output_tokens == 8192
