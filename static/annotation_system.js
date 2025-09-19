/**
 * Interactive Annotation System for Evidence Analysis
 *
 * This module provides functionality for displaying and interacting with
 * text annotations and citations in the evidence analysis UI.
 */

class AnnotationSystem {
    constructor() {
        this.annotations = [];
        this.highlightedElements = new Map();
        this.annotationPopups = new Map();
        this.colors = {
            'support': '#28a745',      // Green
            'concern': '#ffc107',      // Yellow/Orange
            'correction': '#dc3545',   // Red
            'clarification': '#17a2b8', // Cyan
            'reference': '#007bff',    // Blue
            'missing': '#6f42c1'       // Purple
        };
        this.severityOpacity = {
            'info': 0.3,
            'low': 0.4,
            'medium': 0.6,
            'high': 0.8,
            'critical': 1.0
        };
    }

    /**
     * Initialize the annotation system with annotations data
     * @param {Array} annotationsData - Array of annotation objects
     */
    initialize(annotationsData) {
        console.log('Initializing annotation system with', annotationsData.length, 'annotations');
        this.annotations = annotationsData || [];
        this.createAnnotationStyles();
        this.processAnnotations();
        this.createAnnotationPanel();
    }

    /**
     * Create CSS styles for different annotation types
     */
    createAnnotationStyles() {
        const styleElement = document.createElement('style');
        styleElement.id = 'annotation-styles';

        let css = `
        .annotation-highlight {
            position: relative;
            cursor: pointer;
            border-radius: 3px;
            transition: all 0.2s ease;
        }

        .annotation-highlight:hover {
            transform: scale(1.02);
            box-shadow: 0 2px 4px rgba(0,0,0,0.2);
        }

        .annotation-popup {
            position: absolute;
            z-index: 1000;
            background: white;
            border: 1px solid #ddd;
            border-radius: 8px;
            padding: 12px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
            max-width: 350px;
            font-size: 14px;
            line-height: 1.4;
            display: none;
        }

        .annotation-popup.show {
            display: block;
        }

        .annotation-popup-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 8px;
            padding-bottom: 8px;
            border-bottom: 1px solid #eee;
        }

        .annotation-popup-title {
            font-weight: bold;
            margin: 0;
        }

        .annotation-popup-close {
            background: none;
            border: none;
            font-size: 18px;
            cursor: pointer;
            color: #999;
        }

        .annotation-popup-close:hover {
            color: #333;
        }

        .annotation-popup-type {
            display: inline-block;
            padding: 2px 6px;
            border-radius: 12px;
            font-size: 11px;
            font-weight: bold;
            text-transform: uppercase;
            color: white;
        }

        .annotation-popup-message {
            margin: 8px 0;
            color: #333;
        }

        .annotation-popup-actions {
            margin-top: 12px;
            padding-top: 8px;
            border-top: 1px solid #eee;
        }

        .annotation-popup-action {
            font-size: 12px;
            color: #666;
            margin-bottom: 4px;
        }

        .annotation-popup-action strong {
            color: #333;
        }

        .annotation-replacement {
            background: #f8f9fa;
            border: 1px solid #dee2e6;
            border-radius: 4px;
            padding: 8px;
            margin-top: 4px;
            font-family: monospace;
            font-size: 13px;
        }

        .annotation-panel {
            position: fixed;
            right: 20px;
            top: 100px;
            width: 300px;
            max-height: 500px;
            background: white;
            border: 1px solid #ddd;
            border-radius: 8px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
            overflow: hidden;
            z-index: 999;
            display: none;
        }

        .annotation-panel.show {
            display: block;
        }

        .annotation-panel-header {
            background: #f8f9fa;
            padding: 12px;
            border-bottom: 1px solid #ddd;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .annotation-panel-title {
            font-weight: bold;
            margin: 0;
        }

        .annotation-panel-count {
            background: #007bff;
            color: white;
            border-radius: 12px;
            padding: 2px 8px;
            font-size: 12px;
        }

        .annotation-panel-body {
            max-height: 400px;
            overflow-y: auto;
            padding: 8px;
        }

        .annotation-panel-item {
            padding: 8px;
            margin-bottom: 8px;
            border: 1px solid #eee;
            border-radius: 4px;
            cursor: pointer;
            transition: background-color 0.2s ease;
        }

        .annotation-panel-item:hover {
            background: #f8f9fa;
        }

        .annotation-panel-item.active {
            background: #e3f2fd;
            border-color: #2196f3;
        }

        .annotation-panel-item-type {
            font-size: 11px;
            font-weight: bold;
            text-transform: uppercase;
            margin-bottom: 4px;
        }

        .annotation-panel-item-text {
            font-size: 12px;
            color: #666;
            margin-bottom: 4px;
            font-style: italic;
        }

        .annotation-panel-item-message {
            font-size: 13px;
            color: #333;
        }
        `;

        // Add type-specific colors
        Object.entries(this.colors).forEach(([type, color]) => {
            css += `
            .annotation-type-${type} {
                background-color: ${color} !important;
            }

            .annotation-popup-type.type-${type} {
                background-color: ${color};
            }

            .annotation-panel-item-type.type-${type} {
                color: ${color};
            }
            `;
        });

        styleElement.textContent = css;
        document.head.appendChild(styleElement);
    }

    /**
     * Process all annotations and create highlights
     */
    processAnnotations() {
        console.log('Processing', this.annotations.length, 'annotations');

        // Group annotations by section for easier processing
        const annotationsBySection = new Map();

        this.annotations.forEach(annotation => {
            const sectionId = annotation.citation.section_id || 'unknown';
            if (!annotationsBySection.has(sectionId)) {
                annotationsBySection.set(sectionId, []);
            }
            annotationsBySection.get(sectionId).push(annotation);
        });

        // Process each section
        annotationsBySection.forEach((sectionAnnotations, sectionId) => {
            this.processSectionAnnotations(sectionId, sectionAnnotations);
        });
    }

    /**
     * Process annotations for a specific section
     * @param {string} sectionId - Section identifier
     * @param {Array} annotations - Annotations for this section
     */
    processSectionAnnotations(sectionId, annotations) {
        // Find the section content element
        const sectionElement = this.findSectionElement(sectionId);
        if (!sectionElement) {
            console.warn('Could not find section element for', sectionId);
            return;
        }

        // Sort annotations by position (if available) or by text length (longest first)
        annotations.sort((a, b) => {
            if (a.citation.start_position !== -1 && b.citation.start_position !== -1) {
                return a.citation.start_position - b.citation.start_position;
            }
            // Fallback: longer text snippets first to avoid nested highlighting issues
            return b.citation.text_snippet.length - a.citation.text_snippet.length;
        });

        // Apply highlights
        annotations.forEach((annotation, index) => {
            this.createHighlight(sectionElement, annotation, index);
        });
    }

    /**
     * Find the DOM element for a section
     * @param {string} sectionId - Section identifier
     * @returns {Element|null} - The section element or null if not found
     */
    findSectionElement(sectionId) {
        // Try different methods to find the section element
        let element = document.querySelector(`[data-section-id="${sectionId}"]`);

        if (!element) {
            // Look for elements with the section id
            element = document.getElementById(sectionId);
        }

        if (!element) {
            // Look in the results container for content
            const resultsContainer = document.getElementById('results');
            if (resultsContainer) {
                element = resultsContainer;
            }
        }

        return element;
    }

    /**
     * Create a highlight for an annotation
     * @param {Element} container - Container element to search in
     * @param {Object} annotation - Annotation object
     * @param {number} index - Annotation index for unique IDs
     */
    createHighlight(container, annotation, index) {
        const citation = annotation.citation;
        const textToFind = citation.text_snippet;

        if (!textToFind || textToFind.trim().length === 0) {
            console.warn('Empty text snippet for annotation', annotation.annotation_id);
            return;
        }

        // Find and highlight the text
        const highlighted = this.highlightTextInElement(container, textToFind, annotation, index);

        if (highlighted) {
            console.log('Successfully highlighted:', textToFind.substring(0, 50) + '...');
        } else {
            console.warn('Could not highlight text:', textToFind.substring(0, 50) + '...');
        }
    }

    /**
     * Highlight text within an element
     * @param {Element} element - Element to search in
     * @param {string} textToFind - Text to highlight
     * @param {Object} annotation - Annotation object
     * @param {number} index - Annotation index
     * @returns {boolean} - Whether highlighting was successful
     */
    highlightTextInElement(element, textToFind, annotation, index) {
        const walker = document.createTreeWalker(
            element,
            NodeFilter.SHOW_TEXT,
            null,
            false
        );

        const textNodes = [];
        let node;
        while (node = walker.nextNode()) {
            textNodes.push(node);
        }

        // Search for the text in text nodes
        for (let textNode of textNodes) {
            const nodeText = textNode.textContent;
            const searchText = textToFind.toLowerCase().trim();
            const nodeTextLower = nodeText.toLowerCase();

            let startIndex = nodeTextLower.indexOf(searchText);

            // Try fuzzy matching if exact match fails
            if (startIndex === -1 && searchText.length > 20) {
                // Try matching first and last 10 characters
                const startPart = searchText.substring(0, 10);
                const endPart = searchText.substring(searchText.length - 10);

                const startMatch = nodeTextLower.indexOf(startPart);
                if (startMatch !== -1) {
                    const endMatch = nodeTextLower.indexOf(endPart, startMatch + 10);
                    if (endMatch !== -1) {
                        startIndex = startMatch;
                        // Update textToFind to the actual text found
                        textToFind = nodeText.substring(startMatch, endMatch + 10);
                    }
                }
            }

            if (startIndex !== -1) {
                // Create the highlight
                const highlightId = `annotation-${annotation.annotation_id}-${index}`;
                const highlightElement = this.createHighlightElement(annotation, highlightId);

                // Split the text node and insert the highlight
                const beforeText = nodeText.substring(0, startIndex);
                const highlightText = nodeText.substring(startIndex, startIndex + textToFind.length);
                const afterText = nodeText.substring(startIndex + textToFind.length);

                const parent = textNode.parentNode;

                if (beforeText) {
                    parent.insertBefore(document.createTextNode(beforeText), textNode);
                }

                highlightElement.textContent = highlightText;
                parent.insertBefore(highlightElement, textNode);

                if (afterText) {
                    parent.insertBefore(document.createTextNode(afterText), textNode);
                }

                parent.removeChild(textNode);

                // Store reference to the highlight
                this.highlightedElements.set(highlightId, {
                    element: highlightElement,
                    annotation: annotation
                });

                return true;
            }
        }

        return false;
    }

    /**
     * Create a highlight element for an annotation
     * @param {Object} annotation - Annotation object
     * @param {string} highlightId - Unique ID for the highlight
     * @returns {Element} - The highlight element
     */
    createHighlightElement(annotation, highlightId) {
        const span = document.createElement('span');
        span.id = highlightId;
        span.className = `annotation-highlight annotation-type-${annotation.annotation_type}`;

        // Set background color with opacity based on severity
        const color = this.colors[annotation.annotation_type] || this.colors.reference;
        const opacity = this.severityOpacity[annotation.severity] || 0.3;
        span.style.backgroundColor = color + Math.floor(opacity * 255).toString(16).padStart(2, '0');

        // Add click handler
        span.addEventListener('click', (e) => {
            e.stopPropagation();
            this.showAnnotationPopup(highlightId, e.pageX, e.pageY);
        });

        // Add hover effect
        span.addEventListener('mouseenter', () => {
            span.style.boxShadow = `0 0 0 2px ${color}`;
        });

        span.addEventListener('mouseleave', () => {
            span.style.boxShadow = '';
        });

        return span;
    }

    /**
     * Show annotation popup
     * @param {string} highlightId - ID of the highlight element
     * @param {number} x - X coordinate for popup position
     * @param {number} y - Y coordinate for popup position
     */
    showAnnotationPopup(highlightId, x, y) {
        // Hide any existing popups
        this.hideAllPopups();

        const highlightData = this.highlightedElements.get(highlightId);
        if (!highlightData) return;

        const annotation = highlightData.annotation;
        const popup = this.createAnnotationPopup(annotation, highlightId);

        // Position the popup
        document.body.appendChild(popup);

        // Calculate position to keep popup on screen
        const rect = popup.getBoundingClientRect();
        let popupX = x - rect.width / 2;
        let popupY = y - rect.height - 10;

        // Adjust if popup goes off screen
        if (popupX < 10) popupX = 10;
        if (popupX + rect.width > window.innerWidth - 10) {
            popupX = window.innerWidth - rect.width - 10;
        }
        if (popupY < 10) popupY = y + 10;

        popup.style.left = popupX + 'px';
        popup.style.top = popupY + 'px';
        popup.classList.add('show');

        this.annotationPopups.set(highlightId, popup);

        // Auto-hide after 10 seconds
        setTimeout(() => {
            this.hideAnnotationPopup(highlightId);
        }, 10000);
    }

    /**
     * Create annotation popup element
     * @param {Object} annotation - Annotation object
     * @param {string} highlightId - ID of the highlight
     * @returns {Element} - Popup element
     */
    createAnnotationPopup(annotation, highlightId) {
        const popup = document.createElement('div');
        popup.className = 'annotation-popup';

        const color = this.colors[annotation.annotation_type] || this.colors.reference;

        popup.innerHTML = `
            <div class="annotation-popup-header">
                <h4 class="annotation-popup-title">${annotation.title}</h4>
                <button class="annotation-popup-close" onclick="annotationSystem.hideAnnotationPopup('${highlightId}')">&times;</button>
            </div>
            <div class="annotation-popup-type type-${annotation.annotation_type}">${annotation.annotation_type}</div>
            <div class="annotation-popup-message">${annotation.message}</div>
            ${annotation.suggested_action ? `
                <div class="annotation-popup-actions">
                    <div class="annotation-popup-action">
                        <strong>Suggested Action:</strong> ${annotation.suggested_action}
                    </div>
                </div>
            ` : ''}
            ${annotation.suggested_replacement ? `
                <div class="annotation-popup-actions">
                    <div class="annotation-popup-action">
                        <strong>Suggested Replacement:</strong>
                        <div class="annotation-replacement">${annotation.suggested_replacement}</div>
                    </div>
                </div>
            ` : ''}
        `;

        return popup;
    }

    /**
     * Hide annotation popup
     * @param {string} highlightId - ID of the highlight
     */
    hideAnnotationPopup(highlightId) {
        const popup = this.annotationPopups.get(highlightId);
        if (popup) {
            popup.remove();
            this.annotationPopups.delete(highlightId);
        }
    }

    /**
     * Hide all annotation popups
     */
    hideAllPopups() {
        this.annotationPopups.forEach((popup, highlightId) => {
            popup.remove();
        });
        this.annotationPopups.clear();
    }

    /**
     * Create annotation panel showing all annotations
     */
    createAnnotationPanel() {
        const existingPanel = document.getElementById('annotation-panel');
        if (existingPanel) {
            existingPanel.remove();
        }

        const panel = document.createElement('div');
        panel.id = 'annotation-panel';
        panel.className = 'annotation-panel';

        panel.innerHTML = `
            <div class="annotation-panel-header">
                <h3 class="annotation-panel-title">Annotations</h3>
                <span class="annotation-panel-count">${this.annotations.length}</span>
            </div>
            <div class="annotation-panel-body">
                ${this.annotations.map((annotation, index) => `
                    <div class="annotation-panel-item" data-annotation-id="${annotation.annotation_id}" onclick="annotationSystem.scrollToAnnotation('${annotation.annotation_id}')">
                        <div class="annotation-panel-item-type type-${annotation.annotation_type}">${annotation.annotation_type}</div>
                        <div class="annotation-panel-item-text">"${annotation.citation.text_snippet.substring(0, 60)}${annotation.citation.text_snippet.length > 60 ? '...' : ''}"</div>
                        <div class="annotation-panel-item-message">${annotation.message}</div>
                    </div>
                `).join('')}
            </div>
        `;

        document.body.appendChild(panel);

        // Show panel if there are annotations
        if (this.annotations.length > 0) {
            panel.classList.add('show');
        }

        // Create toggle button and summary
        this.createAnnotationControls();
    }

    /**
     * Create annotation controls (toggle button and summary)
     */
    createAnnotationControls() {
        // Create toggle button
        const existingButton = document.getElementById('annotation-toggle-btn');
        if (existingButton) {
            existingButton.remove();
        }

        const toggleButton = document.createElement('button');
        toggleButton.id = 'annotation-toggle-btn';
        toggleButton.className = 'annotation-toggle-btn';
        toggleButton.innerHTML = `
            <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor">
                <path d="M2 3a1 1 0 0 1 1-1h10a1 1 0 0 1 1 1v10a1 1 0 0 1-1 1H3a1 1 0 0 1-1-1V3zm1 0v10h10V3H3z"/>
                <path d="M5 5h6v1H5V5zm0 2h6v1H5V7zm0 2h6v1H5V9z"/>
            </svg>
            Annotations
            <span class="badge">${this.annotations.length}</span>
        `;

        toggleButton.addEventListener('click', () => {
            this.toggleAnnotationPanel();
        });

        document.body.appendChild(toggleButton);

        // Create annotation summary
        this.createAnnotationSummary();
    }

    /**
     * Create annotation summary bar
     */
    createAnnotationSummary() {
        const existingSummary = document.getElementById('annotation-summary');
        if (existingSummary) {
            existingSummary.remove();
        }

        if (this.annotations.length === 0) {
            return;
        }

        const stats = this.getStatistics();
        const summary = document.createElement('div');
        summary.id = 'annotation-summary';
        summary.className = 'annotation-summary show';

        const typeStats = Object.entries(stats.byType).map(([type, count]) => {
            const color = this.colors[type] || this.colors.reference;
            return `
                <div class="annotation-stat">
                    <div class="annotation-stat-color" style="background-color: ${color}"></div>
                    <span class="annotation-stat-label">${type}</span>
                    <span class="annotation-stat-count">(${count})</span>
                </div>
            `;
        }).join('');

        summary.innerHTML = `
            <div class="annotation-summary-title">
                📝 ${this.annotations.length} Citation${this.annotations.length !== 1 ? 's' : ''} & Annotation${this.annotations.length !== 1 ? 's' : ''} Found
            </div>
            <div class="annotation-summary-stats">
                ${typeStats}
            </div>
        `;

        // Insert after the page header or at the beginning of results
        const resultsContainer = document.getElementById('results');
        if (resultsContainer) {
            resultsContainer.insertBefore(summary, resultsContainer.firstChild);
        } else {
            // Fallback: insert at beginning of body
            document.body.insertBefore(summary, document.body.firstChild);
        }
    }

    /**
     * Scroll to and highlight a specific annotation
     * @param {string} annotationId - ID of the annotation
     */
    scrollToAnnotation(annotationId) {
        // Find the highlight element
        const highlightData = Array.from(this.highlightedElements.values())
            .find(data => data.annotation.annotation_id === annotationId);

        if (highlightData) {
            // Scroll to the element
            highlightData.element.scrollIntoView({
                behavior: 'smooth',
                block: 'center'
            });

            // Temporarily highlight the annotation
            const originalBackground = highlightData.element.style.backgroundColor;
            highlightData.element.style.backgroundColor = '#ffeb3b';
            highlightData.element.style.boxShadow = '0 0 0 3px #ffeb3b';

            setTimeout(() => {
                highlightData.element.style.backgroundColor = originalBackground;
                highlightData.element.style.boxShadow = '';
            }, 2000);

            // Update panel selection
            document.querySelectorAll('.annotation-panel-item').forEach(item => {
                item.classList.remove('active');
            });

            const panelItem = document.querySelector(`[data-annotation-id="${annotationId}"]`);
            if (panelItem) {
                panelItem.classList.add('active');
            }
        }
    }

    /**
     * Toggle annotation panel visibility
     */
    toggleAnnotationPanel() {
        const panel = document.getElementById('annotation-panel');
        if (panel) {
            panel.classList.toggle('show');
        }
    }

    /**
     * Get annotation statistics
     * @returns {Object} - Statistics about annotations
     */
    getStatistics() {
        const stats = {
            total: this.annotations.length,
            byType: {},
            bySeverity: {}
        };

        this.annotations.forEach(annotation => {
            // Count by type
            const type = annotation.annotation_type;
            stats.byType[type] = (stats.byType[type] || 0) + 1;

            // Count by severity
            const severity = annotation.severity;
            stats.bySeverity[severity] = (stats.bySeverity[severity] || 0) + 1;
        });

        return stats;
    }
}

// Global instance
let annotationSystem = null;

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', function() {
    console.log('DOM loaded, waiting for annotations data...');
});

// Function to initialize annotations (called from HTML template)
function initializeAnnotations(annotationsData, obsIdx = null, taskIdx = null, docIndex = null) {
    console.log('Initializing annotations with data:', annotationsData);

    // Check if we're in PDF mode (obsIdx and taskIdx provided)
    const isPDFMode = obsIdx !== null && taskIdx !== null;

    if (isPDFMode) {
        // PDF mode - use the PDF annotation system
        const docInfo = docIndex !== null ? ` document ${docIndex}` : '';
        console.log('Initializing PDF annotations for', obsIdx, taskIdx, docInfo);

        if (window.pdfAnnotationSystem) {
            window.pdfAnnotationSystem.setAnnotations(obsIdx, taskIdx, annotationsData, docIndex);
        }

        // Still create the annotation panel for navigation
        if (!annotationSystem) {
            annotationSystem = new AnnotationSystem();
        }
        annotationSystem.annotations = annotationsData || [];
        annotationSystem.createAnnotationPanel();
        annotationSystem.createAnnotationControls();

    } else {
        // Text mode - use the traditional annotation system
        console.log('Initializing text-based annotations');

        if (!annotationSystem) {
            annotationSystem = new AnnotationSystem();
        }

        annotationSystem.initialize(annotationsData);
    }

    // Add keyboard shortcut to toggle panel (works for both modes)
    document.addEventListener('keydown', function(e) {
        if (e.key === 'a' && e.ctrlKey) {
            e.preventDefault();
            if (annotationSystem) {
                annotationSystem.toggleAnnotationPanel();
            }
        }
    });

    // Hide popups when clicking outside (works for both modes)
    document.addEventListener('click', function(e) {
        if (!e.target.closest('.annotation-popup') && !e.target.closest('.annotation-highlight') &&
            !e.target.closest('.pdf-annotation-popup') && !e.target.closest('.pdf-annotation-marker')) {
            if (annotationSystem) {
                annotationSystem.hideAllPopups();
            }
            // Also hide PDF popups
            document.querySelectorAll('.pdf-annotation-popup').forEach(popup => popup.remove());
        }
    });
}