# Audit Engine

Audit Engine is a Python application for extracting audit observations and management responses, organizing follow-up tasks, validating uploaded evidence, and exporting audit-tracking results.

## Features

- Extract observations and responses from audit documents.
- Organize tasks by department, division, contact, and due date.
- Validate PDF and image evidence with AI-assisted analysis.
- Create evidence annotations and citations.
- Export audit-tracking data to Excel.
- Inspect analysis progress and application logs through local viewers.

## Project Structure

- `app.py` — Main audit-tracking Flask application.
- `evidence_app.py` — Evidence validation Flask application.
- `main.py` — Core audit processing and task extraction logic.
- `pdf_tools.py` — PDF extraction utilities.
- `citation_system.py` — Evidence citation and annotation support.
- `templates/` — Web application templates.
- `static/` — Front-end JavaScript and CSS.
- `run.py` — Local entry point for the audit-tracking application.
- `run_evidence.py` — Local entry point for the evidence validation application.
- `run_agent_viewer.py` — Local agent-step viewer.
- `run_logs_ui.py` — Local log viewer.

## Requirements

- Python 3.9 or newer
- AWS Bedrock access for AI-assisted processing

Install the Python dependencies in a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

## Configuration

Credentials and configuration must be supplied through environment variables or an approved AWS credential provider. Never commit credentials, private keys, uploaded evidence, or production infrastructure details.

Supported configuration includes:

- `AWS_BEARER_TOKEN_BEDROCK`, or standard AWS credential variables.
- `AWS_DEFAULT_REGION`.
- `SECRET_KEY` for the main Flask application.
- `FLASK_SECRET_KEY` for the evidence application.

Keep local configuration in an ignored `.env` file or use the AWS SDK credential chain. Use strong, randomly generated Flask secrets in every deployed environment.

## Running Locally

Start the audit-tracking application:

```bash
python run.py
```

Start the evidence validation application in a separate terminal:

```bash
python run_evidence.py
```

The viewer utilities can be started separately when needed:

```bash
python run_agent_viewer.py
python run_logs_ui.py
```

These commands are intended for local development. Use a production WSGI server, disable debug mode, and place the applications behind appropriate authentication and network controls for deployment.

## Data Handling

Uploaded documents, generated annotations, analysis results, logs, and user interaction metadata may contain confidential or personal information. Store them only in approved locations, restrict access, apply retention policies, and remove them when no longer required. Do not add real customer or employee evidence to source control.

## Development Notes

Before sharing changes:

1. Run the relevant tests and checks.
2. Scan files for credentials, private keys, account identifiers, and personal data.
3. Confirm that temporary uploads, logs, and generated artifacts are excluded from source control.

# Collaboration

Thanks for your interest in our solution. Having specific examples of replication and usage allows us to continue to grow and scale our work. If you clone or use this repository, kindly shoot us a quick email to let us know you are interested in this work!

<wwps-cic@amazon.com>

# Disclaimers

**Customers are responsible for making their own independent assessment of the information in this document.**

**This document:**

(a) is for informational purposes only,

(b) references AWS product offerings and practices, which are subject to change without notice,

(c) does not create any commitments or assurances from AWS and its affiliates, suppliers or licensors. AWS products or services are provided "as is" without warranties, representations, or conditions of any kind, whether express or implied. The responsibilities and liabilities of AWS to its customers are controlled by AWS agreements, and this document is not part of, nor does it modify, any agreement between AWS and its customers, and

(d) is not to be considered a recommendation or viewpoint of AWS.

**Additionally, you are solely responsible for testing, security and optimizing all code and assets on GitHub repo, and all such code and assets should be considered:**

(a) as-is and without warranties or representations of any kind,

(b) not suitable for production environments, or on production or other critical data, and

(c) to include shortcuts in order to support rapid prototyping such as, but not limited to, relaxed authentication and authorization and a lack of strict adherence to security best practices.

**All work produced is open source. More information can be found in the GitHub repo.**
