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

    def print_welcome_banner(self) -> None:
        """Print the welcome banner."""
        print(f"\n{Colors.PURPLE.value}╔══════════════════════════════════════════════════════════════╗{Colors.NC.value}")
        print(f"{Colors.PURPLE.value}║{Colors.NC.value}  {Colors.WHITE.value}Dotfiles installer{Colors.NC.value}")
        print(f"{Colors.PURPLE.value}╚══════════════════════════════════════════════════════════════╝{Colors.NC.value}")
