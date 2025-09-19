# Agent Activity Logging System

This system provides comprehensive logging and monitoring of Claude Code agent activities, including tool usage, performance metrics, and analysis workflows.

## Components

### 1. Agent Logger (`agent_logger.py`)
- **Comprehensive logging**: Tracks every tool call, agent response, and performance metric
- **SQLite database**: Structured storage for easy querying and analysis
- **File logging**: Human-readable logs with detailed activity traces
- **Session tracking**: Complete analysis sessions from start to finish
- **Performance metrics**: Duration tracking, success/failure rates, error analysis

### 2. Streamlit UI (`agent_logs_ui.py`)
- **Dashboard view**: Overview of agent activity and performance
- **Session list**: Browse all analysis sessions with filtering
- **Session details**: Deep dive into individual sessions with tool timelines
- **Tool analysis**: Usage statistics and performance by tool type
- **Performance metrics**: Trends, success rates, and comparative analysis

### 3. Integration (`claude_code_evidence_agent.py`)
- **Automatic logging**: All agent activities are logged transparently
- **Tool tracking**: Every tool call is tracked from start to completion
- **Error capture**: Failed operations and error messages are recorded
- **Response logging**: Agent responses and reasoning are captured

## Usage

### Running the Logs UI

```bash
# Start the Streamlit dashboard
python run_logs_ui.py
```

The dashboard will open at `http://localhost:8502` and provides:

- **Real-time monitoring** of agent activities
- **Historical analysis** of performance trends
- **Tool usage statistics** and success rates
- **Session filtering** by time, agent type, and status
- **Detailed session inspection** with tool timelines

### Features

#### Dashboard View
- Total sessions, completion rates, average duration
- Sessions over time with status breakdown
- Tool usage statistics and success rates
- Recent session overview with quick details

#### Session List
- Filterable table of all analysis sessions
- Status indicators (completed, failed, running)
- Quick session details and selection for deep dive

#### Session Details
- Complete session timeline with tool calls
- Input parameters and output results for each tool
- Agent responses and reasoning capture
- Error messages and debugging information

#### Tool Analysis
- Usage statistics by tool type
- Success rates and failure analysis
- Performance distribution and duration analysis
- Tool-specific metrics and trends

#### Performance Metrics
- Session duration trends over time
- Success rate tracking and alerts
- Agent type performance comparison
- Historical performance analysis

## Log Storage

### Database Schema
- **sessions**: Complete analysis sessions
- **tool_calls**: Individual tool executions
- **agent_responses**: Agent text responses

### File Logs
- **Daily log files**: `logs/agent_activity_YYYYMMDD.log`
- **Session backups**: `logs/session_SESSION_ID.json`
- **SQLite database**: `logs/agent_logs.db`

## Automatic Integration

The logging system is automatically integrated into the Claude Code evidence agent. Every analysis session will:

1. **Start session tracking** when analysis begins
2. **Log all tool calls** with inputs, outputs, and timing
3. **Capture agent responses** and reasoning
4. **Record final results** including confidence scores and annotations
5. **Track errors** and debugging information
6. **End session** with complete performance metrics

No additional setup is required - simply run evidence analyses and view the comprehensive logs in the Streamlit dashboard.

## Benefits

- **Debugging**: Detailed logs help identify issues and optimize performance
- **Monitoring**: Real-time visibility into agent activities and health
- **Analytics**: Historical trends and performance analysis
- **Compliance**: Complete audit trail of all agent activities
- **Optimization**: Identify bottlenecks and improvement opportunities