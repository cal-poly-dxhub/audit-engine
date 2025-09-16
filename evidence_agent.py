#!/usr/bin/env python3
"""
Agentic Evidence Analysis System

This module implements an intelligent agent-based workflow for analyzing
large and complex evidence documents using the Claude Code SDK pattern.
The agent can process various document types, understand context,
and provide comprehensive evidence validation.
"""

import os
import json
import time
import logging
from logging.handlers import RotatingFileHandler
from typing import Dict, List, Any, Optional, Tuple, Union
from dataclasses import dataclass, asdict
from enum import Enum
import PyPDF2
import docx
from PIL import Image
import base64
import io
from pathlib import Path
import uuid
from datetime import datetime
import re

# Setup comprehensive logging for the agent
def setup_agent_logging():
    """Setup detailed rotating logs for the evidence agent"""
    # Create logs directory if it doesn't exist
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)

    # Create agent logger
    agent_logger = logging.getLogger('evidence_agent')
    agent_logger.setLevel(logging.DEBUG)

    # Remove existing handlers to avoid duplicates
    for handler in agent_logger.handlers[:]:
        agent_logger.removeHandler(handler)

    # Create formatters
    detailed_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - [%(funcName)s:%(lineno)d] - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    simple_formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%H:%M:%S'
    )

    # Rotating file handler for detailed logs (10MB, keep 5 files)
    file_handler = RotatingFileHandler(
        log_dir / 'evidence_agent_detailed.log',
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(detailed_formatter)

    # Rotating file handler for analysis logs (5MB, keep 3 files)
    analysis_handler = RotatingFileHandler(
        log_dir / 'evidence_analysis.log',
        maxBytes=5*1024*1024,  # 5MB
        backupCount=3,
        encoding='utf-8'
    )
    analysis_handler.setLevel(logging.INFO)
    analysis_handler.setFormatter(simple_formatter)

    # Console handler for real-time monitoring
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(simple_formatter)

    # Add handlers
    agent_logger.addHandler(file_handler)
    agent_logger.addHandler(analysis_handler)
    agent_logger.addHandler(console_handler)

    return agent_logger

# Initialize logger
logger = setup_agent_logging()

class AnalysisType(Enum):
    """Types of evidence analysis the agent can perform"""
    DOCUMENT_STRUCTURE = "document_structure"
    CONTENT_ANALYSIS = "content_analysis"
    COMPLIANCE_CHECK = "compliance_check"
    EVIDENCE_VALIDATION = "evidence_validation"
    CROSS_REFERENCE = "cross_reference"

class DocumentType(Enum):
    """Supported document types"""
    PDF = "pdf"
    DOCX = "docx"
    IMAGE = "image"
    TEXT = "text"
    UNKNOWN = "unknown"

@dataclass
class AnalysisResult:
    """Result of agent analysis"""
    analysis_type: AnalysisType
    confidence: float
    findings: List[str]
    evidence_quality: str  # "high", "medium", "low"
    recommendations: List[str]
    metadata: Dict[str, Any]
    processing_time: float

@dataclass
class ProgressStep:
    """Represents a step in the analysis process"""
    step_id: str
    description: str
    status: str  # "pending", "in_progress", "completed", "failed"
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    details: Optional[str] = None
    substeps: Optional[List['ProgressStep']] = None

class ProgressTracker:
    """Tracks progress of the agentic analysis workflow"""

    def __init__(self, analysis_id: str):
        self.analysis_id = analysis_id
        self.steps: List[ProgressStep] = []
        self.current_step: Optional[ProgressStep] = None
        self.start_time = time.time()
        logger.info(f"[START] Starting analysis session: {analysis_id}")

    def add_step(self, step_id: str, description: str, details: str = None) -> ProgressStep:
        """Add a new step to track"""
        step = ProgressStep(step_id, description, "pending", details=details)
        self.steps.append(step)
        logger.debug(f"[STEP] Added step: {step_id} - {description}")
        return step

    def start_step(self, step_id: str) -> ProgressStep:
        """Mark a step as started"""
        step = next((s for s in self.steps if s.step_id == step_id), None)
        if step:
            step.status = "in_progress"
            step.start_time = time.time()
            self.current_step = step
            logger.info(f"[BEGIN] Starting: {step.description}")
            if step.details:
                logger.debug(f"   Details: {step.details}")
        return step

    def complete_step(self, step_id: str, details: str = None):
        """Mark a step as completed"""
        step = next((s for s in self.steps if s.step_id == step_id), None)
        if step:
            step.status = "completed"
            step.end_time = time.time()
            duration = step.end_time - step.start_time if step.start_time else 0
            logger.info(f"[DONE] Completed: {step.description} ({duration:.2f}s)")
            if details:
                step.details = details
                logger.debug(f"   Result: {details}")
            self.current_step = None

    def fail_step(self, step_id: str, error: str):
        """Mark a step as failed"""
        step = next((s for s in self.steps if s.step_id == step_id), None)
        if step:
            step.status = "failed"
            step.end_time = time.time()
            step.details = error
            logger.error(f"[FAIL] Failed: {step.description} - {error}")
            self.current_step = None

    def get_progress(self) -> Dict[str, Any]:
        """Get current progress status"""
        completed = len([s for s in self.steps if s.status == "completed"])
        total = len(self.steps)
        current_step_desc = self.current_step.description if self.current_step else "Idle"

        return {
            "analysis_id": self.analysis_id,
            "progress_percentage": (completed / total * 100) if total > 0 else 0,
            "completed_steps": completed,
            "total_steps": total,
            "current_step": current_step_desc,
            "elapsed_time": time.time() - self.start_time,
            "steps": [asdict(step) for step in self.steps]
        }

    def log_summary(self):
        """Log a summary of the analysis"""
        total_time = time.time() - self.start_time
        completed = len([s for s in self.steps if s.status == "completed"])
        failed = len([s for s in self.steps if s.status == "failed"])

        logger.info(f"[SUMMARY] Analysis Summary for {self.analysis_id}:")
        logger.info(f"   Total time: {total_time:.2f}s")
        logger.info(f"   Steps completed: {completed}")
        logger.info(f"   Steps failed: {failed}")
        logger.info(f"   Success rate: {(completed/(completed+failed)*100) if (completed+failed) > 0 else 100:.1f}%")

@dataclass
class DocumentSection:
    """Represents a section of a document for analysis"""
    section_id: str
    title: str
    content: str
    page_number: Optional[int] = None
    section_type: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

class EvidenceAnalysisAgent:
    """
    Intelligent agent for comprehensive evidence document analysis.

    This agent implements an agentic workflow that can:
    1. Intelligently segment large documents
    2. Perform specialized analysis on each section
    3. Cross-reference findings across sections
    4. Provide comprehensive evidence validation
    """

    def __init__(self, bedrock_client, max_chunk_size: int = 3000):
        self.bedrock_client = bedrock_client
        self.max_chunk_size = max_chunk_size
        self.analysis_history: List[AnalysisResult] = []
        self.current_progress: Optional[ProgressTracker] = None
        logger.info("[INIT] Evidence Analysis Agent initialized")

    def get_current_progress(self) -> Optional[Dict[str, Any]]:
        """Get current analysis progress if available"""
        if self.current_progress:
            return self.current_progress.get_progress()
        return None

    def analyze_evidence(self,
                        file_content: Union[bytes, str],
                        filename: str,
                        task_description: str,
                        task_context: Dict[str, Any],
                        user_description: str = "") -> Dict[str, Any]:
        """
        Main entry point for agentic evidence analysis.

        Args:
            file_content: Raw file content (bytes for binary files, str for text)
            filename: Name of the file
            task_description: Description of the audit task
            task_context: Context about the task (department, type, etc.)
            user_description: User's explanation of the evidence

        Returns:
            Comprehensive analysis result
        """
        # Initialize progress tracking
        analysis_id = f"analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
        self.current_progress = ProgressTracker(analysis_id)

        # Setup analysis steps
        self.current_progress.add_step("init", "Initialize analysis session", f"File: {filename}")
        self.current_progress.add_step("doc_type", "Determine document type", f"Analyzing file extension and content")
        self.current_progress.add_step("extract", "Extract document content", f"Processing {doc_type.value if 'doc_type' in locals() else 'unknown'} format")
        self.current_progress.add_step("segment", "Segment into logical sections", f"Breaking document into analyzable chunks")
        self.current_progress.add_step("analyze", "Perform section analysis", f"AI analysis of each document section")
        self.current_progress.add_step("cross_ref", "Cross-reference analysis", f"Validate consistency across sections")
        self.current_progress.add_step("synthesize", "Synthesize final results", f"Combine findings into comprehensive assessment")
        self.current_progress.add_step("finalize", "Finalize analysis", f"Generate final report and recommendations")

        try:
            # Step 1: Initialize
            self.current_progress.start_step("init")
            logger.info(f"[ANALYZE] Starting analysis of '{filename}' for task: {task_description[:50]}...")
            logger.debug(f"[CONTEXT] Task context: {task_context}")
            logger.debug(f"[USER] User description: {user_description}")
            self.current_progress.complete_step("init", f"Session {analysis_id} initialized")

            # Step 2: Determine document type and extract content
            self.current_progress.start_step("doc_type")
            doc_type = self._determine_document_type(filename)
            logger.info(f"[DOC_TYPE] Document type detected: {doc_type.value}")
            self.current_progress.complete_step("doc_type", f"Type: {doc_type.value}")

            # Step 3: Extract and structure content
            self.current_progress.start_step("extract")
            logger.debug(f"[EXTRACT] Extracting content from {doc_type.value} file...")
            document_sections = self._extract_document_content(file_content, filename, doc_type)
            self.current_progress.complete_step("extract", f"Content extracted successfully")

            # Step 4: Segment document
            self.current_progress.start_step("segment")
            logger.info(f"[SEGMENT] Document segmented into {len(document_sections)} sections:")
            for i, section in enumerate(document_sections):
                logger.debug(f"   Section {i+1}: {section.title} ({len(section.content)} chars)")
            self.current_progress.complete_step("segment", f"{len(document_sections)} sections created")

            # Step 5: Perform multi-stage analysis
            self.current_progress.start_step("analyze")
            logger.info(f"[AI_ANALYZE] Starting AI analysis of {len(document_sections)} sections...")
            analysis_results = self._perform_agentic_analysis(
                document_sections, task_description, task_context, user_description
            )
            self.current_progress.complete_step("analyze", f"{len(analysis_results)} analysis results generated")

            # Step 6: Cross-reference (conditional)
            if len(document_sections) > 1:
                self.current_progress.start_step("cross_ref")
                logger.info("[CROSS_REF] Performing cross-section validation...")
                # Cross-reference analysis is included in _perform_agentic_analysis
                self.current_progress.complete_step("cross_ref", "Cross-validation completed")
            else:
                logger.debug("[SKIP] Skipping cross-reference analysis (single section document)")

            # Step 7: Synthesize results
            self.current_progress.start_step("synthesize")
            logger.info("[SYNTHESIZE] Synthesizing analysis results...")
            final_result = self._synthesize_analysis_results(
                analysis_results, task_description, task_context
            )
            self.current_progress.complete_step("synthesize", f"Results synthesized: {final_result.get('evidence_quality', 'unknown')} quality")

            # Step 8: Finalize
            self.current_progress.start_step("finalize")
            processing_time = time.time() - self.current_progress.start_time
            final_result['processing_time'] = processing_time
            final_result['document_type'] = doc_type.value
            final_result['sections_analyzed'] = len(document_sections)
            final_result['analysis_id'] = analysis_id

            # Add progress information to result
            final_result['progress_info'] = self.current_progress.get_progress()

            logger.info(f"[SUCCESS] Analysis completed successfully!")
            logger.info(f"   [RESULT] Result: {'VALID' if final_result.get('is_valid') else 'INVALID'} evidence")
            logger.info(f"   [CONFIDENCE] Confidence: {final_result.get('confidence', 0):.2f}")
            logger.info(f"   [QUALITY] Quality: {final_result.get('evidence_quality', 'unknown').upper()}")
            logger.info(f"   [TIME] Processing time: {processing_time:.2f}s")

            self.current_progress.complete_step("finalize", f"Analysis complete - {final_result.get('recommendation', 'unknown')}")
            self.current_progress.log_summary()

            return final_result

        except Exception as e:
            error_msg = f"Analysis failed: {str(e)}"
            logger.error(f"[ERROR] {error_msg}")
            logger.exception("Full error details:")

            # Mark current step as failed if there is one
            if self.current_progress and self.current_progress.current_step:
                self.current_progress.fail_step(self.current_progress.current_step.step_id, str(e))

            return {"error": error_msg, "analysis_id": analysis_id}

    def _determine_document_type(self, filename: str) -> DocumentType:
        """Determine the type of document based on filename"""
        ext = Path(filename).suffix.lower()

        if ext == '.pdf':
            return DocumentType.PDF
        elif ext in ['.docx', '.doc']:
            return DocumentType.DOCX
        elif ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp']:
            return DocumentType.IMAGE
        elif ext in ['.txt', '.md']:
            return DocumentType.TEXT
        else:
            return DocumentType.UNKNOWN

    def _extract_document_content(self,
                                 file_content: Union[bytes, str],
                                 filename: str,
                                 doc_type: DocumentType) -> List[DocumentSection]:
        """Extract and structure content from different document types"""

        if doc_type == DocumentType.PDF:
            return self._extract_pdf_content(file_content)
        elif doc_type == DocumentType.DOCX:
            return self._extract_docx_content(file_content)
        elif doc_type == DocumentType.IMAGE:
            return self._extract_image_content(file_content, filename)
        elif doc_type == DocumentType.TEXT:
            return self._extract_text_content(file_content)
        else:
            return [DocumentSection("unknown", "Unknown Document", str(file_content))]

    def _extract_pdf_content(self, file_content: bytes) -> List[DocumentSection]:
        """Extract structured content from PDF"""
        sections = []

        try:
            pdf_file = io.BytesIO(file_content)
            pdf_reader = PyPDF2.PdfReader(pdf_file)

            # Strategy 1: Extract by pages first
            for page_num, page in enumerate(pdf_reader.pages):
                page_text = page.extract_text()
                if page_text.strip():
                    # Try to identify sections within the page
                    page_sections = self._identify_text_sections(page_text, page_num + 1)
                    sections.extend(page_sections)

            # Strategy 2: If no clear sections found, create logical chunks
            if not sections:
                full_text = "\n".join([page.extract_text() for page in pdf_reader.pages])
                sections = self._create_logical_chunks(full_text)

        except Exception as e:
            logger.error(f"Error extracting PDF content: {str(e)}")
            # Fallback: treat as single section
            sections = [DocumentSection("pdf_error", "PDF Content", f"Error extracting: {str(e)}")]

        return sections

    def _extract_docx_content(self, file_content: bytes) -> List[DocumentSection]:
        """Extract structured content from DOCX"""
        sections = []

        try:
            doc_file = io.BytesIO(file_content)
            doc = docx.Document(doc_file)

            current_section = ""
            current_content = []
            section_counter = 1

            for paragraph in doc.paragraphs:
                text = paragraph.text.strip()
                if not text:
                    continue

                # Check if this looks like a heading
                if self._is_heading(paragraph, text):
                    # Save previous section if exists
                    if current_content:
                        sections.append(DocumentSection(
                            f"section_{section_counter}",
                            current_section or f"Section {section_counter}",
                            "\n".join(current_content)
                        ))
                        section_counter += 1

                    # Start new section
                    current_section = text
                    current_content = []
                else:
                    current_content.append(text)

            # Add final section
            if current_content:
                sections.append(DocumentSection(
                    f"section_{section_counter}",
                    current_section or f"Section {section_counter}",
                    "\n".join(current_content)
                ))

        except Exception as e:
            logger.error(f"Error extracting DOCX content: {str(e)}")
            sections = [DocumentSection("docx_error", "DOCX Content", f"Error extracting: {str(e)}")]

        return sections

    def _extract_image_content(self, file_content: bytes, filename: str) -> List[DocumentSection]:
        """Handle image content for analysis"""
        # For images, we'll create a special section that the analysis agent can handle
        encoded_image = base64.b64encode(file_content).decode('utf-8')

        # Determine media type
        ext = Path(filename).suffix.lower()
        media_type_map = {
            '.png': 'image/png',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.gif': 'image/gif',
            '.webp': 'image/webp',
            '.bmp': 'image/bmp'
        }
        media_type = media_type_map.get(ext, 'image/jpeg')

        return [DocumentSection(
            "image_content",
            f"Image: {filename}",
            "",  # No text content
            metadata={
                "type": "image",
                "encoded_data": encoded_image,
                "media_type": media_type,
                "filename": filename
            }
        )]

    def _extract_text_content(self, file_content: Union[bytes, str]) -> List[DocumentSection]:
        """Extract content from plain text files"""
        if isinstance(file_content, bytes):
            text_content = file_content.decode('utf-8', errors='ignore')
        else:
            text_content = file_content

        return self._create_logical_chunks(text_content)

    def _identify_text_sections(self, text: str, page_num: int) -> List[DocumentSection]:
        """Identify logical sections within text content"""
        sections = []

        # Look for common section markers
        section_patterns = [
            r'^[A-Z\s]{3,}$',  # ALL CAPS headings
            r'^\d+\.\s+[A-Z]',  # Numbered sections
            r'^[IVX]+\.\s+',    # Roman numerals
            r'^[A-Z]\.\s+',     # Letter sections
        ]

        lines = text.split('\n')
        current_section = None
        current_content = []
        section_counter = 1

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Check if this line looks like a section header
            is_header = any(re.match(pattern, line) for pattern in section_patterns)

            if is_header:
                # Save previous section
                if current_content:
                    sections.append(DocumentSection(
                        f"page_{page_num}_section_{section_counter}",
                        current_section or f"Page {page_num} Section {section_counter}",
                        "\n".join(current_content),
                        page_number=page_num
                    ))
                    section_counter += 1

                # Start new section
                current_section = line
                current_content = []
            else:
                current_content.append(line)

        # Add final section
        if current_content:
            sections.append(DocumentSection(
                f"page_{page_num}_section_{section_counter}",
                current_section or f"Page {page_num} Section {section_counter}",
                "\n".join(current_content),
                page_number=page_num
            ))

        # If no sections found, treat entire page as one section
        if not sections:
            sections.append(DocumentSection(
                f"page_{page_num}",
                f"Page {page_num}",
                text,
                page_number=page_num
            ))

        return sections

    def _create_logical_chunks(self, text: str) -> List[DocumentSection]:
        """Create logical chunks from continuous text"""
        sections = []

        # Split into paragraphs first
        paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]

        current_chunk = []
        current_size = 0
        chunk_counter = 1

        for paragraph in paragraphs:
            paragraph_size = len(paragraph)

            # If adding this paragraph would exceed max size, save current chunk
            if current_size + paragraph_size > self.max_chunk_size and current_chunk:
                sections.append(DocumentSection(
                    f"chunk_{chunk_counter}",
                    f"Document Chunk {chunk_counter}",
                    "\n\n".join(current_chunk)
                ))
                chunk_counter += 1
                current_chunk = [paragraph]
                current_size = paragraph_size
            else:
                current_chunk.append(paragraph)
                current_size += paragraph_size

        # Add final chunk
        if current_chunk:
            sections.append(DocumentSection(
                f"chunk_{chunk_counter}",
                f"Document Chunk {chunk_counter}",
                "\n\n".join(current_chunk)
            ))

        return sections

    def _is_heading(self, paragraph, text: str) -> bool:
        """Determine if a paragraph is likely a heading"""
        # Check DOCX paragraph style
        if hasattr(paragraph, 'style') and paragraph.style:
            style_name = paragraph.style.name.lower()
            if 'heading' in style_name or 'title' in style_name:
                return True

        # Check text characteristics
        if len(text) < 100 and (text.isupper() or text.istitle()):
            return True

        # Check for numbering patterns
        if re.match(r'^\d+\.\s+', text) or re.match(r'^[IVX]+\.\s+', text):
            return True

        return False

    def _perform_agentic_analysis(self,
                                 sections: List[DocumentSection],
                                 task_description: str,
                                 task_context: Dict[str, Any],
                                 user_description: str) -> List[AnalysisResult]:
        """Perform multi-stage agentic analysis on document sections"""
        analysis_results = []

        # Stage 1: Individual section analysis
        for section in sections:
            section_result = self._analyze_section(
                section, task_description, task_context, user_description
            )
            analysis_results.append(section_result)

        # Stage 2: Cross-section analysis (if multiple sections)
        if len(sections) > 1:
            cross_analysis = self._perform_cross_section_analysis(
                sections, analysis_results, task_description, task_context
            )
            analysis_results.append(cross_analysis)

        return analysis_results

    def _analyze_section(self,
                        section: DocumentSection,
                        task_description: str,
                        task_context: Dict[str, Any],
                        user_description: str) -> AnalysisResult:
        """Analyze individual document section with specialized prompts"""
        start_time = time.time()

        logger.debug(f"[ANALYZE_SEC] Analyzing section: {section.title}")
        logger.debug(f"   [CONTENT_LEN] Content length: {len(section.content)} characters")
        logger.debug(f"   [SECTION_ID] Section ID: {section.section_id}")

        try:
            # Handle image sections differently
            if section.metadata and section.metadata.get("type") == "image":
                logger.info(f"[IMAGE] Processing image section: {section.metadata.get('filename', 'unknown')}")
                return self._analyze_image_section(section, task_description, task_context, user_description)

            logger.debug(f"[PROMPT] Creating analysis prompt for text section...")
            # Create specialized analysis prompt
            prompt = self._create_section_analysis_prompt(
                section, task_description, task_context, user_description
            )

            logger.debug(f"[AI_CALL] Sending section to AI for analysis (max_tokens=2000)...")
            # Get AI analysis
            response = self.bedrock_client.invoke_model_structured(
                prompt, None, max_tokens=2000
            )

            logger.debug(f"[PARSE] Parsing AI response for section {section.section_id}...")
            # Parse response
            analysis_data = self._parse_analysis_response(response)

            processing_time = time.time() - start_time

            # Log analysis results
            confidence = analysis_data.get('confidence', 0.7)
            quality = analysis_data.get('evidence_quality', 'medium')
            findings_count = len(analysis_data.get('findings', []))

            logger.info(f"[COMPLETE] Section analysis complete: {section.title}")
            logger.info(f"   [CONFIDENCE] Confidence: {confidence:.2f}")
            logger.info(f"   [QUALITY] Quality: {quality}")
            logger.info(f"   [FINDINGS] Findings: {findings_count}")
            logger.info(f"   [TIME] Time: {processing_time:.2f}s")

            return AnalysisResult(
                analysis_type=AnalysisType.CONTENT_ANALYSIS,
                confidence=confidence,
                findings=analysis_data.get('findings', []),
                evidence_quality=quality,
                recommendations=analysis_data.get('recommendations', []),
                metadata={
                    'section_id': section.section_id,
                    'section_title': section.title,
                    'content_length': len(section.content),
                    'compliance_indicators': analysis_data.get('compliance_indicators', []),
                    'concerns': analysis_data.get('concerns', []),
                    'verification_needs': analysis_data.get('verification_needs', [])
                },
                processing_time=processing_time
            )

        except Exception as e:
            processing_time = time.time() - start_time
            logger.error(f"[FAIL_SEC] Section analysis failed: {section.section_id}")
            logger.error(f"   Error: {str(e)}")
            logger.error(f"   Time: {processing_time:.2f}s")
            logger.exception("Full error details:")

            return AnalysisResult(
                analysis_type=AnalysisType.CONTENT_ANALYSIS,
                confidence=0.0,
                findings=[f"Analysis error: {str(e)}"],
                evidence_quality='low',
                recommendations=['Manual review required due to analysis error'],
                metadata={'section_id': section.section_id, 'error': str(e)},
                processing_time=processing_time
            )

    def _analyze_image_section(self,
                              section: DocumentSection,
                              task_description: str,
                              task_context: Dict[str, Any],
                              user_description: str) -> AnalysisResult:
        """Specialized analysis for image sections"""
        start_time = time.time()

        try:
            # Create image analysis prompt
            prompt = f"""
Analyze this evidence image in detail against the audit task requirements.

TASK DESCRIPTION: {task_description}

TASK CONTEXT:
- Department: {task_context.get('department', 'Not specified')}
- Implementation Type: {task_context.get('implementation_type', 'Not specified')}
- Division: {task_context.get('division', 'Not specified')}
- Requires Collaboration: {task_context.get('requires_collaboration', False)}

USER EXPLANATION: {user_description if user_description else 'No explanation provided'}

Provide a comprehensive analysis including:
1. Detailed description of what you observe in the image
2. Specific elements that relate to the audit task
3. Evidence quality assessment
4. Areas of concern or missing elements
5. Recommendations for evidence validation

Return JSON with this structure:
{{
    "confidence": 0.0-1.0,
    "findings": ["detailed list of observations"],
    "evidence_quality": "high/medium/low",
    "recommendations": ["list of recommendations"],
    "visual_elements": ["list of key visual elements identified"],
    "task_relevance": "how well the image addresses the task requirements"
}}
"""

            # Create content with image
            content = [
                {"type": "text", "text": prompt},
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": section.metadata['media_type'],
                        "data": section.metadata['encoded_data']
                    }
                }
            ]

            response = self.bedrock_client.invoke_model_with_image(content, max_tokens=3000)
            analysis_data = self._parse_analysis_response(response)

            processing_time = time.time() - start_time

            return AnalysisResult(
                analysis_type=AnalysisType.CONTENT_ANALYSIS,
                confidence=analysis_data.get('confidence', 0.7),
                findings=analysis_data.get('findings', []),
                evidence_quality=analysis_data.get('evidence_quality', 'medium'),
                recommendations=analysis_data.get('recommendations', []),
                metadata={
                    'section_id': section.section_id,
                    'type': 'image',
                    'filename': section.metadata.get('filename', 'unknown'),
                    'visual_elements': analysis_data.get('visual_elements', []),
                    'task_relevance': analysis_data.get('task_relevance', 'unclear')
                },
                processing_time=processing_time
            )

        except Exception as e:
            logger.error(f"Error analyzing image section: {str(e)}")
            return AnalysisResult(
                analysis_type=AnalysisType.CONTENT_ANALYSIS,
                confidence=0.0,
                findings=[f"Image analysis error: {str(e)}"],
                evidence_quality='low',
                recommendations=['Manual review required'],
                metadata={'section_id': section.section_id, 'error': str(e)},
                processing_time=time.time() - start_time
            )

    def _create_section_analysis_prompt(self,
                                       section: DocumentSection,
                                       task_description: str,
                                       task_context: Dict[str, Any],
                                       user_description: str) -> str:
        """Create specialized prompt for section analysis"""
        return f"""
As an expert evidence analyst, carefully examine this document section for audit compliance.

DOCUMENT SECTION: {section.title}
CONTENT:
{section.content[:self.max_chunk_size]}

AUDIT TASK: {task_description}

TASK CONTEXT:
- Department: {task_context.get('department', 'Not specified')}
- Implementation Type: {task_context.get('implementation_type', 'Not specified')}
- Division: {task_context.get('division', 'Not specified')}
- Requires Collaboration: {task_context.get('requires_collaboration', False)}

USER EXPLANATION: {user_description if user_description else 'No explanation provided'}

Perform a comprehensive analysis of this section:

1. CONTENT ANALYSIS: What specific information does this section contain?
2. TASK RELEVANCE: How directly does this content address the audit task requirements?
3. EVIDENCE QUALITY: Assess the strength and completeness of evidence presented
4. COMPLIANCE INDICATORS: Identify elements that demonstrate compliance or non-compliance
5. GAPS AND CONCERNS: Note any missing information or areas of concern
6. VERIFICATION NEEDS: What additional verification might be needed?

Return your analysis in JSON format:
{{
    "confidence": 0.0-1.0,
    "findings": [
        "Detailed finding 1",
        "Detailed finding 2"
    ],
    "evidence_quality": "high/medium/low",
    "recommendations": [
        "Specific recommendation 1",
        "Specific recommendation 2"
    ],
    "compliance_indicators": ["list of positive indicators"],
    "concerns": ["list of concerns or gaps"],
    "verification_needs": ["list of additional verification needs"]
}}
"""

    def _perform_cross_section_analysis(self,
                                       sections: List[DocumentSection],
                                       section_results: List[AnalysisResult],
                                       task_description: str,
                                       task_context: Dict[str, Any]) -> AnalysisResult:
        """Perform cross-section analysis to identify patterns and inconsistencies"""
        start_time = time.time()

        try:
            # Summarize findings from individual sections
            all_findings = []
            all_concerns = []
            quality_scores = []

            for result in section_results:
                all_findings.extend(result.findings)
                if 'concerns' in result.metadata:
                    all_concerns.extend(result.metadata['concerns'])
                quality_scores.append(result.confidence)

            # Create cross-analysis prompt
            prompt = f"""
Perform a comprehensive cross-section analysis of this evidence document.

AUDIT TASK: {task_description}
DOCUMENT SECTIONS ANALYZED: {len(sections)}

INDIVIDUAL SECTION FINDINGS:
{chr(10).join([f"- {finding}" for finding in all_findings[:20]])}

IDENTIFIED CONCERNS:
{chr(10).join([f"- {concern}" for concern in all_concerns[:10]])}

AVERAGE SECTION CONFIDENCE: {sum(quality_scores) / len(quality_scores) if quality_scores else 0:.2f}

Analyze patterns across sections and provide:
1. CONSISTENCY: Are the findings consistent across sections?
2. COMPLETENESS: Does the document comprehensively address the task?
3. COHERENCE: Do the sections work together to form strong evidence?
4. OVERALL ASSESSMENT: Summary assessment of evidence validity

Return JSON:
{{
    "confidence": 0.0-1.0,
    "findings": ["cross-section patterns and insights"],
    "evidence_quality": "high/medium/low",
    "recommendations": ["overall recommendations"],
    "consistency_assessment": "description of consistency across sections",
    "completeness_score": 0.0-1.0,
    "overall_validity": "valid/invalid/inconclusive"
}}
"""

            response = self.bedrock_client.invoke_model_structured(
                prompt, None, max_tokens=2000
            )

            analysis_data = self._parse_analysis_response(response)

            processing_time = time.time() - start_time

            return AnalysisResult(
                analysis_type=AnalysisType.CROSS_REFERENCE,
                confidence=analysis_data.get('confidence', 0.7),
                findings=analysis_data.get('findings', []),
                evidence_quality=analysis_data.get('evidence_quality', 'medium'),
                recommendations=analysis_data.get('recommendations', []),
                metadata={
                    'analysis_type': 'cross_section',
                    'sections_analyzed': len(sections),
                    'consistency_assessment': analysis_data.get('consistency_assessment', ''),
                    'completeness_score': analysis_data.get('completeness_score', 0.5),
                    'overall_validity': analysis_data.get('overall_validity', 'inconclusive')
                },
                processing_time=processing_time
            )

        except Exception as e:
            logger.error(f"Error in cross-section analysis: {str(e)}")
            return AnalysisResult(
                analysis_type=AnalysisType.CROSS_REFERENCE,
                confidence=0.0,
                findings=[f"Cross-section analysis error: {str(e)}"],
                evidence_quality='low',
                recommendations=['Manual review required'],
                metadata={'error': str(e)},
                processing_time=time.time() - start_time
            )

    def _parse_analysis_response(self, response: str) -> Dict[str, Any]:
        """Parse AI response into structured data"""
        try:
            # Extract JSON from response
            import re
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
            else:
                # Fallback parsing
                return {
                    'confidence': 0.5,
                    'findings': [response[:500] + "..." if len(response) > 500 else response],
                    'evidence_quality': 'medium',
                    'recommendations': ['Review analysis response format']
                }
        except Exception as e:
            logger.error(f"Error parsing analysis response: {str(e)}")
            return {
                'confidence': 0.0,
                'findings': [f"Parse error: {str(e)}"],
                'evidence_quality': 'low',
                'recommendations': ['Manual analysis required']
            }

    def _synthesize_analysis_results(self,
                                   results: List[AnalysisResult],
                                   task_description: str,
                                   task_context: Dict[str, Any]) -> Dict[str, Any]:
        """Synthesize all analysis results into final assessment"""

        if not results:
            return {
                'is_valid': False,
                'confidence': 0.0,
                'reasoning': 'No analysis results available',
                'evidence_quality': 'low',
                'recommendation': 'reject'
            }

        # Calculate overall metrics
        avg_confidence = sum(r.confidence for r in results) / len(results)
        all_findings = []
        all_recommendations = []
        quality_scores = {'high': 0, 'medium': 0, 'low': 0}

        for result in results:
            all_findings.extend(result.findings)
            all_recommendations.extend(result.recommendations)
            quality_scores[result.evidence_quality] += 1

        # Determine overall evidence quality
        if quality_scores['high'] >= quality_scores['medium'] + quality_scores['low']:
            overall_quality = 'high'
        elif quality_scores['low'] > quality_scores['medium'] + quality_scores['high']:
            overall_quality = 'low'
        else:
            overall_quality = 'medium'

        # Determine validity
        is_valid = avg_confidence >= 0.6 and overall_quality != 'low'

        if avg_confidence >= 0.8 and overall_quality == 'high':
            recommendation = 'accept'
        elif avg_confidence >= 0.5 and overall_quality in ['medium', 'high']:
            recommendation = 'request_additional'
        else:
            recommendation = 'reject'

        # Create comprehensive reasoning
        reasoning = f"""
Comprehensive agentic analysis completed:

DOCUMENT STRUCTURE: Analyzed {len([r for r in results if r.analysis_type == AnalysisType.CONTENT_ANALYSIS])} sections
OVERALL CONFIDENCE: {avg_confidence:.2f}
EVIDENCE QUALITY: {overall_quality}

KEY FINDINGS:
{chr(10).join([f"• {finding}" for finding in all_findings[:10]])}

ANALYSIS APPROACH:
- Multi-stage document segmentation and analysis
- Cross-section validation and consistency checking
- Specialized handling for different content types
- Comprehensive evidence quality assessment
"""

        return {
            'is_valid': is_valid,
            'confidence': avg_confidence,
            'reasoning': reasoning.strip(),
            'evidence_quality': overall_quality,
            'recommendation': recommendation,
            'findings': all_findings,
            'recommendations': list(set(all_recommendations)),  # Remove duplicates
            'analysis_metadata': {
                'sections_analyzed': len([r for r in results if r.analysis_type == AnalysisType.CONTENT_ANALYSIS]),
                'cross_references': len([r for r in results if r.analysis_type == AnalysisType.CROSS_REFERENCE]),
                'quality_distribution': quality_scores,
                'processing_stages': len(results)
            }
        }