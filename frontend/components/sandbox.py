"""The DOM sandbox page for JavaScript exercises that touch the page (pure functions).

Student code never reaches the server for these: it runs in the student's own browser,
in an iframe sandboxed to `allow-scripts` only (an opaque origin with no access to the
Streamlit page, cookies or storage) and under a CSP with no network access. See
`dom_sandbox.html` for the page itself.
"""

import json
import re
from pathlib import Path

TEMPLATE = Path(__file__).with_name("dom_sandbox.html")
PLACEHOLDER = "__SANDBOX_PAYLOAD__"

# Code that needs a page: it cannot run on the server's Node.js (no `document` there).
_DOM_USE = re.compile(r"\b(document|window)\s*\.|\baddEventListener\s*\(")
_SELECTOR_CALL = re.compile(
    r"""(?:querySelector(?:All)?|closest|matches)\(\s*(['"`])(.+?)\1"""
    r"""|getElementById\(\s*(['"`])([\w-]+)\3"""
    r"""|getElementsByClassName\(\s*(['"`])([\w-]+)\5"""
)
_COMPOUND = re.compile(r"^([a-zA-Z][\w-]*)?((?:[#.][\w-]+)*)$")
# Tags worth creating for a bare tag selector; anything else becomes a <div>.
_TAGS = {
    "button",
    "input",
    "textarea",
    "select",
    "form",
    "ul",
    "ol",
    "li",
    "p",
    "span",
    "h1",
    "h2",
    "h3",
    "div",
    "section",
    "article",
    "nav",
    "main",
    "a",
    "img",
    "label",
}
MAX_ELEMENTS = 20
MAX_HTML_CHARS = 20_000


def needs_dom(code: str) -> bool:
    return bool(_DOM_USE.search(code))


def scaffold(code: str) -> list[dict[str, object]]:
    """Empty elements for the ids, classes and tags the code looks up, so the course's
    DOM exercises (which ship no HTML) have something to work on."""
    elements: list[dict[str, object]] = []
    seen: set[tuple] = set()
    for match in _SELECTOR_CALL.finditer(code):
        if match.group(4):
            selectors = [f"#{match.group(4)}"]
        elif match.group(6):
            selectors = [f".{match.group(6)}"]
        else:
            selectors = re.split(r"[\s,>+~]+", match.group(2))
        for selector in selectors:
            element = _element(selector)
            key = (element["tag"], element["id"], tuple(element["classes"])) if element else None
            if element and key not in seen:
                seen.add(key)
                elements.append(element)
    return elements[:MAX_ELEMENTS]


def sandbox_page(code: str, html: str = "") -> str:
    """The full page for `st.components.v1.html`. The payload is JSON with `<`, `>` and
    `&` escaped, so nothing in the code or markup can close the template's script."""
    payload = json.dumps({"code": code, "html": html[:MAX_HTML_CHARS], "scaffold": scaffold(code)})
    safe = payload.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    return TEMPLATE.read_text(encoding="utf-8").replace(PLACEHOLDER, safe)


def _element(selector: str) -> dict[str, object] | None:
    match = _COMPOUND.match(selector.strip())
    if not match or not selector.strip():
        return None
    tag, rest = match.group(1), match.group(2)
    ids = re.findall(r"#([\w-]+)", rest)
    classes = re.findall(r"\.([\w-]+)", rest)
    if not tag and not ids and not classes:
        return None
    tag = tag.lower() if tag and tag.lower() in _TAGS else "div"
    return {"tag": tag, "id": ids[0] if ids else None, "classes": classes}
