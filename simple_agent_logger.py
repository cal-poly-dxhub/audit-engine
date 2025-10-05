#!/usr/bin/env python3
"""
Simple Agent Logger for User-Friendly Display

This creates a simple JSON log file that gets overwritten for each new analysis,
making it easy to display the latest agent steps in a user-friendly format.
"""

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional
import logging

class SimpleAgentLogger:
    """Simple logger that creates user-friendly analysis step logs"""

    def __init__(self, log_file: str = "latest_agent_steps.json"):
        self.log_file = Path(log_file)
        self.current_analysis = None
        self.logger = logging.getLogger(__name__)

    def start_analysis(self,
                      task_description: str,
                      task_context: Dict[str, Any],
                      user_description: str,
                      filename: str,
                      agent_type: str = "claude_code_sdk"):
        """Start a new analysis session - overwrites previous log"""

        self.current_analysis = {
            "analysis_info": {
                "task_description": task_description,
                "task_context": task_context,
                "user_description": user_description,
                "filename": filename,
                "agent_type": agent_type,
                "start_time": datetime.now().isoformat(),
                "start_timestamp": time.time()
            },
            "steps": [],
            "status": "running",
            "current_step": "Initializing analysis...",
            "progress": {
                "current_step_number": 0,
                "total_steps": 0,
                "percentage": 0
            }
        }

        self._save_to_file()

    def update_current_step(self, step_description: str, step_number: int = None, total_steps: int = None):
        """Update the current step description"""
        if not self.current_analysis:
            return

        self.current_analysis["current_step"] = step_description

        if step_number is not None:
            self.current_analysis["progress"]["current_step_number"] = step_number

        if total_steps is not None:
            self.current_analysis["progress"]["total_steps"] = total_steps

        if step_number is not None and total_steps is not None and total_steps > 0:
            self.current_analysis["progress"]["percentage"] = int((step_number / total_steps) * 100)

        self._save_to_file()

    def add_step(self,
                step_type: str,
                title: str,
                description: str,
                details: Optional[Dict[str, Any]] = None,
                status: str = "completed"):
        """Add a completed step to the log"""
        if not self.current_analysis:
            return

        step = {
            "step_number": len(self.current_analysis["steps"]) + 1,
            "step_type": step_type,  # "tool_use", "agent_response", "analysis", "error"
            "title": title,
            "description": description,
            "timestamp": datetime.now().isoformat(),
            "status": status,
            "details": details or {}
        }

        self.current_analysis["steps"].append(step)
        self._save_to_file()

    def add_tool_call(self,
                     tool_name: str,
                     input_params: Dict[str, Any],
                     output_result: Optional[str] = None,
                     error_message: Optional[str] = None,
                     duration_ms: Optional[float] = None):
        """Add or update a tool call step"""

        status = "completed" if output_result else ("failed" if error_message else "running")

        # Create user-friendly descriptions for different tools (without emojis)
        if tool_name == "mcp__pdf-tools__extract_pdf_text":
            title = "Extracting text from PDF"
            file_path = input_params.get('file_path', 'file')
            filename = Path(file_path).name if file_path else 'file'
            description = f"Reading document content from {filename}"
        elif tool_name == "Bash":
            command = input_params.get("command", "")
            title = "Running command"
            description = f"Executing: {command}"
        elif tool_name == "Read":
            file_path = input_params.get("file_path", "")
            title = "Reading file"
            description = f"Reading content from {Path(file_path).name if file_path else 'file'}"
        elif tool_name == "Write":
            file_path = input_params.get("file_path", "")
            title = "Writing file"
            description = f"Writing analysis results to {Path(file_path).name if file_path else 'file'}"
        elif tool_name == "Grep":
            pattern = input_params.get("pattern", "")
            title = "Searching content"
            description = f"Searching for pattern: '{pattern}'"
        elif tool_name == "Glob":
            pattern = input_params.get("pattern", "")
            title = "Finding files"
            description = f"Looking for files matching: {pattern}"
        elif tool_name == "WebFetch":
            url = input_params.get("url", "")
            title = "Fetching web content"
            description = f"Retrieving information from: {url}"
        else:
            title = f"Using {tool_name}"
            description = f"Executing {tool_name} tool"

        details = {
            "tool_name": tool_name,
            "input_params": input_params,
            "duration_ms": duration_ms
        }

        if output_result:
            # Truncate long outputs for display
            if len(output_result) > 500:
                details["output_preview"] = output_result[:500] + "... (truncated)"
                details["output_length"] = len(output_result)
            else:
                details["output_preview"] = output_result

        if error_message:
            details["error_message"] = error_message

        # Check if this tool call already exists (to avoid duplicates)
        if self.current_analysis and self.current_analysis["steps"]:
            # Look for existing tool call with same name and input params
            for step in reversed(self.current_analysis["steps"]):
                if (step.get("step_type") == "tool_use" and
                    step.get("details", {}).get("tool_name") == tool_name and
                    step.get("details", {}).get("input_params") == input_params and
                    step.get("status") == "running"):
                    # Update existing step instead of creating new one
                    step["status"] = status
                    step["timestamp"] = datetime.now().isoformat()
                    step["details"].update(details)
                    self._save_to_file()
                    return

        # If no existing running step found, create new one
        self.add_step("tool_use", title, description, details, status)

    def add_agent_response(self, response_text: str):
        """Add an agent response step"""

        # Extract key insights from response for summary
        summary = response_text[:200] + "..." if len(response_text) > 200 else response_text

        details = {
            "full_response": response_text,
            "response_length": len(response_text)
        }

        self.add_step(
            "agent_response",
            "Agent Analysis",
            f"AI analysis: {summary}",
            details
        )

    def add_analysis_milestone(self, milestone: str, description: str, details: Optional[Dict] = None):
        """Add a major analysis milestone"""

        self.add_step(
            "analysis",
            milestone,
            description,
            details or {}
        )

    def complete_analysis(self,
                         final_result: Optional[Dict[str, Any]] = None,
                         error_message: Optional[str] = None):
        """Mark the analysis as completed"""
        if not self.current_analysis:
            return

        end_time = time.time()
        start_time = self.current_analysis["analysis_info"]["start_timestamp"]
        duration_seconds = end_time - start_time

        self.current_analysis["status"] = "completed" if not error_message else "failed"
        self.current_analysis["end_time"] = datetime.now().isoformat()
        self.current_analysis["duration_seconds"] = duration_seconds
        self.current_analysis["current_step"] = "Analysis completed" if not error_message else f"Analysis failed: {error_message}"

        if final_result:
            self.current_analysis["final_result"] = {
                "is_valid": final_result.get("is_valid"),
                "confidence": final_result.get("confidence"),
                "evidence_quality": final_result.get("evidence_quality"),
                "recommendation": final_result.get("recommendation"),
                "reasoning": final_result.get("reasoning", "")[:500] + "..." if len(final_result.get("reasoning", "")) > 500 else final_result.get("reasoning", ""),
                "annotations_count": len(final_result.get("annotations", []))
            }

        if error_message:
            self.current_analysis["error_message"] = error_message

        # Update progress to 100%
        total_steps = len(self.current_analysis["steps"])
        self.current_analysis["progress"]["current_step_number"] = total_steps
        self.current_analysis["progress"]["total_steps"] = total_steps
        self.current_analysis["progress"]["percentage"] = 100

        self._save_to_file()

    def _save_to_file(self):
        """Save current analysis to JSON file"""
        try:
            with open(self.log_file, 'w') as f:
                json.dump(self.current_analysis, f, indent=2, default=str)
        except Exception as e:
            self.logger.error(f"Failed to save simple log: {e}")

    def get_current_analysis(self) -> Optional[Dict[str, Any]]:
        """Get the current analysis data"""
        return self.current_analysis

    def load_latest_analysis(self) -> Optional[Dict[str, Any]]:
        """Load the latest analysis from file"""
        try:
            if self.log_file.exists():
                with open(self.log_file, 'r') as f:
                    return json.load(f)
        except Exception as e:
            self.logger.error(f"Failed to load simple log: {e}")
        return None

# Global instance
simple_logger = SimpleAgentLogger()

# Convenience functions to integrate with existing code
def start_simple_analysis(task_description: str, task_context: Dict[str, Any],
                         user_description: str, filename: str, agent_type: str = "claude_code_sdk"):
    simple_logger.start_analysis(task_description, task_context, user_description, filename, agent_type)

def update_simple_step(step_description: str, step_number: int = None, total_steps: int = None):
    simple_logger.update_current_step(step_description, step_number, total_steps)

def add_simple_tool_call(tool_name: str, input_params: Dict[str, Any],
                        output_result: Optional[str] = None, error_message: Optional[str] = None,
                        duration_ms: Optional[float] = None):
    simple_logger.add_tool_call(tool_name, input_params, output_result, error_message, duration_ms)

def add_simple_agent_response(response_text: str):
    simple_logger.add_agent_response(response_text)

def add_simple_milestone(milestone: str, description: str, details: Optional[Dict] = None):
    simple_logger.add_analysis_milestone(milestone, description, details)

def complete_simple_analysis(final_result: Optional[Dict[str, Any]] = None, error_message: Optional[str] = None):
    simple_logger.complete_analysis(final_result, error_message)