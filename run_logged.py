"""
Windowless launcher for scheduled jobs (CLAUDE.md Section 60, 2026-10-01).

Task Scheduler runs:  pythonw.exe run_logged.py <script.py> <logfile>

pythonw has no console, so nothing can close a window out from under the
job. This wrapper reproduces what the old .bat line did
(`python.exe <script.py> >> <logfile> 2>&1`): append stdout and stderr to
the same log file, then run the script as __main__. Exit code is the
script's own, as before.

Output is line-buffered (cmd's redirection was block-buffered), so a run
that dies early still leaves everything it printed up to that point.
"""
import io
import os
import runpy
import sys

if len(sys.argv) != 3:
    sys.exit(2)

script = os.path.abspath(sys.argv[1])
log_path = os.path.abspath(sys.argv[2])

# One append-mode handle shared by fd 1 and fd 2 -- the same as `>> log 2>&1`,
# and it also catches anything written below the Python level.
log_fd = os.open(log_path, os.O_WRONLY | os.O_APPEND | os.O_CREAT | os.O_BINARY)
os.dup2(log_fd, 1)
os.dup2(log_fd, 2)
os.close(log_fd)

# Text layer: '\n' -> '\r\n' as before; logs are ASCII, so utf-8 is byte-identical.
sys.stdout = io.TextIOWrapper(io.FileIO(1, "wb", closefd=False), encoding="utf-8",
                              errors="backslashreplace", line_buffering=True)
sys.stderr = io.TextIOWrapper(io.FileIO(2, "wb", closefd=False), encoding="utf-8",
                              errors="backslashreplace", line_buffering=True)

sys.argv = [script]
sys.path[0] = os.path.dirname(script)
try:
    runpy.run_path(script, run_name="__main__")
finally:
    sys.stdout.flush()
    sys.stderr.flush()
