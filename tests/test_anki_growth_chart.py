"""Tests for the anki-cards skill's growth_chart.py.

The chart is written straight into an Anki field, so it has to parse as XML, carry
the card's numbers as visible labels, take every non-data colour from currentColor
so night mode works, and keep its arrowhead marker id to itself so two charts on
one screen don't share one."""

import importlib.util
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "assets/claude/skills/anki-cards/scripts/growth_chart.py"
NS = "{http://www.w3.org/2000/svg}"
SYSTEM_PYTHON = Path("/usr/bin/python3")

_spec = importlib.util.spec_from_file_location("growth_chart", SCRIPT)
if _spec is None or _spec.loader is None:
    raise ImportError(f"cannot load {SCRIPT}")
growth_chart = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(growth_chart)


def parse(svg: str) -> ET.Element:
    return ET.fromstring(svg)


def texts(root: ET.Element) -> list[str]:
    return [t.text or "" for t in root.iter(f"{NS}text")]


def value_labels(root: ET.Element) -> list[str]:
    """The labels on the bars or points, the only text set at 20px."""
    return [t.text or "" for t in root.iter(f"{NS}text") if t.get("font-size") == "20"]


def input_labels(root: ET.Element) -> list[str]:
    """The labels under the x-axis, one per bar or point."""
    y = str(growth_chart.BASE + 26)
    return [t.text or "" for t in root.iter(f"{NS}text") if t.get("y") == y]


@pytest.fixture
def square() -> str:
    return growth_chart.bars("sq", [1, 2, 4], [1, 4, 16], "×4", "work 1, 4, 16")


@pytest.fixture
def log() -> str:
    return growth_chart.log_line("lg", "work 1 to 5")


def test_bars_is_valid_svg_with_value_and_input_labels(square: str) -> None:
    root = parse(square)
    labels = texts(root)
    assert value_labels(root) == ["1", "4", "16"]
    assert input_labels(root) == ["1", "2", "4"]
    assert labels.count("×4") == 2  # one arrow between each pair of bars
    assert "items in the input (n)" in labels
    assert "work (steps)" in labels


def test_log_line_labels_every_point_and_drops_the_narrow_arrow(log: str) -> None:
    root = parse(log)
    labels = texts(root)
    assert value_labels(root) == ["1", "2", "3", "4", "5"]
    assert input_labels(root) == ["2", "4", "8", "16", "32"]
    # 4→8, 8→16, 16→32; the 2→4 span is too narrow for a label
    assert labels.count("+1") == 3


def test_arrow_too_narrow_for_its_label_is_left_off() -> None:
    assert growth_chart.arrow("c", 0, 0, growth_chart.MIN_ARROW - 1, 0, "×2") == []
    assert growth_chart.arrow("c", 0, 0, growth_chart.MIN_ARROW, 0, "×2")


@pytest.mark.parametrize("chart", ["square", "log"])
def test_only_the_data_marks_use_a_fixed_colour(chart: str, request: pytest.FixtureRequest) -> None:
    root = parse(request.getfixturevalue(chart))
    for el in root.iter():
        for attr in ("fill", "stroke"):
            value = el.get(attr)
            if value and value != "none":
                assert value in ("currentColor", growth_chart.BLUE), (el.tag, attr, value)
    for t in root.iter(f"{NS}text"):
        assert t.get("fill") == "currentColor"
    assert "color:currentColor" in (root.get("style") or "")


def test_marker_id_is_prefixed_by_the_chart_id_and_referenced_only_by_it() -> None:
    a = parse(growth_chart.bars("one", [1, 2], [1, 2], "×2", "a"))
    b = parse(growth_chart.bars("two", [1, 2], [1, 2], "×2", "b"))
    ids_a = {m.get("id") for m in a.iter(f"{NS}marker")}
    ids_b = {m.get("id") for m in b.iter(f"{NS}marker")}
    assert ids_a == {"one-ah"}
    assert ids_b == {"two-ah"}
    refs = {p.get("marker-end") for p in a.iter(f"{NS}path") if p.get("marker-end")}
    assert refs == {"url(#one-ah)"}


def test_short_and_zero_bars_stay_above_the_axis() -> None:
    root = parse(growth_chart.bars("z", [1, 2, 4], [0, 1, 200], "×2", "a"))
    for bar in root.iter(f"{NS}path"):
        if bar.get("fill") != growth_chart.BLUE:
            continue
        ys = [float(tok[1:]) for tok in (bar.get("d") or "").split() if tok[0] in "V"]
        assert all(y <= growth_chart.BASE for y in ys), bar.get("d")


def test_label_with_markup_characters_still_parses() -> None:
    label = 'n "doubles" & work <grows>'
    root = parse(growth_chart.bars("x", [1, 2], [1, 2], "<×2>", label))
    assert root.get("aria-label") == label
    assert root.get("role") == "img"
    assert "<×2>" in texts(root)


def run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, str(SCRIPT), *args], check=False, capture_output=True, text=True)


def test_cli_bars_prints_the_same_svg_as_the_function() -> None:
    result = run_cli("bars", "--id", "sq", "--x", "1", "2", "4", "--y", "1", "4", "16",
                     "--step", "×4", "--label", "work 1, 4, 16")
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == growth_chart.bars("sq", [1, 2, 4], [1, 4, 16], "×4", "work 1, 4, 16")


def test_cli_preview_writes_the_chart_on_both_backgrounds(tmp_path: Path) -> None:
    page = tmp_path / "preview.html"
    result = run_cli("log", "--id", "lg", "--label", "work 1 to 5", "--preview", str(page))
    assert result.returncode == 0, result.stderr
    html = page.read_text(encoding="utf-8")
    assert html.count(result.stdout.strip()) == 2


@pytest.mark.skipif(not SYSTEM_PYTHON.exists(), reason="no system python3")
def test_cli_runs_under_the_system_python() -> None:
    # The skill runs the script with the system python3 (3.9 on macOS), not the project's.
    result = subprocess.run(
        [str(SYSTEM_PYTHON), str(SCRIPT), "log", "--id", "lg", "--label", "a"],
        check=False, capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == growth_chart.log_line("lg", "a")


@pytest.mark.parametrize("args, message", [
    (["--x", "1", "2", "--y", "0", "0"], "at least one above 0"),
    (["--x", "1", "2", "--y", "-1", "2"], "non-negative"),
    (["--id", 'a"b', "--x", "1", "2", "--y", "1", "2"], "--id must start with a letter"),
    (["--id", "2x", "--x", "1", "2", "--y", "1", "2"], "--id must start with a letter"),
])
def test_cli_rejects_values_it_cannot_draw(args: list[str], message: str) -> None:
    if "--id" not in args:
        args = ["--id", "x", *args]
    result = run_cli("bars", *args, "--step", "×2", "--label", "a")
    assert result.returncode == 2
    assert message in result.stderr


def test_cli_rejects_mismatched_inputs_and_values() -> None:
    result = run_cli("bars", "--id", "x", "--x", "1", "2", "--y", "1", "--step", "×2", "--label", "a")
    assert result.returncode == 2
    assert "same number of values" in result.stderr
