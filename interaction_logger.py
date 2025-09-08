import json
import os
import time
from datetime import datetime
from pathlib import Path
import uuid

class InteractionLogger:
    def __init__(self, log_dir="interaction_logs"):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True)
        
        # Create subdirectories
        (self.log_dir / "sessions").mkdir(exist_ok=True)
        (self.log_dir / "uploads").mkdir(exist_ok=True)
        (self.log_dir / "uploaded_files").mkdir(exist_ok=True)  # Store actual files
        (self.log_dir / "ai_commands").mkdir(exist_ok=True)
        (self.log_dir / "edits").mkdir(exist_ok=True)
        (self.log_dir / "exports").mkdir(exist_ok=True)
        
        # Main interaction log file
        self.main_log_file = self.log_dir / f"interactions_{datetime.now().strftime('%Y%m%d')}.jsonl"
        
    def _write_log(self, log_data):
        """Write log entry to main log file"""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "session_id": log_data.get("session_id"),
            **log_data
        }
        
        with open(self.main_log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(log_entry) + "\n")
    
    def log_session_start(self, session_id, user_ip, user_agent):
        """Log when a user starts a session"""
        session_data = {
            "event_type": "session_start",
            "session_id": session_id,
            "user_ip": user_ip,
            "user_agent": user_agent,
            "platform": "macos" if "Mac" in user_agent else "linux" if "Linux" in user_agent else "unknown"
        }
        
        self._write_log(session_data)
        
        # Create session-specific log file
        session_file = self.log_dir / "sessions" / f"session_{session_id}.json"
        with open(session_file, "w", encoding="utf-8") as f:
            json.dump({
                "session_id": session_id,
                "start_time": datetime.now().isoformat(),
                "user_ip": user_ip,
                "user_agent": user_agent,
                "events": []
            }, f, indent=2)
    
    def log_file_upload(self, session_id, filename, file_size, processing_time, observations_count, file_content=None, success=True, error=None):
        """Log file upload and processing"""
        timestamp = int(time.time())
        stored_filename = None
        
        # Store the actual file if provided
        if file_content and filename:
            # Create safe filename with timestamp
            safe_filename = f"{session_id}_{timestamp}_{filename.replace(' ', '_')}"
            stored_file_path = self.log_dir / "uploaded_files" / safe_filename
            
            try:
                with open(stored_file_path, "wb") as f:
                    f.write(file_content)
                stored_filename = safe_filename
            except Exception as e:
                print(f"Warning: Could not store uploaded file: {e}")
        
        upload_data = {
            "event_type": "file_upload",
            "session_id": session_id,
            "filename": filename,
            "stored_filename": stored_filename,
            "file_size_bytes": file_size,
            "processing_time_seconds": processing_time,
            "observations_extracted": observations_count,
            "success": success,
            "error": error
        }
        
        self._write_log(upload_data)
        
        # Save detailed upload log
        upload_file = self.log_dir / "uploads" / f"upload_{session_id}_{timestamp}.json"
        with open(upload_file, "w", encoding="utf-8") as f:
            json.dump(upload_data, f, indent=2)
    
    def log_ai_command(self, session_id, command, response_time, changes_applied, success=True, error=None):
        """Log AI natural language commands"""
        ai_data = {
            "event_type": "ai_command",
            "session_id": session_id,
            "command": command,
            "response_time_seconds": response_time,
            "changes_applied": changes_applied,
            "success": success,
            "error": error
        }
        
        self._write_log(ai_data)
        
        # Save detailed AI command log
        ai_file = self.log_dir / "ai_commands" / f"ai_{session_id}_{int(time.time())}.json"
        with open(ai_file, "w", encoding="utf-8") as f:
            json.dump(ai_data, f, indent=2)
    
    def log_manual_edit(self, session_id, edit_type, obs_idx, task_idx, field, old_value, new_value):
        """Log manual form edits"""
        edit_data = {
            "event_type": "manual_edit",
            "session_id": session_id,
            "edit_type": edit_type,  # "field_change", "task_add", "task_delete", "task_move", "task_combine"
            "observation_index": obs_idx,
            "task_index": task_idx,
            "field": field,
            "old_value": old_value,
            "new_value": new_value
        }
        
        self._write_log(edit_data)
    
    def log_task_operation(self, session_id, operation, obs_idx, task_indices, details=None):
        """Log task operations (add, delete, move, combine)"""
        operation_data = {
            "event_type": "task_operation",
            "session_id": session_id,
            "operation": operation,  # "add", "delete", "move_up", "move_down", "combine"
            "observation_index": obs_idx,
            "task_indices": task_indices,
            "details": details
        }
        
        self._write_log(operation_data)
    
    def log_matrix_generation(self, session_id, processing_time, total_rows, success=True, error=None):
        """Log matrix generation"""
        matrix_data = {
            "event_type": "matrix_generation",
            "session_id": session_id,
            "processing_time_seconds": processing_time,
            "total_rows": total_rows,
            "success": success,
            "error": error
        }
        
        self._write_log(matrix_data)
    
    def log_export(self, session_id, export_format, filename, success=True, error=None):
        """Log file exports"""
        export_data = {
            "event_type": "export",
            "session_id": session_id,
            "export_format": export_format,
            "filename": filename,
            "success": success,
            "error": error
        }
        
        self._write_log(export_data)
        
        # Save detailed export log
        export_file = self.log_dir / "exports" / f"export_{session_id}_{int(time.time())}.json"
        with open(export_file, "w", encoding="utf-8") as f:
            json.dump(export_data, f, indent=2)
    
    def log_session_end(self, session_id, duration_seconds):
        """Log when a session ends"""
        session_data = {
            "event_type": "session_end",
            "session_id": session_id,
            "duration_seconds": duration_seconds
        }
        
        self._write_log(session_data)
    
    def get_session_summary(self, session_id):
        """Get summary of a session's activities"""
        session_file = self.log_dir / "sessions" / f"session_{session_id}.json"
        if session_file.exists():
            with open(session_file, "r", encoding="utf-8") as f:
                return json.load(f)
        return None
    
    def get_daily_stats(self, date=None):
        """Get daily usage statistics"""
        if date is None:
            date = datetime.now().strftime('%Y%m%d')
        
        log_file = self.log_dir / f"interactions_{date}.jsonl"
        if not log_file.exists():
            return {}
        
        stats = {
            "total_sessions": 0,
            "file_uploads": 0,
            "ai_commands": 0,
            "manual_edits": 0,
            "exports": 0,
            "errors": 0
        }
        
        with open(log_file, "r", encoding="utf-8") as f:
            for line in f:
                entry = json.loads(line)
                event_type = entry.get("event_type")
                
                if event_type == "session_start":
                    stats["total_sessions"] += 1
                elif event_type == "file_upload":
                    stats["file_uploads"] += 1
                elif event_type == "ai_command":
                    stats["ai_commands"] += 1
                elif event_type == "manual_edit":
                    stats["manual_edits"] += 1
                elif event_type == "export":
                    stats["exports"] += 1
                
                if not entry.get("success", True):
                    stats["errors"] += 1
        
        return stats

# Global logger instance
interaction_logger = InteractionLogger()
