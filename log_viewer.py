#!/usr/bin/env python3
"""
Real-time Log Viewer for Agentic Evidence Analysis

This utility provides real-time monitoring of the evidence agent's activity
with detailed logging output and progress tracking.
"""

import os
import sys
import time
import json
from pathlib import Path
from datetime import datetime
import argparse
from typing import Optional, Dict, Any

def tail_log_file(filepath: Path, lines: int = 50):
    """Display the last N lines of a log file"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            file_lines = f.readlines()
            for line in file_lines[-lines:]:
                print(line.rstrip())
    except FileNotFoundError:
        print(f"[ERROR] Log file not found: {filepath}")
    except Exception as e:
        print(f"[ERROR] Error reading log file: {e}")

def follow_log_file(filepath: Path, follow_time: int = 30):
    """Follow a log file for new entries (like tail -f)"""
    print(f"[FOLLOW] Following log file: {filepath}")
    print(f"[TIME] Will monitor for {follow_time} seconds...")
    print("=" * 60)

    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            # Go to end of file
            f.seek(0, 2)

            start_time = time.time()
            while time.time() - start_time < follow_time:
                line = f.readline()
                if line:
                    print(line.rstrip())
                else:
                    time.sleep(0.1)

    except FileNotFoundError:
        print(f"[ERROR] Log file not found: {filepath}")
    except KeyboardInterrupt:
        print("\n[STOP] Monitoring stopped by user")
    except Exception as e:
        print(f"[ERROR] Error following log file: {e}")

def analyze_log_performance(filepath: Path):
    """Analyze performance metrics from the detailed log"""
    print(f"[PERFORMANCE] Analyzing performance metrics from: {filepath}")
    print("=" * 60)

    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        analysis_sessions = []
        current_session = None
        step_times = {}

        for line in lines:
            line = line.strip()

            # Look for analysis start
            if "[START] Starting analysis session:" in line:
                session_id = line.split(":")[-1].strip()
                current_session = {
                    'id': session_id,
                    'start_time': line.split(" - ")[0],
                    'steps': [],
                    'total_time': 0
                }

            # Look for step completions
            elif "[DONE] Completed:" in line and current_session:
                if "(" in line and "s)" in line:
                    # Extract step name and time
                    parts = line.split("[DONE] Completed:")[-1].strip()
                    step_name = parts.split("(")[0].strip()
                    time_part = parts.split("(")[-1].replace("s)", "").strip()
                    try:
                        step_time = float(time_part)
                        current_session['steps'].append({
                            'name': step_name,
                            'time': step_time
                        })
                    except ValueError:
                        pass

            # Look for analysis summary
            elif "[SUMMARY] Analysis Summary for" in line and current_session:
                analysis_sessions.append(current_session)
                current_session = None

        # Display analysis
        if analysis_sessions:
            print(f"[STATS] Found {len(analysis_sessions)} completed analysis sessions:\n")

            for i, session in enumerate(analysis_sessions[-5:], 1):  # Show last 5 sessions
                print(f"Session {i}: {session['id']}")
                print(f"   Start time: {session['start_time']}")
                print(f"   Steps completed: {len(session['steps'])}")

                if session['steps']:
                    total_time = sum(step['time'] for step in session['steps'])
                    print(f"   Total processing time: {total_time:.2f}s")
                    print("   Step breakdown:")
                    for step in session['steps']:
                        print(f"     - {step['name']}: {step['time']:.2f}s")
                print()
        else:
            print("No completed analysis sessions found.")

    except FileNotFoundError:
        print(f"[ERROR] Log file not found: {filepath}")
    except Exception as e:
        print(f"[ERROR] Error analyzing log file: {e}")

def show_log_summary():
    """Show summary of all available log files"""
    log_dir = Path("logs")

    if not log_dir.exists():
        print("[ERROR] Logs directory not found. Run the evidence agent first to generate logs.")
        return

    print("[FILES] Available log files:")
    print("=" * 50)

    log_files = list(log_dir.glob("*.log"))
    if not log_files:
        print("No log files found.")
        return

    for log_file in sorted(log_files):
        stat = log_file.stat()
        size_mb = stat.st_size / (1024 * 1024)
        modified = datetime.fromtimestamp(stat.st_mtime)

        print(f"[FILE] {log_file.name}")
        print(f"   Size: {size_mb:.2f} MB")
        print(f"   Modified: {modified.strftime('%Y-%m-%d %H:%M:%S')}")

        # Try to count lines
        try:
            with open(log_file, 'r', encoding='utf-8') as f:
                line_count = sum(1 for _ in f)
            print(f"   Lines: {line_count:,}")
        except:
            print("   Lines: Unable to count")
        print()

def main():
    parser = argparse.ArgumentParser(
        description="Real-time log viewer for Agentic Evidence Analysis"
    )

    parser.add_argument(
        "command",
        choices=["summary", "tail", "follow", "performance"],
        help="Command to execute"
    )

    parser.add_argument(
        "--file",
        default="evidence_agent_detailed.log",
        help="Log file to analyze (default: evidence_agent_detailed.log)"
    )

    parser.add_argument(
        "--lines",
        type=int,
        default=50,
        help="Number of lines to show with tail command (default: 50)"
    )

    parser.add_argument(
        "--time",
        type=int,
        default=30,
        help="Time to follow log file in seconds (default: 30)"
    )

    args = parser.parse_args()

    log_dir = Path("logs")
    log_file = log_dir / args.file

    print("[LOG_VIEWER] Agentic Evidence Analysis - Log Viewer")
    print("=" * 50)

    if args.command == "summary":
        show_log_summary()

    elif args.command == "tail":
        print(f"[TAIL] Last {args.lines} lines from: {args.file}")
        print("=" * 50)
        tail_log_file(log_file, args.lines)

    elif args.command == "follow":
        follow_log_file(log_file, args.time)

    elif args.command == "performance":
        analyze_log_performance(log_file)

if __name__ == "__main__":
    main()