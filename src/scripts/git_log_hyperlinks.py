#!/usr/bin/env python3
"""
Git Log with Hyperlinks

Enhanced git log formatter that creates clickable hyperlinks for commit hashes
when viewed in modern terminals. Automatically detects GitHub, Bitbucket, GitLab,
and Azure DevOps repositories and generates appropriate URLs for commit links.

Features:
- Colorized output with 256-color and fallback support
- Clickable commit hash hyperlinks (GitHub, Bitbucket, GitLab, Azure DevOps)
- Clean, indented formatting for better readability
- Automatic remote URL detection

Usage:
  This script is automatically set up by the dotfiles install script.
  The install script creates a git alias 'lo' that runs this script.
  
  After running the install script, you can use:
    git lo                    # Enhanced git log with hyperlinks
  
  Manual setup (if not using the install script):
    ln -s "$(pwd)/src/scripts/git-log-hyperlinks.py" ~/bin/git-log-hyperlinks.py
    git config --global alias.lo '!~/bin/git-log-hyperlinks.py'
"""

import re
import subprocess
import sys
from typing import Optional, Dict, Tuple


class GitLogHyperlinks:
    """Enhanced git log formatter with hyperlink support."""
    
    def __init__(self):
        self.colors = self._detect_colors()
        self.commit_url_base = self._detect_commit_url_base()
    
    def _detect_colors(self) -> Dict[str, str]:
        """Detect terminal color support and return color codes."""
        try:
            # Check if terminal supports 256 colors
            colors = int(subprocess.check_output(['tput', 'colors'], text=True).strip())
            if colors >= 256:
                return {
                    'neutral': '\033[38;5;244m',  # 256-color neutral
                    'yellow': '\033[38;5;3m',    # 256-color yellow
                    'green': '\033[38;5;2m',      # 256-color green
                    'subject': '\033[38;5;15m',   # 256-color white
                    'reset': '\033[0m'
                }
        except (subprocess.CalledProcessError, FileNotFoundError):
            pass
        
        # Fallback to basic colors
        return {
            'neutral': '\033[2m',  # dim
            'yellow': '\033[33m', # yellow
            'green': '\033[32m',  # green
            'subject': '\033[37m', # white
            'reset': '\033[0m'
        }
    
    def _detect_commit_url_base(self) -> Optional[str]:
        """Detect the VCS platform and build commit URL base."""
        try:
            remote_url = subprocess.check_output(
                ['git', 'remote', 'get-url', 'origin'], 
                text=True, 
                stderr=subprocess.DEVNULL
            ).strip()
        except subprocess.CalledProcessError:
            return None
        
        # VCS platform detection patterns
        vcs_patterns = {
            'github': [
                r'git@github\.com:([^/]+/[^/]+)',
                r'https://github\.com/([^/]+/[^/]+)'
            ],
            'bitbucket': [
                r'git@bitbucket\.org:([^/]+/[^/]+)',
                r'https://bitbucket\.org/([^/]+/[^/]+)'
            ],
            'gitlab': [
                r'git@gitlab\.com:([^/]+/[^/]+)',
                r'https://gitlab\.com/([^/]+/[^/]+)'
            ],
            'azure': [
                r'git@ssh\.dev\.azure\.com:v3/([^/]+)/([^/]+)/([^/]+)',
                r'https://([^/]+)@dev\.azure\.com/([^/]+)/([^/]+)/_git/([^/]+)'
            ]
        }
        
        # VCS platform URL templates
        vcs_urls = {
            'github': 'https://github.com/{}/commit/',
            'bitbucket': 'https://bitbucket.org/{}/commits/',
            'gitlab': 'https://gitlab.com/{}/-/commit/',
            'azure': 'https://dev.azure.com/{}/{}/_git/{}/commit/'
        }
        
        # Detect VCS platform and build commit URL
        for platform, patterns in vcs_patterns.items():
            for pattern in patterns:
                match = re.search(pattern, remote_url)
                if match:
                    if platform == 'azure':
                        org, project, repo = match.groups()
                        return vcs_urls[platform].format(org, project, repo)
                    else:
                        repo_path = match.group(1).rstrip('.git')
                        return vcs_urls[platform].format(repo_path)
        
        return None
    
    def _get_hash_format(self) -> str:
        """Get the hash format string with hyperlink support if available."""
        if self.commit_url_base:
            # Create hyperlink format
            return f'\033]8;;{self.commit_url_base}%H\a{self.colors["yellow"]}%h\033]8;;\a'
        else:
            # Fallback to colored hash without hyperlink
            return f'{self.colors["yellow"]}%h'
    
    def _get_format_string(self, full: bool = False) -> str:
        """Build the complete format string for git log."""
        hash_format = self._get_hash_format()
        indent = "    "

        format_parts = [
            f'{self.colors["neutral"]}{hash_format} {self.colors["reset"]}%C(auto)%d',
            f'{indent}{self.colors["neutral"]}%cr (%ad) by {self.colors["green"]}%aN',
            f'{indent}{self.colors["subject"]}%s{self.colors["reset"]}'
        ]

        if full:
            # Add blank line between subject and body for readability
            format_parts.append('')
            # Use %w() to wrap and indent the body text
            # %w(0,0,4) = no line width limit, 0 spaces first line indent, 4 spaces subsequent indent
            format_parts.append(f'{indent}%w(0,0,4)%b{self.colors["reset"]}')

        return '\n'.join(format_parts)
    
    def run(self, args: list = None) -> int:
        """Run the enhanced git log with hyperlinks."""
        if args is None:
            args = []

        # Check for --full flag
        full = '--full' in args
        if full:
            args = [arg for arg in args if arg != '--full']

        # First check if we're in a git repository
        try:
            subprocess.run(['git', 'rev-parse', '--git-dir'],
                         check=True, capture_output=True, text=True)
        except subprocess.CalledProcessError:
            # Not in a git repository, let git handle the error message
            try:
                subprocess.run(['git', 'log'] + args, check=True)
            except subprocess.CalledProcessError as e:
                # Let git's error message pass through
                return e.returncode
            return 0

        format_string = self._get_format_string(full=full)
        date_format = "format-local:%Y-%m-%d %H:%M:%S"
        
        git_args = [
            'git', 'log',
            '--graph',
            f'--date={date_format}',
            f'--pretty=format:{format_string}'
        ] + args
        
        try:
            # Run git log with the enhanced formatting
            result = subprocess.run(git_args, check=True)
            return result.returncode
        except subprocess.CalledProcessError as e:
            print(f"Error running git log: {e}", file=sys.stderr)
            return e.returncode
        except KeyboardInterrupt:
            return 130  # Standard exit code for SIGINT


def main():
    """Main entry point for the git log hyperlinks script."""
    script = GitLogHyperlinks()
    sys.exit(script.run(sys.argv[1:]))


if __name__ == '__main__':
    main()
