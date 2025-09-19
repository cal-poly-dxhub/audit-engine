#!/usr/bin/env python3
"""
Agent Logs Streamlit UI

User-friendly interface for viewing comprehensive Claude Code agent activity logs,
tool usage, performance metrics, and analysis workflows.
"""

import streamlit as st
import pandas as pd
import json
import sqlite3
import time
from datetime import datetime, timedelta
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from pathlib import Path
import sys
import os

# Add the current directory to path to import agent_logger
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from agent_logger import AgentLogger

# Configure Streamlit page
st.set_page_config(
    page_title="Agent Activity Logs",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better styling
st.markdown("""
<style>
    .metric-card {
        background-color: #f0f2f6;
        padding: 10px;
        border-radius: 5px;
        margin: 5px 0;
    }
    .tool-success { color: #28a745; }
    .tool-failed { color: #dc3545; }
    .tool-running { color: #ffc107; }
    .session-completed { background-color: #d4edda; }
    .session-failed { background-color: #f8d7da; }
    .session-running { background-color: #fff3cd; }
</style>
""", unsafe_allow_html=True)

@st.cache_resource  # Use cache_resource for non-serializable objects
def load_agent_logger():
    """Load the agent logger instance"""
    return AgentLogger()

def get_recent_sessions(limit=100):
    """Get recent agent sessions"""
    logger = load_agent_logger()
    return logger.get_recent_sessions(limit)

def get_session_details(session_id):
    """Get detailed session information"""
    logger = load_agent_logger()
    return logger.get_session_details(session_id)

def format_duration(duration_ms):
    """Format duration in a human-readable way"""
    if duration_ms is None:
        return "N/A"

    if duration_ms < 1000:
        return f"{duration_ms:.0f}ms"
    elif duration_ms < 60000:
        return f"{duration_ms/1000:.1f}s"
    else:
        return f"{duration_ms/60000:.1f}m"

def format_timestamp(timestamp):
    """Format timestamp in a human-readable way"""
    if timestamp is None:
        return "N/A"

    try:
        dt = datetime.fromtimestamp(timestamp)
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except:
        return str(timestamp)

def get_status_color(status):
    """Get color for status display"""
    colors = {
        'COMPLETED': '#28a745',
        'FAILED': '#dc3545',
        'RUNNING': '#ffc107'
    }
    return colors.get(status, '#6c757d')

def main():
    """Main Streamlit application"""

    st.title("🤖 Claude Code Agent Activity Logs")
    st.markdown("Comprehensive tracking of agent tool usage, performance, and analysis workflows")

    # Sidebar for navigation and filters
    with st.sidebar:
        st.header("Navigation")

        view_mode = st.selectbox(
            "View Mode",
            ["Dashboard", "Live Tool Monitor", "Session List", "Session Details", "Tool Analysis", "Performance Metrics"]
        )

        st.header("Filters")

        # Time range filter
        time_range = st.selectbox(
            "Time Range",
            ["Last Hour", "Last 24 Hours", "Last 7 Days", "Last 30 Days", "All Time"]
        )

        # Agent type filter
        sessions = get_recent_sessions(200)
        if sessions:
            agent_types = list(set([s.get('agent_type', 'Unknown') for s in sessions]))
            selected_agent_types = st.multiselect(
                "Agent Types",
                agent_types,
                default=agent_types
            )
        else:
            selected_agent_types = []

        # Status filter
        status_filter = st.multiselect(
            "Status",
            ["COMPLETED", "FAILED", "RUNNING"],
            default=["COMPLETED", "FAILED", "RUNNING"]
        )

        # Auto-refresh
        auto_refresh = st.checkbox("Auto-refresh (30s)", value=False)

        # Manual refresh button
        if st.button("🔄 Refresh Now"):
            st.cache_resource.clear()  # Clear cache to get fresh data

    # Filter sessions based on criteria
    filtered_sessions = []
    for session in sessions:
        # Time filter
        if time_range != "All Time":
            now = datetime.now().timestamp()
            session_time = session.get('start_time', 0)

            time_deltas = {
                "Last Hour": 3600,
                "Last 24 Hours": 86400,
                "Last 7 Days": 604800,
                "Last 30 Days": 2592000
            }

            if now - session_time > time_deltas.get(time_range, 0):
                continue

        # Agent type filter
        if session.get('agent_type') not in selected_agent_types:
            continue

        # Status filter
        if session.get('status') not in status_filter:
            continue

        filtered_sessions.append(session)

    # Main content based on view mode
    if view_mode == "Dashboard":
        show_dashboard(filtered_sessions)
    elif view_mode == "Live Tool Monitor":
        show_live_tool_monitor(filtered_sessions)
    elif view_mode == "Session List":
        show_session_list(filtered_sessions)
    elif view_mode == "Session Details":
        show_session_details()
    elif view_mode == "Tool Analysis":
        show_tool_analysis(filtered_sessions)
    elif view_mode == "Performance Metrics":
        show_performance_metrics(filtered_sessions)

def show_dashboard(sessions):
    """Show overview dashboard"""

    st.header("📊 Overview Dashboard")

    if not sessions:
        st.warning("No sessions found matching your criteria.")
        return

    # Key metrics row
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Total Sessions", len(sessions))

    with col2:
        completed = len([s for s in sessions if s.get('status') == 'COMPLETED'])
        st.metric("Completed", completed)

    with col3:
        failed = len([s for s in sessions if s.get('status') == 'FAILED'])
        st.metric("Failed", failed)

    with col4:
        avg_duration = sum([s.get('duration_ms', 0) for s in sessions if s.get('duration_ms')]) / len(sessions) if sessions else 0
        st.metric("Avg Duration", format_duration(avg_duration))

    # Charts row
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("📈 Sessions Over Time")

        # Prepare data for time series
        session_times = []
        for session in sessions:
            if session.get('start_time'):
                session_times.append({
                    'timestamp': datetime.fromtimestamp(session['start_time']),
                    'status': session.get('status', 'Unknown'),
                    'agent_type': session.get('agent_type', 'Unknown')
                })

        if session_times:
            df_times = pd.DataFrame(session_times)
            df_times['hour'] = df_times['timestamp'].dt.floor('H')

            hourly_counts = df_times.groupby(['hour', 'status']).size().reset_index(name='count')

            fig = px.bar(hourly_counts, x='hour', y='count', color='status',
                        title="Sessions by Hour and Status")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No time data available")

    with col2:
        st.subheader("🔧 Tool Usage")

        # Get tool usage statistics
        tool_stats = {}
        for session in sessions:
            details = get_session_details(session['session_id'])
            if details and details.get('tool_calls'):
                for tool_call in details['tool_calls']:
                    tool_name = tool_call.get('tool_name', 'Unknown')
                    if tool_name not in tool_stats:
                        tool_stats[tool_name] = {'count': 0, 'failed': 0}
                    tool_stats[tool_name]['count'] += 1
                    if tool_call.get('status') == 'FAILED':
                        tool_stats[tool_name]['failed'] += 1

        if tool_stats:
            tool_df = pd.DataFrame([
                {'tool': tool, 'count': stats['count'], 'success_rate': (stats['count'] - stats['failed']) / stats['count']}
                for tool, stats in tool_stats.items()
            ])

            fig = px.bar(tool_df, x='tool', y='count', title="Tool Usage Count")
            fig.update_layout(xaxis_tickangle=45)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No tool usage data available")

    # Recent sessions with tool details
    st.subheader("🕒 Recent Sessions with Tool Timeline")

    recent_sessions = sessions[:5]  # Show last 5 sessions with details

    for session in recent_sessions:
        status_color = get_status_color(session.get('status', 'Unknown'))

        with st.expander(f"Session {session['session_id'][:8]}... - {session.get('status', 'Unknown')} - {session.get('filename', 'Unknown')}"):
            col1, col2, col3 = st.columns(3)

            with col1:
                st.write(f"**Agent:** {session.get('agent_type', 'Unknown')}")
                st.write(f"**File:** {session.get('filename', 'Unknown')}")

            with col2:
                st.write(f"**Started:** {format_timestamp(session.get('start_time'))}")
                st.write(f"**Duration:** {format_duration(session.get('duration_ms'))}")

            with col3:
                st.write(f"**Status:** {session.get('status', 'Unknown')}")
                if session.get('error_message'):
                    st.error(f"Error: {session['error_message']}")

            # Show tool timeline for this session
            st.write("**Tool Timeline:**")
            try:
                details = get_session_details(session['session_id'])
                st.write(f"Debug: Found {len(details.get('tool_calls', []))} tool calls" if details else "Debug: No details found")

                if details and details.get('tool_calls'):
                    for i, tool_call in enumerate(details['tool_calls']):
                        status_indicator = {'COMPLETED': '[DONE]', 'FAILED': '[FAIL]', 'STARTED': '[RUNNING]'}.get(tool_call.get('status', 'Unknown'), '[?]')

                        tool_name = tool_call.get('tool_name', 'Unknown')
                        duration = format_duration(tool_call.get('duration_ms'))

                        # Show key parameters for important tools
                        params_info = ""
                        if tool_call.get('input_params'):
                            try:
                                if isinstance(tool_call['input_params'], str):
                                    params = json.loads(tool_call['input_params'])
                                else:
                                    params = tool_call['input_params']

                                if tool_name == "Read":
                                    params_info = f" -> {params.get('file_path', 'unknown file')}"
                                elif tool_name == "Write":
                                    params_info = f" -> {params.get('file_path', 'unknown file')}"
                                elif tool_name == "Bash":
                                    cmd = params.get('command', 'unknown command')
                                    params_info = f" -> {cmd[:50]}{'...' if len(cmd) > 50 else ''}"
                                elif tool_name == "Grep":
                                    params_info = f" -> '{params.get('pattern', 'unknown')}' in {params.get('path', 'unknown')}"
                                elif tool_name.startswith("mcp__"):
                                    params_info = f" -> {params.get('file_path', 'PDF processing')}"
                            except:
                                params_info = " -> (params parsing error)"

                        st.write(f"{status_indicator} **{i+1}.** {tool_name} ({duration}){params_info}")

                        # Show brief output for completed tools
                        if tool_call.get('status') == 'COMPLETED' and tool_call.get('output_result'):
                            output = tool_call['output_result']
                            if len(output) > 100:
                                output = output[:100] + "..."
                            st.write(f"   Output: *{output}*")
                        elif tool_call.get('error_message'):
                            st.write(f"   Error: *{tool_call['error_message']}*")
                else:
                    st.write("No tool calls found for this session")
            except Exception as e:
                st.error(f"Error loading tool calls: {str(e)}")

def show_session_list(sessions):
    """Show detailed session list"""

    st.header("📋 Session List")

    if not sessions:
        st.warning("No sessions found matching your criteria.")
        return

    # Prepare data for table
    table_data = []
    for session in sessions:
        table_data.append({
            'Session ID': session['session_id'][:8] + '...',
            'Agent Type': session.get('agent_type', 'Unknown'),
            'Filename': session.get('filename', 'Unknown'),
            'Status': session.get('status', 'Unknown'),
            'Start Time': format_timestamp(session.get('start_time')),
            'Duration': format_duration(session.get('duration_ms')),
            'Task Description': (session.get('task_description', '')[:50] + '...') if session.get('task_description') else 'N/A'
        })

    df = pd.DataFrame(table_data)

    # Add styling to status column
    def style_status(val):
        colors = {
            'COMPLETED': 'background-color: #d4edda',
            'FAILED': 'background-color: #f8d7da',
            'RUNNING': 'background-color: #fff3cd'
        }
        return colors.get(val, '')

    styled_df = df.style.applymap(style_status, subset=['Status'])

    st.dataframe(styled_df, use_container_width=True)

    # Session selection for details
    st.subheader("View Session Details")

    session_options = {f"{s['session_id'][:8]}... - {s.get('agent_type', 'Unknown')}": s['session_id']
                      for s in sessions}

    if session_options:
        selected_session_key = st.selectbox("Select Session", list(session_options.keys()))
        if selected_session_key and st.button("View Details"):
            st.session_state.selected_session_id = session_options[selected_session_key]
            st.rerun()

def show_session_details():
    """Show detailed view of a specific session"""

    st.header("🔍 Session Details")

    # Session ID input
    if 'selected_session_id' in st.session_state:
        default_session_id = st.session_state.selected_session_id
    else:
        default_session_id = ""

    session_id = st.text_input("Session ID", value=default_session_id)

    if not session_id:
        st.info("Enter a session ID to view details")
        return

    details = get_session_details(session_id)

    if not details:
        st.error("Session not found")
        return

    session = details['session']
    tool_calls = details['tool_calls']
    agent_responses = details['agent_responses']

    # Session overview
    st.subheader("Session Overview")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.write(f"**Session ID:** {session['session_id']}")
        st.write(f"**Analysis ID:** {session.get('analysis_id', 'N/A')}")
        st.write(f"**Agent Type:** {session.get('agent_type', 'Unknown')}")

    with col2:
        st.write(f"**Filename:** {session.get('filename', 'Unknown')}")
        st.write(f"**Status:** {session.get('status', 'Unknown')}")
        st.write(f"**Duration:** {format_duration(session.get('duration_ms'))}")

    with col3:
        st.write(f"**Start Time:** {format_timestamp(session.get('start_time'))}")
        st.write(f"**End Time:** {format_timestamp(session.get('end_time'))}")
        st.write(f"**Tool Calls:** {len(tool_calls)}")

    # Task information
    st.subheader("Task Information")

    st.write(f"**Description:** {session.get('task_description', 'N/A')}")
    st.write(f"**User Description:** {session.get('user_description', 'N/A')}")

    if session.get('task_context'):
        st.write("**Context:**")
        st.json(session['task_context'])

    # Final result
    if session.get('final_result'):
        st.subheader("Analysis Result")

        result = session['final_result']

        col1, col2, col3 = st.columns(3)

        with col1:
            st.metric("Valid", str(result.get('is_valid', 'Unknown')))

        with col2:
            confidence = result.get('confidence', 0)
            st.metric("Confidence", f"{confidence:.2%}" if isinstance(confidence, (int, float)) else str(confidence))

        with col3:
            st.metric("Quality", result.get('evidence_quality', 'Unknown'))

        if result.get('reasoning'):
            st.write("**Reasoning:**")
            st.write(result['reasoning'])

        if result.get('annotations'):
            st.write(f"**Annotations:** {len(result['annotations'])} citations found")

    # Error information
    if session.get('error_message'):
        st.subheader("Error Information")
        st.error(session['error_message'])

    # Tool calls timeline
    st.subheader("Tool Calls Timeline")

    if tool_calls:
        for i, tool_call in enumerate(tool_calls):
            status = tool_call.get('status', 'Unknown')
            status_emoji = {'COMPLETED': '✅', 'FAILED': '❌', 'STARTED': '🟡'}.get(status, '❓')

            with st.expander(f"{status_emoji} {tool_call.get('tool_name', 'Unknown')} - {format_duration(tool_call.get('duration_ms'))}"):

                col1, col2 = st.columns(2)

                with col1:
                    st.write(f"**Tool:** {tool_call.get('tool_name', 'Unknown')}")
                    st.write(f"**Status:** {status}")
                    st.write(f"**Duration:** {format_duration(tool_call.get('duration_ms'))}")

                with col2:
                    st.write(f"**Start:** {format_timestamp(tool_call.get('start_time'))}")
                    st.write(f"**End:** {format_timestamp(tool_call.get('end_time'))}")

                if tool_call.get('input_params'):
                    st.write("**Input Parameters:**")
                    st.json(tool_call['input_params'])

                if tool_call.get('output_result'):
                    st.write("**Output:**")
                    st.code(tool_call['output_result'][:1000] + ('...' if len(tool_call['output_result']) > 1000 else ''))

                if tool_call.get('error_message'):
                    st.error(f"**Error:** {tool_call['error_message']}")
    else:
        st.info("No tool calls recorded for this session")

    # Agent responses
    st.subheader("Agent Responses")

    if agent_responses:
        for i, response in enumerate(agent_responses):
            with st.expander(f"Response {i + 1} - {format_timestamp(response.get('timestamp'))}"):
                st.write(response.get('response_text', 'No text'))
    else:
        st.info("No agent responses recorded for this session")

def show_tool_analysis(sessions):
    """Show tool usage analysis"""

    st.header("🔧 Tool Usage Analysis")

    if not sessions:
        st.warning("No sessions found matching your criteria.")
        return

    # Collect tool statistics
    tool_stats = {}
    total_duration_by_tool = {}

    for session in sessions:
        details = get_session_details(session['session_id'])
        if details and details.get('tool_calls'):
            for tool_call in details['tool_calls']:
                tool_name = tool_call.get('tool_name', 'Unknown')

                if tool_name not in tool_stats:
                    tool_stats[tool_name] = {
                        'total': 0,
                        'completed': 0,
                        'failed': 0,
                        'durations': []
                    }

                tool_stats[tool_name]['total'] += 1

                if tool_call.get('status') == 'COMPLETED':
                    tool_stats[tool_name]['completed'] += 1
                elif tool_call.get('status') == 'FAILED':
                    tool_stats[tool_name]['failed'] += 1

                if tool_call.get('duration_ms'):
                    tool_stats[tool_name]['durations'].append(tool_call['duration_ms'])

                    if tool_name not in total_duration_by_tool:
                        total_duration_by_tool[tool_name] = 0
                    total_duration_by_tool[tool_name] += tool_call['duration_ms']

    if not tool_stats:
        st.info("No tool usage data available")
        return

    # Tool usage overview
    st.subheader("Tool Usage Overview")

    tool_df = pd.DataFrame([
        {
            'Tool': tool,
            'Total Calls': stats['total'],
            'Completed': stats['completed'],
            'Failed': stats['failed'],
            'Success Rate': f"{(stats['completed'] / stats['total'] * 100):.1f}%" if stats['total'] > 0 else "0%",
            'Avg Duration': format_duration(sum(stats['durations']) / len(stats['durations'])) if stats['durations'] else "N/A",
            'Total Duration': format_duration(sum(stats['durations'])) if stats['durations'] else "N/A"
        }
        for tool, stats in tool_stats.items()
    ])

    st.dataframe(tool_df, use_container_width=True)

    # Charts
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Tool Usage Count")

        usage_data = [(tool, stats['total']) for tool, stats in tool_stats.items()]
        usage_data.sort(key=lambda x: x[1], reverse=True)

        fig = px.bar(
            x=[item[1] for item in usage_data],
            y=[item[0] for item in usage_data],
            orientation='h',
            title="Total Tool Calls"
        )
        fig.update_layout(showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader("Success Rate by Tool")

        success_data = [
            {
                'Tool': tool,
                'Success Rate': (stats['completed'] / stats['total'] * 100) if stats['total'] > 0 else 0
            }
            for tool, stats in tool_stats.items()
        ]

        fig = px.bar(
            pd.DataFrame(success_data),
            x='Tool',
            y='Success Rate',
            title="Success Rate (%)"
        )
        fig.update_layout(xaxis_tickangle=45)
        st.plotly_chart(fig, use_container_width=True)

    # Duration analysis
    st.subheader("Performance Analysis")

    duration_data = []
    for tool, stats in tool_stats.items():
        if stats['durations']:
            for duration in stats['durations']:
                duration_data.append({
                    'Tool': tool,
                    'Duration (ms)': duration
                })

    if duration_data:
        duration_df = pd.DataFrame(duration_data)

        fig = px.box(duration_df, x='Tool', y='Duration (ms)', title="Duration Distribution by Tool")
        fig.update_layout(xaxis_tickangle=45)
        st.plotly_chart(fig, use_container_width=True)

def show_performance_metrics(sessions):
    """Show performance metrics and trends"""

    st.header("📈 Performance Metrics")

    if not sessions:
        st.warning("No sessions found matching your criteria.")
        return

    # Performance overview
    st.subheader("Performance Overview")

    # Calculate metrics
    total_sessions = len(sessions)
    completed_sessions = len([s for s in sessions if s.get('status') == 'COMPLETED'])
    failed_sessions = len([s for s in sessions if s.get('status') == 'FAILED'])

    durations = [s.get('duration_ms', 0) for s in sessions if s.get('duration_ms')]
    avg_duration = sum(durations) / len(durations) if durations else 0

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Total Sessions", total_sessions)

    with col2:
        success_rate = (completed_sessions / total_sessions * 100) if total_sessions > 0 else 0
        st.metric("Success Rate", f"{success_rate:.1f}%")

    with col3:
        st.metric("Avg Duration", format_duration(avg_duration))

    with col4:
        max_duration = max(durations) if durations else 0
        st.metric("Max Duration", format_duration(max_duration))

    # Performance trends
    if len(sessions) > 1:
        st.subheader("Performance Trends")

        # Prepare time series data
        time_data = []
        for session in sessions:
            if session.get('start_time') and session.get('duration_ms'):
                time_data.append({
                    'timestamp': datetime.fromtimestamp(session['start_time']),
                    'duration': session['duration_ms'],
                    'status': session.get('status', 'Unknown'),
                    'agent_type': session.get('agent_type', 'Unknown')
                })

        if time_data:
            time_df = pd.DataFrame(time_data)
            time_df = time_df.sort_values('timestamp')

            # Duration trend
            fig = px.scatter(time_df, x='timestamp', y='duration', color='status',
                           title="Session Duration Over Time",
                           hover_data=['agent_type'])

            # Add trend line
            fig.add_scatter(x=time_df['timestamp'],
                          y=time_df['duration'].rolling(window=5, center=True).mean(),
                          mode='lines', name='5-session Moving Average')

            st.plotly_chart(fig, use_container_width=True)

    # Agent performance comparison
    st.subheader("Agent Performance Comparison")

    agent_stats = {}
    for session in sessions:
        agent_type = session.get('agent_type', 'Unknown')

        if agent_type not in agent_stats:
            agent_stats[agent_type] = {
                'sessions': 0,
                'completed': 0,
                'failed': 0,
                'durations': []
            }

        agent_stats[agent_type]['sessions'] += 1

        if session.get('status') == 'COMPLETED':
            agent_stats[agent_type]['completed'] += 1
        elif session.get('status') == 'FAILED':
            agent_stats[agent_type]['failed'] += 1

        if session.get('duration_ms'):
            agent_stats[agent_type]['durations'].append(session['duration_ms'])

    if len(agent_stats) > 1:
        agent_df = pd.DataFrame([
            {
                'Agent Type': agent,
                'Sessions': stats['sessions'],
                'Success Rate': f"{(stats['completed'] / stats['sessions'] * 100):.1f}%" if stats['sessions'] > 0 else "0%",
                'Avg Duration': format_duration(sum(stats['durations']) / len(stats['durations'])) if stats['durations'] else "N/A"
            }
            for agent, stats in agent_stats.items()
        ])

        st.dataframe(agent_df, use_container_width=True)

if __name__ == "__main__":
    # Check if logs directory and database exist
    logs_dir = Path("logs")
    db_path = logs_dir / "agent_logs.db"

    if not logs_dir.exists() or not db_path.exists():
        st.error("No agent logs found. Please run some agent analyses first.")
        st.info("The logging system will create logs automatically when you use the evidence analysis agent.")
    else:
        main()