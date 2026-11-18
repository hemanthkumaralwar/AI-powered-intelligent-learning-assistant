import copy
import json
from collections.abc import Callable
from pathlib import Path

import pytest

REAL_COURSE = (
    Path(__file__).resolve().parents[2] / "eval" / "materials" / "javascript-beginner.json"
)


@pytest.fixture(scope="session")
def real_course_bytes() -> bytes:
    return REAL_COURSE.read_bytes()


@pytest.fixture
def small_course(real_course_bytes: bytes) -> dict:
    """The real course trimmed to 2 modules x 2 lessons, with ids made distinct."""
    course = copy.deepcopy(json.loads(real_course_bytes))
    course["course"]["courseId"] = "small-js"
    modules = course["course"]["modules"][:2]
    for m_index, module in enumerate(modules, 1):
        module["moduleId"] = f"small-js-mod-{m_index}"
        module["lessons"] = module["lessons"][:2]
        for l_index, lesson in enumerate(module["lessons"], 1):
            lesson["lessonId"] = f"small-js-mod-{m_index}-lesson-{l_index}"
    course["course"]["modules"] = modules
    return course


@pytest.fixture
def to_bytes() -> Callable[[dict], bytes]:
    return lambda data: json.dumps(data).encode()
