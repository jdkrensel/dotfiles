CRITICAL: NEVER use Bash for file operations. The Bash tool is NOT in the approved permissions list and will trigger prompts every time. You MUST use these pre-approved tools instead:
- Finding files: Use Glob tool (NOT find, NOT ls). Example: Glob(pattern="**/*.{sql,cs,ts,js}", path="/path")
- Searching content: Use Grep tool (NOT grep, NOT rg). Example: Grep(pattern="function", path="/path")
- Reading files: Use Read tool (NOT cat, NOT head, NOT tail). Example: Read(file_path="/path/file.txt")
Using Bash for any of these operations will interrupt the user with permission prompts. Always use the specialized tools.

Keep commits atomic: commit only the files you touched and list each path explicitly. For tracked files run git commit -m "<scoped message>" -- path/to/file1 path/to/file2. For brand-new files, use the one-liner git restore --staged :/ && git add "path/to/file1" "path/to/file2" && git commit -m "<scoped message>" -- path/to/file1 path/to/file2

When writing Python code, NEVER put import statements anywhere other than the top of the file. All imports must be at the beginning of the file, before any other code.

When writing Python code, always use modern type hint syntax (Python 3.9+): use lowercase built-in types `list`, `dict`, `tuple` instead of importing `List`, `Dict`, `Tuple` from typing module. For example: `list[int]`, `dict[str, int]`, `tuple[str, ...]`.
