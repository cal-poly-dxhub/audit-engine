#!/usr/bin/env python3
"""
PDF Tools for Claude Code SDK Evidence Agent

Simple PDF text extraction tool that just works.
"""

import logging
from typing import Any, Dict
from pathlib import Path

# Claude Code SDK imports
from claude_code_sdk import tool, create_sdk_mcp_server

# Try to import PDF libraries
try:
    import pdfplumber
    PDFPLUMBER_AVAILABLE = True
except ImportError:
    PDFPLUMBER_AVAILABLE = False

try:
    import fitz  # PyMuPDF
    PYMUPDF_AVAILABLE = True
except ImportError:
    PYMUPDF_AVAILABLE = False

try:
    import PyPDF2
    PYPDF2_AVAILABLE = True
except ImportError:
    PYPDF2_AVAILABLE = False

logger = logging.getLogger(__name__)

@tool(
    name="extract_pdf_text",
    description="Extract all text content from a PDF file",
    input_schema={"file_path": str}
)
async def extract_pdf_text(args: Dict[str, Any]) -> Dict[str, Any]:
    """Extract text from PDF file using the best available method."""

    file_path = args["file_path"]

    # Check if file exists
    if not Path(file_path).exists():
        return {
            "content": [{
                "type": "text",
                "text": f"Error: PDF file not found at {file_path}"
            }],
            "is_error": True
        }

    # Check if any PDF library is available
    if not (PDFPLUMBER_AVAILABLE or PYMUPDF_AVAILABLE or PYPDF2_AVAILABLE):
        return {
            "content": [{
                "type": "text",
                "text": """No PDF libraries available. Install one with:

pip install pdfplumber

Then retry the extraction."""
            }],
            "is_error": True
        }

    # Try extraction methods in order of preference
    extracted_text = None
    method_used = None

    # Try pdfplumber first (best for most PDFs)
    if PDFPLUMBER_AVAILABLE and not extracted_text:
        try:
            with pdfplumber.open(file_path) as pdf:
                text_parts = []
                for i, page in enumerate(pdf.pages, 1):
                    page_text = page.extract_text()
                    if page_text:
                        text_parts.append(f"--- Page {i} ---\n{page_text}\n")

                if text_parts:
                    extracted_text = "\n".join(text_parts)
                    method_used = "pdfplumber"
        except Exception as e:
            logger.warning(f"pdfplumber failed: {e}")

    # Try PyMuPDF if pdfplumber didn't work
    if PYMUPDF_AVAILABLE and not extracted_text:
        try:
            doc = fitz.open(file_path)
            text_parts = []
            for i in range(doc.page_count):
                page = doc[i]
                page_text = page.get_text()
                if page_text:
                    text_parts.append(f"--- Page {i+1} ---\n{page_text}\n")
            doc.close()

            if text_parts:
                extracted_text = "\n".join(text_parts)
                method_used = "pymupdf"
        except Exception as e:
            logger.warning(f"pymupdf failed: {e}")

    # Try PyPDF2 as last resort
    if PYPDF2_AVAILABLE and not extracted_text:
        try:
            with open(file_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                text_parts = []
                for i, page in enumerate(pdf_reader.pages, 1):
                    page_text = page.extract_text()
                    if page_text:
                        text_parts.append(f"--- Page {i} ---\n{page_text}\n")

                if text_parts:
                    extracted_text = "\n".join(text_parts)
                    method_used = "pypdf2"
        except Exception as e:
            logger.warning(f"pypdf2 failed: {e}")

    # Return results
    if extracted_text:
        return {
            "content": [{
                "type": "text",
                "text": f"""PDF Text Extraction Results
{'='*50}
File: {Path(file_path).name}
Method: {method_used}

Extracted Text:
{'-'*20}
{extracted_text.strip()}

✓ Text extraction completed successfully."""
            }]
        }
    else:
        return {
            "content": [{
                "type": "text",
                "text": f"""Failed to extract text from {Path(file_path).name}

This could mean:
- The PDF contains only images (needs OCR)
- The PDF is password protected
- The PDF structure is corrupted

Available libraries: {[lib for lib, avail in [('pdfplumber', PDFPLUMBER_AVAILABLE), ('pymupdf', PYMUPDF_AVAILABLE), ('pypdf2', PYPDF2_AVAILABLE)] if avail]}"""
            }],
            "is_error": True
        }

def create_pdf_tools_server():
    """Create the PDF tools MCP server."""
    return create_sdk_mcp_server(
        name="pdf-tools",
        version="1.0.0",
        tools=[extract_pdf_text]
    )