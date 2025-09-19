import streamlit as st
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

# Initialize colorama
init(autoreset=True)

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

def log_step(step_name: str, status: str = "START", details: str = ""):
    """Log step with color coding"""
    timestamp = datetime.now().strftime("%H:%M:%S")
    if status == "START":
        print(f"{Fore.BLUE}[{timestamp}] {step_name} - STARTED{Style.RESET_ALL}")
        logger.info(f"{step_name} - STARTED - {details}")
    elif status == "END":
        print(f"{Fore.GREEN}[{timestamp}] {step_name} - COMPLETED{Style.RESET_ALL}")
        logger.info(f"{step_name} - COMPLETED - {details}")
    elif status == "ERROR":
        print(f"{Fore.RED}[{timestamp}] {step_name} - ERROR{Style.RESET_ALL}")
        logger.error(f"{step_name} - ERROR - {details}")
    elif status == "INFO":
        print(f"{Fore.YELLOW}[{timestamp}] {step_name} - INFO{Style.RESET_ALL}")
        logger.info(f"{step_name} - INFO - {details}")

def log_llm_interaction(prompt: str, response: str, model_id: str, duration: float):
    """Log LLM interactions with detailed info"""
    print(f"{Fore.MAGENTA}[LLM] Model: {model_id} | Duration: {duration:.2f}s{Style.RESET_ALL}")
    print(f"{Fore.CYAN}[LLM INPUT] Length: {len(prompt)} chars{Style.RESET_ALL}")
    logger.info(f"LLM_INPUT - Model: {model_id} - Prompt length: {len(prompt)}")
    print(f"{Fore.CYAN}[LLM OUTPUT] Length: {len(response)} chars{Style.RESET_ALL}")
    logger.info(f"LLM_OUTPUT - Response length: {len(response)}")

# Configure Streamlit page
st.set_page_config(
    page_title="Cal Poly AuditEngine",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

class BedrockClient:
    """AWS Bedrock client for LLM interactions"""

    def __init__(self):
        self.client = boto3.client("bedrock-runtime", region_name="us-west-2")
        self.model_id = "us.anthropic.claude-sonnet-4-20250514-v1:0"

    def invoke_model(self, prompt: str, max_tokens: int = 4000) -> str:
        """Invoke Claude Sonnet 4 model"""
        start_time = time.time()
        log_step("LLM_INVOCATION", "START", f"Model: {self.model_id}")
        
        try:
            body = json.dumps(
                {
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": max_tokens,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.2,  # Lower temperature for more consistent extraction
                }
            )

            response = self.client.invoke_model(
                body=body, modelId=self.model_id, contentType="application/json"
            )

            response_body = json.loads(response.get("body").read())
            result = response_body.get("content")[0].get("text")
            
            duration = time.time() - start_time
            log_llm_interaction(prompt, result, self.model_id, duration)
            log_step("LLM_INVOCATION", "END", f"Duration: {duration:.2f}s")
            
            # Wait 60 seconds to prevent throttling
            # time.sleep(60)
            
            return result

        except Exception as e:
            duration = time.time() - start_time
            log_step("LLM_INVOCATION", "ERROR", f"Error: {str(e)}")
            st.error(f"Error invoking Bedrock model: {str(e)}")
            return None

class AuditDocumentProcessor:
    """Process audit documents and extract structured information"""

    def __init__(self, bedrock_client: BedrockClient):
        self.bedrock_client = bedrock_client

    def extract_pdf_text(self, pdf_file) -> str:
        """Extract text from uploaded PDF file"""
        start_time = time.time()
        log_step("PDF_TEXT_EXTRACTION", "START", f"File: {pdf_file.name}")
        
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
            st.error(f"Error extracting PDF text: {str(e)}")
            return ""

    def extract_observations_and_responses(self, audit_text: str) -> List[Dict]:
        """Extract observations and their verbatim management responses from audit text"""
        start_time = time.time()
        log_step("EXTRACT_OBSERVATIONS", "START")

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

        Return as a JSON array. Here's the audit report:

        {audit_text}

        IMPORTANT: The management_response field must contain the EXACT text from the document, preserving all details.
        """

        response = self.bedrock_client.invoke_model(prompt, max_tokens=4000)

        try:
            log_step("EXTRACT_OBSERVATIONS", "INFO", "Parsing extracted observations")
            
            # Handle None response
            if response is None:
                log_step("EXTRACT_OBSERVATIONS", "ERROR", "Received None response from LLM")
                return []
            
            json_start = response.find("[")
            json_end = response.rfind("]") + 1
            json_str = response[json_start:json_end]
            
            observations = json.loads(json_str)
            duration = time.time() - start_time
            log_step("EXTRACT_OBSERVATIONS", "END", f"Extracted {len(observations)} observations in {duration:.2f}s")
            return observations
            
        except Exception as e:
            duration = time.time() - start_time
            log_step("EXTRACT_OBSERVATIONS", "ERROR", f"JSON parsing error: {str(e)}")
            st.error(f"Error parsing observations: {str(e)}")
            return []

    def split_management_response_into_tasks(self, observation: Dict) -> List[Dict]:
        """Split a management response into discrete implementation tasks"""
        start_time = time.time()
        log_step("SPLIT_TASKS", "START", f"Observation: {observation.get('observation_title', 'N/A')}")

        management_response = observation.get('management_response', '')
        if not management_response:
            return [observation]

        prompt = f"""
        Analyze this management response and extract only the ACTIONABLE IMPLEMENTATION CONTENT for tracking.

        Management Response:
        {management_response}

        SMART EXTRACTION RULES:
        1. **IGNORE acknowledgment phrases** like "We concur", "We agree", "We acknowledge", "As recommended"
        2. **IGNORE general statements** that don't describe specific actions or deliverables
        3. **FOCUS ON ACTION VERBS** like "will implement", "is meeting", "creating", "developing", "establishing"
        4. **EXTRACT actionable commitments**, not opinions or agreements
        5. **GROUP related actions** together into logical implementation units

        Split actionable content into discrete implementation tasks based on:
        - **Specific actions being taken** (meetings, policy creation, system updates, etc.)
        - **Deliverables being produced** (policies, procedures, reports, etc.)
        - **Process improvements being implemented**
        - **Different responsible parties mentioned**
        - **Different timelines mentioned**
        - **Numbered or bulleted items**

        IMPORTANT GUIDELINES:
        - SKIP non-actionable acknowledgment text ("We concur", "We agree", etc.)
        - FOCUS on what is actually being DONE, not what is being acknowledged
        - Use VERBATIM text but only for the actionable portions
        - GROUP related actions together into coherent work packages

        COVERAGE REQUIREMENT: Ensure all ACTIONABLE content is captured, but exclude acknowledgment statements and general agreements that don't describe specific work.

        EXAMPLE:
        Given: "We concur with the finding. As recommended, the University Controller is meeting with the Property Accounting Office to streamline the process..."

        WRONG: Task 1: "We concur with the finding."
        CORRECT: Task 1: "The University Controller is meeting with the Property Accounting Office to streamline the process..."

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

        Return as JSON array. Each element represents one row in the tracking matrix.
        """

        response = self.bedrock_client.invoke_model(prompt, max_tokens=2000)

        try:
            log_step("SPLIT_TASKS", "INFO", "Parsing task breakdown")
            
            # Handle None response
            if response is None:
                log_step("SPLIT_TASKS", "ERROR", "Received None response from LLM")
                return [{
                    "task_text": management_response,
                    "inferred_department": "To be determined [User input required]",
                    "implementation_type": "To be determined",
                    "requires_collaboration": False,
                    "inferred_division": "",
                    "inferred_vp": [],
                    "inferred_cabinet_member": []
                }]
            
            json_start = response.find("[")
            json_end = response.rfind("]") + 1
            json_str = response[json_start:json_end]
            
            tasks = json.loads(json_str)
            
            # If no tasks identified, return the whole response as one task
            if not tasks:
                tasks = [{
                    "task_text": management_response,
                    "inferred_department": "To be determined [User input required]",
                    "implementation_type": "To be determined",
                    "requires_collaboration": False
                }]
            
            duration = time.time() - start_time
            log_step("SPLIT_TASKS", "END", f"Split into {len(tasks)} tasks in {duration:.2f}s")
            return tasks
            
        except Exception as e:
            duration = time.time() - start_time
            log_step("SPLIT_TASKS", "ERROR", f"Error: {str(e)}")
            # Return whole response as single task on error
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
            
            # Generate step letters (A, B, C, etc.)
            step_letters = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
            
            for task_idx, task in enumerate(tasks):
                # Create observation step (1A, 1B, 1C, etc.)
                if task_idx < len(step_letters):
                    obs_step = f"{obs_num}{step_letters[task_idx]}"
                else:
                    obs_step = f"{obs_num}_{task_idx+1}"
                
                row = {
                    "Observation #": obs_num if task_idx == 0 else None,  # Only show on first row
                    "Observation": obs_title,
                    "Observation Step": obs_step,
                    "Implementation Tasks per Management Response": task.get('task_text', ''),
                    "Severity Rating (per Task)": severity,
                    "Severity Rating (per Observation)": severity if task_idx == 0 else None,
                    "Management/Implementation Type": task.get('implementation_type', 'Process Improvement'),
                    "Department(s) Responsible": task.get('inferred_department', 'To be determined [User input required]'),
                    "Department Collaboration Required?": "Yes" if task.get('requires_collaboration', False) else "No",
                    "Contact": "",  # User to fill
                    "VP": "; ".join(task.get('inferred_vp', [])) if isinstance(task.get('inferred_vp'), list) else task.get('inferred_vp', ''),  # LLM inferred
                    "Division": task.get('inferred_division', ''),  # LLM inferred
                    "Cabinet Member": "; ".join(task.get('inferred_cabinet_member', [])) if isinstance(task.get('inferred_cabinet_member'), list) else task.get('inferred_cabinet_member', ''),  # LLM inferred
                    "Status Notes": f"Generated from audit report - {datetime.now().strftime('%Y-%m-%d')}",
                    "Original Due Date": completion_date if completion_date else "",
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
            # Write main tracking sheet
            df.to_excel(writer, sheet_name="Audit Tracking Matrix", index=False)

            # Get workbook and worksheet
            workbook = writer.book
            worksheet = writer.sheets["Audit Tracking Matrix"]

            # Define formats
            header_format = workbook.add_format(
                {
                    "bold": True,
                    "bg_color": "#003366",  # Cal Poly dark blue
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

            # Format headers
            for col_num, value in enumerate(df.columns.values):
                worksheet.write(0, col_num, value, header_format)

            # Format data cells with conditional formatting for severity
            for row_num in range(1, len(df) + 1):
                for col_num in range(len(df.columns)):
                    cell_value = df.iloc[row_num - 1, col_num]
                    
                    # Apply severity-based formatting
                    if col_num in [4, 5]:  # Severity columns
                        if cell_value == "Significant Issue":
                            worksheet.write(row_num, col_num, cell_value, severity_high)
                        elif cell_value == "Observation for Improvement":
                            worksheet.write(row_num, col_num, cell_value, severity_medium)
                        else:
                            worksheet.write(row_num, col_num, cell_value, cell_format)
                    else:
                        worksheet.write(row_num, col_num, cell_value, cell_format)

            # Set column widths
            column_widths = [
                10,  # Observation #
                30,  # Observation
                12,  # Observation Step
                50,  # Implementation Tasks
                20,  # Severity (per Task)
                20,  # Severity (per Observation)
                25,  # Management Type
                30,  # Departments
                15,  # Collaboration Required
                20,  # Contact
                15,  # VP
                15,  # Division
                20,  # Cabinet Member
                30,  # Status Notes
                15,  # Original Due Date
                15,  # Extended Date 1
                15,  # Extended Date 2
                15,  # Extended Date 3
                20,  # Due Date Status
                30,  # Implementation Status
                25,  # Internal Tracking
                25,  # Audit Committee Status
            ]
            
            for i, width in enumerate(column_widths[:len(df.columns)]):
                worksheet.set_column(i, i, width)

            # Set row height for header
            worksheet.set_row(0, 30)

            # Add summary sheet
            summary_data = {
                "Metric": [
                    "Total Observations",
                    "Total Implementation Tasks",
                    "Significant Issues",
                    "Observations for Improvement",
                    "Tasks Requiring Collaboration",
                    "Report Generation Date",
                ],
                "Value": [
                    df["Observation #"].nunique(),
                    len(df),
                    len(df[df["Severity Rating (per Observation)"] == "Significant Issue"]),
                    len(df[df["Severity Rating (per Observation)"] == "Observation for Improvement"]),
                    len(df[df["Department Collaboration Required?"] == "Yes"]),
                    datetime.now().strftime("%Y-%m-%d %H:%M"),
                ],
            }
            
            summary_df = pd.DataFrame(summary_data)
            summary_df.to_excel(writer, sheet_name="Summary", index=False)

            # Format summary sheet
            summary_worksheet = writer.sheets["Summary"]
            for col_num, value in enumerate(summary_df.columns.values):
                summary_worksheet.write(0, col_num, value, header_format)
            
            summary_worksheet.set_column(0, 0, 30)
            summary_worksheet.set_column(1, 1, 30)

        buffer.seek(0)
        duration = time.time() - start_time
        log_step("EXCEL_EXPORT", "END", f"Excel file created in {duration:.2f}s")
        return buffer

def main():
    log_step("APPLICATION_START", "START", "Initializing Cal Poly AuditEngine")
    
    st.title("Cal Poly AuditEngine")
    st.markdown("Transform audit reports into actionable tracking matrices with AI assistance")

    # Initialize session state
    if "bedrock_client" not in st.session_state:
        st.session_state.bedrock_client = BedrockClient()
    if "processor" not in st.session_state:
        st.session_state.processor = AuditDocumentProcessor(st.session_state.bedrock_client)
    if "matrix_generator" not in st.session_state:
        st.session_state.matrix_generator = AuditTrackingMatrix()
    if "observations_with_tasks" not in st.session_state:
        st.session_state.observations_with_tasks = []
    if "current_matrix" not in st.session_state:
        st.session_state.current_matrix = None

    # Main layout
    col1, col2 = st.columns([2, 1])

    with col1:
        st.header("Step 1: Upload Audit Report")
        uploaded_file = st.file_uploader(
            "Upload your audit report PDF",
            type=["pdf"],
            help="The system will extract observations and management responses directly from the document"
        )

        if uploaded_file is not None:
            log_step("FILE_UPLOAD", "END", f"File: {uploaded_file.name}")
            
            if st.button("Extract Observations & Management Responses", type="primary", use_container_width=True):
                with st.spinner("Reading PDF..."):
                    audit_text = st.session_state.processor.extract_pdf_text(uploaded_file)

                if audit_text:
                    with st.spinner("Extracting observations and management responses..."):
                        observations = st.session_state.processor.extract_observations_and_responses(audit_text)

                    if observations:
                        st.success(f"Extracted {len(observations)} observations")
                        
                        # Process each observation to split into tasks
                        observations_with_tasks = []
                        progress_bar = st.progress(0)
                        
                        for i, obs in enumerate(observations):
                            st.write(f"Processing observation {i+1}: {obs.get('observation_title', 'Unnamed')}")
                            tasks = st.session_state.processor.split_management_response_into_tasks(obs)
                            observations_with_tasks.append((obs, tasks))
                            progress_bar.progress((i + 1) / len(observations))
                        
                        st.session_state.observations_with_tasks = observations_with_tasks
                        st.success("Processing complete! Review and edit below.")
                        st.rerun()

        # Review and Edit Section
        if st.session_state.observations_with_tasks:
            st.markdown("---")
            st.header("Step 2: Review & Edit Extracted Information")
            st.info("Review the extracted information. The system has preserved the verbatim management responses and suggested task breakdowns.")

            # Summary metrics
            total_tasks = sum(len(tasks) for _, tasks in st.session_state.observations_with_tasks)
            col_a, col_b, col_c = st.columns(3)
            with col_a:
                st.metric("Observations", len(st.session_state.observations_with_tasks))
            with col_b:
                st.metric("Total Tasks", total_tasks)
            with col_c:
                st.metric("Average Tasks/Observation", f"{total_tasks/len(st.session_state.observations_with_tasks):.1f}")

            edited_observations_with_tasks = []

            for obs_idx, (observation, tasks) in enumerate(st.session_state.observations_with_tasks):
                with st.expander(f"Observation {obs_idx+1}: {observation.get('observation_title', 'Unnamed')}", expanded=(obs_idx < 2)):
                    
                    # Observation details (read-only for reference)
                    st.markdown("### Observation Details")
                    st.text_area(
                        "Description",
                        value=observation.get('observation_description', ''),
                        disabled=True,
                        height=100,
                        key=f"desc_{obs_idx}"
                    )
                    
                    # Severity selection
                    severity_options = ["Significant Issue", "Observation for Improvement"]
                    current_severity = observation.get('severity', 'Observation for Improvement')
                    if current_severity not in severity_options:
                        current_severity = "Observation for Improvement"
                    
                    severity = st.selectbox(
                        "Severity Rating",
                        options=severity_options,
                        index=severity_options.index(current_severity),
                        key=f"severity_{obs_idx}"
                    )
                    
                    st.markdown("### Management Response Tasks")
                    st.markdown("*Below are the verbatim excerpts from the management response, split into trackable tasks:*")
                    
                    edited_tasks = []
                    for task_idx, task in enumerate(tasks):
                        st.markdown(f"#### Task {chr(65 + task_idx)} (Step {obs_idx+1}{chr(65 + task_idx)})")
                        
                        # Show the verbatim text (non-editable to preserve traceability)
                        st.text_area(
                            "Management Response Text (Verbatim)",
                            value=task.get('task_text', ''),
                            disabled=True,
                            height=100,
                            key=f"task_text_{obs_idx}_{task_idx}"
                        )
                        
                        col_left, col_right = st.columns(2)
                        
                        with col_left:
                            # Department - editable
                            dept = st.text_input(
                                "Department(s) Responsible",
                                value=task.get('inferred_department', ''),
                                key=f"dept_{obs_idx}_{task_idx}",
                                help="AI suggestion - please verify and update"
                            )
                            
                            # Implementation type
                            impl_type = st.selectbox(
                                "Implementation Type",
                                options=[
                                    "Process Improvement",
                                    "Policy Change",
                                    "Process Assessment/Evaluation",
                                    "New Process Implementation",
                                    "Communication/Reinforcement",
                                    "Remediation",
                                    "Other"
                                ],
                                index=0,
                                key=f"impl_type_{obs_idx}_{task_idx}"
                            )
                        
                        with col_right:
                            # Contact - user input
                            contact = st.text_input(
                                "Contact Person",
                                placeholder="Enter name/title",
                                key=f"contact_{obs_idx}_{task_idx}"
                            )
                            
                            # Collaboration required
                            collab = st.checkbox(
                                "Department Collaboration Required?",
                                value=task.get('requires_collaboration', False),
                                key=f"collab_{obs_idx}_{task_idx}"
                            )
                        
                        # Division selection
                        division_options = [
                            "Academic Affairs",
                            "Administration and Finance", 
                            "Information Technology Services",
                            "Research",
                            "Strategic Enrollment Management",
                            "Student Affairs",
                            "University Communications and Marketing",
                            "University Development and Alumni Engagement",
                            "University Office of Diversity and Inclusion",
                            "University Personnel",
                            "Other"
                        ]
                        
                        current_division = task.get('inferred_division', '')
                        if current_division and current_division in division_options:
                            division_index = division_options.index(current_division)
                        else:
                            division_index = len(division_options) - 1  # Default to "Other"
                        
                        division_selection = st.selectbox(
                            "Division",
                            options=division_options,
                            index=division_index,
                            key=f"division_{obs_idx}_{task_idx}"
                        )
                        
                        # If "Other" is selected, show text input
                        if division_selection == "Other":
                            division = st.text_input(
                                "Specify Division",
                                value=current_division if current_division not in division_options[:-1] else '',
                                key=f"division_other_{obs_idx}_{task_idx}"
                            )
                        else:
                            division = division_selection
                        
                        # VP selection (multiple)
                        vp_options = [
                            "President",
                            "Interim Provost and Executive Vice President for Academic Affairs",
                            "Senior Vice President, Administration and Finance, Chief Financial Officer (CFO)",
                            "Vice President & CEO of Cal Poly Solano Campus",
                            "Interim Vice President University Personnel and Chief Human Resources Officer",
                            "Vice President for Strategic Initiatives and Advocacy",
                            "Chief of Staff",
                            "Vice President of Strategic Enrollment Management and Student Affairs",
                            "Vice President, Information Technology and Chief Information Officer (CIO)",
                            "Vice President, Facilities Management and Development",
                            "Vice President, University Communications and Marketing",
                            "CEO, Cal Poly Partners",
                            "Vice President, University Development & Alumni Engagement and CEO of the Cal Poly Foundation",
                            "University Counsel"
                        ]
                        
                        current_vp = task.get('inferred_vp', [])
                        if isinstance(current_vp, str):
                            current_vp = [current_vp] if current_vp else []
                        
                        vp_selection = st.multiselect(
                            "VP (select multiple if applicable)",
                            options=vp_options,
                            default=[vp for vp in current_vp if vp in vp_options],
                            key=f"vp_{obs_idx}_{task_idx}"
                        )
                        
                        # Cabinet Member selection (multiple)
                        cabinet_selection = st.multiselect(
                            "Cabinet Member (select multiple if applicable)",
                            options=vp_options,  # Same list as VP
                            default=[cm for cm in task.get('inferred_cabinet_member', []) if isinstance(task.get('inferred_cabinet_member'), list) and cm in vp_options] if isinstance(task.get('inferred_cabinet_member'), list) else ([task.get('inferred_cabinet_member')] if task.get('inferred_cabinet_member') and task.get('inferred_cabinet_member') in vp_options else []),
                            key=f"cabinet_{obs_idx}_{task_idx}"
                        )
                        
                        # Due date with shortcuts
                        col_date, col_shortcuts = st.columns([2, 1])
                        
                        # Check for date shortcut selections
                        date_key = f"selected_date_{obs_idx}_{task_idx}"
                        
                        with col_shortcuts:
                            st.write("Quick dates:")
                            from datetime import datetime, timedelta
                            today = datetime.now().date()
                            
                            btn_col1, btn_col2, btn_col3 = st.columns(3)
                            with btn_col1:
                                if st.button("30d", key=f"date_30_{obs_idx}_{task_idx}"):
                                    st.session_state[date_key] = today + timedelta(days=30)
                            with btn_col2:
                                if st.button("60d", key=f"date_60_{obs_idx}_{task_idx}"):
                                    st.session_state[date_key] = today + timedelta(days=60)
                            with btn_col3:
                                if st.button("90d", key=f"date_90_{obs_idx}_{task_idx}"):
                                    st.session_state[date_key] = today + timedelta(days=90)
                        
                        with col_date:
                            due_date = st.date_input(
                                "Target Completion Date",
                                value=st.session_state.get(date_key, None),
                                key=f"date_{obs_idx}_{task_idx}"
                            )
                        
                        edited_task = {
                            'task_text': task.get('task_text', ''),
                            'inferred_department': dept,
                            'implementation_type': impl_type,
                            'requires_collaboration': collab,
                            'contact': contact,
                            'inferred_division': division,
                            'inferred_vp': vp_selection,
                            'inferred_cabinet_member': cabinet_selection,
                            'due_date': due_date.strftime('%m/%d/%Y') if due_date else ''
                        }
                        edited_tasks.append(edited_task)
                    
                    # Update observation with edited severity
                    edited_observation = observation.copy()
                    edited_observation['severity'] = severity
                    
                    edited_observations_with_tasks.append((edited_observation, edited_tasks))

            st.session_state.edited_observations_with_tasks = edited_observations_with_tasks

            st.markdown("---")
            if st.button("Generate Evidence Request Matrix", type="primary", use_container_width=True):
                with st.spinner("Generating tracking matrix..."):
                    matrix_df = st.session_state.matrix_generator.create_matrix_from_observations(
                        st.session_state.edited_observations_with_tasks
                    )
                    
                    # Update contact and due date information from edited data
                    row_idx = 0
                    for obs_idx, (obs, tasks) in enumerate(st.session_state.edited_observations_with_tasks):
                        for task in tasks:
                            if row_idx < len(matrix_df):
                                matrix_df.at[row_idx, 'Contact'] = task.get('contact', '')
                                if task.get('due_date'):
                                    matrix_df.at[row_idx, 'Original Due Date'] = task.get('due_date')
                                row_idx += 1
                    
                    st.session_state.current_matrix = matrix_df
                    st.success("Matrix generated successfully!")
                    st.rerun()

        # Display Generated Matrix
        if st.session_state.current_matrix is not None:
            st.markdown("---")
            st.header("Step 3: Review and Export Matrix")

            # Display metrics
            col_a, col_b, col_c, col_d = st.columns(4)
            with col_a:
                st.metric("Total Rows", len(st.session_state.current_matrix))
            with col_b:
                unique_obs = st.session_state.current_matrix["Observation #"].nunique()
                st.metric("Observations", unique_obs)
            with col_c:
                sig_issues = len(st.session_state.current_matrix[
                    st.session_state.current_matrix["Severity Rating (per Observation)"] == "Significant Issue"
                ])
                st.metric("Significant Issues", sig_issues)
            with col_d:
                collab_required = len(st.session_state.current_matrix[
                    st.session_state.current_matrix["Department Collaboration Required?"] == "Yes"
                ])
                st.metric("Requiring Collaboration", collab_required)

            # Display the matrix
            st.dataframe(st.session_state.current_matrix, use_container_width=True, height=400)

            # Export options
            st.markdown("### Export Options")
            audit_title = st.text_input(
                "Audit Title for Export",
                value="Audit Evidence Request Matrix",
                placeholder="Enter audit name"
            )

            col_export, col_reset = st.columns(2)
            
            with col_export:
                if st.button("Generate Excel File", type="secondary", use_container_width=True):
                    with st.spinner("Creating Excel file..."):
                        excel_buffer = st.session_state.matrix_generator.export_to_excel(
                            st.session_state.current_matrix, audit_title
                        )
                    
                    filename = f"{audit_title.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
                    
                    st.download_button(
                        label="Download Excel File",
                        data=excel_buffer.getvalue(),
                        file_name=filename,
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True
                    )
                    st.success("Excel file ready for download!")

            with col_reset:
                if st.button("Start New Analysis", use_container_width=True):
                    # Reset session state
                    for key in ['observations_with_tasks', 'edited_observations_with_tasks', 'current_matrix']:
                        if key in st.session_state:
                            del st.session_state[key]
                    st.rerun()

    with col2:
        pass

if __name__ == "__main__":
    main()