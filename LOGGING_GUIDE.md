# Agentic Evidence Analysis - Logging Guide

## Overview

The agentic evidence analysis system includes comprehensive logging to provide full visibility into the agent's decision-making process and performance metrics.

## Log Files

### 1. Detailed Agent Logs
**File:** `logs/evidence_agent_detailed.log`
- **Size Limit:** 10MB (rotates, keeps 5 files)
- **Content:** Complete agent activity with debug information
- **Format:** `YYYY-MM-DD HH:MM:SS - logger_name - LEVEL - [function:line] - message`

**Example entries:**
```
2024-01-15 14:30:15 - evidence_agent - INFO - [analyze_evidence:271] - [ANALYZE] Starting analysis of 'security_report.pdf' for task: Implement new security protocols...
2024-01-15 14:30:15 - evidence_agent - DEBUG - [analyze_evidence:272] - [CONTEXT] Task context: {'department': 'IT Security', 'implementation_type': 'Security Enhancement'}
2024-01-15 14:30:16 - evidence_agent - INFO - [_determine_document_type:279] - [DOC_TYPE] Document type detected: pdf
```

### 2. Analysis Summary Logs
**File:** `logs/evidence_analysis.log`
- **Size Limit:** 5MB (rotates, keeps 3 files)
- **Content:** High-level analysis progress and results
- **Format:** `HH:MM:SS - LEVEL - message`

**Example entries:**
```
14:30:15 - INFO - [START] Starting analysis session: analysis_20240115_143015_a1b2c3d4
14:30:16 - INFO - [BEGIN] Starting: Determine document type
14:30:16 - INFO - [DONE] Completed: Determine document type (0.12s)
14:30:17 - INFO - [COMPLETE] Section analysis complete: Executive Summary
```

## Progress Tracking

### Real-time Progress Monitoring

The agent provides detailed progress tracking through:

1. **Console Output** - Real-time updates with text indicators and status
2. **Progress API** - `/agent_progress` endpoint for web monitoring
3. **Log Files** - Persistent record of all activities

### Progress Steps

Each analysis follows these tracked steps:
1. **Initialize** - Setup analysis session
2. **Document Type** - Detect file format (PDF, DOCX, image, etc.)
3. **Extract** - Extract content from document
4. **Segment** - Break into logical sections
5. **Analyze** - AI analysis of each section
6. **Cross-reference** - Validate consistency (multi-section docs)
7. **Synthesize** - Combine results
8. **Finalize** - Generate final report

## Log Viewer Tool

### Installation
```bash
python log_viewer.py --help
```

### Commands

#### 1. Show Log Summary
```bash
python log_viewer.py summary
```
Shows all available log files with sizes and modification dates.

#### 2. View Recent Entries
```bash
python log_viewer.py tail --lines 100
```
Shows the last 100 lines from the detailed log.

#### 3. Follow Logs in Real-time
```bash
python log_viewer.py follow --time 60
```
Monitors the log file for 60 seconds, showing new entries as they appear.

#### 4. Performance Analysis
```bash
python log_viewer.py performance
```
Analyzes completed analysis sessions and shows performance metrics.

### Options
- `--file` - Specify which log file to analyze (default: evidence_agent_detailed.log)
- `--lines` - Number of lines for tail command (default: 50)
- `--time` - Monitoring duration for follow command (default: 30 seconds)

## What Gets Logged

### Section Analysis
- Section identification and parsing
- Content length and type
- AI prompt creation and execution
- Response parsing and validation
- Confidence scores and findings
- Processing times for each step

### Document Processing
- File type detection
- Content extraction methods
- Section segmentation logic
- Cross-section validation
- Error handling and recovery

### Performance Metrics
- Step-by-step timing
- Overall processing duration
- Success/failure rates
- Resource utilization
- Analysis quality scores

### Error Handling
- Detailed exception information
- Recovery attempts
- Fallback strategies
- User-facing error messages

## Monitoring During Analysis

### Real-time Monitoring Setup

1. **Start the Evidence App:**
   ```bash
   python run_evidence.py
   ```

2. **In a second terminal, monitor logs:**
   ```bash
   python log_viewer.py follow
   ```

3. **In a third terminal, test the system:**
   ```bash
   python test_agentic_evidence.py
   ```

### Progress API Monitoring

Check analysis progress programmatically:
```bash
curl http://localhost:5001/agent_progress
```

Response format:
```json
{
  "analysis_id": "analysis_20240115_143015_a1b2c3d4",
  "progress_percentage": 62.5,
  "completed_steps": 5,
  "total_steps": 8,
  "current_step": "Perform section analysis",
  "elapsed_time": 45.7,
  "steps": [...]
}
```

## Log Analysis Examples

### Finding Performance Bottlenecks
```bash
# Show detailed timing for each step
python log_viewer.py performance

# Look for slow sections
grep "Section analysis complete" logs/evidence_agent_detailed.log | tail -10
```

### Debugging Failed Analyses
```bash
# Show recent errors
grep "\[FAIL\]\|\[ERROR\]" logs/evidence_agent_detailed.log | tail -20

# Follow logs during a problematic analysis
python log_viewer.py follow --time 120
```

### Monitoring System Health
```bash
# Check analysis success rate
grep "\[SUMMARY\] Analysis Summary" logs/evidence_agent_detailed.log | tail -10

# Monitor memory and performance
grep "Analysis completed successfully" logs/evidence_analysis.log | wc -l
```

## Integration with Web Interface

The web interface can display real-time progress by polling the `/agent_progress` endpoint:

```javascript
// Example JavaScript for progress monitoring
function checkAnalysisProgress() {
    fetch('/agent_progress')
        .then(response => response.json())
        .then(data => {
            if (data.progress_percentage !== undefined) {
                updateProgressBar(data.progress_percentage);
                updateCurrentStep(data.current_step);
            }
        });
}

// Poll every 2 seconds during analysis
setInterval(checkAnalysisProgress, 2000);
```

## Troubleshooting

### Common Issues

1. **Log directory not created**
   - Solution: Run the agent once to auto-create logs/ directory

2. **Permission errors**
   - Solution: Ensure write permissions for logs/ directory

3. **Large log files**
   - Logs automatically rotate when they reach size limits
   - Old log files are kept with numbered extensions (.1, .2, etc.)

4. **Missing log entries**
   - Check if multiple instances are running
   - Verify logging level is set correctly

### Log Level Configuration

The system uses different log levels:
- **DEBUG**: Detailed internal operations
- **INFO**: Important steps and results
- **WARNING**: Non-critical issues
- **ERROR**: Failures and exceptions

## Best Practices

1. **Monitor during development** - Use `python log_viewer.py follow` during testing
2. **Regular log rotation** - Logs auto-rotate, but monitor disk space
3. **Performance baseline** - Use performance analysis to establish baselines
4. **Error trending** - Monitor error patterns over time
5. **User feedback correlation** - Cross-reference logs with user reports

## Log Retention

- **Detailed logs**: 5 files × 10MB = ~50MB maximum
- **Analysis logs**: 3 files × 5MB = ~15MB maximum
- **Total storage**: ~65MB maximum for all log files
- **Automatic cleanup**: Oldest files are automatically removed when limits are reached