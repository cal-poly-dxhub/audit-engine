#!/usr/bin/env python3
"""
Script to run the Agent Logs Streamlit UI

Usage:
    python run_logs_ui.py

This will start the Streamlit server and open the agent logs dashboard.
"""

import subprocess
import sys
import os
from pathlib import Path

def main():
    """Run the Streamlit logs UI"""

    # Get the directory of this script
    script_dir = Path(__file__).parent

    # Path to the Streamlit app
    streamlit_app = script_dir / "agent_logs_ui.py"

    if not streamlit_app.exists():
        print("Error: agent_logs_ui.py not found!")
        sys.exit(1)

    print("🚀 Starting Agent Logs UI...")
    print(f"📂 Working directory: {script_dir}")
    print("📊 Dashboard will open in your browser")
    print("🔄 Press Ctrl+C to stop the server")
    print()

    # Run Streamlit
    try:
        subprocess.run([
            sys.executable, "-m", "streamlit", "run",
            str(streamlit_app),
            "--server.port", "8502",  # Use different port than main app
            "--server.headless", "false",
            "--server.runOnSave", "true",
            "--theme.base", "light"
        ], cwd=script_dir)
    except KeyboardInterrupt:
        print("\n🛑 Agent Logs UI stopped")
    except Exception as e:
        print(f"❌ Error running Streamlit: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()