Keep commits atomic: commit only the files you touched and list each path explicitly. For tracked files run git commit -m "<scoped message>" -- path/to/file1 path/to/file2. For brand-new files, use the one-liner git restore --staged :/ && git add "path/to/file1" "path/to/file2" && git commit -m "<scoped message>" -- path/to/file1 path/to/file2

When writing Python code, NEVER put import statements anywhere other than the top of the file. All imports must be at the beginning of the file, before any other code.
