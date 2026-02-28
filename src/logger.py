"""
Simple logging utility for PriorityLens.

Logs all output to both console and file with timestamps.
Minimal implementation - no log levels or configuration.
"""

import sys
from datetime import datetime, timezone
from pathlib import Path

LOG_FILE = "classifier.log"


def log(message: str, end: str = "\n") -> None:
    """
    Print message to console and append to log file with timestamp.

    Args:
        message: The message to log
        end: Line ending (default newline, matches print() behavior)
    """
    # Print to console
    print(message, end=end)

    # Append to log file with timestamp
    try:
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

        # Only add timestamp prefix for actual content lines (not empty lines)
        if message.strip():
            log_entry = f"[{timestamp}] {message}{end}"
        else:
            log_entry = f"{message}{end}"

        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(log_entry)

    except IOError as e:
        # If logging fails, don't crash - just continue
        # Print warning to stderr to avoid interfering with stdout
        print(f"Warning: Failed to write to log file: {e}", file=sys.stderr)


def log_separator() -> None:
    """Log a visual separator line."""
    log("=" * 60)


def log_session_start() -> None:
    """Log the start of a new classification session."""
    log_separator()
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    log(f"Classification session started: {timestamp}")
    log_separator()


def log_session_end() -> None:
    """Log the end of a classification session."""
    log_separator()
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    log(f"Classification session ended: {timestamp}")
    log_separator()
    log("")
