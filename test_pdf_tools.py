#!/usr/bin/env python3
"""
Test script for PDF tools integration
"""

import asyncio
import tempfile
from pathlib import Path
from claude_code_evidence_agent import ClaudeCodeEvidenceAgent

async def test_pdf_agent():
    """Test the agent with a sample PDF-like scenario."""

    print("[TEST] Testing Claude Code Evidence Agent with PDF tools")

    # Create a test PDF content (simulate)
    test_content = b"""This is sample PDF content that would be extracted.

    SECURITY IMPLEMENTATION REPORT
    ==============================

    This report outlines the implementation of new security protocols
    for data access controls and user authentication systems.

    IMPLEMENTED MEASURES:
    - Multi-factor authentication deployed
    - Role-based access control implemented
    - Security audit completed with 98% compliance
    """

    # Test data
    task_description = "Implement new security protocols for data access controls"
    task_context = {
        "department": "IT Security",
        "implementation_type": "Security Enhancement",
        "division": "Information Technology",
        "requires_collaboration": True
    }
    user_description = "This document shows our security implementation results"

    # Create agent
    agent = ClaudeCodeEvidenceAgent()

    # Test with a fake PDF file name (the agent will try to use PDF tools)
    result = await agent.analyze_evidence(
        test_content,
        "security_implementation_report.pdf",  # PDF extension
        task_description,
        task_context,
        user_description
    )

    print(f"[TEST] Analysis completed:")
    print(f"  Valid: {result.get('is_valid', 'unknown')}")
    print(f"  Confidence: {result.get('confidence', 0):.2f}")
    print(f"  Quality: {result.get('evidence_quality', 'unknown')}")
    print(f"  Processing time: {result.get('processing_time', 0):.2f}s")
    print(f"  Agent type: {result.get('agent_type', 'unknown')}")

    if result.get('error'):
        print(f"  Error: {result['error']}")

    return result

if __name__ == "__main__":
    asyncio.run(test_pdf_agent())