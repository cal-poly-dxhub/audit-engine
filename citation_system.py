#!/usr/bin/env python3
"""
Citation and Annotation System for Evidence Analysis

This module provides structures and utilities for creating interactive citations
and annotations that highlight specific passages in documents.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Union
from enum import Enum
import re
import uuid


class AnnotationType(Enum):
    """Types of annotations that can be created"""
    SUPPORT = "support"          # Highlights supporting evidence
    CONCERN = "concern"          # Highlights concerns or issues
    CORRECTION = "correction"    # Suggests corrections
    CLARIFICATION = "clarification"  # Requests clarification
    REFERENCE = "reference"      # General reference or citation
    MISSING = "missing"          # Points out missing information


class AnnotationSeverity(Enum):
    """Severity levels for annotations"""
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class Citation:
    """Represents a specific text citation with location information"""
    citation_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    # Text location information
    text_snippet: str = ""           # The actual text being cited
    start_position: int = -1         # Character position in the document
    end_position: int = -1           # End character position
    page_number: Optional[int] = None
    section_id: Optional[str] = None
    paragraph_index: Optional[int] = None

    # Context information
    context_before: str = ""         # Text before the citation for context
    context_after: str = ""          # Text after the citation for context

    # Fuzzy matching support
    text_pattern: Optional[str] = None  # Regex pattern for flexible matching
    confidence_score: float = 1.0    # How confident we are in the match

    def to_dict(self) -> Dict[str, Any]:
        """Convert citation to dictionary for JSON serialization"""
        return {
            'citation_id': self.citation_id,
            'text_snippet': self.text_snippet,
            'start_position': self.start_position,
            'end_position': self.end_position,
            'page_number': self.page_number,
            'section_id': self.section_id,
            'paragraph_index': self.paragraph_index,
            'context_before': self.context_before,
            'context_after': self.context_after,
            'text_pattern': self.text_pattern,
            'confidence_score': self.confidence_score
        }


@dataclass
class Annotation:
    """Represents an annotation with citation and commentary"""
    annotation_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    citation: Citation = field(default_factory=Citation)

    # Annotation content
    annotation_type: AnnotationType = AnnotationType.REFERENCE
    severity: AnnotationSeverity = AnnotationSeverity.INFO
    title: str = ""
    message: str = ""
    suggested_action: Optional[str] = None
    suggested_replacement: Optional[str] = None

    # Additional metadata
    tags: List[str] = field(default_factory=list)
    related_annotations: List[str] = field(default_factory=list)  # IDs of related annotations

    def to_dict(self) -> Dict[str, Any]:
        """Convert annotation to dictionary for JSON serialization"""
        return {
            'annotation_id': self.annotation_id,
            'citation': self.citation.to_dict(),
            'annotation_type': self.annotation_type.value,
            'severity': self.severity.value,
            'title': self.title,
            'message': self.message,
            'suggested_action': self.suggested_action,
            'suggested_replacement': self.suggested_replacement,
            'tags': self.tags,
            'related_annotations': self.related_annotations
        }


@dataclass
class AnnotationSet:
    """Collection of annotations for a document"""
    document_id: str
    annotations: List[Annotation] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def add_annotation(self, annotation: Annotation):
        """Add an annotation to the set"""
        self.annotations.append(annotation)

    def get_by_type(self, annotation_type: AnnotationType) -> List[Annotation]:
        """Get all annotations of a specific type"""
        return [ann for ann in self.annotations if ann.annotation_type == annotation_type]

    def get_by_severity(self, severity: AnnotationSeverity) -> List[Annotation]:
        """Get all annotations of a specific severity"""
        return [ann for ann in self.annotations if ann.severity == severity]

    def to_dict(self) -> Dict[str, Any]:
        """Convert annotation set to dictionary for JSON serialization"""
        return {
            'document_id': self.document_id,
            'annotations': [ann.to_dict() for ann in self.annotations],
            'metadata': self.metadata
        }


class CitationMatcher:
    """Utility class for matching citations in text"""

    @staticmethod
    def find_text_position(full_text: str, target_text: str, context_size: int = 50) -> Optional[Citation]:
        """
        Find the position of target text in full text and create a citation

        Args:
            full_text: The complete document text
            target_text: The text to find and cite
            context_size: Number of characters for context before/after

        Returns:
            Citation object if found, None otherwise
        """
        # Clean up the target text for better matching
        cleaned_target = re.sub(r'\s+', ' ', target_text.strip())

        # Try exact match first
        start_pos = full_text.find(cleaned_target)

        if start_pos == -1:
            # Try fuzzy matching with normalized whitespace
            normalized_full_text = re.sub(r'\s+', ' ', full_text)
            start_pos = normalized_full_text.find(cleaned_target)

            if start_pos == -1:
                # Try partial matching (first 20 and last 20 characters)
                if len(cleaned_target) > 40:
                    start_part = cleaned_target[:20]
                    end_part = cleaned_target[-20:]

                    start_match = normalized_full_text.find(start_part)
                    if start_match != -1:
                        # Look for end part within reasonable distance
                        search_end = min(start_match + len(cleaned_target) + 100, len(normalized_full_text))
                        end_match = normalized_full_text.find(end_part, start_match)

                        if end_match != -1 and end_match < search_end:
                            start_pos = start_match
                            end_pos = end_match + len(end_part)
                            actual_text = normalized_full_text[start_pos:end_pos]
                        else:
                            return None
                    else:
                        return None
                else:
                    return None
            else:
                end_pos = start_pos + len(cleaned_target)
                actual_text = cleaned_target
        else:
            end_pos = start_pos + len(cleaned_target)
            actual_text = cleaned_target

        # Extract context
        context_start = max(0, start_pos - context_size)
        context_end = min(len(full_text), end_pos + context_size)

        context_before = full_text[context_start:start_pos].strip()
        context_after = full_text[end_pos:context_end].strip()

        return Citation(
            text_snippet=actual_text,
            start_position=start_pos,
            end_position=end_pos,
            context_before=context_before,
            context_after=context_after,
            confidence_score=1.0 if start_pos == full_text.find(cleaned_target) else 0.8
        )

    @staticmethod
    def create_pattern_citation(text_pattern: str, full_text: str) -> List[Citation]:
        """
        Create citations for all matches of a regex pattern

        Args:
            text_pattern: Regex pattern to match
            full_text: The complete document text

        Returns:
            List of Citation objects for all matches
        """
        citations = []

        try:
            for match in re.finditer(text_pattern, full_text, re.IGNORECASE | re.MULTILINE):
                start_pos = match.start()
                end_pos = match.end()
                matched_text = match.group()

                context_start = max(0, start_pos - 50)
                context_end = min(len(full_text), end_pos + 50)

                citation = Citation(
                    text_snippet=matched_text,
                    start_position=start_pos,
                    end_position=end_pos,
                    context_before=full_text[context_start:start_pos].strip(),
                    context_after=full_text[end_pos:context_end].strip(),
                    text_pattern=text_pattern,
                    confidence_score=0.9
                )
                citations.append(citation)
        except re.error:
            # Invalid regex pattern
            pass

        return citations


def create_support_annotation(text_snippet: str, message: str, title: str = "Supporting Evidence") -> Annotation:
    """Helper function to create a support annotation"""
    citation = Citation(text_snippet=text_snippet)
    return Annotation(
        citation=citation,
        annotation_type=AnnotationType.SUPPORT,
        severity=AnnotationSeverity.INFO,
        title=title,
        message=message
    )


def create_concern_annotation(text_snippet: str, message: str, severity: AnnotationSeverity = AnnotationSeverity.MEDIUM,
                            suggested_action: Optional[str] = None) -> Annotation:
    """Helper function to create a concern annotation"""
    citation = Citation(text_snippet=text_snippet)
    return Annotation(
        citation=citation,
        annotation_type=AnnotationType.CONCERN,
        severity=severity,
        title="Concern Identified",
        message=message,
        suggested_action=suggested_action
    )


def create_correction_annotation(text_snippet: str, message: str, suggested_replacement: str,
                               severity: AnnotationSeverity = AnnotationSeverity.HIGH) -> Annotation:
    """Helper function to create a correction annotation"""
    citation = Citation(text_snippet=text_snippet)
    return Annotation(
        citation=citation,
        annotation_type=AnnotationType.CORRECTION,
        severity=severity,
        title="Correction Needed",
        message=message,
        suggested_replacement=suggested_replacement
    )