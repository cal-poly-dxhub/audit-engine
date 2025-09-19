#!/usr/bin/env python3
"""
Comprehensive Agent Activity Logger

This module provides detailed logging and tracking of all Claude Code agent activities,
including tool usage, responses, performance metrics, and analysis workflows.
"""

import json
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Any, Optional
import logging
from dataclasses import dataclass, asdict
from enum import Enum
import sqlite3
import threading

class LogLevel(Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"

class ToolStatus(Enum):
    STARTED = "STARTED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"

@dataclass
class ToolCall:
    """Represents a single tool call made by the agent"""
    tool_id: str
    tool_name: str
    input_params: Dict[str, Any]
    output_result: Optional[str] = None
    error_message: Optional[str] = None
    status: ToolStatus = ToolStatus.STARTED
    start_time: float = 0.0
    end_time: Optional[float] = None
    duration_ms: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            'tool_id': self.tool_id,
            'tool_name': self.tool_name,
            'input_params': self.input_params,
            'output_result': self.output_result,
            'error_message': self.error_message,
            'status': self.status.value,
            'start_time': self.start_time,
            'end_time': self.end_time,
            'duration_ms': self.duration_ms
        }

@dataclass
class AgentSession:
    """Represents a complete agent analysis session"""
    session_id: str
    analysis_id: str
    agent_type: str
    task_description: str
    task_context: Dict[str, Any]
    user_description: str
    filename: str
    start_time: float
    end_time: Optional[float] = None
    duration_ms: Optional[float] = None
    tool_calls: List[ToolCall] = None
    agent_responses: List[str] = None
    final_result: Optional[Dict[str, Any]] = None
    status: str = "RUNNING"
    error_message: Optional[str] = None

    def __post_init__(self):
        if self.tool_calls is None:
            self.tool_calls = []
        if self.agent_responses is None:
            self.agent_responses = []

    def to_dict(self) -> Dict[str, Any]:
        return {
            'session_id': self.session_id,
            'analysis_id': self.analysis_id,
            'agent_type': self.agent_type,
            'task_description': self.task_description,
            'task_context': self.task_context,
            'user_description': self.user_description,
            'filename': self.filename,
            'start_time': self.start_time,
            'end_time': self.end_time,
            'duration_ms': self.duration_ms,
            'tool_calls': [tc.to_dict() for tc in self.tool_calls],
            'agent_responses': self.agent_responses,
            'final_result': self.final_result,
            'status': self.status,
            'error_message': self.error_message
        }

class AgentLogger:
    """Comprehensive logging system for Claude Code agent activities"""

    def __init__(self, log_dir: str = "logs"):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True)

        # Setup file logging
        self.setup_file_logging()

        # Setup SQLite database for structured logs
        self.setup_database()

        # Current session tracking
        self.current_session: Optional[AgentSession] = None
        self.current_tool_calls: Dict[str, ToolCall] = {}
        self.lock = threading.Lock()

        self.logger = logging.getLogger(__name__)

    def setup_file_logging(self):
        """Setup comprehensive file logging"""
        log_file = self.log_dir / f"agent_activity_{datetime.now().strftime('%Y%m%d')}.log"

        formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - [%(name)s] - %(message)s'
        )

        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(formatter)
        file_handler.setLevel(logging.DEBUG)

        logger = logging.getLogger('agent_logger')
        logger.setLevel(logging.DEBUG)
        logger.addHandler(file_handler)

        # Prevent duplicate logs
        logger.propagate = False

        self.file_logger = logger

    def setup_database(self):
        """Setup SQLite database for structured logging"""
        db_path = self.log_dir / "agent_logs.db"
        self.db_path = db_path

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Create sessions table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                analysis_id TEXT,
                agent_type TEXT,
                task_description TEXT,
                task_context TEXT,
                user_description TEXT,
                filename TEXT,
                start_time REAL,
                end_time REAL,
                duration_ms REAL,
                status TEXT,
                error_message TEXT,
                final_result TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Create tool_calls table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS tool_calls (
                tool_id TEXT PRIMARY KEY,
                session_id TEXT,
                tool_name TEXT,
                input_params TEXT,
                output_result TEXT,
                error_message TEXT,
                status TEXT,
                start_time REAL,
                end_time REAL,
                duration_ms REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (session_id) REFERENCES sessions (session_id)
            )
        ''')

        # Create agent_responses table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS agent_responses (
                response_id TEXT PRIMARY KEY,
                session_id TEXT,
                response_text TEXT,
                response_order INTEGER,
                timestamp REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (session_id) REFERENCES sessions (session_id)
            )
        ''')

        conn.commit()
        conn.close()

    def start_session(self,
                     analysis_id: str,
                     agent_type: str,
                     task_description: str,
                     task_context: Dict[str, Any],
                     user_description: str,
                     filename: str) -> str:
        """Start a new agent analysis session"""

        with self.lock:
            session_id = str(uuid.uuid4())
            start_time = time.time()

            self.current_session = AgentSession(
                session_id=session_id,
                analysis_id=analysis_id,
                agent_type=agent_type,
                task_description=task_description,
                task_context=task_context,
                user_description=user_description,
                filename=filename,
                start_time=start_time
            )

            # Log to file
            self.file_logger.info(f"[SESSION_START] {session_id} - Analysis: {analysis_id}")
            self.file_logger.info(f"[SESSION_DETAILS] Agent: {agent_type}, File: {filename}")
            self.file_logger.info(f"[TASK] {task_description}")
            self.file_logger.info(f"[CONTEXT] {json.dumps(task_context, indent=2)}")
            self.file_logger.info(f"[USER_DESC] {user_description}")

            # Store in database
            self._save_session_to_db()

            return session_id

    def log_tool_start(self, tool_name: str, input_params: Dict[str, Any]) -> str:
        """Log the start of a tool call"""

        with self.lock:
            if not self.current_session:
                self.file_logger.warning("Tool call logged without active session")
                return ""

            tool_id = str(uuid.uuid4())
            start_time = time.time()

            tool_call = ToolCall(
                tool_id=tool_id,
                tool_name=tool_name,
                input_params=input_params,
                status=ToolStatus.STARTED,
                start_time=start_time
            )

            self.current_tool_calls[tool_id] = tool_call
            self.current_session.tool_calls.append(tool_call)

            # Log to file with detailed parameters
            self.file_logger.info(f"[TOOL_START] {tool_name} - ID: {tool_id}")

            # Log specific tool parameters based on tool type
            if tool_name == "Bash":
                command = input_params.get("command", "")
                self.file_logger.info(f"[BASH_COMMAND] {command}")
            elif tool_name == "Read":
                file_path = input_params.get("file_path", "")
                self.file_logger.info(f"[READ_FILE] {file_path}")
            elif tool_name == "Write":
                file_path = input_params.get("file_path", "")
                content_length = len(input_params.get("content", ""))
                self.file_logger.info(f"[WRITE_FILE] {file_path} ({content_length} chars)")
            elif tool_name == "Grep":
                pattern = input_params.get("pattern", "")
                path = input_params.get("path", "")
                self.file_logger.info(f"[GREP_SEARCH] '{pattern}' in {path}")
            elif tool_name == "Glob":
                pattern = input_params.get("pattern", "")
                self.file_logger.info(f"[GLOB_SEARCH] {pattern}")
            elif tool_name.startswith("mcp__"):
                self.file_logger.info(f"[MCP_TOOL] {tool_name}")

            # Log all parameters for debugging
            self.file_logger.debug(f"[TOOL_PARAMS] {json.dumps(input_params, indent=2)}")

            return tool_id

    def log_tool_complete(self, tool_id: str, output_result: str):
        """Log the completion of a tool call"""

        with self.lock:
            if tool_id not in self.current_tool_calls:
                self.file_logger.warning(f"Tool completion logged for unknown tool: {tool_id}")
                return

            tool_call = self.current_tool_calls[tool_id]
            end_time = time.time()
            duration_ms = (end_time - tool_call.start_time) * 1000

            tool_call.end_time = end_time
            tool_call.duration_ms = duration_ms
            tool_call.output_result = output_result
            tool_call.status = ToolStatus.COMPLETED

            # Log to file
            self.file_logger.info(f"[TOOL_COMPLETE] {tool_call.tool_name} - Duration: {duration_ms:.1f}ms")

            # Log output preview for different tool types
            if tool_call.tool_name == "Bash":
                output_preview = output_result[:200] if output_result else "No output"
                self.file_logger.info(f"[BASH_OUTPUT] {output_preview}{'...' if len(output_result) > 200 else ''}")
            elif tool_call.tool_name == "Read":
                lines = output_result.count('\n') if output_result else 0
                self.file_logger.info(f"[READ_OUTPUT] {lines} lines read")
            elif tool_call.tool_name in ["Grep", "Glob"]:
                matches = output_result.count('\n') if output_result else 0
                self.file_logger.info(f"[SEARCH_OUTPUT] {matches} matches found")

            # Save tool call to database
            self._save_tool_call_to_db(tool_call)

    def log_tool_error(self, tool_id: str, error_message: str):
        """Log a tool call error"""

        with self.lock:
            if tool_id not in self.current_tool_calls:
                self.file_logger.warning(f"Tool error logged for unknown tool: {tool_id}")
                return

            tool_call = self.current_tool_calls[tool_id]
            end_time = time.time()
            duration_ms = (end_time - tool_call.start_time) * 1000

            tool_call.end_time = end_time
            tool_call.duration_ms = duration_ms
            tool_call.error_message = error_message
            tool_call.status = ToolStatus.FAILED

            # Log to file
            self.file_logger.error(f"[TOOL_ERROR] {tool_call.tool_name} - {error_message}")

            # Save tool call to database
            self._save_tool_call_to_db(tool_call)

    def log_agent_response(self, response_text: str):
        """Log agent response text"""

        with self.lock:
            if not self.current_session:
                self.file_logger.warning("Agent response logged without active session")
                return

            self.current_session.agent_responses.append(response_text)

            # Log to file with preview
            response_preview = response_text[:300] if response_text else ""
            self.file_logger.info(f"[AGENT_RESPONSE] {response_preview}{'...' if len(response_text) > 300 else ''}")

            # Save to database
            self._save_agent_response_to_db(response_text, len(self.current_session.agent_responses) - 1)

    def end_session(self, final_result: Optional[Dict[str, Any]] = None, error_message: Optional[str] = None):
        """End the current agent session"""

        with self.lock:
            if not self.current_session:
                self.file_logger.warning("Session end logged without active session")
                return

            end_time = time.time()
            duration_ms = (end_time - self.current_session.start_time) * 1000

            self.current_session.end_time = end_time
            self.current_session.duration_ms = duration_ms
            self.current_session.final_result = final_result
            self.current_session.error_message = error_message
            self.current_session.status = "COMPLETED" if not error_message else "FAILED"

            # Log session summary
            self.file_logger.info(f"[SESSION_END] {self.current_session.session_id}")
            self.file_logger.info(f"[SESSION_SUMMARY] Duration: {duration_ms:.1f}ms, Tools used: {len(self.current_session.tool_calls)}")

            if final_result:
                is_valid = final_result.get('is_valid', 'unknown')
                confidence = final_result.get('confidence', 0)
                self.file_logger.info(f"[ANALYSIS_RESULT] Valid: {is_valid}, Confidence: {confidence:.2f}")

            if error_message:
                self.file_logger.error(f"[SESSION_ERROR] {error_message}")

            # Save final session state to database
            self._save_session_to_db()

            # Save session to JSON file for backup
            self._save_session_to_json()

            # Reset current session
            self.current_session = None
            self.current_tool_calls.clear()

    def _save_session_to_db(self):
        """Save current session to database"""
        if not self.current_session:
            return

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            INSERT OR REPLACE INTO sessions
            (session_id, analysis_id, agent_type, task_description, task_context,
             user_description, filename, start_time, end_time, duration_ms,
             status, error_message, final_result)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            self.current_session.session_id,
            self.current_session.analysis_id,
            self.current_session.agent_type,
            self.current_session.task_description,
            json.dumps(self.current_session.task_context),
            self.current_session.user_description,
            self.current_session.filename,
            self.current_session.start_time,
            self.current_session.end_time,
            self.current_session.duration_ms,
            self.current_session.status,
            self.current_session.error_message,
            json.dumps(self.current_session.final_result) if self.current_session.final_result else None
        ))

        conn.commit()
        conn.close()

    def _save_tool_call_to_db(self, tool_call: ToolCall):
        """Save tool call to database"""
        if not self.current_session:
            return

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            INSERT OR REPLACE INTO tool_calls
            (tool_id, session_id, tool_name, input_params, output_result,
             error_message, status, start_time, end_time, duration_ms)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            tool_call.tool_id,
            self.current_session.session_id,
            tool_call.tool_name,
            json.dumps(tool_call.input_params),
            tool_call.output_result,
            tool_call.error_message,
            tool_call.status.value,
            tool_call.start_time,
            tool_call.end_time,
            tool_call.duration_ms
        ))

        conn.commit()
        conn.close()

    def _save_agent_response_to_db(self, response_text: str, order: int):
        """Save agent response to database"""
        if not self.current_session:
            return

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        response_id = str(uuid.uuid4())

        cursor.execute('''
            INSERT INTO agent_responses
            (response_id, session_id, response_text, response_order, timestamp)
            VALUES (?, ?, ?, ?, ?)
        ''', (
            response_id,
            self.current_session.session_id,
            response_text,
            order,
            time.time()
        ))

        conn.commit()
        conn.close()

    def _save_session_to_json(self):
        """Save session to JSON file for backup"""
        if not self.current_session:
            return

        json_file = self.log_dir / f"session_{self.current_session.session_id}.json"

        with open(json_file, 'w') as f:
            json.dump(self.current_session.to_dict(), f, indent=2, default=str)

    def get_recent_sessions(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent agent sessions from database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            SELECT * FROM sessions
            ORDER BY created_at DESC
            LIMIT ?
        ''', (limit,))

        columns = [desc[0] for desc in cursor.description]
        sessions = []

        for row in cursor.fetchall():
            session_dict = dict(zip(columns, row))
            # Parse JSON fields
            if session_dict['task_context']:
                session_dict['task_context'] = json.loads(session_dict['task_context'])
            if session_dict['final_result']:
                session_dict['final_result'] = json.loads(session_dict['final_result'])
            sessions.append(session_dict)

        conn.close()
        return sessions

    def get_session_details(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get detailed information for a specific session"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Get session info
        cursor.execute('SELECT * FROM sessions WHERE session_id = ?', (session_id,))
        session_row = cursor.fetchone()

        if not session_row:
            conn.close()
            return None

        session_columns = [desc[0] for desc in cursor.description]
        session = dict(zip(session_columns, session_row))

        # Parse JSON fields
        if session['task_context']:
            session['task_context'] = json.loads(session['task_context'])
        if session['final_result']:
            session['final_result'] = json.loads(session['final_result'])

        # Get tool calls
        cursor.execute('''
            SELECT * FROM tool_calls
            WHERE session_id = ?
            ORDER BY start_time ASC
        ''', (session_id,))

        tool_columns = [desc[0] for desc in cursor.description]
        tool_calls = []

        for row in cursor.fetchall():
            tool_call = dict(zip(tool_columns, row))
            if tool_call['input_params']:
                tool_call['input_params'] = json.loads(tool_call['input_params'])
            tool_calls.append(tool_call)

        # Get agent responses
        cursor.execute('''
            SELECT * FROM agent_responses
            WHERE session_id = ?
            ORDER BY response_order ASC
        ''', (session_id,))

        response_columns = [desc[0] for desc in cursor.description]
        responses = []

        for row in cursor.fetchall():
            response = dict(zip(response_columns, row))
            responses.append(response)

        conn.close()

        return {
            'session': session,
            'tool_calls': tool_calls,
            'agent_responses': responses
        }

# Global logger instance
agent_logger = AgentLogger()

# Convenience functions
def start_agent_session(analysis_id: str, agent_type: str, task_description: str,
                       task_context: Dict[str, Any], user_description: str, filename: str) -> str:
    return agent_logger.start_session(analysis_id, agent_type, task_description,
                                    task_context, user_description, filename)

def log_tool_start(tool_name: str, input_params: Dict[str, Any]) -> str:
    return agent_logger.log_tool_start(tool_name, input_params)

def log_tool_complete(tool_id: str, output_result: str):
    agent_logger.log_tool_complete(tool_id, output_result)

def log_tool_error(tool_id: str, error_message: str):
    agent_logger.log_tool_error(tool_id, error_message)

def log_agent_response(response_text: str):
    agent_logger.log_agent_response(response_text)

def end_agent_session(final_result: Optional[Dict[str, Any]] = None, error_message: Optional[str] = None):
    agent_logger.end_session(final_result, error_message)