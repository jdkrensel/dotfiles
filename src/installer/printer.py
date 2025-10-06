"""
Terminal output formatting and printing utilities for the dotfiles installer.

This module provides a Printer class that handles all formatted terminal output
with consistent styling, colors, and icons for different types of messages.
"""

from .constants import Colors


class Printer:
    """
    Handles formatted terminal output for the dotfiles installer.
    
    This class provides methods for printing different types of messages with
    consistent styling, colors, and visual indicators. All methods automatically
    handle color formatting and reset colors after each message.
    """
    
    def print_section_header(self, title: str) -> None:
        """
        Print a formatted section header with a bordered box.
        
        Used to separate major sections of the installation process.
        
        Args:
            title: The section title to display in the header
        """
        print(f"\n{Colors.CYAN.value}▶ {Colors.WHITE.value}{title}{Colors.NC.value}")
    
    def print_current_step(self, message: str) -> None:
        """
        Print a message indicating the current step being performed.
        
        Used to show what the installer is currently doing.
        
        Args:
            message: Description of the current step (e.g., "Installing Homebrew packages...")
        """
        print(f"\n{Colors.BLUE.value}▶{Colors.NC.value} {Colors.WHITE.value}{message}{Colors.NC.value}")
    
    def print_success(self, message: str) -> None:
        """
        Print a success message with a green checkmark.
        
        Used to indicate that a step completed successfully.
        
        Args:
            message: Success message to display
        """
        print(f"{Colors.GREEN.value}✓{Colors.NC.value} {message}")
    
    def print_info(self, message: str) -> None:
        """
        Print an informational message with a yellow info icon.
        
        Used to provide additional context or information to the user.
        
        Args:
            message: Information message to display
        """
        print(f"{Colors.YELLOW.value}ℹ{Colors.NC.value} {message}")
    
    def print_error(self, message: str) -> None:
        """
        Print an error message with a red X icon.
        
        Used to indicate that something went wrong during installation.
        
        Args:
            message: Error message to display
        """
        print(f"{Colors.RED.value}✗{Colors.NC.value} {message}")
    
    def print_welcome_banner(self) -> None:
        """
        Print the welcome banner for the dotfiles installer.
        
        Displays a decorative banner to welcome the user to the installation process.
        """
        print(f"\n{Colors.PURPLE.value}╔══════════════════════════════════════════════════════════════╗{Colors.NC.value}")
        print(f"{Colors.PURPLE.value}║{Colors.NC.value}  {Colors.WHITE.value}Dotfiles installer{Colors.NC.value}")
        print(f"{Colors.PURPLE.value}╚══════════════════════════════════════════════════════════════╝{Colors.NC.value}")
