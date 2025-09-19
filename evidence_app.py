from flask import Flask, render_template, request, jsonify, send_file, session
import pandas as pd
import boto3
import json
import PyPDF2
import io
from datetime import datetime, timedelta
import xlsxwriter
from io import BytesIO
import re
from typing import Dict, List, Any, Optional, Tuple
import logging
from colorama import init, Fore, Back, Style
import time
import os
import uuid
from pydantic import BaseModel, Field
from dotenv import load_dotenv
from interaction_logger import interaction_logger
import base64
from PIL import Image, ImageDraw, ImageFont
import colorsys
import random
import fitz  # PyMuPDF

# Load environment variables
load_dotenv()

# Initialize colorama for colored console output
init(autoreset=True)

app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'your-secret-key-here')

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('evidence_engine.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Global variables
current_progress = {"message": "Ready", "step": 0, "total": 0}
app_data = {}

# Store multiple evidence documents per task
task_evidence_store = {}  # Format: {"obs_idx-task_idx": [{"file_info": {...}, "validation_result": {...}}, ...]}

# Import existing classes from app.py
from app import BedrockClient, AuditDocumentProcessor, log_step, log_request

# Import the Claude Code SDK evidence analysis agent
from claude_code_evidence_agent import AsyncEvidenceAgent

class EvidenceValidator:
    def __init__(self, bedrock_client: BedrockClient):
        self.bedrock_client = bedrock_client
        # Initialize the Claude Code SDK evidence agent
        self.claude_code_agent = AsyncEvidenceAgent()
        
    def validate_pdf_evidence(self, pdf_file, task_description: str, task_context: dict, user_description: str = "") -> dict:
        """Validate PDF evidence against task requirements"""
        try:
            # Extract text from PDF
            pdf_reader = PyPDF2.PdfReader(pdf_file)
            pdf_text = ""
            for page in pdf_reader.pages:
                pdf_text += page.extract_text() + "\n"
            
            # Create validation prompt
            prompt = f"""
Analyze this evidence document against the audit task requirements.

TASK DESCRIPTION: {task_description}

TASK CONTEXT:
- Department: {task_context.get('department', 'Not specified')}
- Implementation Type: {task_context.get('implementation_type', 'Not specified')}
- Division: {task_context.get('division', 'Not specified')}
- Requires Collaboration: {task_context.get('requires_collaboration', False)}

USER EXPLANATION: {user_description if user_description else 'No explanation provided'}

EVIDENCE DOCUMENT TEXT:
{pdf_text[:4000]}...

EVALUATION APPROACH:
- Use COMMON SENSE and GOOD FAITH interpretation when evaluating evidence
- Consider the SPIRIT and INTENT of the task, not just literal word matching
- Give REASONABLE BENEFIT OF THE DOUBT when evidence substantially addresses the task
- Accept evidence that demonstrates MEANINGFUL PROGRESS or COMPLETION even if not perfectly comprehensive
- Consider the USER'S EXPLANATION as valuable context for how the document relates to the task
- Avoid being overly strict or pedantic - focus on whether the evidence reasonably demonstrates task fulfillment

Evaluate if this evidence document adequately demonstrates completion of the audit task. Consider the user's explanation of how the document provides evidence. Return JSON:
{{
    "is_valid": true/false,
    "confidence": 0.0-1.0,
    "reasoning": "detailed explanation",
    "missing_elements": ["list of missing requirements"],
    "strengths": ["list of what the evidence demonstrates well"],
    "recommendation": "accept/reject/request_additional"
}}
"""
            
            response = self.bedrock_client.invoke_model_structured(prompt, None, max_tokens=2000)
            
            # Parse JSON response
            import re
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
            else:
                return {"error": "Could not parse validation response"}
                
        except Exception as e:
            return {"error": f"Error validating PDF: {str(e)}"}
    
    def validate_image_evidence(self, image_file, task_description: str, task_context: dict, user_description: str = "") -> dict:
        """Validate image evidence with bounding box annotations"""
        try:
            # Encode image to base64
            image_data = image_file.read()
            image_file.seek(0)  # Reset for potential reuse
            encoded_image = base64.b64encode(image_data).decode('utf-8')
            
            # Determine media type
            filename = image_file.filename.lower()
            if filename.endswith('.png'):
                media_type = 'image/png'
            elif filename.endswith('.gif'):
                media_type = 'image/gif'
            elif filename.endswith('.webp'):
                media_type = 'image/webp'
            else:
                media_type = 'image/jpeg'
            
            # Create validation prompt with image
            prompt = f"""
Analyze this evidence image against the audit task requirements.

TASK DESCRIPTION: {task_description}

TASK CONTEXT:
- Department: {task_context.get('department', 'Not specified')}
- Implementation Type: {task_context.get('implementation_type', 'Not specified')}
- Division: {task_context.get('division', 'Not specified')}
- Requires Collaboration: {task_context.get('requires_collaboration', False)}

USER EXPLANATION: {user_description if user_description else 'No explanation provided'}

EVALUATION APPROACH:
- Use COMMON SENSE and GOOD FAITH interpretation when evaluating evidence
- Consider the SPIRIT and INTENT of the task, not just literal word matching
- Give REASONABLE BENEFIT OF THE DOUBT when evidence substantially addresses the task
- Accept evidence that demonstrates MEANINGFUL PROGRESS or COMPLETION even if not perfectly comprehensive
- Consider the USER'S EXPLANATION as valuable context for how the image relates to the task
- Avoid being overly strict or pedantic - focus on whether the evidence reasonably demonstrates task fulfillment

First describe what you see in the image, then evaluate if this visual evidence adequately demonstrates completion of the audit task. Consider the user's explanation of how the image provides evidence.

If the evidence is VALID, draw bounding boxes around the specific parts that support task completion.
If the evidence is INVALID, draw bounding boxes around problematic areas or missing elements.

Return JSON with this exact format:
{{
    "is_valid": true/false,
    "confidence": 0.0-1.0,
    "reasoning": "detailed explanation of what you see and why it validates/invalidates the task",
    "missing_elements": ["list of missing requirements"],
    "strengths": ["list of what the evidence demonstrates well"],
    "recommendation": "accept/reject/request_additional",
    "bounding_boxes": [
        {{
            "element": "description of highlighted area",
            "bbox": [x1, y1, x2, y2],
            "confidence": 0.95,
            "type": "evidence/issue"
        }}
    ]
}}

Coordinates should be normalized (0-1). Be precise with bounding boxes.
"""
            
            # Call Claude with image
            content = [
                {"type": "text", "text": prompt},
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": media_type,
                        "data": encoded_image
                    }
                }
            ]
            
            response = self.bedrock_client.invoke_model_with_image(content, max_tokens=3000)
            
            # Parse JSON response
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
                
                # Generate annotated image if bounding boxes exist
                if result.get('bounding_boxes'):
                    annotated_image_path = self.create_annotated_image(image_data, result['bounding_boxes'], image_file.filename)
                    result['annotated_image'] = annotated_image_path
                
                return result
            else:
                return {"error": "Could not parse validation response"}
                
        except Exception as e:
            return {"error": f"Error validating image: {str(e)}"}
    
    def create_annotated_image(self, image_data: bytes, bboxes: List[dict], filename: str) -> str:
        """Create annotated image with bounding boxes"""
        try:
            # Create output directory
            output_dir = os.path.join(os.getcwd(), 'evidence_annotations')
            os.makedirs(output_dir, exist_ok=True)
            
            # Load image
            image = Image.open(io.BytesIO(image_data))
            draw = ImageDraw.Draw(image)
            width, height = image.size
            
            # Try to load font
            try:
                font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 24)
            except:
                font = ImageFont.load_default()
            
            for bbox in bboxes:
                # Get color based on type
                if bbox.get('type') == 'evidence':
                    color = '#00FF00'  # Green for valid evidence
                else:
                    color = '#FF0000'  # Red for issues
                
                x1, y1, x2, y2 = bbox['bbox']
                x1, x2 = x1 * width, x2 * width
                y1, y2 = y1 * height, y2 * height
                
                # Draw rectangle
                draw.rectangle([x1, y1, x2, y2], outline=color, width=3)
                
                # Draw label
                label = f"{bbox['element']} ({bbox['confidence']:.2f})"
                text_bbox = draw.textbbox((x1, y1-30), label, font=font)
                text_width = text_bbox[2] - text_bbox[0]
                text_height = text_bbox[3] - text_bbox[1]
                
                # Background for text
                draw.rectangle([x1, y1-30, x1+text_width, y1-30+text_height], fill=(0, 0, 0))
                draw.text((x1, y1-30), label, fill=color, font=font)
            
            # Save annotated image
            timestamp = int(time.time())
            output_filename = f"annotated_{timestamp}_{filename}"
            output_path = os.path.join(output_dir, output_filename)
            image.save(output_path)
            
            return output_filename
            
        except Exception as e:
            logger.error(f"Error creating annotated image: {str(e)}")
            return None

    def validate_evidence_with_agent(self, evidence_file, task_description: str, task_context: dict, user_description: str = "", use_agentic: bool = True) -> dict:
        """
        Enhanced evidence validation using agentic workflow for complex documents.

        This method provides intelligent document analysis that can:
        - Handle large, complex documents by breaking them into logical sections
        - Perform cross-section analysis for consistency
        - Provide detailed evidence quality assessment
        - Generate comprehensive recommendations

        Args:
            evidence_file: Uploaded file object
            task_description: Description of the audit task
            task_context: Context about the task (department, type, etc.)
            user_description: User's explanation of the evidence
            use_agentic: Whether to use the agentic workflow (default: True)

        Returns:
            Enhanced validation result with detailed analysis
        """
        try:
            # Read file content
            file_content = evidence_file.read()
            evidence_file.seek(0)  # Reset for potential reuse
            filename = evidence_file.filename

            if use_agentic:
                logger.info(f"Starting Claude Code SDK agent analysis for {filename}")

                # Store PDF file temporarily for viewer access
                pdf_filename = None
                if filename.lower().endswith('.pdf'):
                    import tempfile
                    import os

                    # Create temp directory if it doesn't exist
                    temp_dir = os.path.join(os.getcwd(), 'temp_pdfs')
                    os.makedirs(temp_dir, exist_ok=True)

                    # Generate unique filename
                    import uuid
                    unique_id = str(uuid.uuid4())[:8]
                    pdf_filename = f"{unique_id}_{filename}"
                    pdf_path = os.path.join(temp_dir, pdf_filename)

                    # Save the PDF file
                    with open(pdf_path, 'wb') as f:
                        f.write(file_content)

                # Use the Claude Code SDK agent for comprehensive analysis
                result = self.claude_code_agent.analyze_evidence_sync(
                    file_content,
                    filename,
                    task_description,
                    task_context,
                    user_description
                )

                # Add metadata about the analysis method
                result['analysis_method'] = 'claude_code_sdk_agent'
                result['agent_version'] = '2.0'

                # Add PDF file path for viewer
                if pdf_filename:
                    result['pdf_filename'] = pdf_filename

                # If agentic analysis was successful, enhance with bounding boxes for images
                if result.get('is_valid') and not result.get('error'):
                    filename_lower = filename.lower()
                    if filename_lower.endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp')):
                        # For images, still generate bounding boxes using the original method
                        bbox_result = self.validate_image_evidence(evidence_file, task_description, task_context, user_description)
                        if bbox_result.get('bounding_boxes'):
                            result['bounding_boxes'] = bbox_result['bounding_boxes']
                            if bbox_result.get('annotated_image'):
                                result['annotated_image'] = bbox_result['annotated_image']

                return result
            else:
                # Fallback to original validation methods
                filename_lower = filename.lower()
                if filename_lower.endswith('.pdf'):
                    return self.validate_pdf_evidence(evidence_file, task_description, task_context, user_description)
                elif filename_lower.endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp')):
                    return self.validate_image_evidence(evidence_file, task_description, task_context, user_description)
                else:
                    return {"error": "Unsupported file type for non-agentic analysis"}

        except Exception as e:
            logger.error(f"Error in agentic evidence validation: {str(e)}")
            return {"error": f"Enhanced validation failed: {str(e)}"}

    def validate_multiple_evidence_collective(self, documents_content: List[dict], task_description: str, task_context: dict, user_description: str = "") -> dict:
        """
        Perform collective analysis of multiple evidence documents for a single task.

        This method analyzes all documents together to:
        - Identify complementary evidence across documents
        - Check for consistency between documents
        - Provide comprehensive task completion assessment
        - Generate consolidated recommendations

        Args:
            documents_content: List of document info with content and individual results
            task_description: Description of the audit task
            task_context: Context about the task
            user_description: User's explanation of the evidence

        Returns:
            Collective validation result
        """
        try:
            logger.info(f"Starting collective analysis of {len(documents_content)} documents")

            # Prepare combined analysis using Claude Code SDK agent
            combined_content = ""
            document_summaries = []

            for i, doc in enumerate(documents_content):
                doc_summary = f"\nDOCUMENT {i+1}: {doc['filename']}\n{'='*50}\n"

                # Add individual analysis summary
                individual_result = doc.get('individual_result', {})
                if individual_result.get('reasoning'):
                    doc_summary += f"Individual Analysis: {individual_result['reasoning'][:200]}...\n"

                document_summaries.append(doc_summary)
                combined_content += doc_summary

            # Create collective analysis prompt
            collective_prompt = f"""
Perform a COLLECTIVE ANALYSIS of multiple evidence documents for a single audit task.

TASK DESCRIPTION: {task_description}

TASK CONTEXT:
- Department: {task_context.get('department', 'Not specified')}
- Implementation Type: {task_context.get('implementation_type', 'Not specified')}
- Division: {task_context.get('division', 'Not specified')}
- Requires Collaboration: {task_context.get('requires_collaboration', False)}

USER EXPLANATION: {user_description if user_description else 'No explanation provided'}

DOCUMENTS TO ANALYZE:
{combined_content}

COLLECTIVE ANALYSIS INSTRUCTIONS:

1. **CROSS-DOCUMENT ANALYSIS**: Examine how the documents work together
2. **COMPLEMENTARY EVIDENCE**: Identify how documents complement each other
3. **CONSISTENCY CHECK**: Look for consistency or conflicts between documents
4. **COMPREHENSIVE COVERAGE**: Assess if all task requirements are covered collectively
5. **QUALITY ASSESSMENT**: Evaluate the overall strength of the evidence package
6. **FINAL DETERMINATION**: Make a collective validation decision

EVALUATION APPROACH:
- Use COMMON SENSE and GOOD FAITH interpretation when evaluating evidence
- Consider the SPIRIT and INTENT of the task, not just literal word matching
- Give REASONABLE BENEFIT OF THE DOUBT when evidence substantially addresses the task
- Accept evidence that demonstrates MEANINGFUL PROGRESS or COMPLETION even if not perfectly comprehensive
- Consider the USER'S EXPLANATION as valuable context for how the documents relate to the task
- Avoid being overly strict or pedantic - focus on whether the evidence reasonably demonstrates task fulfillment

Provide your analysis in this JSON format:

```json
{{
    "is_valid": true/false,
    "confidence": 0.0-1.0,
    "evidence_quality": "high/medium/low",
    "reasoning": "detailed explanation of collective analysis and decision",
    "strengths": ["collective strengths across all documents"],
    "missing_elements": ["requirements still not addressed by any document"],
    "recommendations": ["actionable recommendations for the evidence package"],
    "recommendation": "accept/reject/request_additional",
    "document_synergy": "how documents work together",
    "cross_document_findings": [
        {{
            "finding": "description of finding across documents",
            "documents_involved": ["doc1.pdf", "doc2.pdf"],
            "significance": "high/medium/low"
        }}
    ],
    "collective_coverage": {{
        "requirements_covered": ["list of requirements covered by the document set"],
        "coverage_percentage": 0.0-1.0,
        "coverage_gaps": ["requirements not covered by any document"]
    }}
}}
```

Focus on the collective strength and coverage of all documents together.
"""

            # Use bedrock client for collective analysis
            collective_response = self.bedrock_client.invoke_model_structured(
                collective_prompt, None, max_tokens=3000
            )

            # Parse JSON response
            import re
            json_match = re.search(r'\{.*\}', collective_response, re.DOTALL)
            if json_match:
                collective_result = json.loads(json_match.group())

                # Add metadata
                collective_result['analysis_method'] = 'collective_multi_document'
                collective_result['document_count'] = len(documents_content)
                collective_result['processing_time'] = time.time()

                logger.info(f"Collective analysis completed for {len(documents_content)} documents")
                logger.info(f"Collective validity: {collective_result.get('is_valid')}, Confidence: {collective_result.get('confidence', 0):.2f}")

                return collective_result
            else:
                return {"error": "Could not parse collective analysis response"}

        except Exception as e:
            logger.error(f"Error in collective evidence validation: {str(e)}")
            return {"error": f"Collective validation failed: {str(e)}"}

# Initialize components
bedrock_client = BedrockClient()
processor = AuditDocumentProcessor(bedrock_client)
evidence_validator = EvidenceValidator(bedrock_client)

@app.route('/')
def index():
    # Create or get session ID
    if 'session_id' not in session:
        session['session_id'] = str(uuid.uuid4())
        session['session_start'] = time.time()
        
        # Log session start
        user_ip = request.environ.get('HTTP_X_FORWARDED_FOR', request.remote_addr)
        user_agent = request.headers.get('User-Agent', '')
        interaction_logger.log_session_start(session['session_id'], user_ip, user_agent)
    
    return render_template('evidence_index.html')

@app.route('/upload_audit', methods=['POST'])
def upload_audit():
    """Upload and process audit document to extract tasks"""
    global current_progress
    upload_start_time = time.time()
    session_id = session.get('session_id', 'unknown')
    
    log_request('/upload_audit', 'POST')
    current_progress["message"] = "Processing audit document..."
    
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    file_content = file.read()
    file_size = len(file_content)
    file.seek(0)
    
    if file and file.filename.lower().endswith('.pdf'):
        try:
            audit_text = processor.extract_pdf_text(file)
            
            if audit_text:
                current_progress["message"] = "Extracting observations and responses..."
                observations = processor.extract_observations_and_responses(audit_text)
                
                if observations:
                    current_progress["message"] = "Processing tasks..."
                    
                    # Use the same task extraction process as main app
                    observations_with_tasks = []
                    for observation in observations:
                        # Create tasks from management response using same approach as main app
                        if observation.get('management_response'):
                            # Use the existing task extraction prompt from main app
                            task_prompt = f"""
Analyze this management response and extract only the ACTIONABLE IMPLEMENTATION CONTENT for tracking.

Management Response:
{observation.get('management_response', '')}

SMART EXTRACTION RULES:
1. **IGNORE acknowledgment phrases** like "We concur", "We agree", "We acknowledge", "As recommended"
2. **IGNORE general statements** that don't describe specific actions or deliverables
3. **FOCUS ON ACTION VERBS** like "will implement", "is meeting", "creating", "developing", "establishing"
4. **EXTRACT actionable commitments**, not opinions or agreements
5. **GROUP related actions** together into logical implementation units

Create discrete implementation tasks by identifying:
- **Specific actions being taken** (meetings, policy creation, system updates, etc.)
- **Deliverables being produced** (policies, procedures, reports, etc.)
- **Process improvements being implemented**
- **System or procedural changes being made**

IMPORTANT GUIDELINES:
- SKIP non-actionable acknowledgment text ("We concur", "We agree", etc.)
- FOCUS on what is actually being DONE, not what is being acknowledged
- GROUP related actions together into coherent work packages
- Each task should represent a meaningful, trackable implementation effort
- Aim for 2-6 substantial actionable tasks
- Use VERBATIM text but only for the actionable portions

COVERAGE REQUIREMENT: Ensure all ACTIONABLE content is captured, but exclude acknowledgment statements and general agreements that don't describe specific work.

For each task segment, provide:
- task_text: The EXACT text segment(s) from the management response grouped together as one logical task
- inferred_department: Department likely responsible [Inferred from context]
- implementation_type: Type of action (e.g., "Process Improvement", "Policy Change", etc.)
- requires_collaboration: true/false based on whether multiple parties are mentioned
- inferred_division: Best match based on context
- inferred_vp: Best match based on context
- inferred_cabinet_member: Best match based on context
- contact: ""
- due_date: ""

COVERAGE VERIFICATION: Before finalizing your tasks, review the management response to ensure all ACTIONABLE content is captured, but exclude non-actionable acknowledgments.

EXAMPLE:
Given: "We concur with the finding. As recommended, the University Controller is meeting with the Property Accounting Office to streamline the process for adding and removing assets to/from the Asset Management System. This includes creating formal policies in order to ensure the campus is in compliance with respective executive orders and campus interest."

WRONG: Task 1: "We concur with the finding." Task 2: "As recommended, the University Controller is meeting with..."

CORRECT: Task 1: "The University Controller is meeting with the Property Accounting Office to streamline the process for adding and removing assets to/from the Asset Management System. This includes creating formal policies in order to ensure the campus is in compliance with respective executive orders and campus interest."

Return a JSON object with this structure:
{{
    "tasks": [
        {{
            "task_text": "EXACT verbatim text segment(s) grouped as one logical implementation task",
            "inferred_department": "Department responsible",
            "implementation_type": "Process Improvement",
            "contact": "",
            "requires_collaboration": false,
            "inferred_division": "",
            "inferred_vp": "",
            "inferred_cabinet_member": "",
            "due_date": ""
        }}
    ]
}}
"""
                            
                            tasks_result = processor.bedrock_client.invoke_model_structured(
                                task_prompt,
                                None,
                                max_tokens=3000
                            )
                            
                            # Parse tasks from response
                            tasks = []
                            if tasks_result:
                                import re
                                json_match = re.search(r'\{.*\}', tasks_result, re.DOTALL)
                                if json_match:
                                    try:
                                        parsed_tasks = json.loads(json_match.group())
                                        tasks = parsed_tasks.get('tasks', [])
                                    except:
                                        pass
                            
                            # Fallback: create single task from management response
                            if not tasks:
                                tasks = [{
                                    'task_text': observation.get('management_response', ''),
                                    'inferred_department': observation.get('inferred_department', ''),
                                    'implementation_type': 'Process Improvement',
                                    'contact': '',
                                    'requires_collaboration': False,
                                    'inferred_division': '',
                                    'inferred_vp': '',
                                    'inferred_cabinet_member': '',
                                    'due_date': ''
                                }]
                        else:
                            # No management response, skip this observation
                            continue
                        
                        observations_with_tasks.append([observation, tasks])
                    
                    session_id = str(uuid.uuid4())
                    app_data[session_id] = {'observations_with_tasks': observations_with_tasks}
                    session['audit_session_id'] = session_id
                    
                    processing_time = time.time() - upload_start_time
                    current_progress["message"] = "Ready"
                    
                    # Count total tasks
                    total_tasks = sum(len(tasks) for _, tasks in observations_with_tasks)
                    
                    # Log successful upload
                    interaction_logger.log_file_upload(session['session_id'], file.filename, file_size, processing_time, len(observations), file_content, True)
                    
                    return jsonify({
                        'success': True,
                        'observations_count': len(observations),
                        'total_tasks': total_tasks,
                        'observations_with_tasks': observations_with_tasks
                    })
                else:
                    return jsonify({'error': 'No observations found in the document'}), 400
            else:
                return jsonify({'error': 'Could not extract text from PDF'}), 400
        except Exception as e:
            return jsonify({'error': f'Error processing file: {str(e)}'}), 500
    else:
        return jsonify({'error': 'Please upload a PDF file'}), 400

@app.route('/upload_evidence', methods=['POST'])
def upload_evidence():
    """Upload and validate evidence for a specific task"""
    session_id = session.get('session_id', 'unknown')
    
    try:
        # Get form data
        obs_idx = int(request.form.get('obs_idx'))
        task_idx = int(request.form.get('task_idx'))
        task_description = request.form.get('task_description', '')
        task_context = json.loads(request.form.get('task_context', '{}'))
        user_description = request.form.get('user_description', '')
        
        if 'evidence_file' not in request.files:
            return jsonify({'error': 'No evidence file uploaded'}), 400
        
        evidence_file = request.files['evidence_file']
        if evidence_file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        filename = evidence_file.filename.lower()
        
        # Validate evidence based on file type
        if filename.endswith('.pdf'):
            result = evidence_validator.validate_pdf_evidence(evidence_file, task_description, task_context, user_description)
        elif filename.endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp')):
            result = evidence_validator.validate_image_evidence(evidence_file, task_description, task_context, user_description)
        else:
            return jsonify({'error': 'Unsupported file type. Please upload PDF or image files.'}), 400
        
        # Log evidence validation
        interaction_logger.log_manual_edit(
            session_id, 'evidence_upload', obs_idx, task_idx, 
            'evidence_validation', user_description, json.dumps(result)
        )
        
        return jsonify(result)

    except Exception as e:
        return jsonify({'error': f'Error validating evidence: {str(e)}'}), 500

@app.route('/upload_evidence_agent', methods=['POST'])
def upload_evidence_agent():
    """Upload and validate evidence using the agentic workflow for complex document analysis"""
    session_id = session.get('session_id', 'unknown')

    try:
        # Get form data
        obs_idx = int(request.form.get('obs_idx'))
        task_idx = int(request.form.get('task_idx'))
        task_description = request.form.get('task_description', '')
        task_context = json.loads(request.form.get('task_context', '{}'))
        user_description = request.form.get('user_description', '')
        use_agentic = request.form.get('use_agentic', 'true').lower() == 'true'

        if 'evidence_file' not in request.files:
            return jsonify({'error': 'No evidence file uploaded'}), 400

        evidence_file = request.files['evidence_file']
        if evidence_file.filename == '':
            return jsonify({'error': 'No file selected'}), 400

        # Use the enhanced agentic validation
        result = evidence_validator.validate_evidence_with_agent(
            evidence_file, task_description, task_context, user_description, use_agentic
        )

        # Store evidence in multi-document store
        task_key = f"{obs_idx}-{task_idx}"
        if task_key not in task_evidence_store:
            task_evidence_store[task_key] = []

        evidence_entry = {
            "file_info": {
                "filename": evidence_file.filename,
                "timestamp": datetime.now().isoformat(),
                "user_description": user_description
            },
            "validation_result": result
        }
        task_evidence_store[task_key].append(evidence_entry)

        # Add evidence count to result
        result['evidence_count'] = len(task_evidence_store[task_key])
        result['evidence_index'] = len(task_evidence_store[task_key]) - 1

        # Log agentic evidence validation
        interaction_logger.log_manual_edit(
            session_id, 'evidence_upload_agent', obs_idx, task_idx,
            'agentic_evidence_validation', user_description, json.dumps(result)
        )

        return jsonify(result)

    except Exception as e:
        return jsonify({'error': f'Error in agentic evidence validation: {str(e)}'}), 500

@app.route('/get_annotated_image/<filename>')
def get_annotated_image(filename):
    """Serve annotated images"""
    try:
        output_dir = os.path.join(os.getcwd(), 'evidence_annotations')
        file_path = os.path.join(output_dir, filename)
        
        if os.path.exists(file_path):
            return send_file(file_path)
        else:
            return jsonify({'error': 'Image not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/get_pdf/<filename>')
def get_pdf(filename):
    """Serve PDF files for the PDF viewer"""
    try:
        pdf_dir = os.path.join(os.getcwd(), 'temp_pdfs')
        file_path = os.path.join(pdf_dir, filename)

        if os.path.exists(file_path):
            return send_file(file_path, mimetype='application/pdf')
        else:
            return jsonify({'error': 'PDF not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/get_pdf_text_data/<filename>')
def get_pdf_text_data(filename):
    """Extract precise text positioning data from PDF using PyMuPDF"""
    try:
        pdf_dir = os.path.join(os.getcwd(), 'temp_pdfs')
        file_path = os.path.join(pdf_dir, filename)

        if not os.path.exists(file_path):
            return jsonify({'error': 'PDF not found'}), 404

        # Open PDF with PyMuPDF
        doc = fitz.open(file_path)
        pages_data = []

        for page_num in range(len(doc)):
            page = doc[page_num]

            # Get page dimensions
            rect = page.rect
            page_width = rect.width
            page_height = rect.height

            # Extract text blocks with precise positioning
            blocks = page.get_text("dict")

            text_items = []
            full_text_parts = []

            for block in blocks["blocks"]:
                if "lines" in block:  # Text block
                    for line in block["lines"]:
                        for span in line["spans"]:
                            # Get bounding box
                            bbox = span["bbox"]  # [x0, y0, x1, y1]

                            text_item = {
                                "text": span["text"],
                                "bbox": {
                                    "x0": bbox[0],
                                    "y0": bbox[1],
                                    "x1": bbox[2],
                                    "y1": bbox[3]
                                },
                                "font": span.get("font", ""),
                                "size": span.get("size", 12),
                                "flags": span.get("flags", 0)
                            }

                            text_items.append(text_item)
                            full_text_parts.append(span["text"])

            # Combine into page data
            page_data = {
                "page_number": page_num + 1,
                "width": page_width,
                "height": page_height,
                "text_items": text_items,
                "full_text": " ".join(full_text_parts)
            }

            pages_data.append(page_data)

        doc.close()

        return jsonify({
            "success": True,
            "filename": filename,
            "pages": pages_data
        })

    except Exception as e:
        logger.error(f"Error extracting PDF text data: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/upload_multiple_evidence', methods=['POST'])
def upload_multiple_evidence():
    """Upload and validate multiple evidence documents for a single task"""
    session_id = session.get('session_id', 'unknown')

    try:
        # Get form data
        obs_idx = int(request.form.get('obs_idx'))
        task_idx = int(request.form.get('task_idx'))
        task_description = request.form.get('task_description', '')
        task_context = json.loads(request.form.get('task_context', '{}'))
        user_description = request.form.get('user_description', '')

        # Get multiple files
        evidence_files = request.files.getlist('evidence_files')
        if not evidence_files:
            return jsonify({'error': 'No evidence files uploaded'}), 400

        # Validate file count (limit to reasonable number)
        if len(evidence_files) > 10:
            return jsonify({'error': 'Too many files. Maximum 10 evidence documents per task.'}), 400

        results = []
        all_documents_content = []

        # Process each file individually first
        for i, evidence_file in enumerate(evidence_files):
            if evidence_file.filename == '':
                continue

            file_content = evidence_file.read()
            evidence_file.seek(0)  # Reset for potential reuse

            # Individual validation
            result = evidence_validator.validate_evidence_with_agent(
                evidence_file, task_description, task_context,
                f"Document {i+1}: {user_description}", True
            )

            # Store document content for collective analysis
            all_documents_content.append({
                'filename': evidence_file.filename,
                'content': file_content,
                'individual_result': result
            })

            results.append({
                'filename': evidence_file.filename,
                'result': result,
                'document_index': i
            })

        # Perform collective analysis using Claude Code SDK agent
        collective_result = evidence_validator.claude_code_agent.analyze_multiple_evidence_sync(
            all_documents_content, task_description, task_context, user_description
        )

        # Store in multi-document store
        task_key = f"{obs_idx}-{task_idx}"
        task_evidence_store[task_key] = [{
            "file_info": {
                "filenames": [f['filename'] for f in all_documents_content],
                "timestamp": datetime.now().isoformat(),
                "user_description": user_description,
                "is_multi_document": True
            },
            "validation_result": collective_result,
            "individual_results": results
        }]

        collective_result['evidence_count'] = len(evidence_files)
        collective_result['individual_results'] = results

        # Log multi-document validation
        interaction_logger.log_manual_edit(
            session_id, 'multi_evidence_upload', obs_idx, task_idx,
            'multi_document_validation', user_description, json.dumps(collective_result)
        )

        return jsonify(collective_result)

    except Exception as e:
        return jsonify({'error': f'Error in multi-document validation: {str(e)}'}), 500

@app.route('/get_task_evidence/<int:obs_idx>/<int:task_idx>')
def get_task_evidence(obs_idx, task_idx):
    """Get all evidence documents for a specific task"""
    try:
        task_key = f"{obs_idx}-{task_idx}"
        evidence_list = task_evidence_store.get(task_key, [])

        return jsonify({
            'success': True,
            'evidence_count': len(evidence_list),
            'evidence_documents': evidence_list
        })
    except Exception as e:
        return jsonify({'error': f'Error retrieving task evidence: {str(e)}'}), 500

@app.route('/remove_evidence/<int:obs_idx>/<int:task_idx>/<int:evidence_idx>', methods=['DELETE'])
def remove_evidence(obs_idx, task_idx, evidence_idx):
    """Remove a specific evidence document from a task"""
    try:
        task_key = f"{obs_idx}-{task_idx}"
        if task_key in task_evidence_store and evidence_idx < len(task_evidence_store[task_key]):
            removed_evidence = task_evidence_store[task_key].pop(evidence_idx)

            # Clean up associated files if needed
            if 'pdf_filename' in removed_evidence.get('validation_result', {}):
                pdf_filename = removed_evidence['validation_result']['pdf_filename']
                pdf_path = os.path.join(os.getcwd(), 'temp_pdfs', pdf_filename)
                if os.path.exists(pdf_path):
                    os.remove(pdf_path)

            return jsonify({
                'success': True,
                'remaining_count': len(task_evidence_store[task_key])
            })
        else:
            return jsonify({'error': 'Evidence document not found'}), 404
    except Exception as e:
        return jsonify({'error': f'Error removing evidence: {str(e)}'}), 500

@app.route('/progress')
def get_progress():
    return jsonify(current_progress)

@app.route('/agent_progress')
def get_agent_progress():
    """Get current Claude Code agent analysis progress"""
    try:
        if evidence_validator.claude_code_agent:
            progress_info = evidence_validator.claude_code_agent.agent.get_analysis_status()
            return jsonify(progress_info)
        else:
            return jsonify({"message": "No active analysis session", "status": "idle"})
    except Exception as e:
        return jsonify({"error": f"Could not get progress: {str(e)}"}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5001)
