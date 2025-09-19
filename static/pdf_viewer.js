/**
 * Advanced PDF Viewer with Precise Text Highlighting
 *
 * This module provides PDF viewing capabilities using PDF.js with precise
 * text highlighting using PyMuPDF backend for accurate bounding boxes.
 */

class PDFViewer {
    constructor(containerId, obsIdx, taskIdx, docIndex = null) {
        this.containerId = containerId;
        this.obsIdx = obsIdx;
        this.taskIdx = taskIdx;
        this.docIndex = docIndex;
        this.pdf = null;
        this.currentPage = 1;
        this.totalPages = 0;
        this.scale = 1.2;
        this.canvas = null;
        this.context = null;
        this.highlightLayer = null;
        this.pdfTextData = null; // PyMuPDF text data with precise bounding boxes

        // Create element IDs based on whether this is a multi-document viewer
        const canvasId = docIndex !== null ? `pdf-canvas-${obsIdx}-${taskIdx}-${docIndex}` : `pdf-canvas-${obsIdx}-${taskIdx}`;
        const pageInfoId = docIndex !== null ? `page-info-${obsIdx}-${taskIdx}-${docIndex}` : `page-info-${obsIdx}-${taskIdx}`;

        // Get DOM elements with the correct IDs
        this.canvas = document.getElementById(canvasId);
        this.pageInfo = document.getElementById(pageInfoId);

        if (this.canvas) {
            this.context = this.canvas.getContext('2d');
            this.setupHighlightLayer();
        } else {
            console.error('Canvas not found with ID:', canvasId);
        }
    }

    setupHighlightLayer() {
        // Create highlight layer container
        const wrapper = this.canvas.parentElement;

        this.highlightLayer = document.createElement('div');
        this.highlightLayer.className = 'pdf-highlight-layer';
        this.highlightLayer.style.cssText = `
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            pointer-events: none;
            z-index: 10;
        `;

        wrapper.appendChild(this.highlightLayer);
    }

    async loadPDF(pdfUrl) {
        try {
            console.log('Loading PDF:', pdfUrl);

            // Set PDF.js worker
            pdfjsLib.GlobalWorkerOptions.workerSrc = 'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js';

            // Load the PDF
            const loadingTask = pdfjsLib.getDocument(pdfUrl);
            this.pdf = await loadingTask.promise;
            this.totalPages = this.pdf.numPages;

            console.log('PDF loaded successfully. Pages:', this.totalPages);

            // Load precise text data from PyMuPDF backend
            const filename = pdfUrl.split('/').pop();
            await this.loadTextData(filename);

            // Render the first page
            await this.renderPage(1);

            // Update page info
            this.updatePageInfo();

            return true;
        } catch (error) {
            console.error('Error loading PDF:', error);
            this.showError('Failed to load PDF: ' + error.message);
            return false;
        }
    }

    async loadTextData(filename) {
        try {
            console.log('Loading text data for:', filename);
            const response = await fetch(`/get_pdf_text_data/${filename}`);
            const data = await response.json();

            if (data.success) {
                this.pdfTextData = data.pages;
                console.log('Text data loaded:', this.pdfTextData.length, 'pages');
            } else {
                console.error('Failed to load text data:', data.error);
            }
        } catch (error) {
            console.error('Error loading text data:', error);
        }
    }

    async renderPage(pageNumber) {
        if (!this.pdf || pageNumber < 1 || pageNumber > this.totalPages) {
            return;
        }

        try {
            const page = await this.pdf.getPage(pageNumber);
            const viewport = page.getViewport({ scale: this.scale });

            // Set canvas dimensions
            this.canvas.width = viewport.width;
            this.canvas.height = viewport.height;
            this.canvas.style.width = '100%';
            this.canvas.style.height = 'auto';

            // Update highlight layer size
            this.highlightLayer.style.width = this.canvas.style.width;
            this.highlightLayer.style.height = this.canvas.style.height;

            // Render the page
            const renderContext = {
                canvasContext: this.context,
                viewport: viewport
            };

            await page.render(renderContext).promise;

            this.currentPage = pageNumber;
            this.updatePageInfo();

            console.log('Rendered page:', pageNumber);

            // Clear existing highlights and re-render annotations
            this.clearHighlights();

            // Trigger annotation update for this page
            if (window.pdfAnnotationSystem) {
                window.pdfAnnotationSystem.updateAnnotationsForPage(this.obsIdx, this.taskIdx, pageNumber, this.docIndex);
            }

            // Set up a small delay to reposition highlights after rendering
            setTimeout(() => {
                this.repositionHighlights();
            }, 100);

        } catch (error) {
            console.error('Error rendering page:', error);
            this.showError('Failed to render page: ' + error.message);
        }
    }

    textExistsOnPage(textToFind, pageNumber) {
        if (!this.pdfTextData || !this.pdfTextData[pageNumber - 1]) {
            return false;
        }

        const pageData = this.pdfTextData[pageNumber - 1];
        const fullPageText = pageData.full_text;

        // Check if text exists in the full page text
        const cleanSearchText = textToFind.toLowerCase().trim();
        const fullTextLower = fullPageText.toLowerCase();

        let startIndex = fullTextLower.indexOf(cleanSearchText);

        if (startIndex === -1) {
            // Try fuzzy matching with normalized whitespace
            const normalizedText = fullPageText.replace(/\s+/g, ' ').toLowerCase();
            const normalizedSearch = cleanSearchText.replace(/\s+/g, ' ');
            startIndex = normalizedText.indexOf(normalizedSearch);
        }

        return startIndex !== -1;
    }

    highlightText(textToFind, annotationType, annotation) {
        const pageNumber = this.currentPage;

        if (!this.pdfTextData || !this.pdfTextData[pageNumber - 1]) {
            console.warn('No text data available for page', pageNumber);
            return false;
        }

        const pageData = this.pdfTextData[pageNumber - 1];
        const textItems = pageData.text_items;
        const fullPageText = pageData.full_text;

        console.log('Highlighting text:', textToFind);
        console.log('Page text items:', textItems.length);

        // Find the text in the full page text
        const cleanSearchText = textToFind.toLowerCase().trim();
        const fullTextLower = fullPageText.toLowerCase();

        let startIndex = fullTextLower.indexOf(cleanSearchText);

        if (startIndex === -1) {
            // Try fuzzy matching with normalized whitespace
            const normalizedText = fullPageText.replace(/\s+/g, ' ').toLowerCase();
            const normalizedSearch = cleanSearchText.replace(/\s+/g, ' ');
            startIndex = normalizedText.indexOf(normalizedSearch);

            if (startIndex === -1) {
                console.warn('Could not find text to highlight:', textToFind);
                return false;
            }
        }

        const endIndex = startIndex + textToFind.length;

        // Find which text items contain our target text
        let currentPos = 0;
        const itemsToHighlight = [];

        for (let i = 0; i < textItems.length; i++) {
            const item = textItems[i];
            const itemText = item.text;
            const itemStart = currentPos;
            const itemEnd = currentPos + itemText.length;

            // Check if this item overlaps with our target text
            if (itemEnd > startIndex && itemStart < endIndex) {
                const highlightStart = Math.max(0, startIndex - itemStart);
                const highlightEnd = Math.min(itemText.length, endIndex - itemStart);

                if (highlightStart < highlightEnd) {
                    itemsToHighlight.push({
                        item: item,
                        highlightStart: highlightStart,
                        highlightEnd: highlightEnd,
                        text: itemText.substring(highlightStart, highlightEnd)
                    });
                }
            }

            currentPos = itemEnd + 1; // +1 for space between items
        }

        console.log('Items to highlight:', itemsToHighlight.length);

        // Create highlight elements using precise bounding boxes
        itemsToHighlight.forEach((highlightInfo, idx) => {
            this.createPreciseHighlight(highlightInfo, annotationType, annotation, idx);
        });

        return itemsToHighlight.length > 0;
    }

    createPreciseHighlight(highlightInfo, annotationType, annotation, index) {
        const item = highlightInfo.item;
        const bbox = item.bbox;

        // Calculate scale factor between PyMuPDF coordinates and canvas
        const pageData = this.pdfTextData[this.currentPage - 1];

        // Get scale from canvas dimensions or parent container
        let scaleX, scaleY;

        // First try to use the visible canvas dimensions
        if (this.canvas.offsetWidth > 0 && this.canvas.offsetHeight > 0) {
            scaleX = this.canvas.offsetWidth / pageData.width;
            scaleY = this.canvas.offsetHeight / pageData.height;
        } else {
            // Canvas is not visible (e.g., in collapsed accordion)
            // Use the container width or a reasonable default
            const containerWidth = this.canvas.parentElement?.offsetWidth || 800;

            // Calculate based on aspect ratio - assume canvas width matches container
            scaleX = containerWidth / pageData.width;
            scaleY = scaleX; // Maintain aspect ratio

            console.log('Canvas hidden, using container-based scale:', { scaleX, scaleY, containerWidth, pageWidth: pageData.width, pageHeight: pageData.height });
        }

        // Convert PyMuPDF coordinates to canvas coordinates
        const x = bbox.x0 * scaleX;
        const y = bbox.y0 * scaleY;
        const width = (bbox.x1 - bbox.x0) * scaleX;
        const height = (bbox.y1 - bbox.y0) * scaleY;

        // Store scale factors for later repositioning
        const highlightData = {
            originalBbox: bbox,
            scaleX: scaleX,
            scaleY: scaleY,
            pageData: pageData
        };

        const highlight = document.createElement('div');
        highlight.className = `pdf-text-highlight annotation-type-${annotationType}`;

        // Color mapping
        const colors = {
            'support': '#28a745',
            'concern': '#ffc107',
            'correction': '#dc3545',
            'clarification': '#17a2b8',
            'reference': '#007bff',
            'missing': '#6f42c1'
        };

        const color = colors[annotationType] || colors.reference;

        highlight.style.cssText = `
            position: absolute;
            left: ${x}px;
            top: ${y}px;
            width: ${width}px;
            height: ${height}px;
            background-color: ${color}40;
            border: 1px solid ${color};
            pointer-events: all;
            cursor: pointer;
            z-index: 11;
            border-radius: 2px;
        `;

        // Add click handler with proper event binding
        highlight.addEventListener('click', (e) => {
            e.stopPropagation();
            this.showAnnotationPopup(annotation, e.clientX, e.clientY);
        });

        // Add hover effect
        highlight.addEventListener('mouseenter', () => {
            highlight.style.backgroundColor = `${color}60`;
        });

        highlight.addEventListener('mouseleave', () => {
            highlight.style.backgroundColor = `${color}40`;
        });

        // Store highlight data for repositioning
        highlight.dataset.highlightData = JSON.stringify(highlightData);
        highlight.dataset.annotationId = annotation.annotation_id;

        this.highlightLayer.appendChild(highlight);

        console.log('Created highlight:', {
            x: x,
            y: y,
            width: width,
            height: height,
            text: highlightInfo.text,
            scaleX: scaleX,
            scaleY: scaleY
        });
    }

    showAnnotationPopup(annotation, x, y) {
        // Remove any existing popups
        document.querySelectorAll('.pdf-annotation-popup').forEach(popup => popup.remove());

        const popup = document.createElement('div');
        popup.className = 'pdf-annotation-popup';
        popup.style.cssText = `
            position: fixed;
            left: ${x - 175}px;
            top: ${y - 10}px;
            width: 350px;
            background: white;
            border: 1px solid #ddd;
            border-radius: 8px;
            padding: 12px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
            z-index: 1000;
            font-size: 14px;
            line-height: 1.4;
        `;

        const colors = {
            'support': '#28a745',
            'concern': '#ffc107',
            'correction': '#dc3545',
            'clarification': '#17a2b8',
            'reference': '#007bff',
            'missing': '#6f42c1'
        };

        popup.innerHTML = `
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; padding-bottom: 8px; border-bottom: 1px solid #eee;">
                <h6 style="margin: 0; font-weight: bold;">${annotation.title}</h6>
                <button onclick="this.parentElement.parentElement.remove()" style="background: none; border: none; font-size: 18px; cursor: pointer;">&times;</button>
            </div>
            <div style="display: inline-block; padding: 2px 6px; border-radius: 12px; font-size: 11px; font-weight: bold; text-transform: uppercase; color: white; background-color: ${colors[annotation.annotation_type] || colors.reference}; margin-bottom: 8px;">
                ${annotation.annotation_type}
            </div>
            <div style="margin: 8px 0; color: #333;">
                ${annotation.message}
            </div>
            ${annotation.citation.text_snippet ? `
                <div style="background: #f8f9fa; border: 1px solid #dee2e6; border-radius: 4px; padding: 8px; margin: 8px 0; font-style: italic; font-size: 13px;">
                    "${annotation.citation.text_snippet}"
                </div>
            ` : ''}
            ${annotation.suggested_action ? `
                <div style="margin-top: 12px; padding-top: 8px; border-top: 1px solid #eee; font-size: 12px; color: #666;">
                    <strong>Suggested Action:</strong> ${annotation.suggested_action}
                </div>
            ` : ''}
            ${annotation.suggested_replacement ? `
                <div style="margin-top: 8px; font-size: 12px; color: #666;">
                    <strong>Suggested Replacement:</strong>
                    <div style="background: #f8f9fa; border: 1px solid #dee2e6; border-radius: 4px; padding: 8px; margin-top: 4px; font-family: monospace; font-size: 13px;">
                        ${annotation.suggested_replacement}
                    </div>
                </div>
            ` : ''}
        `;

        document.body.appendChild(popup);

        // Auto-hide after 10 seconds
        setTimeout(() => {
            if (popup.parentElement) {
                popup.remove();
            }
        }, 10000);

        // Position popup to stay on screen
        const rect = popup.getBoundingClientRect();
        if (rect.right > window.innerWidth) {
            popup.style.left = (x - rect.width - 10) + 'px';
        }
        if (rect.bottom > window.innerHeight) {
            popup.style.top = (y - rect.height - 10) + 'px';
        }

        console.log('Showing annotation popup:', annotation.title);
    }

    async previousPage() {
        if (this.currentPage > 1) {
            await this.renderPage(this.currentPage - 1);
        }
    }

    async nextPage() {
        if (this.currentPage < this.totalPages) {
            await this.renderPage(this.currentPage + 1);
        }
    }

    updatePageInfo() {
        if (this.pageInfo) {
            this.pageInfo.textContent = `Page ${this.currentPage} of ${this.totalPages}`;
        }
    }

    clearHighlights() {
        if (this.highlightLayer) {
            this.highlightLayer.innerHTML = '';
        }
    }

    /**
     * Reposition all highlights when canvas becomes visible or changes size
     */
    repositionHighlights() {
        if (!this.highlightLayer || !this.pdfTextData) {
            return;
        }

        const pageData = this.pdfTextData[this.currentPage - 1];
        if (!pageData) {
            return;
        }

        // Calculate new scale factors
        let newScaleX, newScaleY;

        if (this.canvas.offsetWidth > 0 && this.canvas.offsetHeight > 0) {
            newScaleX = this.canvas.offsetWidth / pageData.width;
            newScaleY = this.canvas.offsetHeight / pageData.height;
        } else {
            const containerWidth = this.canvas.parentElement?.offsetWidth || 800;
            newScaleX = containerWidth / pageData.width;
            newScaleY = newScaleX;
        }

        // Update all existing highlights
        const highlights = this.highlightLayer.querySelectorAll('.pdf-text-highlight');
        highlights.forEach(highlight => {
            const storedData = highlight.dataset.highlightData;
            if (storedData) {
                try {
                    const data = JSON.parse(storedData);
                    const bbox = data.originalBbox;

                    // Recalculate position with new scale
                    const x = bbox.x0 * newScaleX;
                    const y = bbox.y0 * newScaleY;
                    const width = (bbox.x1 - bbox.x0) * newScaleX;
                    const height = (bbox.y1 - bbox.y0) * newScaleY;

                    // Update highlight position
                    highlight.style.left = `${x}px`;
                    highlight.style.top = `${y}px`;
                    highlight.style.width = `${width}px`;
                    highlight.style.height = `${height}px`;

                    // Update stored data
                    data.scaleX = newScaleX;
                    data.scaleY = newScaleY;
                    highlight.dataset.highlightData = JSON.stringify(data);

                } catch (e) {
                    console.error('Error repositioning highlight:', e);
                }
            }
        });

        console.log('Repositioned', highlights.length, 'highlights with scale:', { newScaleX, newScaleY });
    }

    showError(message) {
        if (this.canvas) {
            this.context.fillStyle = '#f8d7da';
            this.context.fillRect(0, 0, this.canvas.width, this.canvas.height);
            this.context.fillStyle = '#721c24';
            this.context.font = '16px Arial';
            this.context.textAlign = 'center';
            this.context.fillText(message, this.canvas.width / 2, this.canvas.height / 2);
        }
    }
}

// Global PDF viewer instances
window.pdfViewers = new Map();

// Global PDF annotation system
window.pdfAnnotationSystem = {
    annotations: new Map(),

    setAnnotations(obsIdx, taskIdx, annotations, docIndex = null) {
        const key = docIndex !== null ? `${obsIdx}-${taskIdx}-${docIndex}` : `${obsIdx}-${taskIdx}`;
        this.annotations.set(key, annotations || []);
        console.log('Set annotations for', key, ':', annotations?.length || 0);

        // Update annotations for current page
        this.updateAnnotationsForPage(obsIdx, taskIdx, 1, docIndex);
    },

    updateAnnotationsForPage(obsIdx, taskIdx, pageNumber, docIndex = null) {
        const key = docIndex !== null ? `${obsIdx}-${taskIdx}-${docIndex}` : `${obsIdx}-${taskIdx}`;
        const annotations = this.annotations.get(key) || [];
        const viewer = window.pdfViewers.get(key);

        if (!viewer) {
            console.log('No viewer found for', key);
            return;
        }

        // Clear existing highlights
        viewer.clearHighlights();

        console.log('Updating annotations for page', pageNumber, '- found', annotations.length, 'annotations');

        // Add text highlights for this page
        annotations.forEach((annotation, index) => {
            const citation = annotation.citation || {};
            const textSnippet = citation.text_snippet;

            if (!textSnippet || !textSnippet.trim()) {
                return; // Skip annotations without text snippets
            }

            // Use page number if available, otherwise try to find the text on this page
            const annotationPage = citation.page_number;

            if (annotationPage) {
                // If we have a specific page number, only show on that page
                if (annotationPage === pageNumber) {
                    console.log('Highlighting annotation:', annotation.annotation_type, textSnippet.substring(0, 50) + '...');
                    const success = viewer.highlightText(textSnippet, annotation.annotation_type, annotation);
                    if (!success) {
                        console.warn('Failed to highlight text:', textSnippet.substring(0, 50) + '...');
                    }
                }
            } else {
                // If no page number, first check if text exists on this page before trying to highlight
                if (viewer.textExistsOnPage(textSnippet, pageNumber)) {
                    console.log('Highlighting annotation:', annotation.annotation_type, textSnippet.substring(0, 50) + '...');
                    const success = viewer.highlightText(textSnippet, annotation.annotation_type, annotation);
                    if (!success) {
                        console.warn('Failed to highlight text:', textSnippet.substring(0, 50) + '...');
                    }
                }
            }
        });
    }
};

// Global functions for page navigation (called from HTML buttons)
function previousPage(obsIdx, taskIdx, docIndex = null) {
    const key = docIndex !== null ? `${obsIdx}-${taskIdx}-${docIndex}` : `${obsIdx}-${taskIdx}`;
    const viewer = window.pdfViewers.get(key);
    if (viewer) {
        viewer.previousPage();
    }
}

function nextPage(obsIdx, taskIdx, docIndex = null) {
    const key = docIndex !== null ? `${obsIdx}-${taskIdx}-${docIndex}` : `${obsIdx}-${taskIdx}`;
    const viewer = window.pdfViewers.get(key);
    if (viewer) {
        viewer.nextPage();
    }
}

// Global function to initialize PDF viewer (called from HTML)
function initializePDFViewer(obsIdx, taskIdx, pdfFilename, docIndex = null) {
    console.log('Initializing PDF viewer for', obsIdx, taskIdx, 'with file:', pdfFilename, docIndex !== null ? `(document ${docIndex})` : '');

    // Create unique keys for single vs multi-document scenarios
    const key = docIndex !== null ? `${obsIdx}-${taskIdx}-${docIndex}` : `${obsIdx}-${taskIdx}`;
    const canvasId = docIndex !== null ? `pdf-canvas-${obsIdx}-${taskIdx}-${docIndex}` : `pdf-canvas-${obsIdx}-${taskIdx}`;
    const viewerId = docIndex !== null ? `pdf-viewer-${obsIdx}-${taskIdx}-${docIndex}` : `pdf-viewer-${obsIdx}-${taskIdx}`;

    const viewer = new PDFViewer(viewerId, obsIdx, taskIdx, docIndex);
    window.pdfViewers.set(key, viewer);

    // Update the viewer to use the correct canvas ID
    viewer.canvasId = canvasId;

    // Load the PDF
    const pdfUrl = `/get_pdf/${pdfFilename}`;
    viewer.loadPDF(pdfUrl).then(success => {
        if (success) {
            console.log('PDF viewer initialized successfully');
            // Reposition highlights after PDF is fully loaded
            setTimeout(() => {
                viewer.repositionHighlights();
            }, 500);
        } else {
            console.error('Failed to initialize PDF viewer');
        }
    });
}

// Hide popups when clicking outside
document.addEventListener('click', function(e) {
    if (!e.target.closest('.pdf-annotation-popup') && !e.target.closest('.pdf-text-highlight')) {
        document.querySelectorAll('.pdf-annotation-popup').forEach(popup => popup.remove());
    }
});