"""
Process inspection utilities.

This module provides functions for inspecting running processes,
including getting parent process information.
"""

import os
import subprocess


def get_parent_process_name() -> str | None:
    """
    Get the name of the parent process without external dependencies.

    Returns:
        The name of the parent process, or None if unable to determine
    """
    command = ["ps", "-p", str(os.getppid()), "-o", "comm="]
    try:
        output = subprocess.check_output(command, text=True, stderr=subprocess.DEVNULL)
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None
    return output.strip()
