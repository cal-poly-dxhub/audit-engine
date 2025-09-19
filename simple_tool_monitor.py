#!/usr/bin/env python3
"""
Simple Tool Monitor - Shows all tool calls from the most recent session
"""

import streamlit as st
import sqlite3
import json
from pathlib import Path
from datetime import datetime

st.title("Tool Calls Monitor")

# Get the most recent session
logs_dir = Path("logs")
db_path = logs_dir / "agent_logs.db"

if not db_path.exists():
    st.error("No agent logs found")
    st.stop()

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Get most recent session
cursor.execute('''
    SELECT session_id, task_description, filename, start_time, status
    FROM sessions
    ORDER BY start_time DESC
    LIMIT 1
''')

session_row = cursor.fetchone()

if not session_row:
    st.error("No sessions found")
    st.stop()

session_id, task_description, filename, start_time, status = session_row

st.subheader(f"Most Recent Session")
st.write(f"**File:** {filename}")
st.write(f"**Task:** {task_description}")
st.write(f"**Started:** {datetime.fromtimestamp(start_time).strftime('%Y-%m-%d %H:%M:%S')}")
st.write(f"**Status:** {status}")

st.subheader("All Tool Calls:")

# Get all tool calls for this session
cursor.execute('''
    SELECT tool_name, input_params, output_result, error_message, status, start_time, duration_ms
    FROM tool_calls
    WHERE session_id = ?
    ORDER BY start_time ASC
''', (session_id,))

tool_calls = cursor.fetchall()

if not tool_calls:
    st.warning("No tool calls found for this session")
else:
    for i, (tool_name, input_params, output_result, error_message, status, start_time, duration_ms) in enumerate(tool_calls):

        duration = f"{duration_ms/1000:.1f}s" if duration_ms else "N/A"

        st.write(f"**{i+1}. {tool_name}** ({status}) - {duration}")

        # Show input parameters
        if input_params:
            try:
                params = json.loads(input_params)
                if tool_name == "Read":
                    st.write(f"   → Reading: {params.get('file_path', 'unknown')}")
                elif tool_name == "Write":
                    st.write(f"   → Writing to: {params.get('file_path', 'unknown')}")
                elif tool_name == "Bash":
                    st.write(f"   → Command: {params.get('command', 'unknown')}")
                elif tool_name == "Grep":
                    st.write(f"   → Searching: '{params.get('pattern', 'unknown')}' in {params.get('path', 'unknown')}")
                elif tool_name.startswith("mcp__"):
                    st.write(f"   → PDF file: {params.get('file_path', 'unknown')}")
                else:
                    st.write(f"   → Input: {str(params)[:100]}...")
            except:
                st.write(f"   → Input: {input_params[:100]}...")

        # Show output or error
        if status == "COMPLETED" and output_result:
            preview = output_result[:200] + "..." if len(output_result) > 200 else output_result
            st.write(f"   → Output: {preview}")
        elif error_message:
            st.write(f"   → Error: {error_message}")

        st.write("")  # Add spacing

conn.close()

# Auto-refresh button
if st.button("Refresh"):
    st.rerun()