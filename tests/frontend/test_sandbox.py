"""DOM sandbox page: detection, generated elements, and that student code stays data."""

import json
import re

import pytest

from components.sandbox import PLACEHOLDER, TEMPLATE, needs_dom, sandbox_page, scaffold


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        ("document.querySelector('.x')", True),
        ("window . alert(1)", True),
        ("button.addEventListener('click', f)", True),
        ("console.log([1, 2].map(n => n * 2))", False),
        ("const documentation = 1", False),
    ],
)
def test_needs_dom(code: str, expected: bool) -> None:
    assert needs_dom(code) is expected


def test_scaffold_creates_the_elements_the_code_looks_up() -> None:
    code = """
    const out = document.querySelector('.output');
    const btn = document.getElementById("save");
    document.querySelectorAll(`ul.list > li`);
    document.getElementsByClassName('card');
    document.querySelector('.output');  // duplicate
    document.querySelector('[data-x]');  // attribute selector: skipped
    """

    elements = scaffold(code)

    assert elements == [
        {"tag": "div", "id": None, "classes": ["output"]},
        {"tag": "div", "id": "save", "classes": []},
        {"tag": "ul", "id": None, "classes": ["list"]},
        {"tag": "li", "id": None, "classes": []},
        {"tag": "div", "id": None, "classes": ["card"]},
    ]


def test_scaffold_is_capped() -> None:
    code = "\n".join(f"document.querySelector('.c{n}')" for n in range(50))

    assert len(scaffold(code)) == 20


def test_unknown_tags_become_divs() -> None:
    assert scaffold("document.querySelector('marquee#m')") == [
        {"tag": "div", "id": "m", "classes": []}
    ]


def test_code_cannot_break_out_of_the_payload_script() -> None:
    code = "console.log('</script><script>alert(1)</script>') && a < b"
    html = "<p>hi</p>"

    page = sandbox_page(code, html)

    assert "</script><script>alert(1)" not in page
    raw = re.search(r"var payload = (\{.*?\});", page, re.DOTALL).group(1)
    assert json.loads(raw) == {"code": code, "html": html, "scaffold": []}


def test_the_template_isolates_student_code() -> None:
    template = TEMPLATE.read_text(encoding="utf-8")

    (iframe,) = re.findall(r"<iframe[^>]*>", template)

    assert template.count(PLACEHOLDER) == 1
    assert re.search(r'\bsandbox="allow-scripts"', iframe)  # exactly scripts, nothing more
    assert "default-src \\'none\\'" in template
    assert "event.source !== frame.contentWindow" in template
    assert "event.source !== parent" in template
