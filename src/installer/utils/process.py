"""
Process inspection utilities.

This module provides functions for inspecting running processes,
including getting parent process information.
"""

from __future__ import annotations

import os
import subprocess
import sys


def get_parent_process_name() -> str | None:
    """
    Get the name of the parent process without external dependencies.
    
    Returns:
        The name of the parent process, or None if unable to determine
    """
    try:
        ppid = os.getppid()
        
        if sys.platform == "win32":
            command = ['tasklist', '/fi', f'PID eq {ppid}', '/nh', '/fo', 'CSV']
            output = subprocess.check_output(command, text=True, stderr=subprocess.DEVNULL)
            return output.strip().split(',')[0].strip('"')
        else:
            command = ['ps', '-p', str(ppid), '-o', 'comm=']
            output = subprocess.check_output(command, text=True, stderr=subprocess.DEVNULL)
            return output.strip()

    except (subprocess.CalledProcessError, FileNotFoundError, IndexError):
        return None
