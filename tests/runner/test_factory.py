import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.runner.factory import build_code_runner_service
from app.runner.fake import FakeRunner
from app.runner.godbolt import GodboltRunner, GodboltSharer
from app.runner.judge0 import Judge0Runner

pytestmark = pytest.mark.anyio


def settings(**overrides) -> Settings:
    return Settings(_env_file=None, **overrides)


async def test_default_is_judge0_then_godbolt_with_godbolt_sharing() -> None:
    service = build_code_runner_service(settings())

    assert [type(r) for r in service._runners] == [Judge0Runner, GodboltRunner]
    assert isinstance(service._sharer, GodboltSharer)
    assert str(service._runners[0]._client.base_url) == "https://ce.judge0.com"
    assert service._runners[0]._client.headers["user-agent"].startswith("ArchintX")
    await service.aclose()


async def test_runner_order_and_fake_come_from_settings() -> None:
    service = build_code_runner_service(settings(code_runners="fake, godbolt"))

    assert [type(r) for r in service._runners] == [FakeRunner, GodboltRunner]
    await service.aclose()


def test_fake_runner_refused_in_production() -> None:
    with pytest.raises(ValidationError, match="CODE_RUNNERS=fake is not allowed"):
        settings(environment="production", code_runners="judge0,fake")


@pytest.mark.parametrize("value", ["", " , ", "wandbox"])
def test_runner_list_must_name_known_runners(value: str) -> None:
    with pytest.raises(ValidationError):
        settings(code_runners=value)
