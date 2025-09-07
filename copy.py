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
from typing import Dict, List, Any, Optional
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
        print(f"{Fore.BLUE}[{timestamp}] 🚀 {step_name} - STARTED{Style.RESET_ALL}")
        logger.info(f"{step_name} - STARTED - {details}")
    elif status == "END":
        print(f"{Fore.GREEN}[{timestamp}] ✅ {step_name} - COMPLETED{Style.RESET_ALL}")
        logger.info(f"{step_name} - COMPLETED - {details}")
    elif status == "ERROR":
        print(f"{Fore.RED}[{timestamp}] ❌ {step_name} - ERROR{Style.RESET_ALL}")
        logger.error(f"{step_name} - ERROR - {details}")
    elif status == "INFO":
        print(f"{Fore.YELLOW}[{timestamp}] ℹ️  {step_name} - INFO{Style.RESET_ALL}")
        logger.info(f"{step_name} - INFO - {details}")

def log_llm_interaction(prompt: str, response: str, model_id: str, duration: float):
    """Log LLM interactions with detailed info"""
    print(f"{Fore.MAGENTA}[LLM] Model: {model_id} | Duration: {duration:.2f}s{Style.RESET_ALL}")
    print(f"{Fore.CYAN}[LLM INPUT] Length: {len(prompt)} chars{Style.RESET_ALL}")
    logger.info(f"LLM_INPUT - Model: {model_id} - Prompt length: {len(prompt)} - Prompt: {prompt[:500]}...")
    print(f"{Fore.CYAN}[LLM OUTPUT] Length: {len(response)} chars{Style.RESET_ALL}")
    logger.info(f"LLM_OUTPUT - Response length: {len(response)} - Response: {response[:500]}...")

# Configure Streamlit page
st.set_page_config(
    page_title="Cal Poly Audit Evidence Tracker",
    page_icon=None,
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
        log_step("LLM_INVOCATION", "START", f"Model: {self.model_id}, Max tokens: {max_tokens}")
        
        try:
            body = json.dumps(
                {
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": max_tokens,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.3,
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
            
            return result

        except Exception as e:
            duration = time.time() - start_time
            log_step("LLM_INVOCATION", "ERROR", f"Error: {str(e)}, Duration: {duration:.2f}s")
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
                text += page_text + "\n"
                if i % 5 == 0:  # Log every 5 pages
                    log_step("PDF_TEXT_EXTRACTION", "INFO", f"Processed page {i+1}/{page_count}")
            
            duration = time.time() - start_time
            log_step("PDF_TEXT_EXTRACTION", "END", f"Extracted {len(text)} chars in {duration:.2f}s")
            return text
            
        except Exception as e:
            duration = time.time() - start_time
            log_step("PDF_TEXT_EXTRACTION", "ERROR", f"Error: {str(e)}, Duration: {duration:.2f}s")
            st.error(f"Error extracting PDF text: {str(e)}")
            return ""

    def parse_audit_observations(self, audit_text: str) -> List[Dict]:
        """Use LLM to parse audit observations from text"""
        start_time = time.time()
        log_step("PARSE_OBSERVATIONS", "START", f"Text length: {len(audit_text)} chars")

        prompt = f"""
        You are an expert audit analyst. Please analyze the following audit report text and extract all observations/findings in a structured format.

        For each observation found, extract:
        1. Observation number (if available)
        2. Observation title/name
        3. Description of the observation/finding
        4. Recommendations made
        5. Management response (if available)
        6. Implementation tasks mentioned in management response
        7. Due dates mentioned (if any)
        8. Departments/roles mentioned as responsible
        9. Severity level (if mentioned or can be inferred)

        Return the result as a JSON array where each observation is an object with the above fields.

        Audit Report Text:
        {audit_text}

        Please ensure the JSON is valid and properly formatted.
        """

        response = self.bedrock_client.invoke_model(prompt, max_tokens=4000)

        try:
            log_step("PARSE_OBSERVATIONS", "INFO", "Parsing JSON response")
            # Extract JSON from response
            json_start = response.find("[")
            json_end = response.rfind("]") + 1
            json_str = response[json_start:json_end]

            observations = json.loads(json_str)
            duration = time.time() - start_time
            log_step("PARSE_OBSERVATIONS", "END", f"Found {len(observations)} observations in {duration:.2f}s")
            return observations
            
        except Exception as e:
            duration = time.time() - start_time
            log_step("PARSE_OBSERVATIONS", "ERROR", f"JSON parsing error: {str(e)}, Duration: {duration:.2f}s")
            st.error(f"Error parsing LLM response: {str(e)}")
            return []

    def generate_implementation_suggestions(self, observation: Dict) -> Dict:
        """Generate implementation suggestions for an observation"""
        start_time = time.time()
        obs_title = observation.get('title', 'N/A')
        log_step("GENERATE_SUGGESTIONS", "START", f"Observation: {obs_title}")

        prompt = f"""
        You are an expert audit implementation consultant. Based on the following audit observation, suggest implementation details:

        Observation: {observation.get('title', 'N/A')}
        Description: {observation.get('description', 'N/A')}
        Recommendations: {observation.get('recommendations', 'N/A')}
        Management Response: {observation.get('management_response', 'N/A')}

        Please provide suggestions for:
        1. Specific implementation tasks (break down into actionable steps)
        2. Likely responsible departments (be specific to university context)
        3. Estimated timeline for implementation
        4. Potential contacts or roles who should be involved
        5. Evidence that will be needed to verify completion
        6. Risk level (High/Medium/Low) based on the nature of the finding

        Return as JSON with these fields: implementation_tasks, responsible_departments, timeline_estimate, key_contacts, evidence_needed, risk_level, collaboration_required
        """

        response = self.bedrock_client.invoke_model(prompt, max_tokens=2000)

        try:
            log_step("GENERATE_SUGGESTIONS", "INFO", f"Parsing suggestions for: {obs_title}")
            json_start = response.find("{")
            json_end = response.rfind("}") + 1
            json_str = response[json_start:json_end]

            suggestions = json.loads(json_str)
            duration = time.time() - start_time
            log_step("GENERATE_SUGGESTIONS", "END", f"Generated suggestions in {duration:.2f}s")
            return suggestions
            
        except Exception as e:
            duration = time.time() - start_time
            log_step("GENERATE_SUGGESTIONS", "ERROR", f"Parsing error: {str(e)}, Duration: {duration:.2f}s")
            st.warning(f"Could not parse implementation suggestions: {str(e)}")
            return {}


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

    def create_matrix_from_observations(
        self, observations: List[Dict], suggestions: List[Dict]
    ) -> pd.DataFrame:
        """Create tracking matrix DataFrame from observations"""
        start_time = time.time()
        log_step("CREATE_MATRIX", "START", f"Processing {len(observations)} observations")

        rows = []

        for i, obs in enumerate(observations):
            log_step("CREATE_MATRIX", "INFO", f"Processing observation {i+1}: {obs.get('title', 'Unnamed')}")
            suggestion = suggestions[i] if i < len(suggestions) else {}

            # Split implementation tasks if multiple
            tasks = suggestion.get("implementation_tasks", [])
            if isinstance(tasks, str):
                tasks = [tasks]
            elif isinstance(tasks, list):
                # Handle list items that might be strings or dictionaries
                string_tasks = []
                for task in tasks:
                    if isinstance(task, str):
                        string_tasks.append(task)
                    elif isinstance(task, dict):
                        # If it's a dict, try to extract meaningful text
                        if "task" in task:
                            string_tasks.append(task["task"])
                        elif "description" in task:
                            string_tasks.append(task["description"])
                        else:
                            # Convert the entire dict to a readable string
                            string_tasks.append(str(task))
                    else:
                        string_tasks.append(str(task))
                tasks = string_tasks

            if not tasks:
                tasks = ["Implementation task to be defined"]

            log_step("CREATE_MATRIX", "INFO", f"Creating {len(tasks)} rows for observation {i+1}")

            for j, task in enumerate(tasks):
                row = {
                    "Observation #": i + 1 if j == 0 else None,
                    "Observation": obs.get("title", "Observation title needed"),
                    "Observation Step": (
                        f"{i+1}{'ABCDEFGHIJ'[j]}" if j < 10 else f"{i+1}_{j+1}"
                    ),
                    "Implementation Tasks per Management Response": task,
                    "Severity Rating (per Task)": suggestion.get(
                        "risk_level", "To be determined"
                    ),
                    "Severity Rating (per Observation)": suggestion.get(
                        "risk_level", "To be determined"
                    ),
                    "Management/Implementation Type": "Process Improvement",  # Default
                    "Department(s) Responsible": ", ".join(
                        suggestion.get("responsible_departments", ["To be determined"])
                    ),
                    "Department Collaboration Required?": (
                        "Yes"
                        if suggestion.get("collaboration_required", True)
                        else "No"
                    ),
                    "Contact": "To be assigned",
                    "VP": "To be determined",
                    "Division": "To be determined",
                    "Cabinet Member": "To be determined",
                    "Status Notes": f"Generated from audit analysis - {datetime.now().strftime('%Y-%m-%d')}",
                    "Original Due Date": self._estimate_due_date(
                        suggestion.get("timeline_estimate", "90 days")
                    ),
                    "Extended Due Date 1": None,
                    "Extended Due Date 2": None,
                    "Extended Due Date 3": None,
                    "Due Date Status": "Not Started",
                    "Implementation Response Status": "Pending management review",
                    "Internal Tracking per Task": "Not Started",
                    "Audit Committee Reporting Status": "Not Started",
                }
                rows.append(row)

        df = pd.DataFrame(rows)
        duration = time.time() - start_time
        log_step("CREATE_MATRIX", "END", f"Created matrix with {len(df)} rows in {duration:.2f}s")
        return df

    def _estimate_due_date(self, timeline_str: str) -> str:
        """Estimate due date from timeline string"""
        try:
            # Extract number of days/months from timeline
            import re

            days_match = re.search(r"(\d+)\s*days?", timeline_str.lower())
            months_match = re.search(r"(\d+)\s*months?", timeline_str.lower())

            if days_match:
                days = int(days_match.group(1))
                due_date = datetime.now() + timedelta(days=days)
            elif months_match:
                months = int(months_match.group(1))
                due_date = datetime.now() + timedelta(
                    days=months * 30
                )  # Rough estimate
            else:
                # Default to 90 days
                due_date = datetime.now() + timedelta(days=90)

            return due_date.strftime("%Y-%m-%d")
        except:
            # Default to 90 days from now
            return (datetime.now() + timedelta(days=90)).strftime("%Y-%m-%d")

    def export_to_excel(self, df: pd.DataFrame, audit_title: str) -> BytesIO:
        """Export DataFrame to Excel file"""
        start_time = time.time()
        log_step("EXCEL_EXPORT", "START", f"Exporting {len(df)} rows to Excel")

        buffer = BytesIO()

        with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
            # Write main tracking sheet
            df.to_excel(writer, sheet_name="Audit Tracking Matrix", index=False)

            # Get workbook and worksheet
            workbook = writer.book
            worksheet = writer.sheets["Audit Tracking Matrix"]

            # Define formats
            header_format = workbook.add_format(
                {
                    "bold": True,
                    "bg_color": "#4CAF50",
                    "font_color": "white",
                    "border": 1,
                    "text_wrap": True,
                    "valign": "top",
                }
            )

            cell_format = workbook.add_format(
                {"text_wrap": True, "valign": "top", "border": 1}
            )

            # Format headers
            for col_num, value in enumerate(df.columns.values):
                worksheet.write(0, col_num, value, header_format)

            # Format data cells
            for row_num in range(1, len(df) + 1):
                for col_num in range(len(df.columns)):
                    worksheet.write(
                        row_num, col_num, df.iloc[row_num - 1, col_num], cell_format
                    )

            # Set column widths
            column_widths = [
                10,
                25,
                12,
                40,
                20,
                20,
                25,
                25,
                15,
                20,
                15,
                15,
                15,
                30,
                15,
                15,
                15,
                15,
                20,
                30,
                20,
                20,
            ]
            for i, width in enumerate(column_widths[: len(df.columns)]):
                worksheet.set_column(i, i, width)

            # Add summary sheet
            summary_df = pd.DataFrame(
                {
                    "Metric": [
                        "Total Observations",
                        "Total Implementation Tasks",
                        "High Risk Items",
                        "Medium Risk Items",
                        "Low Risk Items",
                        "Average Timeline (Days)",
                    ],
                    "Value": [
                        df["Observation #"].nunique(),
                        len(df),
                        len(df[df["Severity Rating (per Task)"] == "High"]),
                        len(df[df["Severity Rating (per Task)"] == "Medium"]),
                        len(df[df["Severity Rating (per Task)"] == "Low"]),
                        90,  # Default average
                    ],
                }
            )

            summary_df.to_excel(writer, sheet_name="Summary", index=False)

        buffer.seek(0)
        duration = time.time() - start_time
        log_step("EXCEL_EXPORT", "END", f"Excel file created in {duration:.2f}s")
        return buffer


def main():
    log_step("APPLICATION_START", "START", "Initializing Cal Poly AuditEngine")
    
    st.title("Cal Poly AuditEngine")
    st.markdown(
        "**Transform audit reports into actionable evidence request matrices instantly**"
    )

    # Initialize session state
    if "bedrock_client" not in st.session_state:
        log_step("BEDROCK_INIT", "START", "Initializing Bedrock client")
        st.session_state.bedrock_client = BedrockClient()
        log_step("BEDROCK_INIT", "END", "Bedrock client initialized")

    if "processor" not in st.session_state:
        log_step("PROCESSOR_INIT", "START", "Initializing document processor")
        st.session_state.processor = AuditDocumentProcessor(
            st.session_state.bedrock_client
        )
        log_step("PROCESSOR_INIT", "END", "Document processor initialized")

    if "matrix_generator" not in st.session_state:
        log_step("MATRIX_INIT", "START", "Initializing matrix generator")
        st.session_state.matrix_generator = AuditTrackingMatrix()
        log_step("MATRIX_INIT", "END", "Matrix generator initialized")

    if "current_observations" not in st.session_state:
        st.session_state.current_observations = []

    if "current_matrix" not in st.session_state:
        st.session_state.current_matrix = None

    if "processing_stage" not in st.session_state:
        st.session_state.processing_stage = "upload"

    # Progress indicator
    stages = ["Upload", "AI Analysis", "Review & Edit", "Generate Matrix"]
    current_stage_index = (
        stages.index(st.session_state.processing_stage.replace("_", " ").title())
        if st.session_state.processing_stage.replace("_", " ").title() in stages
        else 0
    )

    cols = st.columns(len(stages))
    for i, stage in enumerate(stages):
        with cols[i]:
            if i <= current_stage_index:
                st.markdown(f"**{stage}**")
            else:
                st.markdown(f"{stage}")

    st.markdown("---")

    # Main workflow
    col1, col2 = st.columns([2, 1])

    with col1:
        # Upload Section
        st.header("Upload Audit Report")
        uploaded_file = st.file_uploader(
            "Drop your audit report PDF here",
            type=["pdf"],
            help="Upload the audit report PDF to automatically extract observations and generate evidence requests",
        )

        if uploaded_file is not None:
            log_step("FILE_UPLOAD", "END", f"File uploaded: {uploaded_file.name}, Size: {uploaded_file.size} bytes")
            st.success("File uploaded successfully!")

            if st.button(
                "Analyze with AI", type="primary", use_container_width=True
            ):
                log_step("AI_ANALYSIS_WORKFLOW", "START", "Starting AI analysis workflow")
                
                with st.spinner("Extracting text from PDF..."):
                    audit_text = st.session_state.processor.extract_pdf_text(
                        uploaded_file
                    )

                if audit_text:
                    st.success(f"Extracted {len(audit_text):,} characters from PDF")

                    with st.spinner(
                        "AI is analyzing audit observations... This may take 30-60 seconds."
                    ):
                        observations = (
                            st.session_state.processor.parse_audit_observations(
                                audit_text
                            )
                        )

                    if observations:
                        st.session_state.current_observations = observations
                        st.session_state.processing_stage = "ai_analysis"

                        # Generate implementation suggestions immediately
                        suggestions = []
                        progress_bar = st.progress(0)
                        st.write("Generating implementation suggestions...")
                        
                        log_step("SUGGESTIONS_BATCH", "START", f"Generating suggestions for {len(observations)} observations")

                        for i, obs in enumerate(observations):
                            suggestion = st.session_state.processor.generate_implementation_suggestions(
                                obs
                            )
                            suggestions.append(suggestion)
                            progress_bar.progress((i + 1) / len(observations))

                        st.session_state.implementation_suggestions = suggestions
                        st.session_state.processing_stage = "review_edit"
                        
                        log_step("AI_ANALYSIS_WORKFLOW", "END", f"Analysis complete: {len(observations)} observations processed")
                        st.success(
                            f"Successfully extracted {len(observations)} observations!"
                        )
                        st.rerun()
                    else:
                        log_step("AI_ANALYSIS_WORKFLOW", "ERROR", "No observations extracted from document")
                        st.error(
                            "No observations were extracted. Please check the document format."
                        )

        # Review and Edit Section
        if (
            hasattr(st.session_state, "implementation_suggestions")
            and st.session_state.current_observations
        ):
            st.markdown("---")
            st.header("Review & Edit AI Suggestions")
            st.info(
                "The AI has made its best guesses, but your expertise is needed to refine department assignments, contacts, and timelines!"
            )

            # Quick summary
            col_a, col_b, col_c = st.columns(3)
            with col_a:
                st.metric(
                    "Observations Found", len(st.session_state.current_observations)
                )
            with col_b:
                total_tasks = sum(
                    len(s.get("implementation_tasks", []))
                    for s in st.session_state.implementation_suggestions
                )
                st.metric("Implementation Tasks", total_tasks)
            with col_c:
                high_risk_count = sum(
                    1
                    for s in st.session_state.implementation_suggestions
                    if s.get("risk_level") == "High"
                )
                st.metric("High Risk Items", high_risk_count)

            edited_observations = []
            edited_suggestions = []

            # Department options - Fixed to match actual Cal Poly departments
            cal_poly_departments = [
                "Administration & Finance",
                "Academic Affairs",
                "Student Affairs",
                "University Advancement",
                "Property Accounting Office",
                "University Accounting and Reporting",
                "Strategic Business Services",
                "Information Technology Services",
                "Facilities Management",
                "Risk Management",
                "Procurement Services",
                "Distribution Services",
                "Human Resources",
                "Environmental Health & Safety",
                "Other",
            ]

            for i, (obs, suggestion) in enumerate(
                zip(
                    st.session_state.current_observations,
                    st.session_state.implementation_suggestions,
                )
            ):
                with st.expander(
                    f"Observation {i+1}: {obs.get('title', 'Unnamed Observation')}",
                    expanded=i < 3,
                ):
                    col_left, col_right = st.columns(2)

                    with col_left:
                        st.markdown("**Observation Details**")

                        edited_title = st.text_input(
                            "Title", value=obs.get("title", ""), key=f"title_{i}"
                        )

                        edited_description = st.text_area(
                            "Description",
                            value=obs.get("description", ""),
                            key=f"desc_{i}",
                            height=100,
                        )

                        edited_recommendations = st.text_area(
                            "Recommendations",
                            value=obs.get("recommendations", ""),
                            key=f"rec_{i}",
                            height=100,
                        )

                    with col_right:
                        st.markdown("**Implementation Planning**")

                        # Department selection - Fixed to use valid defaults
                        suggested_depts = suggestion.get("responsible_departments", [])
                        if isinstance(suggested_depts, str):
                            suggested_depts = [suggested_depts]

                        # Filter suggested departments to only include valid options
                        valid_defaults = [
                            dept
                            for dept in suggested_depts
                            if dept in cal_poly_departments
                        ]
                        if not valid_defaults and suggested_depts:
                            valid_defaults = ["Other"]  # Default fallback

                        departments = st.multiselect(
                            "Responsible Departments",
                            options=cal_poly_departments,
                            default=valid_defaults,
                            key=f"depts_{i}",
                        )

                        # Contact information
                        contact = st.text_input(
                            "Primary Contact",
                            value=(
                                suggestion.get("key_contacts", [""])[0]
                                if suggestion.get("key_contacts")
                                else ""
                            ),
                            placeholder="e.g., Controller, Director",
                            key=f"contact_{i}",
                        )

                        col_risk, col_time = st.columns(2)
                        with col_risk:
                            risk_level = st.selectbox(
                                "Risk Level",
                                options=["High", "Medium", "Low"],
                                index=["High", "Medium", "Low"].index(
                                    suggestion.get("risk_level", "Medium")
                                ),
                                key=f"risk_{i}",
                            )

                        with col_time:
                            timeline = st.selectbox(
                                "Timeline",
                                options=[
                                    "30 days",
                                    "60 days",
                                    "90 days",
                                    "6 months",
                                    "1 year",
                                ],
                                index=2,  # Default to 90 days
                                key=f"timeline_{i}",
                            )

                        # Implementation tasks
                        tasks_value = suggestion.get("implementation_tasks", [])
                        if isinstance(tasks_value, list):
                            # Handle list items that might be strings or dictionaries
                            string_tasks = []
                            for task in tasks_value:
                                if isinstance(task, str):
                                    string_tasks.append(task)
                                elif isinstance(task, dict):
                                    # If it's a dict, try to extract meaningful text
                                    if "task" in task:
                                        string_tasks.append(task["task"])
                                    elif "description" in task:
                                        string_tasks.append(task["description"])
                                    else:
                                        # Convert the entire dict to a readable string
                                        string_tasks.append(str(task))
                                else:
                                    string_tasks.append(str(task))
                            tasks_text = "\n".join(string_tasks)
                        else:
                            tasks_text = str(tasks_value)

                        tasks = st.text_area(
                            "Implementation Tasks (one per line)",
                            value=tasks_text,
                            key=f"tasks_{i}",
                            height=120,
                        )

                    # Store edited data
                    edited_obs = {
                        "title": edited_title,
                        "description": edited_description,
                        "recommendations": edited_recommendations,
                    }

                    edited_suggestion = {
                        "responsible_departments": departments,
                        "key_contacts": [contact] if contact else [],
                        "risk_level": risk_level,
                        "timeline_estimate": timeline,
                        "implementation_tasks": [
                            task.strip() for task in tasks.split("\n") if task.strip()
                        ],
                        "collaboration_required": len(departments) > 1,
                    }

                    edited_observations.append(edited_obs)
                    edited_suggestions.append(edited_suggestion)

            # Store edited data in session state
            st.session_state.edited_observations = edited_observations
            st.session_state.edited_suggestions = edited_suggestions

            st.markdown("---")
            if st.button(
                "Generate Evidence Request Matrix",
                type="primary",
                use_container_width=True,
            ):
                log_step("MATRIX_GENERATION", "START", f"Generating matrix from {len(edited_observations)} observations")
                
                with st.spinner("Generating tracking matrix..."):
                    matrix_df = st.session_state.matrix_generator.create_matrix_from_observations(
                        edited_observations, edited_suggestions
                    )
                    st.session_state.current_matrix = matrix_df
                    st.session_state.processing_stage = "generate_matrix"
                    
                log_step("MATRIX_GENERATION", "END", f"Matrix generated with {len(matrix_df)} rows")
                st.success("Matrix generated successfully!")
                st.rerun()

        # Matrix Results Section
        if st.session_state.current_matrix is not None:
            st.markdown("---")
            st.header("Evidence Request Matrix")

            # Summary metrics
            col_a, col_b, col_c, col_d = st.columns(4)
            with col_a:
                st.metric(
                    "Total Observations",
                    st.session_state.current_matrix["Observation #"].nunique(),
                )
            with col_b:
                st.metric("Evidence Requests", len(st.session_state.current_matrix))
            with col_c:
                high_risk = len(
                    st.session_state.current_matrix[
                        st.session_state.current_matrix["Severity Rating (per Task)"]
                        == "High"
                    ]
                )
                st.metric(
                    "High Priority",
                    high_risk,
                    delta=f"{(high_risk/len(st.session_state.current_matrix)*100):.0f}%",
                )
            with col_d:
                unique_depts = len(
                    set(
                        [
                            dept.strip()
                            for depts in st.session_state.current_matrix[
                                "Department(s) Responsible"
                            ]
                            .fillna("")
                            .tolist()
                            for dept in depts.split(",")
                            if dept.strip()
                        ]
                    )
                )
                st.metric("Departments", unique_depts)

            # Matrix preview
            st.dataframe(
                st.session_state.current_matrix, use_container_width=True, height=400
            )

            # Export section
            st.markdown("### Export Results")
            audit_title = st.text_input(
                "Audit Name",
                value="Cal Poly Audit Evidence Request",
                placeholder="Enter a name for this audit",
            )

            col_export, col_preview = st.columns(2)
            with col_export:
                if st.button(
                    "Download Excel Matrix",
                    type="secondary",
                    use_container_width=True,
                ):
                    with st.spinner("Creating Excel file..."):
                        excel_buffer = (
                            st.session_state.matrix_generator.export_to_excel(
                                st.session_state.current_matrix, audit_title
                            )
                        )

                    filename = f"{audit_title.replace(' ', '_')}_Evidence_Matrix_{datetime.now().strftime('%Y%m%d')}.xlsx"

                    st.download_button(
                        label="Download Excel File",
                        data=excel_buffer.getvalue(),
                        file_name=filename,
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True,
                    )
                    st.success("Excel file ready for download!")

            with col_preview:
                if st.button("Start New Analysis", use_container_width=True):
                    # Reset session state
                    for key in [
                        "current_observations",
                        "current_matrix",
                        "implementation_suggestions",
                        "edited_observations",
                        "edited_suggestions",
                    ]:
                        if key in st.session_state:
                            del st.session_state[key]
                    st.session_state.processing_stage = "upload"
                    st.rerun()

    with col2:
        # Sidebar information
        st.markdown("### Quick Guide")
        st.markdown(
            """
        **How it works:**
        1. **Upload** your audit PDF
        2. **AI analyzes** and extracts observations
        3. **Review & edit** the suggestions
        4. **Generate** evidence request matrix
        5. **Download** Excel file for tracking
        
        **Tips:**
        - Ensure your PDF has clear observation sections
        - Review department assignments carefully
        - Set realistic timelines based on complexity
        - Use the Excel file for audit committee reporting
        """
        )

        if st.session_state.current_observations:
            st.markdown("### Current Analysis")
            st.json(
                {
                    "observations": len(st.session_state.current_observations),
                    "stage": st.session_state.processing_stage,
                    "has_matrix": st.session_state.current_matrix is not None,
                }
            )

        st.markdown("### Need Help?")
        st.markdown(
            """
        **Contact:**
        - Stephanie DaRosa (sdarosa@calpoly.edu)
        - Alexia Acosta (aacost47@calpoly.edu)
        
        **Resources:**
        - [Implementation Guide](https://calpoly-dxhub.slack.com/files/U05GFDKAZPE/F09BHBUFV2N/implementation_documentation_11.14.23.pdf)
        - [Process Examples](https://calpoly-dxhub.slack.com/files/U05GFDKAZPE/F09BCDWQM5H/example_process.xlsx)
        """
        )


if __name__ == "__main__":
    main()
