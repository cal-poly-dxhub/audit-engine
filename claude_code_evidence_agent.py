#!/usr/bin/env python3
"""
Claude Code SDK Evidence Analysis Agent

This module implements a proper evidence analysis agent using the Claude Code Python SDK.
The agent can analyze documents, understand context, and provide comprehensive evidence validation.
"""

import asyncio
import json
import time
import logging
from typing import Dict, List, Any, Optional, Union
from pathlib import Path
import tempfile
import os
from datetime import datetime

# Claude Code SDK imports
from claude_code_sdk import (
    ClaudeSDKClient,
    ClaudeCodeOptions,
    AssistantMessage,
    TextBlock,
    ToolUseBlock,
    ToolResultBlock,
    ResultMessage
)

# Import PDF tools
from pdf_tools import create_pdf_tools_server

# Import citation system
from citation_system import (
    Citation, Annotation, AnnotationSet, AnnotationType, AnnotationSeverity,
    CitationMatcher, create_support_annotation, create_concern_annotation, create_correction_annotation
)

# Import comprehensive logging
from agent_logger import (
    start_agent_session, log_tool_start, log_tool_complete, log_tool_error,
    log_agent_response, end_agent_session
)

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ClaudeCodeEvidenceAgent:
    """
    Evidence analysis agent using the Claude Code Python SDK.

    This agent can analyze various types of evidence documents and provide
    comprehensive validation against audit task requirements.
    """

    def __init__(self, options: Optional[ClaudeCodeOptions] = None):
        """Initialize the Claude Code evidence agent."""

        # Configure default options if none provided
        if options is None:
            # Create PDF tools server
            pdf_server = create_pdf_tools_server()

            options = ClaudeCodeOptions(
                allowed_tools=[
                    "Read",           # Read files
                    "Write",          # Write analysis results
                    "Bash",           # Execute commands and install libraries
                    "Glob",           # Find files
                    "Grep",           # Search content
                    "WebFetch",       # Web research if needed
                    "mcp__pdf-tools__extract_pdf_text"  # PDF text extraction
                ],
                mcp_servers={"pdf-tools": pdf_server},  # Add PDF tools server
                permission_mode="acceptEdits",  # Auto-accept file operations
                system_prompt="""You are an expert evidence analysis agent specializing in audit compliance validation.

Your role is to:
1. Analyze evidence documents thoroughly and systematically
2. Evaluate how well evidence supports specific audit task requirements
3. Identify strengths, weaknesses, and missing elements
4. Provide detailed confidence assessments and recommendations
5. Generate comprehensive reports with actionable insights

For each analysis:
- Break down complex documents into logical sections
- Cross-reference requirements against evidence
- Provide specific examples and citations
- Assess completeness and quality
- Generate clear recommendations (accept/reject/request_additional)

Be thorough, objective, and provide detailed reasoning for all assessments."""
            )

        self.options = options
        self.client = None
        self.current_analysis_id = None

        logger.info("[INIT] Claude Code Evidence Agent initialized")

    async def analyze_evidence(self,
                             file_content: Union[bytes, str],
                             filename: str,
                             task_description: str,
                             task_context: Dict[str, Any],
                             user_description: str = "") -> Dict[str, Any]:
        """
        Analyze evidence using Claude Code SDK agent capabilities.

        Args:
            file_content: Raw file content
            filename: Name of the evidence file
            task_description: Description of the audit task
            task_context: Context about the task (department, type, etc.)
            user_description: User's explanation of the evidence

        Returns:
            Comprehensive analysis result
        """
        analysis_start_time = time.time()
        self.current_analysis_id = f"analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        logger.info(f"[START] Starting Claude Code agent analysis: {self.current_analysis_id}")
        logger.info(f"[DOCUMENT] Analyzing '{filename}' for task: {task_description[:50]}...")

        # Start comprehensive logging session
        session_id = start_agent_session(
            analysis_id=self.current_analysis_id,
            agent_type="claude_code_sdk",
            task_description=task_description,
            task_context=task_context,
            user_description=user_description,
            filename=filename
        )

        try:
            # Create temporary file for the evidence
            temp_file_path = await self._create_temp_evidence_file(file_content, filename)

            # Initialize Claude Code client
            async with ClaudeSDKClient(options=self.options) as client:
                self.client = client

                # Create comprehensive analysis prompt
                analysis_prompt = self._create_analysis_prompt(
                    temp_file_path, task_description, task_context, user_description
                )

                logger.info("[AGENT] Sending analysis request to Claude Code agent...")
                logger.info(f"[AGENT_PROMPT] Task: {task_description}")
                logger.info(f"[AGENT_PROMPT] Context: Department={task_context.get('department')}, Type={task_context.get('implementation_type')}")
                logger.info(f"[AGENT_PROMPT] User Description: {user_description}")
                logger.info(f"[AGENT_PROMPT] Evidence File: {temp_file_path}")

                # Send analysis request to the agent
                await client.query(analysis_prompt)

                # Collect agent response
                full_response = ""
                tool_results = []

                async for message in client.receive_response():
                    if isinstance(message, AssistantMessage):
                        for block in message.content:
                            if isinstance(block, TextBlock):
                                # Log agent's thinking and responses
                                if block.text.strip():
                                    logger.info(f"[AGENT_RESPONSE] {block.text[:200]}{'...' if len(block.text) > 200 else ''}")
                                    log_agent_response(block.text)  # Comprehensive logging
                                full_response += block.text
                            elif isinstance(block, ToolUseBlock):
                                # Start comprehensive tool logging
                                tool_id = log_tool_start(block.name, block.input)

                                # Log detailed tool usage
                                logger.info(f"[TOOL_USE] Agent using tool: {block.name}")

                                # Log specific tool inputs based on tool type
                                if block.name == "Bash":
                                    command = block.input.get("command", "")
                                    logger.info(f"[BASH_COMMAND] Executing: {command}")
                                elif block.name == "Write":
                                    file_path = block.input.get("file_path", "")
                                    content_preview = block.input.get("content", "")[:100]
                                    logger.info(f"[WRITE_FILE] Writing to: {file_path}")
                                    logger.info(f"[WRITE_CONTENT] Content preview: {content_preview}...")
                                elif block.name == "Read":
                                    file_path = block.input.get("file_path", "")
                                    logger.info(f"[READ_FILE] Reading: {file_path}")
                                elif block.name == "Grep":
                                    pattern = block.input.get("pattern", "")
                                    path = block.input.get("path", "")
                                    logger.info(f"[GREP_SEARCH] Searching for '{pattern}' in {path}")
                                elif block.name == "Glob":
                                    pattern = block.input.get("pattern", "")
                                    logger.info(f"[GLOB_SEARCH] Finding files matching: {pattern}")
                                else:
                                    # Log full input for other tools
                                    logger.info(f"[TOOL_INPUT] {block.input}")

                                tool_results.append({
                                    "tool": block.name,
                                    "input": block.input,
                                    "tool_id": tool_id  # Track for completion logging
                                })
                            elif isinstance(block, ToolResultBlock):
                                # Find the corresponding tool result for logging
                                matching_tool = None
                                for tool_result in reversed(tool_results):
                                    if tool_result.get("tool_id"):
                                        matching_tool = tool_result
                                        break

                                # Log tool completion or error
                                if block.is_error:
                                    error_message = str(block.content)
                                    logger.error(f"[TOOL_ERROR] Tool execution failed: {error_message}")
                                    if matching_tool:
                                        log_tool_error(matching_tool["tool_id"], error_message)
                                else:
                                    result_preview = str(block.content)[:300] if block.content else "No content"
                                    logger.info(f"[TOOL_RESULT] Tool output: {result_preview}{'...' if len(str(block.content)) > 300 else ''}")
                                    if matching_tool:
                                        log_tool_complete(matching_tool["tool_id"], str(block.content))
                    elif isinstance(message, ResultMessage):
                        logger.info(f"[RESULT] Analysis completed - Duration: {message.duration_ms}ms")
                        if message.is_error:
                            logger.error(f"[ANALYSIS_ERROR] Analysis failed: {message.result}")
                        break

                # Parse and structure the results
                analysis_result = await self._parse_agent_response(
                    full_response, tool_results, analysis_start_time
                )

                # Clean up temporary file
                await self._cleanup_temp_file(temp_file_path)

                analysis_result['analysis_id'] = self.current_analysis_id
                analysis_result['agent_type'] = 'claude_code_sdk'
                analysis_result['processing_time'] = time.time() - analysis_start_time

                logger.info(f"[SUCCESS] Claude Code agent analysis completed in {analysis_result['processing_time']:.2f}s")

                # End logging session with success
                end_agent_session(final_result=analysis_result)

                return analysis_result

        except Exception as e:
            error_message = f"Agent analysis failed: {str(e)}"
            logger.error(f"[ERROR] Claude Code agent analysis failed: {str(e)}")

            # End logging session with error
            end_agent_session(error_message=error_message)

            return {
                "error": error_message,
                "analysis_id": self.current_analysis_id,
                "processing_time": time.time() - analysis_start_time
            }

    async def _create_temp_evidence_file(self, file_content: Union[bytes, str], filename: str) -> str:
        """Create a temporary file with the evidence content."""

        # Create temporary directory for analysis
        temp_dir = Path(tempfile.gettempdir()) / "claude_code_evidence"
        temp_dir.mkdir(exist_ok=True)

        # Create temp file with original filename
        temp_file_path = temp_dir / f"{self.current_analysis_id}_{filename}"

        # Write content to temporary file
        if isinstance(file_content, bytes):
            temp_file_path.write_bytes(file_content)
        else:
            temp_file_path.write_text(file_content, encoding='utf-8')

        logger.info(f"[TEMP_FILE] Created temporary evidence file: {temp_file_path}")
        return str(temp_file_path)

    def _create_analysis_prompt(self,
                               file_path: str,
                               task_description: str,
                               task_context: Dict[str, Any],
                               user_description: str) -> str:
        """Create a comprehensive analysis prompt for the Claude Code agent."""

        return f"""
I need you to perform a comprehensive evidence analysis using your available tools. Here's what I need:

EVIDENCE FILE: {file_path}
AUDIT TASK: {task_description}

TASK CONTEXT:
- Department: {task_context.get('department', 'Not specified')}
- Implementation Type: {task_context.get('implementation_type', 'Not specified')}
- Division: {task_context.get('division', 'Not specified')}
- Requires Collaboration: {task_context.get('requires_collaboration', False)}

USER EXPLANATION: {user_description if user_description else 'No explanation provided'}

ANALYSIS INSTRUCTIONS:

1. **EXTRACT PDF TEXT**: Use the mcp__pdf-tools__extract_pdf_text tool to extract text from the PDF
2. **DOCUMENT ANALYSIS**: Break down the document structure and key content areas
3. **REQUIREMENTS MAPPING**: Compare evidence against the specific audit task requirements
4. **QUALITY ASSESSMENT**: Evaluate completeness, relevance, and strength of evidence
5. **CITATION GENERATION**: Identify specific text passages to highlight with annotations
6. **DETAILED FINDINGS**: Identify specific supporting elements and gaps
7. **COMPREHENSIVE REPORT**: Generate final assessment with confidence scores and citations

EVALUATION APPROACH:
- Use COMMON SENSE and GOOD FAITH interpretation when evaluating evidence
- Consider the SPIRIT and INTENT of the task, not just literal word matching
- Give REASONABLE BENEFIT OF THE DOUBT when evidence substantially addresses the task
- Accept evidence that demonstrates MEANINGFUL PROGRESS or COMPLETION even if not perfectly comprehensive
- Consider the USER'S EXPLANATION as valuable context for how the document relates to the task
- Avoid being overly strict or pedantic - focus on whether the evidence reasonably demonstrates task fulfillment

IMPORTANT:
- DO NOT write or execute Python code - use the provided MCP PDF extraction tool instead
- DO NOT install libraries or create scripts
- Focus on analysis, not technical implementation
- Use the mcp__pdf-tools__extract_pdf_text tool for all PDF text extraction needs

CITATION REQUIREMENTS:
- For each key finding (positive or negative), identify the specific text passage that led to your conclusion
- Include exact quotes from the document as "text_snippet"
- Use appropriate annotation types:
  * "support" - text that supports compliance or positive findings
  * "concern" - text that raises concerns or shows potential issues
  * "correction" - text that contains errors or needs changes
  * "missing" - points where required information is absent
  * "clarification" - text that needs further explanation
  * "reference" - general citations for context
- Choose severity levels: info (general), low, medium, high, critical
- Provide helpful titles and detailed explanations for each annotation
- Include suggested actions for concerns/corrections when possible

Please provide your analysis in this JSON format at the end:

```json
{{
    "is_valid": true/false,
    "confidence": 0.0-1.0,
    "evidence_quality": "high/medium/low",
    "reasoning": "detailed explanation of your analysis and decision",
    "strengths": ["specific strengths found in the evidence"],
    "missing_elements": ["specific requirements not addressed"],
    "recommendations": ["actionable recommendations"],
    "recommendation": "accept/reject/request_additional",
    "annotations": [
        {{
            "text_snippet": "exact text from document to highlight",
            "annotation_type": "support|concern|correction|clarification|reference|missing",
            "severity": "info|low|medium|high|critical",
            "title": "brief title for annotation",
            "message": "detailed explanation or comment",
            "suggested_action": "what should be done (optional)",
            "suggested_replacement": "replacement text if correction needed (optional)"
        }}
    ],
    "detailed_findings": {{
        "document_structure": "description of document organization",
        "key_sections": ["list of important sections identified"],
        "compliance_indicators": ["specific elements showing compliance"],
        "concerns": ["areas of concern or potential issues"],
        "supporting_evidence": ["specific examples that support the task"]
    }},
    "analysis_metadata": {{
        "document_type": "detected document type",
        "content_length": "approximate content size",
        "sections_analyzed": "number of sections examined",
        "tools_used": ["list of tools you used in analysis"]
    }}
}}
```

Start by reading and analyzing the evidence document systematically.
"""

    def _process_annotations(self, annotations_data: List[Dict[str, Any]], document_text: str = "") -> List[Dict[str, Any]]:
        """Process annotation data from AI response into properly formatted annotations"""
        processed_annotations = []

        if not annotations_data:
            return processed_annotations

        for annotation_data in annotations_data:
            try:
                # Extract annotation information
                text_snippet = annotation_data.get('text_snippet', '')
                annotation_type_str = annotation_data.get('annotation_type', 'reference')
                severity_str = annotation_data.get('severity', 'info')
                title = annotation_data.get('title', 'Citation')
                message = annotation_data.get('message', '')
                suggested_action = annotation_data.get('suggested_action')
                suggested_replacement = annotation_data.get('suggested_replacement')

                # Validate annotation type and severity
                valid_types = ['support', 'concern', 'correction', 'clarification', 'reference', 'missing']
                valid_severities = ['info', 'low', 'medium', 'high', 'critical']

                if annotation_type_str not in valid_types:
                    annotation_type_str = 'reference'

                if severity_str not in valid_severities:
                    severity_str = 'info'

                # Create annotation object using the citation system
                citation = Citation(text_snippet=text_snippet, confidence_score=1.0)

                # If we have document text, try to find the position
                if document_text and text_snippet:
                    located_citation = CitationMatcher.find_text_position(document_text, text_snippet)
                    if located_citation:
                        citation = located_citation

                annotation = Annotation(
                    citation=citation,
                    annotation_type=AnnotationType(annotation_type_str),
                    severity=AnnotationSeverity(severity_str),
                    title=title,
                    message=message,
                    suggested_action=suggested_action,
                    suggested_replacement=suggested_replacement
                )

                processed_annotations.append(annotation.to_dict())
                logger.debug(f"[CITATION] Processed annotation: {annotation_type_str} - {title}")

            except Exception as e:
                logger.error(f"Error processing annotation: {str(e)}")
                continue

        return processed_annotations

    async def _parse_agent_response(self,
                                   response_text: str,
                                   tool_results: List[Dict],
                                   start_time: float) -> Dict[str, Any]:
        """Parse the agent's response and extract structured analysis results."""

        try:
            # Try to extract JSON from the response
            import re
            json_match = re.search(r'```json\s*(\{.*?\})\s*```', response_text, re.DOTALL)

            if json_match:
                json_str = json_match.group(1)
                parsed_result = json.loads(json_str)
                logger.info("[PARSE] Successfully extracted JSON analysis results")

                # Process annotations if they exist
                if 'annotations' in parsed_result and parsed_result['annotations']:
                    # Try to get document text from tool results for better citation matching
                    document_text = ""
                    for tool_result in tool_results:
                        if 'extracted_text' in str(tool_result):
                            # Try to extract document text from PDF extraction results
                            try:
                                tool_content = str(tool_result)
                                if 'text' in tool_content:
                                    document_text = tool_content
                                    break
                            except:
                                pass

                    processed_annotations = self._process_annotations(
                        parsed_result['annotations'],
                        document_text
                    )
                    parsed_result['annotations'] = processed_annotations
                    logger.info(f"[CITATIONS] Processed {len(processed_annotations)} annotations")

                # Add processing metadata
                parsed_result['full_response'] = response_text
                parsed_result['tool_operations'] = tool_results
                parsed_result['analysis_method'] = 'claude_code_sdk_agent'

                return parsed_result
            else:
                # Fallback: create structured result from text response
                logger.warning("[PARSE] No JSON found, creating structured result from text")

                return {
                    "is_valid": self._extract_validity_from_text(response_text),
                    "confidence": self._extract_confidence_from_text(response_text),
                    "evidence_quality": self._extract_quality_from_text(response_text),
                    "reasoning": response_text[:1000] + "..." if len(response_text) > 1000 else response_text,
                    "strengths": self._extract_strengths_from_text(response_text),
                    "missing_elements": self._extract_missing_from_text(response_text),
                    "recommendations": self._extract_recommendations_from_text(response_text),
                    "recommendation": self._extract_recommendation_from_text(response_text),
                    "annotations": [],  # No annotations in fallback case
                    "full_response": response_text,
                    "tool_operations": tool_results,
                    "analysis_method": "claude_code_sdk_agent_fallback"
                }

        except json.JSONDecodeError as e:
            logger.error(f"[PARSE_ERROR] Failed to parse JSON: {str(e)}")
            return {
                "error": f"Failed to parse agent response: {str(e)}",
                "full_response": response_text,
                "tool_operations": tool_results,
                "annotations": []  # No annotations in error case
            }

    def _extract_validity_from_text(self, text: str) -> bool:
        """Extract validity assessment from text response."""
        text_lower = text.lower()
        if "is_valid" in text_lower:
            return "true" in text_lower or "valid" in text_lower
        return "accept" in text_lower or "approve" in text_lower

    def _extract_confidence_from_text(self, text: str) -> float:
        """Extract confidence score from text response."""
        import re
        confidence_match = re.search(r'confidence[:\s]*([0-9.]+)', text.lower())
        if confidence_match:
            try:
                return float(confidence_match.group(1))
            except ValueError:
                pass
        return 0.7  # Default confidence

    def _extract_quality_from_text(self, text: str) -> str:
        """Extract evidence quality from text response."""
        text_lower = text.lower()
        if "high quality" in text_lower or "strong evidence" in text_lower:
            return "high"
        elif "low quality" in text_lower or "weak evidence" in text_lower:
            return "low"
        return "medium"

    def _extract_strengths_from_text(self, text: str) -> List[str]:
        """Extract strengths from text response."""
        # Simple extraction - look for bullet points or numbered lists with positive indicators
        strengths = []
        lines = text.split('\n')
        for line in lines:
            if any(word in line.lower() for word in ['strength', 'good', 'strong', 'demonstrates', 'shows']):
                if any(marker in line for marker in ['•', '-', '*']) or line.strip().startswith(tuple('123456789')):
                    strengths.append(line.strip())
        return strengths[:5]  # Limit to 5 items

    def _extract_missing_from_text(self, text: str) -> List[str]:
        """Extract missing elements from text response."""
        missing = []
        lines = text.split('\n')
        for line in lines:
            if any(word in line.lower() for word in ['missing', 'lack', 'absent', 'not found', 'incomplete']):
                if any(marker in line for marker in ['•', '-', '*']) or line.strip().startswith(tuple('123456789')):
                    missing.append(line.strip())
        return missing[:5]  # Limit to 5 items

    def _extract_recommendations_from_text(self, text: str) -> List[str]:
        """Extract recommendations from text response."""
        recommendations = []
        lines = text.split('\n')
        for line in lines:
            if any(word in line.lower() for word in ['recommend', 'suggest', 'should', 'need to', 'consider']):
                if any(marker in line for marker in ['•', '-', '*']) or line.strip().startswith(tuple('123456789')):
                    recommendations.append(line.strip())
        return recommendations[:5]  # Limit to 5 items

    def _extract_recommendation_from_text(self, text: str) -> str:
        """Extract final recommendation from text response."""
        text_lower = text.lower()
        if "reject" in text_lower or "not acceptable" in text_lower:
            return "reject"
        elif "accept" in text_lower or "approve" in text_lower:
            return "accept"
        return "request_additional"

    async def _cleanup_temp_file(self, file_path: str):
        """Clean up temporary files."""
        try:
            Path(file_path).unlink(missing_ok=True)
            logger.info(f"[CLEANUP] Removed temporary file: {file_path}")
        except Exception as e:
            logger.warning(f"[CLEANUP] Failed to remove temp file: {str(e)}")

    async def analyze_multiple_evidence(self,
                                      documents_content: List[Dict[str, Any]],
                                      task_description: str,
                                      task_context: Dict[str, Any],
                                      user_description: str = "") -> Dict[str, Any]:
        """
        Analyze multiple evidence documents collectively using Claude Code SDK agent.

        Args:
            documents_content: List of document info with filename and content
            task_description: Description of the audit task
            task_context: Context about the task
            user_description: User's explanation of the evidence

        Returns:
            Collective analysis result
        """
        analysis_start_time = time.time()
        self.current_analysis_id = f"multi_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        logger.info(f"[START] Starting Claude Code multi-document analysis: {self.current_analysis_id}")

        # Start comprehensive logging session
        session_id = start_agent_session(
            analysis_id=self.current_analysis_id,
            agent_type="claude_code_sdk_multi",
            task_description=task_description,
            task_context=task_context,
            user_description=user_description,
            filename=f"multi_doc_{len(documents_content)}_files"
        )

        try:
            # Create temporary files for all evidence documents
            temp_file_paths = []

            for i, doc in enumerate(documents_content):
                temp_file_path = await self._create_temp_evidence_file(
                    doc['content'], f"{i+1}_{doc['filename']}"
                )
                temp_file_paths.append(temp_file_path)

            # Initialize Claude Code client
            async with ClaudeSDKClient(options=self.options) as client:
                self.client = client

                # Create multi-document analysis prompt
                analysis_prompt = self._create_multi_document_analysis_prompt(
                    temp_file_paths, documents_content, task_description, task_context, user_description
                )

                logger.info("[AGENT] Sending multi-document analysis request to Claude Code agent...")

                # Send analysis request to the agent
                await client.query(analysis_prompt)

                # Collect agent response
                full_response = ""
                tool_results = []

                async for message in client.receive_response():
                    if isinstance(message, AssistantMessage):
                        for block in message.content:
                            if isinstance(block, TextBlock):
                                if block.text.strip():
                                    logger.info(f"[AGENT_RESPONSE] {block.text[:200]}{'...' if len(block.text) > 200 else ''}")
                                    log_agent_response(block.text)
                                full_response += block.text
                            elif isinstance(block, ToolUseBlock):
                                tool_id = log_tool_start(block.name, block.input)
                                logger.info(f"[TOOL_USE] Agent using tool: {block.name}")
                                tool_results.append({
                                    "tool": block.name,
                                    "input": block.input,
                                    "tool_id": tool_id
                                })
                            elif isinstance(block, ToolResultBlock):
                                matching_tool = None
                                for tool_result in reversed(tool_results):
                                    if tool_result.get("tool_id"):
                                        matching_tool = tool_result
                                        break

                                if block.is_error:
                                    error_message = str(block.content)
                                    logger.error(f"[TOOL_ERROR] Tool execution failed: {error_message}")
                                    if matching_tool:
                                        log_tool_error(matching_tool["tool_id"], error_message)
                                else:
                                    result_preview = str(block.content)[:300] if block.content else "No content"
                                    logger.info(f"[TOOL_RESULT] Tool output: {result_preview}{'...' if len(str(block.content)) > 300 else ''}")
                                    if matching_tool:
                                        log_tool_complete(matching_tool["tool_id"], str(block.content))
                    elif isinstance(message, ResultMessage):
                        logger.info(f"[RESULT] Multi-document analysis completed - Duration: {message.duration_ms}ms")
                        break

                # Parse and structure the results
                analysis_result = await self._parse_agent_response(
                    full_response, tool_results, analysis_start_time
                )

                # Clean up temporary files
                for temp_file_path in temp_file_paths:
                    await self._cleanup_temp_file(temp_file_path)

                analysis_result['analysis_id'] = self.current_analysis_id
                analysis_result['agent_type'] = 'claude_code_sdk_multi'
                analysis_result['processing_time'] = time.time() - analysis_start_time
                analysis_result['document_count'] = len(documents_content)

                logger.info(f"[SUCCESS] Claude Code multi-document analysis completed in {analysis_result['processing_time']:.2f}s")

                # End logging session with success
                end_agent_session(final_result=analysis_result)

                return analysis_result

        except Exception as e:
            error_message = f"Multi-document agent analysis failed: {str(e)}"
            logger.error(f"[ERROR] Claude Code multi-document analysis failed: {str(e)}")

            # Clean up temp files on error
            for temp_file_path in temp_file_paths:
                await self._cleanup_temp_file(temp_file_path)

            # End logging session with error
            end_agent_session(error_message=error_message)

            return {
                "error": error_message,
                "analysis_id": self.current_analysis_id,
                "processing_time": time.time() - analysis_start_time
            }

    def _create_multi_document_analysis_prompt(self,
                                             file_paths: List[str],
                                             documents_content: List[Dict[str, Any]],
                                             task_description: str,
                                             task_context: Dict[str, Any],
                                             user_description: str) -> str:
        """Create a comprehensive multi-document analysis prompt for the Claude Code agent."""

        files_list = "\n".join([f"- {path}" for path in file_paths])

        return f"""
I need you to perform a COLLECTIVE ANALYSIS of multiple evidence documents for a single audit task using your available tools.

EVIDENCE FILES:
{files_list}

AUDIT TASK: {task_description}

TASK CONTEXT:
- Department: {task_context.get('department', 'Not specified')}
- Implementation Type: {task_context.get('implementation_type', 'Not specified')}
- Division: {task_context.get('division', 'Not specified')}
- Requires Collaboration: {task_context.get('requires_collaboration', False)}

USER EXPLANATION: {user_description if user_description else 'No explanation provided'}

MULTI-DOCUMENT ANALYSIS INSTRUCTIONS:

1. **EXTRACT AND READ ALL DOCUMENTS**: Use the PDF extraction tools to read all documents
2. **INDIVIDUAL ANALYSIS**: Analyze each document separately against the task requirements
3. **CROSS-DOCUMENT COMPARISON**: Compare and contrast findings across documents
4. **COMPLEMENTARY EVIDENCE**: Identify how documents complement each other
5. **CONSISTENCY ASSESSMENT**: Check for consistency or conflicts between documents
6. **COMPREHENSIVE COVERAGE**: Evaluate if all task requirements are covered collectively
7. **COLLECTIVE VALIDATION**: Make a final determination based on all documents together

EVALUATION APPROACH:
- Use COMMON SENSE and GOOD FAITH interpretation when evaluating evidence
- Consider the SPIRIT and INTENT of the task, not just literal word matching
- Give REASONABLE BENEFIT OF THE DOUBT when evidence substantially addresses the task
- Accept evidence that demonstrates MEANINGFUL PROGRESS or COMPLETION even if not perfectly comprehensive
- Consider the USER'S EXPLANATION as valuable context for how the documents relate to the task
- Avoid being overly strict or pedantic - focus on whether the evidence reasonably demonstrates task fulfillment

IMPORTANT:
- Analyze ALL documents provided - don't skip any
- Look for evidence that spans multiple documents
- Identify gaps that might be filled by combining document insights
- Consider document quality and relevance collectively
- Provide specific cross-references between documents

Please provide your analysis in this JSON format at the end:

```json
{{
    "is_valid": true/false,
    "confidence": 0.0-1.0,
    "evidence_quality": "high/medium/low",
    "reasoning": "detailed explanation of collective analysis and decision",
    "strengths": ["collective strengths across all documents"],
    "missing_elements": ["requirements not addressed by any document"],
    "recommendations": ["actionable recommendations for the evidence package"],
    "recommendation": "accept/reject/request_additional",
    "document_synergy": "explanation of how documents work together",
    "individual_document_summaries": [
        {{
            "filename": "document1.pdf",
            "key_findings": ["main findings from this document"],
            "contribution": "how this document contributes to task evidence",
            "quality": "high/medium/low"
        }}
    ],
    "cross_document_findings": [
        {{
            "finding": "description of finding that spans multiple documents",
            "documents_involved": ["doc1.pdf", "doc2.pdf"],
            "significance": "high/medium/low",
            "explanation": "detailed explanation of the cross-document finding"
        }}
    ],
    "collective_coverage": {{
        "requirements_covered": ["list of requirements covered by the document set"],
        "coverage_percentage": 0.0-1.0,
        "coverage_gaps": ["requirements not covered by any document"],
        "redundant_coverage": ["requirements covered by multiple documents"]
    }},
    "annotations": [
        {{
            "document": "filename",
            "text_snippet": "exact text from document to highlight",
            "annotation_type": "support|concern|correction|clarification|reference|missing",
            "severity": "info|low|medium|high|critical",
            "title": "brief title for annotation",
            "message": "detailed explanation or comment",
            "cross_document_reference": "reference to related content in other documents (optional)"
        }}
    ]
}}
```

Start by reading and analyzing all evidence documents systematically, then provide the collective assessment.
"""

    def get_analysis_status(self) -> Dict[str, Any]:
        """Get current analysis status."""
        return {
            "analysis_id": self.current_analysis_id,
            "agent_type": "claude_code_sdk",
            "status": "active" if self.client else "idle"
        }


# Async wrapper for Flask integration
class AsyncEvidenceAgent:
    """Wrapper to make the async agent work with Flask."""

    def __init__(self):
        self.agent = ClaudeCodeEvidenceAgent()

    def analyze_evidence_sync(self,
                            file_content: Union[bytes, str],
                            filename: str,
                            task_description: str,
                            task_context: Dict[str, Any],
                            user_description: str = "") -> Dict[str, Any]:
        """Synchronous wrapper for the async analyze_evidence method."""

        # Run the async method in a new event loop
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            result = loop.run_until_complete(
                self.agent.analyze_evidence(
                    file_content, filename, task_description,
                    task_context, user_description
                )
            )

            loop.close()
            return result

        except Exception as e:
            logger.error(f"[SYNC_WRAPPER] Error in async wrapper: {str(e)}")
            return {
                "error": f"Agent wrapper error: {str(e)}",
                "analysis_method": "claude_code_sdk_error"
            }

    def analyze_multiple_evidence_sync(self,
                                     documents_content: List[Dict[str, Any]],
                                     task_description: str,
                                     task_context: Dict[str, Any],
                                     user_description: str = "") -> Dict[str, Any]:
        """Synchronous wrapper for multi-document analysis."""

        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            result = loop.run_until_complete(
                self.agent.analyze_multiple_evidence(
                    documents_content, task_description,
                    task_context, user_description
                )
            )

            loop.close()
            return result

        except Exception as e:
            logger.error(f"[MULTI_SYNC_WRAPPER] Error in multi-document async wrapper: {str(e)}")
            return {
                "error": f"Multi-document agent wrapper error: {str(e)}",
                "analysis_method": "claude_code_sdk_multi_error"
            }


# Test function
async def test_claude_code_agent():
    """Test the Claude Code evidence agent."""

    print("[TEST] Testing Claude Code Evidence Agent")

    # Sample test data
    sample_document = """
    SECURITY IMPLEMENTATION REPORT
    ==============================

    This report outlines the implementation of new security protocols
    for data access controls and user authentication systems.

    IMPLEMENTED MEASURES:
    - Multi-factor authentication deployed
    - Role-based access control implemented
    - Security audit completed with 98% compliance
    """

    task_description = "Implement new security protocols for data access controls"
    task_context = {
        "department": "IT Security",
        "implementation_type": "Security Enhancement",
        "division": "Information Technology",
        "requires_collaboration": True
    }
    user_description = "This document shows our security implementation results"

    # Create and test agent
    agent = ClaudeCodeEvidenceAgent()

    result = await agent.analyze_evidence(
        sample_document,
        "security_implementation_report.txt",
        task_description,
        task_context,
        user_description
    )

    print(f"[TEST] Analysis completed:")
    print(f"  Valid: {result.get('is_valid', 'unknown')}")
    print(f"  Confidence: {result.get('confidence', 0):.2f}")
    print(f"  Quality: {result.get('evidence_quality', 'unknown')}")
    print(f"  Processing time: {result.get('processing_time', 0):.2f}s")


if __name__ == "__main__":
    asyncio.run(test_claude_code_agent())