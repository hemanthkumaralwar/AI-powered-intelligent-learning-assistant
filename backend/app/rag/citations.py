"""Find the source markers ([1], [2]...) in a reply and drop ones that match no source."""

import re

# Code is left untouched: `arr[0]` or `matrix[2]` are indexes, not citations. A fence
# the model never closed runs to the end of the reply.
_CODE = re.compile(r"(```.*?(?:```|\Z)|`[^`\n]*`)", re.DOTALL)
_MARKER = re.compile(r"\[(\d{1,3})\]")


def resolve_markers(text: str, source_count: int) -> tuple[str, list[int]]:
    """Return `text` without invalid markers, plus the valid source numbers in first-cited
    order. Only prose is scanned; code spans and fenced blocks are kept as written."""
    cited: list[int] = []

    def check(match: re.Match[str]) -> str:
        number = int(match.group(1))
        if not 1 <= number <= source_count:
            return ""
        if number not in cited:
            cited.append(number)
        return match.group(0)

    parts = _CODE.split(text)
    # re.split with one capturing group alternates prose (even) and code (odd).
    parts[::2] = [_MARKER.sub(check, prose) for prose in parts[::2]]
    return "".join(parts), cited
