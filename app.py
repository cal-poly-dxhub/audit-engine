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

# Load environment variables
load_dotenv()

# Initialize colorama
init(autoreset=True)

# Pydantic models for structured output
class Observation(BaseModel):
    observation_number: str = Field(description="The observation number (e.g., '1', '2', etc.)")
    observation_title: str = Field(description="The exact title/heading of the observation")
    observation_description: str = Field(description="Brief description of the finding/issue")
    severity: str = Field(description="'Significant Issue' or 'Observation for Improvement'")
    recommendations: Optional[str] = Field(description="The auditor's recommendations if present")
    management_response: str = Field(description="THE COMPLETE, VERBATIM management response text")
    anticipated_completion_date: Optional[str] = Field(description="Any mentioned completion date")

class ObservationList(BaseModel):
    observations: List[Observation] = Field(description="List of all observations extracted from the audit report")

class Task(BaseModel):
    task_text: str = Field(description="The EXACT text segment from the management response")
    inferred_department: str = Field(description="Department likely responsible")
    implementation_type: str = Field(description="Type of action (e.g., 'Process Improvement', 'Policy Change', etc.)")
    requires_collaboration: bool = Field(description="Whether multiple parties are mentioned")
    inferred_division: Optional[str] = Field(description="Best match division based on context")
    inferred_vp: Optional[str] = Field(description="Best match VP titles based on context (comma-separated if multiple)")
    inferred_cabinet_member: Optional[str] = Field(description="Best match Cabinet Member titles based on context (comma-separated if multiple)")

    @classmethod
    def from_dict(cls, data: dict):
        """Create Task from dict with flexible VP/Cabinet handling"""
        # Handle VP field - convert list to string or keep as string
        if isinstance(data.get('inferred_vp'), list):
            data['inferred_vp'] = '; '.join(data['inferred_vp'])
        
        # Handle Cabinet Member field - convert list to string or keep as string  
        if isinstance(data.get('inferred_cabinet_member'), list):
            data['inferred_cabinet_member'] = '; '.join(data['inferred_cabinet_member'])
            
        return cls(**data)

class TaskList(BaseModel):
    tasks: List[Task] = Field(description="List of implementation tasks from the management response")

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('audit_engine.log')
    ]
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'your-secret-key-here')

# Progress tracking
current_progress = {"message": "Ready"}

@app.route('/progress')
def get_progress():
    return jsonify(current_progress)

@app.route('/process_nl_command', methods=['POST'])
def process_nl_command():
    global current_progress
    from datetime import datetime
    log_request('/process_nl_command', 'POST')
    
    try:
        data = request.json
        command = data.get('command', '')
        observations_with_tasks = data.get('observations_with_tasks', [])
        
        current_progress["message"] = "Processing natural language command..."
        
        # Create a prompt for the LLM to parse the command
        prompt = f"""
Parse this natural language command and return a JSON response with the changes to apply.

Command: "{command}"

Available observations and tasks:
"""
        
        # Add context about available observations and tasks
        for obs_idx, (observation, tasks) in enumerate(observations_with_tasks):
            prompt += f"\nObservation {obs_idx + 1}: {observation.get('observation_title', 'Unnamed')} ({len(tasks)} tasks)\n"
            for task_idx, task in enumerate(tasks):
                task_letter = chr(65 + task_idx)  # A, B, C, etc.
                current_contact = task.get('contact', 'Not set')
                current_due_date = task.get('due_date', 'Not set')
                current_division = task.get('inferred_division', 'Not set')
                prompt += f"  Task {obs_idx + 1}{task_letter}: {task.get('task_text', '')[:100]}...\n"
                prompt += f"    Contact: {current_contact}, Due Date: {current_due_date}, Division: {current_division}\n"
        
        prompt += """
Return JSON with this structure:
{
  "changes": [
    {
      "obs_idx": 0,
      "task_idx": 0, 
      "field": "contact",
      "value": "President Armstrong"
    }
  ],
  "summary": "Changed contact for 3 tasks to President Armstrong"
}

IMPORTANT - Available fields (use EXACTLY these names):
- task_text (for management response text)
- contact (for contact person)
- due_date (for due dates, use YYYY-MM-DD format)
- inferred_department (for department)
- inferred_division (for division)
- inferred_vp (for VP)
- inferred_cabinet_member (for cabinet member)
- implementation_type (for implementation type)
- requires_collaboration (for collaboration, use true/false)

Special operations:
- For combining tasks: use "action": "combine", "obs_idx": 0, "task_indices": [0,1,2]
- For swapping tasks: change the task_text field of both tasks
- For deleting tasks: use "action": "delete", "obs_idx": 0, "task_idx": 1

Task references: "1A" = obs_idx: 0, task_idx: 0; "1B" = obs_idx: 0, task_idx: 1; "2C" = obs_idx: 1, task_idx: 2
For "one month from now", calculate the actual date from today.
For relative date changes like "increase by 10 days", use the current due date shown above. If no current date exists, assume today's date as the starting point.
Current date for calculations: {datetime.now().strftime('%Y-%m-%d')}
"""
        
        # Call LLM to parse the command
        try:
            llm_response = processor.bedrock_client.invoke_model_structured(prompt, None, max_tokens=2000)
            
            if not llm_response:
                current_progress["message"] = "Ready"
                return jsonify({'error': 'AI did not provide a response'}), 400
                
        except Exception as llm_error:
            current_progress["message"] = "Ready"
            log_step("NL_COMMAND", "ERROR", f"LLM call failed: {str(llm_error)}")
            return jsonify({'error': f'AI processing failed: {str(llm_error)}'}), 500
        
        # Extract JSON from response
        import re
        try:
            json_match = re.search(r'\{.*\}', llm_response, re.DOTALL)
            if json_match:
                parsed_command = json.loads(json_match.group())
                current_progress["message"] = "Ready"
                return jsonify({
                    'success': True,
                    'changes': parsed_command.get('changes', []),
                    'summary': parsed_command.get('summary', 'Applied changes')
                })
            else:
                current_progress["message"] = "Ready"
                return jsonify({'error': 'Could not find JSON in AI response'}), 400
        except json.JSONDecodeError as json_error:
            current_progress["message"] = "Ready"
            return jsonify({'error': f'Could not parse AI response: {str(json_error)}'}), 400
            
    except Exception as e:
        current_progress["message"] = "Ready"
        log_step("NL_COMMAND", "ERROR", f"Exception: {str(e)}")
        return jsonify({'error': f'Error processing command: {str(e)}'}), 500

# In-memory storage to avoid session size limits
app_data = {}

def log_step(step_name: str, status: str = "START", details: str = ""):
    """Log step with color coding"""
    timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    if status == "START":
        print(f"{Fore.BLUE}[{timestamp}] {step_name} - STARTED{Style.RESET_ALL} {details}")
        logger.info(f"{step_name} - STARTED - {details}")
    elif status == "END":
        print(f"{Fore.GREEN}[{timestamp}] {step_name} - COMPLETED{Style.RESET_ALL} {details}")
        logger.info(f"{step_name} - COMPLETED - {details}")
    elif status == "ERROR":
        print(f"{Fore.RED}[{timestamp}] {step_name} - ERROR{Style.RESET_ALL} {details}")
        logger.error(f"{step_name} - ERROR - {details}")
    elif status == "INFO":
        print(f"{Fore.YELLOW}[{timestamp}] {step_name} - INFO{Style.RESET_ALL} {details}")
        logger.info(f"{step_name} - INFO - {details}")
    elif status == "DEBUG":
        print(f"{Fore.CYAN}[{timestamp}] {step_name} - DEBUG{Style.RESET_ALL} {details}")
        logger.debug(f"{step_name} - DEBUG - {details}")

def log_llm_interaction(prompt: str, response: str, model_id: str, duration: float):
    """Log LLM interactions with detailed info"""
    timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    print(f"{Fore.MAGENTA}[{timestamp}] [LLM] Model: {model_id} | Duration: {duration:.2f}s{Style.RESET_ALL}")
    print(f"{Fore.CYAN}[{timestamp}] [LLM INPUT] Length: {len(prompt)} chars{Style.RESET_ALL}")
    print(f"{Fore.CYAN}[{timestamp}] [LLM INPUT PREVIEW] {prompt[:200]}...{Style.RESET_ALL}")
    logger.info(f"LLM_INPUT - Model: {model_id} - Prompt length: {len(prompt)} - Preview: {prompt[:200]}...")
    print(f"{Fore.CYAN}[{timestamp}] [LLM OUTPUT] Length: {len(response)} chars{Style.RESET_ALL}")
    print(f"{Fore.CYAN}[{timestamp}] [LLM OUTPUT PREVIEW] {response[:200]}...{Style.RESET_ALL}")
    logger.info(f"LLM_OUTPUT - Response length: {len(response)} - Preview: {response[:200]}...")

def log_request(endpoint: str, method: str, data_size: int = 0):
    """Log HTTP requests"""
    timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    print(f"{Fore.WHITE}{Back.BLUE}[{timestamp}] [HTTP] {method} {endpoint} - Data: {data_size} bytes{Style.RESET_ALL}")
    logger.info(f"HTTP_REQUEST - {method} {endpoint} - Data size: {data_size}")

def log_data_processing(operation: str, input_size: int, output_size: int, duration: float):
    """Log data processing operations"""
    timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    print(f"{Fore.GREEN}[{timestamp}] [DATA] {operation} - Input: {input_size} | Output: {output_size} | Duration: {duration:.3f}s{Style.RESET_ALL}")
    logger.info(f"DATA_PROCESSING - {operation} - Input: {input_size} - Output: {output_size} - Duration: {duration:.3f}s")

class BedrockClient:
    """AWS Bedrock client for LLM interactions with structured output"""

    def __init__(self):
        # Get API key from environment
        # Create client with API key authentication
        self.client = boto3.client(
            "bedrock-runtime", 
            region_name="us-west-2"
        )
        self.model_id = "us.anthropic.claude-sonnet-4-20250514-v1:0"
        #self.model_id = "anthropic.claude-3-5-haiku-20241022-v1:0"
        #self.model_id = "us.anthropic.claude-opus-4-1-20250805-v1:0"

    def invoke_model_structured(self, prompt: str, response_model, max_tokens: int = 4000):
        """Invoke Claude with structured output using regular API call"""
        start_time = time.time()
        log_step("LLM_INVOCATION", "START", f"Model: {self.model_id}, Max tokens: {max_tokens}, Response model: {response_model.__name__ if response_model else 'None'}")
        
        # Log input BEFORE making the call
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        print(f"{Fore.CYAN}[{timestamp}] [LLM INPUT] Length: {len(prompt)} chars{Style.RESET_ALL}")
        print(f"{Fore.CYAN}[{timestamp}] [LLM INPUT PREVIEW] {prompt[:500]}...{Style.RESET_ALL}")
        logger.info(f"LLM_INPUT - Model: {self.model_id} - Prompt length: {len(prompt)} - Preview: {prompt[:500]}...")
        
        # Save full input to file
        input_filename = f"llm_input_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')[:-3]}.txt"
        with open(input_filename, 'w', encoding='utf-8') as f:
            f.write(f"=== LLM INPUT ===\n")
            f.write(f"Model: {self.model_id}\n")
            f.write(f"Timestamp: {datetime.now().isoformat()}\n")
            f.write(f"Length: {len(prompt)} chars\n")
            f.write(f"Max tokens: {max_tokens}\n")
            f.write(f"Response model: {response_model.__name__ if response_model else 'None'}\n")
            f.write(f"\n=== FULL PROMPT ===\n")
            f.write(prompt)
        print(f"{Fore.GREEN}[{timestamp}] [FILE] Saved full input to: {input_filename}{Style.RESET_ALL}")
        
        try:
            log_step("LLM_REQUEST_PREP", "START", f"Preparing regular request body")
            body = json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": max_tokens,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.2,
            })
            log_step("LLM_REQUEST_PREP", "END", f"Request body size: {len(body)} bytes")

            log_step("LLM_API_CALL", "START", f"Starting streaming Bedrock API call")
            
            # Use streaming invoke_model_with_response_stream
            response = self.client.invoke_model_with_response_stream(
                body=body, 
                modelId=self.model_id, 
                contentType="application/json"
            )
            
            # Stream and collect response
            result_text = ""
            for event in response['body']:
                chunk = json.loads(event['chunk']['bytes'])
                if chunk['type'] == 'content_block_delta':
                    text_chunk = chunk['delta']['text']
                    print(text_chunk, end='', flush=True)
                    result_text += text_chunk
            
            log_step("LLM_API_CALL", "END", f"Streaming completed")
            
            duration = time.time() - start_time
            
            # Log output summary
            timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
            print(f"{Fore.MAGENTA}[{timestamp}] [LLM] Model: {self.model_id} | Duration: {duration:.2f}s{Style.RESET_ALL}")
            print(f"{Fore.CYAN}[{timestamp}] [LLM OUTPUT] Length: {len(result_text)} chars{Style.RESET_ALL}")
            logger.info(f"LLM_OUTPUT - Response length: {len(result_text)}")
            
            # Save full output to file
            output_filename = f"llm_output_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')[:-3]}.txt"
            with open(output_filename, 'w', encoding='utf-8') as f:
                f.write(f"=== LLM OUTPUT ===\n")
                f.write(f"Model: {self.model_id}\n")
                f.write(f"Timestamp: {datetime.now().isoformat()}\n")
                f.write(f"Duration: {duration:.2f}s\n")
                f.write(f"Length: {len(result_text)} chars\n")
                f.write(f"\n=== FULL RESPONSE ===\n")
                f.write(result_text)
            print(f"{Fore.GREEN}[{timestamp}] [FILE] Saved full output to: {output_filename}{Style.RESET_ALL}")
            
            # Parse with instructor for validation
            try:
                log_step("JSON_EXTRACTION", "START", f"Extracting JSON from response")
                # Extract JSON from response
                json_start = result_text.find("{")
                json_end = result_text.rfind("}") + 1
                if json_start == -1:
                    json_start = result_text.find("[")
                    json_end = result_text.rfind("]") + 1
                
                json_str = result_text[json_start:json_end]
                log_step("JSON_EXTRACTION", "END", f"Extracted JSON length: {len(json_str)}")
                
                log_step("JSON_PARSE", "START", f"Parsing extracted JSON")
                parsed_data = json.loads(json_str)
                log_step("JSON_PARSE", "END", f"JSON parsed successfully, type: {type(parsed_data)}")
                
                # Validate with Pydantic
                log_step("PYDANTIC_VALIDATION", "START", f"Validating with {response_model.__name__ if response_model else 'None'}")
                if response_model == ObservationList:
                    if isinstance(parsed_data, list):
                        validated = ObservationList(observations=[Observation(**obs) for obs in parsed_data])
                        log_step("PYDANTIC_VALIDATION", "END", f"Validated {len(validated.observations)} observations")
                    else:
                        validated = ObservationList(**parsed_data)
                        log_step("PYDANTIC_VALIDATION", "END", f"Validated observation list")
                elif response_model == TaskList:
                    if isinstance(parsed_data, list):
                        # Use flexible Task creation
                        tasks = []
                        for i, task_data in enumerate(parsed_data):
                            try:
                                log_step("TASK_VALIDATION", "DEBUG", f"Validating task {i+1}/{len(parsed_data)}")
                                tasks.append(Task.from_dict(task_data))
                            except Exception as e:
                                log_step("TASK_VALIDATION", "ERROR", f"Task {i+1} validation error: {str(e)}")
                                # Fallback with safe defaults
                                safe_task = {
                                    'task_text': task_data.get('task_text', ''),
                                    'inferred_department': task_data.get('inferred_department', 'To be determined'),
                                    'implementation_type': task_data.get('implementation_type', 'Process Improvement'),
                                    'requires_collaboration': task_data.get('requires_collaboration', False),
                                    'inferred_division': task_data.get('inferred_division', ''),
                                    'inferred_vp': '',
                                    'inferred_cabinet_member': ''
                                }
                                tasks.append(Task(**safe_task))
                        validated = TaskList(tasks=tasks)
                        log_step("PYDANTIC_VALIDATION", "END", f"Validated {len(tasks)} tasks")
                    else:
                        validated = TaskList(**parsed_data)
                        log_step("PYDANTIC_VALIDATION", "END", f"Validated task list")
                elif response_model is None:
                    # No validation needed, return raw text
                    validated = result_text
                    log_step("PYDANTIC_VALIDATION", "END", f"No validation - returning raw text")
                else:
                    validated = response_model(**parsed_data)
                    log_step("PYDANTIC_VALIDATION", "END", f"Validated with custom model")
                
                log_step("LLM_INVOCATION", "END", f"Duration: {duration:.2f}s - Structured output validated")
                return validated
                
            except (json.JSONDecodeError, ValueError) as e:
                log_step("JSON_VALIDATION", "ERROR", f"JSON parsing error: {str(e)}")
                log_step("LLM_INVOCATION", "END", f"Duration: {duration:.2f}s - Fallback to text")
                # Fallback to original text parsing
                return result_text

        except Exception as e:
            duration = time.time() - start_time
            log_step("LLM_INVOCATION", "ERROR", f"Error: {str(e)} - Duration: {duration:.2f}s")
            return None

    def invoke_model(self, prompt: str, max_tokens: int = 4000) -> str:
        """Legacy method for backward compatibility"""
        return self.invoke_model_structured(prompt, None, max_tokens)

class AuditDocumentProcessor:
    """Process audit documents and extract structured information"""

    def __init__(self, bedrock_client: BedrockClient):
        self.bedrock_client = bedrock_client
        self.llm_process_start_time = None
        self.llm_process_end_time = None

    def extract_pdf_text(self, pdf_file) -> str:
        """Extract text from uploaded PDF file"""
        start_time = time.time()
        log_step("PDF_TEXT_EXTRACTION", "START", f"File: {pdf_file.filename}")
        
        try:
            pdf_reader = PyPDF2.PdfReader(pdf_file)
            text = ""
            page_count = len(pdf_reader.pages)
            
            log_step("PDF_TEXT_EXTRACTION", "INFO", f"Processing {page_count} pages")
            
            for i, page in enumerate(pdf_reader.pages):
                page_text = page.extract_text()
                text += f"\n[PAGE {i+1}]\n{page_text}\n"
                
            duration = time.time() - start_time
            log_step("PDF_TEXT_EXTRACTION", "END", f"Extracted {len(text)} chars in {duration:.2f}s")
            return text
            
        except Exception as e:
            duration = time.time() - start_time
            log_step("PDF_TEXT_EXTRACTION", "ERROR", f"Error: {str(e)}")
            return ""

    def extract_observations_and_responses(self, audit_text: str) -> List[Dict]:
        """Extract observations and their verbatim management responses from audit text"""
        start_time = time.time()
        self.llm_process_start_time = start_time  # Start global LLM timing
        log_step("EXTRACT_OBSERVATIONS", "START")
        log_step("LLM_PROCESS_TIMING", "START", "Beginning entire LLM process timing")

        prompt = f"""
        You are an expert audit analyst. Extract ALL observations/findings and their COMPLETE management responses from this audit report.

        CRITICAL INSTRUCTIONS:
        1. Extract the VERBATIM management response text - do not summarize or paraphrase
        2. Include the ENTIRE management response, even if it's multiple paragraphs
        3. Preserve ALL details including dates, names, and specific commitments
        4. Look for sections like "MANAGEMENT RESPONSE", "Management's Response", or similar headings
        5. Each observation should have its corresponding management response

        For each observation, extract:
        - observation_number: The observation number (e.g., "1", "2", etc.)
        - observation_title: The exact title/heading of the observation
        - observation_description: Brief description of the finding/issue
        - severity: "Significant Issue" or "Observation for Improvement" (if stated, otherwise infer)
        - recommendations: The auditor's recommendations (if present)
        - management_response: THE COMPLETE, VERBATIM management response text
        - anticipated_completion_date: Any mentioned completion date (extract as-is)

        Return as a JSON object with an "observations" array. Here's the audit report:

        {audit_text}

        IMPORTANT: The management_response field must contain the EXACT text from the document, preserving all details.
        """

        response = self.bedrock_client.invoke_model_structured(prompt, ObservationList, max_tokens=4000)

        try:
            log_step("EXTRACT_OBSERVATIONS", "INFO", "Processing structured observations")
            
            if response is None:
                log_step("EXTRACT_OBSERVATIONS", "ERROR", "Received None response from LLM")
                return []
            
            if isinstance(response, ObservationList):
                observations = [obs.model_dump() for obs in response.observations]
                duration = time.time() - start_time
                log_step("EXTRACT_OBSERVATIONS", "END", f"Extracted {len(observations)} observations in {duration:.2f}s")
                return observations
            else:
                # Fallback to original parsing
                json_start = response.find("[")
                json_end = response.rfind("]") + 1
                json_str = response[json_start:json_end]
                observations = json.loads(json_str)
                duration = time.time() - start_time
                log_step("EXTRACT_OBSERVATIONS", "END", f"Extracted {len(observations)} observations in {duration:.2f}s")
                return observations
            
        except Exception as e:
            duration = time.time() - start_time
            log_step("EXTRACT_OBSERVATIONS", "ERROR", f"Parsing error: {str(e)}")
            return []

    def split_management_response_into_tasks(self, observation: Dict) -> List[Dict]:
        """Split a management response into discrete implementation tasks"""
        start_time = time.time()
        log_step("SPLIT_TASKS", "START", f"Observation: {observation.get('observation_title', 'N/A')}")

        management_response = observation.get('management_response', '')
        if not management_response:
            self.llm_process_end_time = time.time()  # End global LLM timing
            total_llm_duration = self.llm_process_end_time - self.llm_process_start_time
            log_step("LLM_PROCESS_TIMING", "END", f"Total LLM process duration: {total_llm_duration:.2f}s")
            return [observation]

        prompt = f"""
        Analyze this management response and identify natural breakpoints for implementation tracking.
        
        Management Response:
        {management_response}

        Split this response into discrete implementation tasks based on:
        1. Sentences starting with "Additionally", "Further", "Also", "We will", etc.
        2. Different initiatives or actions described
        3. Different responsible parties mentioned
        4. Different timelines mentioned
        5. Numbered or bulleted items

        CRITICAL: Each task should be a VERBATIM excerpt from the management response.
        Do not paraphrase or summarize - use the EXACT text, just split intelligently.

        For each task segment, provide:
        - task_text: The EXACT text segment from the management response
        - inferred_department: Department likely responsible [Inferred from context]
        - implementation_type: Type of action (e.g., "Process Improvement", "Policy Change", etc.)
        - requires_collaboration: true/false based on whether multiple parties are mentioned
        - inferred_division: Best match from these divisions based on context:
          * Academic Affairs
          * Administration and Finance
          * Information Technology Services
          * Research
          * Strategic Enrollment Management
          * Student Affairs
          * University Communications and Marketing
          * University Development and Alumni Engagement
          * University Office of Diversity and Inclusion
          * University Personnel
        - inferred_vp: Best match(es) from these VP titles based on context (can be multiple):
          * President
          * Interim Provost and Executive Vice President for Academic Affairs
          * Senior Vice President, Administration and Finance, Chief Financial Officer (CFO)
          * Vice President & CEO of Cal Poly Solano Campus
          * Interim Vice President University Personnel and Chief Human Resources Officer
          * Vice President for Strategic Initiatives and Advocacy
          * Chief of Staff
          * Vice President of Strategic Enrollment Management and Student Affairs
          * Vice President, Information Technology and Chief Information Officer (CIO)
          * Vice President, Facilities Management and Development
          * Vice President, University Communications and Marketing
          * CEO, Cal Poly Partners
          * Vice President, University Development & Alumni Engagement and CEO of the Cal Poly Foundation
          * University Counsel
        - inferred_cabinet_member: Best match(es) from these Cabinet Member titles based on context (can be multiple):
          * President
          * Interim Provost and Executive Vice President for Academic Affairs
          * Senior Vice President, Administration and Finance, Chief Financial Officer (CFO)
          * Vice President & CEO of Cal Poly Solano Campus
          * Interim Vice President University Personnel and Chief Human Resources Officer
          * Vice President for Strategic Initiatives and Advocacy
          * Chief of Staff
          * Vice President of Strategic Enrollment Management and Student Affairs
          * Vice President, Information Technology and Chief Information Officer (CIO)
          * Vice President, Facilities Management and Development
          * Vice President, University Communications and Marketing
          * CEO, Cal Poly Partners
          * Vice President, University Development & Alumni Engagement and CEO of the Cal Poly Foundation
          * University Counsel

        Return as JSON object with a "tasks" array. Each element represents one row in the tracking matrix.
        """

        response = self.bedrock_client.invoke_model_structured(prompt, TaskList, max_tokens=2000)

        try:
            log_step("SPLIT_TASKS", "INFO", "Processing structured task breakdown")
            
            if response is None:
                log_step("SPLIT_TASKS", "ERROR", "Received None response from LLM")
                self.llm_process_end_time = time.time()  # End global LLM timing
                total_llm_duration = self.llm_process_end_time - self.llm_process_start_time
                log_step("LLM_PROCESS_TIMING", "END", f"Total LLM process duration: {total_llm_duration:.2f}s")
                return [{
                    "task_text": management_response,
                    "inferred_department": "To be determined [User input required]",
                    "implementation_type": "To be determined",
                    "requires_collaboration": False,
                    "inferred_division": "",
                    "inferred_vp": [],
                    "inferred_cabinet_member": []
                }]
            
            if isinstance(response, TaskList):
                tasks = [task.model_dump() for task in response.tasks]
                if not tasks:
                    tasks = [{
                        "task_text": management_response,
                        "inferred_department": "To be determined [User input required]",
                        "implementation_type": "To be determined",
                        "requires_collaboration": False,
                        "inferred_division": "",
                        "inferred_vp": "",
                        "inferred_cabinet_member": ""
                    }]
                
                duration = time.time() - start_time
                self.llm_process_end_time = time.time()  # End global LLM timing
                total_llm_duration = self.llm_process_end_time - self.llm_process_start_time
                log_step("LLM_PROCESS_TIMING", "END", f"Total LLM process duration: {total_llm_duration:.2f}s")
                log_step("SPLIT_TASKS", "END", f"Split into {len(tasks)} tasks in {duration:.2f}s")
                return tasks
            else:
                # Fallback to original parsing
                try:
                    json_start = response.find("[")
                    json_end = response.rfind("]") + 1
                    if json_start == -1:
                        json_start = response.find("{")
                        json_end = response.rfind("}") + 1
                        if json_start != -1:
                            # Single object, wrap in array
                            json_str = f"[{response[json_start:json_end]}]"
                        else:
                            raise ValueError("No JSON found")
                    else:
                        json_str = response[json_start:json_end]
                    
                    tasks = json.loads(json_str)
                    
                    # Clean up tasks data
                    for task in tasks:
                        if isinstance(task.get('inferred_vp'), list):
                            task['inferred_vp'] = '; '.join(task['inferred_vp'])
                        if isinstance(task.get('inferred_cabinet_member'), list):
                            task['inferred_cabinet_member'] = '; '.join(task['inferred_cabinet_member'])
                    
                    if not tasks:
                        tasks = [{
                            "task_text": management_response,
                            "inferred_department": "To be determined [User input required]",
                            "implementation_type": "To be determined",
                            "requires_collaboration": False
                        }]
                    
                    duration = time.time() - start_time
                    self.llm_process_end_time = time.time()  # End global LLM timing
                    total_llm_duration = self.llm_process_end_time - self.llm_process_start_time
                    log_step("LLM_PROCESS_TIMING", "END", f"Total LLM process duration: {total_llm_duration:.2f}s")
                    log_step("SPLIT_TASKS", "END", f"Split into {len(tasks)} tasks in {duration:.2f}s")
                    return tasks
                except Exception as parse_error:
                    log_step("SPLIT_TASKS", "ERROR", f"Fallback parsing error: {str(parse_error)}")
                    duration = time.time() - start_time
                    self.llm_process_end_time = time.time()  # End global LLM timing
                    total_llm_duration = self.llm_process_end_time - self.llm_process_start_time
                    log_step("LLM_PROCESS_TIMING", "END", f"Total LLM process duration: {total_llm_duration:.2f}s")
                    log_step("SPLIT_TASKS", "END", f"Using fallback single task in {duration:.2f}s")
                    return [{
                        "task_text": management_response,
                        "inferred_department": "To be determined [User input required]",
                        "implementation_type": "To be determined",
                        "requires_collaboration": False,
                        "inferred_division": "",
                        "inferred_vp": "",
                        "inferred_cabinet_member": ""
                    }]
            
        except Exception as e:
            duration = time.time() - start_time
            self.llm_process_end_time = time.time()  # End global LLM timing
            total_llm_duration = self.llm_process_end_time - self.llm_process_start_time
            log_step("LLM_PROCESS_TIMING", "END", f"Total LLM process duration: {total_llm_duration:.2f}s")
            log_step("SPLIT_TASKS", "ERROR", f"Error: {str(e)}")
            return [{
                "task_text": management_response,
                "inferred_department": "To be determined [User input required]",
                "implementation_type": "To be determined",
                "requires_collaboration": False
            }]

class AuditTrackingMatrix:
    """Generate and manage audit tracking matrix"""

    def __init__(self):
        self.columns = [
            "Observation #",
            "Observation",
            "Observation Step",
            "Implementation Tasks per Management Response",
            "Severity Rating (per Task)",
            "Severity Rating (per Observation)",
            "Management/Implementation Type",
            "Department(s) Responsible",
            "Department Collaboration Required?",
            "Contact",
            "VP",
            "Division",
            "Cabinet Member",
            "Status Notes",
            "Original Due Date",
            "Extended Due Date 1",
            "Extended Due Date 2",
            "Extended Due Date 3",
            "Due Date Status",
            "Implementation Response Status",
            "Internal Tracking per Task",
            "Audit Committee Reporting Status",
        ]

    def create_matrix_from_observations(self, observations_with_tasks: List[Tuple[Dict, List[Dict]]]) -> pd.DataFrame:
        """Create tracking matrix DataFrame from observations and their tasks"""
        start_time = time.time()
        log_step("CREATE_MATRIX", "START")

        rows = []
        
        for obs_num, (observation, tasks) in enumerate(observations_with_tasks, 1):
            obs_title = observation.get('observation_title', 'Unnamed Observation')
            severity = observation.get('severity', 'Observation for Improvement')
            completion_date = observation.get('anticipated_completion_date', '')
            
            log_step("CREATE_MATRIX", "INFO", f"Processing observation {obs_num}: {obs_title}")
            
            step_letters = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
            
            for task_idx, task in enumerate(tasks):
                if task_idx < len(step_letters):
                    obs_step = f"{obs_num}{step_letters[task_idx]}"
                else:
                    obs_step = f"{obs_num}_{task_idx+1}"
                
                row = {
                    "Observation #": obs_num if task_idx == 0 else "",
                    "Observation": obs_title,
                    "Observation Step": obs_step,
                    "Implementation Tasks per Management Response": task.get('task_text', ''),
                    "Severity Rating (per Task)": severity,
                    "Severity Rating (per Observation)": severity if task_idx == 0 else "",
                    "Management/Implementation Type": task.get('implementation_type', 'Process Improvement'),
                    "Department(s) Responsible": task.get('inferred_department', 'To be determined [User input required]'),
                    "Department Collaboration Required?": "Yes" if task.get('requires_collaboration', False) else "No",
                    "Contact": task.get('contact', ''),
                    "VP": task.get('inferred_vp', '') if isinstance(task.get('inferred_vp'), str) else "; ".join(task.get('inferred_vp', [])),
                    "Division": task.get('inferred_division', ''),
                    "Cabinet Member": task.get('inferred_cabinet_member', '') if isinstance(task.get('inferred_cabinet_member'), str) else "; ".join(task.get('inferred_cabinet_member', [])),
                    "Status Notes": f"Generated from audit report - {datetime.now().strftime('%Y-%m-%d')}",
                    "Original Due Date": task.get('due_date', completion_date if completion_date else ""),
                    "Extended Due Date 1": "",
                    "Extended Due Date 2": "",
                    "Extended Due Date 3": "",
                    "Due Date Status": "Not Started",
                    "Implementation Response Status": "Pending management review",
                    "Internal Tracking per Task": "Not Started",
                    "Audit Committee Reporting Status": "Not Started" if task_idx == 0 else "",
                }
                rows.append(row)

        df = pd.DataFrame(rows, columns=self.columns)
        duration = time.time() - start_time
        log_step("CREATE_MATRIX", "END", f"Created matrix with {len(df)} rows in {duration:.2f}s")
        return df

    def export_to_excel(self, df: pd.DataFrame, audit_title: str) -> BytesIO:
        """Export DataFrame to Excel with proper formatting"""
        start_time = time.time()
        log_step("EXCEL_EXPORT", "START")

        buffer = BytesIO()

        with pd.ExcelWriter(buffer, engine="xlsxwriter", engine_kwargs={'options': {'nan_inf_to_errors': True}}) as writer:
            df.to_excel(writer, sheet_name="Audit Tracking Matrix", index=False)

            workbook = writer.book
            worksheet = writer.sheets["Audit Tracking Matrix"]

            header_format = workbook.add_format(
                {
                    "bold": True,
                    "bg_color": "#003366",
                    "font_color": "white",
                    "border": 1,
                    "text_wrap": True,
                    "valign": "top",
                    "align": "center",
                }
            )

            cell_format = workbook.add_format(
                {"text_wrap": True, "valign": "top", "border": 1}
            )

            severity_high = workbook.add_format(
                {"bg_color": "#FFE6E6", "text_wrap": True, "valign": "top", "border": 1}
            )

            severity_medium = workbook.add_format(
                {"bg_color": "#FFF4E6", "text_wrap": True, "valign": "top", "border": 1}
            )

            for col_num, value in enumerate(df.columns.values):
                worksheet.write(0, col_num, value, header_format)

            for row_num in range(1, len(df) + 1):
                for col_num in range(len(df.columns)):
                    cell_value = df.iloc[row_num - 1, col_num]
                    
                    if col_num in [4, 5]:
                        if cell_value == "Significant Issue":
                            worksheet.write(row_num, col_num, cell_value, severity_high)
                        elif cell_value == "Observation for Improvement":
                            worksheet.write(row_num, col_num, cell_value, severity_medium)
                        else:
                            worksheet.write(row_num, col_num, cell_value, cell_format)
                    else:
                        worksheet.write(row_num, col_num, cell_value, cell_format)

            column_widths = [10, 30, 12, 50, 20, 20, 25, 30, 15, 20, 15, 15, 20, 30, 15, 15, 15, 15, 20, 30, 25, 25]
            
            for i, width in enumerate(column_widths[:len(df.columns)]):
                worksheet.set_column(i, i, width)

            worksheet.set_row(0, 30)

        buffer.seek(0)
        duration = time.time() - start_time
        log_step("EXCEL_EXPORT", "END", f"Excel file created in {duration:.2f}s")
        return buffer

# Initialize global objects
bedrock_client = BedrockClient()
processor = AuditDocumentProcessor(bedrock_client)
matrix_generator = AuditTrackingMatrix()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    global current_progress
    log_request('/upload', 'POST')
    log_step("FILE_UPLOAD", "START", "Processing file upload request")
    current_progress["message"] = "Validating file..."
    
    if 'file' not in request.files:
        log_step("FILE_UPLOAD", "ERROR", "No file in request")
        current_progress["message"] = "Ready"
        return jsonify({'error': 'No file uploaded'}), 400
    
    file = request.files['file']
    if file.filename == '':
        log_step("FILE_UPLOAD", "ERROR", "Empty filename")
        current_progress["message"] = "Ready"
        return jsonify({'error': 'No file selected'}), 400
    
    log_step("FILE_VALIDATION", "INFO", f"File: {file.filename}, Size: {len(file.read())} bytes")
    file.seek(0)  # Reset file pointer after reading size
    
    if file and file.filename.lower().endswith('.pdf'):
        try:
            current_progress["message"] = "Extracting text from PDF..."
            log_step("PDF_PROCESSING", "START", f"Processing PDF: {file.filename}")
            audit_text = processor.extract_pdf_text(file)
            log_step("PDF_PROCESSING", "END", f"Extracted {len(audit_text)} characters")
            
            if audit_text:
                current_progress["message"] = "Extracting observations and responses..."
                log_step("OBSERVATION_EXTRACTION", "START", "Starting observation extraction")
                observations = processor.extract_observations_and_responses(audit_text)
                log_step("OBSERVATION_EXTRACTION", "END", f"Extracted {len(observations)} observations")
                
                if observations:
                    current_progress["message"] = "Finalizing results..."
                    session_id = str(uuid.uuid4())
                    app_data[session_id] = {'observations': observations}
                    session['session_id'] = session_id
                    log_step("SESSION_STORAGE", "INFO", f"Stored data with session ID: {session_id}")
                    
                    log_step("FILE_UPLOAD", "END", f"Successfully processed {file.filename}")
                    current_progress["message"] = "Ready"
                    return jsonify({
                        'success': True,
                        'observations_count': len(observations),
                        'observations': observations
                    })
                else:
                    log_step("FILE_UPLOAD", "ERROR", "No observations found in document")
                    current_progress["message"] = "Ready"
                    return jsonify({'error': 'No observations found in the document'}), 400
            else:
                log_step("FILE_UPLOAD", "ERROR", "Could not extract text from PDF")
                current_progress["message"] = "Ready"
                return jsonify({'error': 'Could not extract text from PDF'}), 400
        except Exception as e:
            log_step("FILE_UPLOAD", "ERROR", f"Exception: {str(e)}")
            current_progress["message"] = "Ready"
            return jsonify({'error': f'Error processing file: {str(e)}'}), 500
    else:
        log_step("FILE_UPLOAD", "ERROR", f"Invalid file type: {file.filename}")
        current_progress["message"] = "Ready"
        return jsonify({'error': 'Please upload a PDF file'}), 400

@app.route('/process_tasks', methods=['POST'])
def process_tasks():
    global current_progress
    log_request('/process_tasks', 'POST')
    log_step("TASK_PROCESSING", "START", "Processing task breakdown request")
    
    try:
        session_id = session.get('session_id')
        log_step("SESSION_CHECK", "INFO", f"Session ID: {session_id}")
        
        if not session_id or session_id not in app_data:
            log_step("TASK_PROCESSING", "ERROR", "No observations found in session")
            current_progress["message"] = "Ready"
            return jsonify({'error': 'No observations found in session'}), 400
        
        observations = app_data[session_id]['observations']
        log_step("DATA_RETRIEVAL", "INFO", f"Retrieved {len(observations)} observations from session")
        
        observations_with_tasks = []
        for i, obs in enumerate(observations):
            current_progress["message"] = f"Breaking down observation {i+1} of {len(observations)} into tasks..."
            log_step("TASK_BREAKDOWN", "START", f"Processing observation {i+1}/{len(observations)}: {obs.get('observation_title', 'Unnamed')}")
            start_time = time.time()
            
            tasks = processor.split_management_response_into_tasks(obs)
            
            duration = time.time() - start_time
            log_data_processing(f"Task breakdown {i+1}", 1, len(tasks), duration)
            log_step("TASK_BREAKDOWN", "END", f"Observation {i+1} split into {len(tasks)} tasks")
            
            observations_with_tasks.append((obs, tasks))
        
        current_progress["message"] = "Finalizing task breakdown..."
        app_data[session_id]['observations_with_tasks'] = observations_with_tasks
        log_step("SESSION_UPDATE", "INFO", f"Updated session with task data")
        
        total_tasks = sum(len(tasks) for _, tasks in observations_with_tasks)
        log_step("TASK_PROCESSING", "END", f"Processed {len(observations)} observations into {total_tasks} total tasks")
        
        current_progress["message"] = "Ready"
        return jsonify({
            'success': True,
            'observations_with_tasks': observations_with_tasks
        })
    except Exception as e:
        log_step("TASK_PROCESSING", "ERROR", f"Exception: {str(e)}")
        current_progress["message"] = "Ready"
        return jsonify({'error': f'Error processing tasks: {str(e)}'}), 500

@app.route('/generate_matrix', methods=['POST'])
def generate_matrix():
    log_request('/generate_matrix', 'POST', len(request.data))
    log_step("MATRIX_GENERATION", "START", "Processing matrix generation request")
    
    try:
        data = request.json
        log_step("REQUEST_PARSE", "INFO", f"Parsed request data, keys: {list(data.keys()) if data else 'None'}")
        
        edited_observations_with_tasks = data.get('observations_with_tasks', [])
        log_step("DATA_VALIDATION", "INFO", f"Received {len(edited_observations_with_tasks)} observations with tasks")
        
        if not edited_observations_with_tasks:
            log_step("MATRIX_GENERATION", "ERROR", "No observations data provided")
            return jsonify({'error': 'No observations data provided'}), 400
        
        log_step("MATRIX_CREATION", "START", "Creating tracking matrix")
        start_time = time.time()
        
        matrix_df = matrix_generator.create_matrix_from_observations(edited_observations_with_tasks)
        
        # Check for NaN values and log them
        nan_count = matrix_df.isna().sum().sum()
        if nan_count > 0:
            log_step("DATA_VALIDATION", "WARNING", f"Found {nan_count} NaN values in matrix data")
            nan_columns = matrix_df.columns[matrix_df.isna().any()].tolist()
            log_step("DATA_VALIDATION", "WARNING", f"Columns with NaN values: {nan_columns}")
        
        # Replace NaN values with empty strings (which converts to valid JSON)
        matrix_df = matrix_df.fillna('')
        matrix_data = matrix_df.to_dict('records')
        
        duration = time.time() - start_time
        log_data_processing("Matrix creation", len(edited_observations_with_tasks), len(matrix_data), duration)
        
        session_id = session.get('session_id')
        if session_id and session_id in app_data:
            app_data[session_id]['current_matrix'] = matrix_data
            app_data[session_id]['matrix_df'] = matrix_df.to_dict()
            log_step("SESSION_UPDATE", "INFO", f"Updated session with matrix data")
        
        # Calculate metrics
        metrics = {
            'total_rows': len(matrix_df),
            'observations': matrix_df["Observation #"].nunique(),
            'significant_issues': len(matrix_df[matrix_df["Severity Rating (per Observation)"] == "Significant Issue"]),
            'collaboration_required': len(matrix_df[matrix_df["Department Collaboration Required?"] == "Yes"])
        }
        log_step("METRICS_CALCULATION", "INFO", f"Calculated metrics: {metrics}")
        
        log_step("MATRIX_GENERATION", "END", f"Generated matrix with {len(matrix_data)} rows")
        
        response_data = {
            'success': True,
            'matrix': matrix_data,
            'metrics': metrics
        }
        
        # Log the exact JSON response for debugging
        import json
        json_response = json.dumps(response_data, default=str)
        log_step("JSON_RESPONSE", "INFO", f"Response length: {len(json_response)} characters")
        
        # Log first 500 and last 500 characters of response
        if len(json_response) > 1000:
            log_step("JSON_RESPONSE", "DEBUG", f"First 500 chars: {json_response[:500]}")
            log_step("JSON_RESPONSE", "DEBUG", f"Last 500 chars: {json_response[-500:]}")
        else:
            log_step("JSON_RESPONSE", "DEBUG", f"Full response: {json_response}")
        
        return jsonify(response_data)
    except Exception as e:
        log_step("MATRIX_GENERATION", "ERROR", f"Exception: {str(e)}")
        return jsonify({'error': f'Error generating matrix: {str(e)}'}), 500

@app.route('/export_excel', methods=['POST'])
def export_excel():
    try:
        data = request.json
        audit_title = data.get('audit_title', 'Audit Evidence Request Matrix')
        
        session_id = session.get('session_id')
        if not session_id or session_id not in app_data or 'matrix_df' not in app_data[session_id]:
            return jsonify({'error': 'No matrix data found'}), 400
        
        matrix_dict = app_data[session_id]['matrix_df']
        matrix_df = pd.DataFrame.from_dict(matrix_dict)
        excel_buffer = matrix_generator.export_to_excel(matrix_df, audit_title)
        
        filename = f"{audit_title.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
        
        # Save to temporary file
        temp_path = f"/tmp/{filename}"
        with open(temp_path, 'wb') as f:
            f.write(excel_buffer.getvalue())
        
        return send_file(
            temp_path,
            as_attachment=True,
            download_name=filename,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
    except Exception as e:
        return jsonify({'error': f'Error exporting Excel: {str(e)}'}), 500

@app.route('/reset', methods=['POST'])
def reset_session():
    session_id = session.get('session_id')
    if session_id and session_id in app_data:
        del app_data[session_id]
    session.clear()
    return jsonify({'success': True})

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
