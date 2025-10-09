#!/usr/bin/env python3
"""
Agent Steps Viewer Runner

Simple script to start the Streamlit app for viewing agent analysis steps.
"""

import subprocess
import sys
import os
from pathlib import Path

def main():
    """Run the Streamlit agent steps viewer"""

    print("🔍 Evidence Analysis Agent Steps Viewer")
    print("=" * 50)
    print("Starting Streamlit app to view agent analysis steps...")
    print("This will show real-time progress of evidence analysis.")
    print()

    # Check if streamlit is installed
    try:
        import streamlit
        print("✅ Streamlit found")
    except ImportError:
        print("❌ Streamlit not found. Installing...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "streamlit", "pandas"])
            print("✅ Streamlit installed successfully")
        except subprocess.CalledProcessError as e:
            print(f"❌ Failed to install Streamlit: {e}")
            return

    # Set working directory
    script_dir = Path(__file__).parent
    os.chdir(script_dir)

    # Run streamlit app
    app_path = script_dir / "agent_steps_viewer.py"

    print(f"🚀 Starting Streamlit app...")
    print(f"📁 Working directory: {script_dir}")
    print(f"📊 App will be available at: http://localhost:8501")
    print()
    print("💡 Tip: Keep this running in a separate terminal while you use the evidence validation app")
    print("💡 The viewer will automatically update when new analysis starts")
    print()
    print("Press Ctrl+C to stop the viewer")
    print("-" * 50)

    try:
        # Run streamlit with optimized settings for local development
        subprocess.run([
            sys.executable, "-m", "streamlit", "run", str(app_path),
            "--server.port", "8501",
            "--server.headless", "false",
            "--browser.gatherUsageStats", "false",
            "--server.fileWatcherType", "none"  # Disable file watcher to avoid conflicts
        ])
    except KeyboardInterrupt:
        print("\n👋 Agent Steps Viewer stopped")
    except Exception as e:
        print(f"❌ Error running Streamlit app: {e}")

if __name__ == "__main__":
    main()