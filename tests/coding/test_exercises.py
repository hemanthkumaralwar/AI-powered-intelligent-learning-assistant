from app.coding.exercises import matches_exercise

BUG_HUNT = "const counter = 0;\ncounter = counter + 1;\nconsole.log(counter);"


def test_exact_and_reformatted_copies_match() -> None:
    assert matches_exercise(BUG_HUNT, [BUG_HUNT])
    assert matches_exercise(
        "const counter=0;   counter = counter + 1;\n\n console.log(counter);", [BUG_HUNT]
    )


def test_lightly_renamed_copy_matches() -> None:
    renamed = BUG_HUNT.replace("counter", "count")

    assert matches_exercise(renamed, [BUG_HUNT])


def test_unrelated_code_does_not_match() -> None:
    other = "function greet(name) {\n  return `Hello, ${name}!`;\n}\nconsole.log(greet('Ada'));"

    assert not matches_exercise(other, [BUG_HUNT])


def test_no_exercises_or_blank_ones_never_match() -> None:
    assert not matches_exercise(BUG_HUNT, [])
    assert not matches_exercise(BUG_HUNT, ["   ", ""])
