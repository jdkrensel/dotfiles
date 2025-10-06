"""
Shell command execution utilities.

This module provides functions for executing shell commands and checking
if commands exist in the system PATH.
"""

import subprocess


def run_command(command: str, check: bool = True, shell: bool = True) -> subprocess.CompletedProcess:
    """
    Run a shell command and return the result.
    
    Args:
        command: The shell command to execute
        check: Whether to raise an exception on non-zero exit code
        shell: Whether to run the command through the shell
        
    Returns:
        CompletedProcess object with the command result
        
    Raises:
        subprocess.CalledProcessError: If check=True and command returns non-zero exit code
    """
    return subprocess.run(command, shell=shell, check=check, capture_output=True, text=True)


def command_exists(command: str) -> bool:
    """
    Check if a command exists in the system PATH.
    
    Args:
        command: The command name to check for
        
    Returns:
        True if the command exists and is executable, False otherwise
    """
    try:
        subprocess.run(f"command -v {command}", shell=True, check=True, capture_output=True)
        return True
    except subprocess.CalledProcessError:
        return False
