#!/usr/bin/env python3
"""
Extract tool calls from log files and display them
"""

import streamlit as st
import re
from pathlib import Path
from datetime import datetime

st.title("Tool Calls from Logs")

# Read the most recent log file
logs_dir = Path("logs")
log_files = list(logs_dir.glob("agent_activity_*.log"))

if not log_files:
    st.error("No log files found")
    st.stop()

# Get most recent log file
latest_log = max(log_files, key=lambda x: x.stat().st_mtime)
st.write(f"Reading from: {latest_log.name}")

# Read log content
with open(latest_log, 'r') as f:
    log_content = f.read()

# Find the most recent session
session_pattern = r'\[SESSION_START\] ([a-f0-9-]+) - Analysis: ([^"\n]+)'
sessions = re.findall(session_pattern, log_content)

if not sessions:
    st.error("No sessions found in logs")
    st.stop()

# Get the most recent session
most_recent_session_id, analysis_id = sessions[-1]
st.subheader(f"Most Recent Session: {analysis_id}")
st.write(f"Session ID: {most_recent_session_id}")

# Extract session details
session_start_pattern = rf'\[SESSION_START\] {re.escape(most_recent_session_id)}.*\n.*\[SESSION_DETAILS\] Agent: ([^,]+), File: ([^\n]+)'
session_match = re.search(session_start_pattern, log_content)

if session_match:
    agent_type, filename = session_match.groups()
    st.write(f"**Agent:** {agent_type}")
    st.write(f"**File:** {filename}")

# Extract task description
task_pattern = rf'\[SESSION_START\] {re.escape(most_recent_session_id)}.*\n.*\n.*\[TASK\] ([^\n]+)'
task_match = re.search(task_pattern, log_content)
if task_match:
    st.write(f"**Task:** {task_match.group(1)}")

st.subheader("Tool Calls:")

# Extract all tool-related logs for this session
session_logs = []
in_session = False
session_end_pattern = rf'\[SESSION_END\] {re.escape(most_recent_session_id)}'

for line in log_content.split('\n'):
    if f'[SESSION_START] {most_recent_session_id}' in line:
        in_session = True
    elif re.search(session_end_pattern, line):
        in_session = False
        session_logs.append(line)  # Include the end line
        break

    if in_session:
        session_logs.append(line)

# Parse tool calls from session logs
tool_calls = []
current_tool = None

for line in session_logs:
    # Tool start
    tool_start_match = re.search(r'\[TOOL_START\] ([^-]+) - ID: ([a-f0-9-]+)', line)
    if tool_start_match:
        tool_name, tool_id = tool_start_match.groups()
        current_tool = {
            'name': tool_name.strip(),
            'id': tool_id,
            'status': 'STARTED',
            'start_line': line
        }
        tool_calls.append(current_tool)
        continue

    # Tool parameters (for context)
    if '[MCP_TOOL]' in line and current_tool:
        current_tool['type'] = 'MCP Tool'
    elif '[BASH_COMMAND]' in line and current_tool:
        cmd_match = re.search(r'\[BASH_COMMAND\] (.+)', line)
        if cmd_match:
            current_tool['command'] = cmd_match.group(1)
    elif '[READ_FILE]' in line and current_tool:
        file_match = re.search(r'\[READ_FILE\] (.+)', line)
        if file_match:
            current_tool['file_path'] = file_match.group(1)
    elif '[WRITE_FILE]' in line and current_tool:
        file_match = re.search(r'\[WRITE_FILE\] (.+)', line)
        if file_match:
            current_tool['file_path'] = file_match.group(1)
    elif '[GREP_SEARCH]' in line and current_tool:
        search_match = re.search(r'\[GREP_SEARCH\] (.+)', line)
        if search_match:
            current_tool['search'] = search_match.group(1)

    # Tool completion (look for tool result or error)
    if '[TOOL_RESULT]' in line and current_tool:
        result_match = re.search(r'\[TOOL_RESULT\] (.+)', line)
        if result_match:
            current_tool['status'] = 'COMPLETED'
            current_tool['result'] = result_match.group(1)
    elif '[TOOL_ERROR]' in line and current_tool:
        error_match = re.search(r'\[TOOL_ERROR\] (.+)', line)
        if error_match:
            current_tool['status'] = 'FAILED'
            current_tool['error'] = error_match.group(1)

# Display tool calls
if not tool_calls:
    st.warning("No tool calls found in this session")
else:
    for i, tool in enumerate(tool_calls):
        status_indicator = {'COMPLETED': '[DONE]', 'FAILED': '[FAIL]', 'STARTED': '[RUNNING]'}.get(tool['status'], '[?]')

        st.write(f"**{i+1}. {tool['name']}** {status_indicator}")

        # Show parameters/context
        if 'command' in tool:
            st.write(f"   → Command: {tool['command']}")
        elif 'file_path' in tool:
            st.write(f"   → File: {tool['file_path']}")
        elif 'search' in tool:
            st.write(f"   → Search: {tool['search']}")
        elif 'type' in tool:
            st.write(f"   → Type: {tool['type']}")

        # Show result or error
        if tool['status'] == 'COMPLETED' and 'result' in tool:
            st.write(f"   → Output: {tool['result']}")
        elif tool['status'] == 'FAILED' and 'error' in tool:
            st.write(f"   → Error: {tool['error']}")

        st.write("")  # Spacing

# Manual refresh
if st.button("Refresh"):
    st.rerun()