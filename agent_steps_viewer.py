#!/usr/bin/env python3
"""
Agent Steps Viewer - Streamlit App

A simple, user-friendly interface to view the latest evidence analysis agent steps.
This app reads from the latest_agent_steps.json file and displays the process
in an easy-to-understand format for non-technical stakeholders.
"""

import streamlit as st
import json
import time
from datetime import datetime
from pathlib import Path
import pandas as pd

# Page configuration
st.set_page_config(
    page_title="Evidence Analysis Agent Steps",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded"
)

def load_latest_analysis():
    """Load the latest analysis from the JSON file"""
    log_file = Path("latest_agent_steps.json")

    if not log_file.exists():
        return None

    try:
        with open(log_file, 'r') as f:
            return json.load(f)
    except Exception as e:
        st.error(f"Error loading analysis data: {e}")
        return None

def format_duration(seconds):
    """Format duration in a human-readable way"""
    if seconds < 1:
        return f"{seconds*1000:.0f}ms"
    elif seconds < 60:
        return f"{seconds:.1f}s"
    else:
        minutes = int(seconds // 60)
        remaining_seconds = seconds % 60
        return f"{minutes}m {remaining_seconds:.1f}s"

def format_timestamp(iso_timestamp):
    """Format ISO timestamp for display"""
    try:
        dt = datetime.fromisoformat(iso_timestamp.replace('Z', '+00:00'))
        return dt.strftime("%H:%M:%S")
    except:
        return iso_timestamp

def get_step_icon(step_type):
    """Get icon for step type"""
    icons = {
        "tool_use": "Tool",
        "agent_response": "AI",
        "analysis": "Analysis",
        "error": "Error"
    }
    return icons.get(step_type, "Step")

def display_task_info(analysis_data):
    """Display task information"""
    info = analysis_data.get("analysis_info", {})

    st.header("Task Information")

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Task Details")
        st.write(f"**Description:** {info.get('task_description', 'N/A')}")
        st.write(f"**Document:** {info.get('filename', 'N/A')}")
        st.write(f"**Agent Type:** {info.get('agent_type', 'N/A')}")

        if info.get('user_description'):
            st.write(f"**User Explanation:** {info.get('user_description')}")

    with col2:
        st.subheader("Context")
        context = info.get('task_context', {})
        if context:
            st.write(f"**Department:** {context.get('department', 'N/A')}")
            st.write(f"**Type:** {context.get('implementation_type', 'N/A')}")
            st.write(f"**Division:** {context.get('division', 'N/A')}")

            if context.get('requires_collaboration'):
                st.write("**Collaboration:** Required")
        else:
            st.write("No context information available")

def display_progress(analysis_data):
    """Display analysis progress"""
    status = analysis_data.get("status", "unknown")
    current_step = analysis_data.get("current_step", "No current step")
    progress_info = analysis_data.get("progress", {})

    # Status indicator
    status_colors = {
        "running": "Running",
        "completed": "Completed",
        "failed": "Failed"
    }

    status_text = status_colors.get(status, "Unknown")

    st.header(f"Analysis Status: {status_text}")
    st.write(f"**Current Step:** {current_step}")

    # Progress bar
    if progress_info.get("total_steps", 0) > 0:
        progress_pct = progress_info.get("percentage", 0)
        current_num = progress_info.get("current_step_number", 0)
        total_num = progress_info.get("total_steps", 0)

        st.progress(progress_pct / 100)
        st.write(f"Step {current_num} of {total_num} ({progress_pct}%)")

    # Timing information
    if analysis_data.get("start_time"):
        start_time = analysis_data["analysis_info"]["start_time"]
        st.write(f"**Started:** {format_timestamp(start_time)}")

        if analysis_data.get("end_time"):
            duration = analysis_data.get("duration_seconds", 0)
            st.write(f"**Duration:** {format_duration(duration)}")
        elif status == "running":
            # Calculate current duration for running analysis
            start_ts = analysis_data["analysis_info"]["start_timestamp"]
            current_duration = time.time() - start_ts
            st.write(f"**Running for:** {format_duration(current_duration)}")

def display_steps(analysis_data):
    """Display analysis steps"""
    steps = analysis_data.get("steps", [])

    if not steps:
        st.info("No steps recorded yet.")
        return

    st.header(f"Analysis Steps ({len(steps)} total)")

    # Create tabs for different step types
    all_steps_tab, tools_tab, responses_tab = st.tabs(["All Steps", "Tool Usage", "AI Responses"])

    with all_steps_tab:
        for i, step in enumerate(steps):
            with st.expander(f"Step {step.get('step_number', i+1)}: {step.get('title', 'Unnamed Step')}",
                           expanded=(i >= len(steps) - 3)):  # Show last 3 steps expanded

                col1, col2, col3 = st.columns([3, 1, 1])

                with col1:
                    st.write(f"**[{get_step_icon(step.get('step_type', 'unknown'))}] {step.get('title', 'Unnamed Step')}**")
                    st.write(step.get('description', 'No description'))

                with col2:
                    st.write(f"**Status:** {step.get('status', 'unknown')}")
                    st.write(f"**Time:** {format_timestamp(step.get('timestamp', ''))}")

                with col3:
                    step_type = step.get('step_type', 'unknown')
                    st.write(f"**Type:** {step_type}")

                # Show details for tool usage
                details = step.get('details', {})
                if details and step.get('step_type') == 'tool_use':
                    st.subheader("Tool Details")

                    tool_name = details.get('tool_name', 'Unknown')
                    st.write(f"**Tool:** {tool_name}")

                    if details.get('duration_ms'):
                        duration = details['duration_ms'] / 1000
                        st.write(f"**Duration:** {format_duration(duration)}")

                    # Input parameters
                    if details.get('input_params'):
                        st.write("**Input Parameters:**")
                        input_params = details['input_params']

                        # Show key parameters in a readable way
                        if tool_name == "mcp__pdf-tools__extract_pdf_text":
                            file_path = input_params.get('file_path', '')
                            st.write(f"  - File: {Path(file_path).name if file_path else 'Unknown'}")
                        elif tool_name == "Bash":
                            command = input_params.get('command', '')
                            st.code(command, language='bash')
                        elif tool_name in ["Read", "Write"]:
                            file_path = input_params.get('file_path', '')
                            st.write(f"  - File: {Path(file_path).name if file_path else 'Unknown'}")
                        elif tool_name == "Grep":
                            pattern = input_params.get('pattern', '')
                            path = input_params.get('path', '')
                            st.write(f"  - Pattern: `{pattern}`")
                            st.write(f"  - Path: {path}")
                        else:
                            # Show a few key parameters
                            for key, value in list(input_params.items())[:3]:
                                if isinstance(value, str) and len(value) > 100:
                                    st.write(f"  - {key}: {value[:100]}...")
                                else:
                                    st.write(f"  - {key}: {value}")

                    # Output/Error
                    if details.get('output_preview'):
                        st.write("**Output Preview:**")
                        output = details['output_preview']
                        if len(output) > 200:
                            st.text_area("Output", output, height=100, key=f"output_{i}")
                        else:
                            st.code(output)

                        if details.get('output_length'):
                            st.write(f"*Full output: {details['output_length']} characters*")

                    if details.get('error_message'):
                        st.error(f"**Error:** {details['error_message']}")

                # Show details for agent responses
                elif details and step.get('step_type') == 'agent_response':
                    if details.get('full_response'):
                        response = details['full_response']
                        if len(response) > 500:
                            st.text_area("Full Response", response, height=200, key=f"response_{i}")
                        else:
                            st.write(response)

                        st.write(f"*Response length: {details.get('response_length', len(response))} characters*")

    with tools_tab:
        tool_steps = [s for s in steps if s.get('step_type') == 'tool_use']
        if tool_steps:
            # Create a summary table
            tool_data = []
            for step in tool_steps:
                details = step.get('details', {})
                tool_data.append({
                    'Step': step.get('step_number', 0),
                    'Tool': details.get('tool_name', 'Unknown'),
                    'Status': step.get('status', 'unknown'),
                    'Duration': f"{details.get('duration_ms', 0)/1000:.2f}s" if details.get('duration_ms') else 'N/A',
                    'Time': format_timestamp(step.get('timestamp', ''))
                })

            df = pd.DataFrame(tool_data)
            st.dataframe(df, use_container_width=True)
        else:
            st.info("No tool usage steps recorded yet.")

    with responses_tab:
        response_steps = [s for s in steps if s.get('step_type') == 'agent_response']
        if response_steps:
            for i, step in enumerate(response_steps):
                st.subheader(f"Response {i+1} - {format_timestamp(step.get('timestamp', ''))}")
                details = step.get('details', {})
                if details.get('full_response'):
                    st.text_area(f"Response {i+1}", details['full_response'], height=150, key=f"resp_tab_{i}")
        else:
            st.info("No AI response steps recorded yet.")

def display_final_result(analysis_data):
    """Display final analysis result"""
    final_result = analysis_data.get("final_result")

    if not final_result:
        return

    st.header("Final Analysis Result")

    col1, col2, col3 = st.columns(3)

    with col1:
        is_valid = final_result.get("is_valid")
        if is_valid is True:
            st.success("Evidence ACCEPTED")
        elif is_valid is False:
            st.error("Evidence REJECTED")
        else:
            st.warning("Result Unknown")

    with col2:
        confidence = final_result.get("confidence", 0)
        if confidence > 0:
            st.metric("Confidence", f"{confidence*100:.1f}%")

    with col3:
        quality = final_result.get("evidence_quality", "unknown")
        st.write(f"**Quality:** {quality.title()}")

    # Recommendation
    recommendation = final_result.get("recommendation", "unknown")
    rec_colors = {
        "accept": "success",
        "reject": "error",
        "request_additional": "warning"
    }
    rec_color = rec_colors.get(recommendation, "info")

    if recommendation == "accept":
        st.success("**Recommendation:** Accept Evidence")
    elif recommendation == "reject":
        st.error("**Recommendation:** Reject Evidence")
    elif recommendation == "request_additional":
        st.warning("**Recommendation:** Request Additional Evidence")
    else:
        st.info(f"**Recommendation:** {recommendation}")

    # Reasoning
    if final_result.get("reasoning"):
        st.subheader("Reasoning")
        st.write(final_result["reasoning"])

    # Annotations count
    annotations_count = final_result.get("annotations_count", 0)
    if annotations_count > 0:
        st.write(f"**Citations Found:** {annotations_count} text passages highlighted")

def main():
    """Main application"""
    st.title("Evidence Analysis Agent Steps")
    st.markdown("*Real-time view of AI agent analysis process*")

    # Auto-refresh control
    col1, col2, col3 = st.columns([2, 1, 1])

    with col1:
        auto_refresh = st.checkbox("Auto-refresh (5 seconds)", value=True)

    with col2:
        if st.button("Refresh Now"):
            st.rerun()

    with col3:
        if st.button("View Full Logs"):
            st.info("Check the 'logs' directory for detailed technical logs")

    # Load and display analysis
    analysis_data = load_latest_analysis()

    if not analysis_data:
        st.warning("No analysis data found. Upload a document in the evidence validation app to see agent steps here.")
        st.info("Make sure the evidence validation server is running and you've submitted a document for analysis.")

        # Show example of what this will look like
        st.subheader("Preview: What you'll see here")
        st.info("Agent analysis steps will be displayed in real-time when you upload evidence documents.")
        return

    # Display all sections
    display_task_info(analysis_data)
    st.divider()

    display_progress(analysis_data)
    st.divider()

    display_steps(analysis_data)
    st.divider()

    display_final_result(analysis_data)

    # Auto-refresh
    if auto_refresh and analysis_data.get("status") == "running":
        time.sleep(5)
        st.rerun()

    # Footer
    st.markdown("---")
    st.markdown("*Evidence Analysis Agent Steps Viewer - Built with Streamlit*")

if __name__ == "__main__":
    main()