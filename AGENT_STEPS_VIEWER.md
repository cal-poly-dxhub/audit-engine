# Agent Steps Viewer 🔍

A user-friendly interface to view evidence analysis agent steps in real-time.

## What This Does

When you upload documents for evidence analysis, the AI agent performs many steps behind the scenes:
- Extracting text from PDFs
- Searching for specific content
- Running analysis tools
- Making decisions about evidence validity

This viewer shows all these steps in a simple, non-technical format that stakeholders can understand.

## Quick Start

### 1. Start the Evidence Analysis Server
```bash
python3 run_evidence.py
```
This runs on http://localhost:5001

### 2. Start the Agent Steps Viewer
```bash
python3 run_agent_viewer.py
```
This runs on http://localhost:8501

### 3. Upload Evidence
- Go to http://localhost:5001
- Upload an audit document
- Upload evidence for any task
- Watch the steps appear in real-time at http://localhost:8501

## What You'll See

### Task Information
- Task description and context
- Document being analyzed
- User's explanation of the evidence

### Real-Time Progress
- Current step the agent is working on
- Progress bar showing completion percentage
- Time elapsed and estimated completion

### Detailed Steps
- **Tool Usage**: See what tools the agent uses (PDF extraction, text search, etc.)
- **AI Responses**: Read the agent's analysis and reasoning
- **Analysis Milestones**: Major decision points in the process

### Final Results
- ✅/❌ Accept/Reject decision
- Confidence percentage
- Evidence quality rating
- Detailed reasoning
- Number of citations found

## Features

- **Auto-refresh**: Updates automatically when analysis is running
- **User-friendly**: No technical jargon, clear explanations
- **Real-time**: See steps as they happen
- **Detailed**: Drill down into any step for full information
- **Organized**: Separate tabs for different types of information

## Files Created

- `latest_agent_steps.json` - Simple log file (overwrites each analysis)
- `logs/` - Detailed technical logs (preserved)
- `agent_steps_viewer.py` - Streamlit app
- `run_agent_viewer.py` - Easy startup script

## For Developers

The system uses two logging approaches:
1. **Technical logs** (`agent_logger.py`) - Full database + file logging for debugging
2. **Simple logs** (`simple_agent_logger.py`) - User-friendly JSON for the viewer

Both run simultaneously, so you have both detailed technical logs and user-friendly summaries.

## Troubleshooting

### Viewer shows "No analysis data found"
- Make sure you've uploaded a document in the evidence app
- Check that both servers are running
- The log file `latest_agent_steps.json` should exist

### Steps not updating
- Check that auto-refresh is enabled
- Try clicking "Refresh Now"
- Make sure an analysis is actually running

### Installation issues
```bash
pip install streamlit pandas
```

## Benefits for Non-Technical Users

- **Transparency**: See exactly what the AI is doing
- **Trust**: Understand the analysis process
- **Verification**: Check that the AI found the right information
- **Learning**: Understand how evidence validation works
- **Debugging**: If results seem wrong, see where the process went off track