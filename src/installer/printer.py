"""Terminal output formatting for the dotfiles installer."""

from .constants import Colors


class Printer:
    """Prints consistently styled, colorized messages to the terminal."""

    def print_section_header(self, title: str) -> None:
        """Print a major section header."""
        print(f"\n{Colors.CYAN.value}▶ {Colors.WHITE.value}{title}{Colors.NC.value}")

    def print_current_step(self, message: str) -> None:
        """Print the current step being performed."""
        print(f"\n{Colors.BLUE.value}▶{Colors.NC.value} {Colors.WHITE.value}{message}{Colors.NC.value}")

    def print_success(self, message: str) -> None:
        """Print a green success message."""
        print(f"{Colors.GREEN.value}✓{Colors.NC.value} {message}")

    def print_info(self, message: str) -> None:
        """Print a yellow informational message."""
        print(f"{Colors.YELLOW.value}ℹ{Colors.NC.value} {message}")

    def print_warning(self, message: str) -> None:
        """Print a yellow warning message."""
        print(f"{Colors.YELLOW.value}⚠{Colors.NC.value} {message}")

    def print_error(self, message: str) -> None:
        """Print a red error message."""
        print(f"{Colors.RED.value}✗{Colors.NC.value} {message}")

    def print_table(self, headers: list[str], rows: list[list[str]]) -> None:
        """Print left-aligned columns sized to their widest cell.

        Cells must be plain text: column widths are measured with ``len``, so an
        embedded ANSI escape would pad the column by its invisible length. Colorize
        around the table (headers here, summary lines via the other helpers), not
        inside it.

        No rows prints nothing at all, headers included — a caller with an empty
        result should say so in words rather than show an empty frame.
        """
        if not rows:
            return
        widths = [max(len(cell) for cell in column) for column in zip(headers, *rows, strict=True)]

        def render(cells: list[str]) -> str:
            padded = (cell.ljust(width) for cell, width in zip(cells, widths, strict=True))
            return "  ".join(padded).rstrip()

        print(f"{Colors.WHITE.value}{render(headers)}{Colors.NC.value}")
        print(f"{Colors.BLUE.value}{render(['-' * width for width in widths])}{Colors.NC.value}")
        for row in rows:
            print(render(row))

    def print_welcome_banner(self) -> None:
        """Print the welcome banner."""
        print(f"\n{Colors.PURPLE.value}╔══════════════════════════════════════════════════════════════╗{Colors.NC.value}")
        print(f"{Colors.PURPLE.value}║{Colors.NC.value}  {Colors.WHITE.value}Dotfiles installer{Colors.NC.value}")
        print(f"{Colors.PURPLE.value}╚══════════════════════════════════════════════════════════════╝{Colors.NC.value}")
