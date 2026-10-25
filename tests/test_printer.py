"""Tests for Printer output that has a fixed shape."""

from installer.printer import Printer


def test_welcome_banner_is_a_single_unboxed_title(capsys):
    """The banner is one title line, with no box that wraps on a narrow terminal."""
    Printer().print_welcome_banner()

    lines = capsys.readouterr().out.strip().splitlines()
    assert len(lines) == 1
    assert "Dotfiles installer" in lines[0]
    assert not any(character in lines[0] for character in "╔╗╚╝║═")
