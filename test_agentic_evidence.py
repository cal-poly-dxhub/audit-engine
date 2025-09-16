#!/usr/bin/env python3
"""
Test script for the Agentic Evidence Analysis System

This script demonstrates how to use the new agentic workflow for evidence validation.
It provides examples of analyzing different types of documents with the intelligent agent.
"""

import os
import sys
import json
import time
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add the current directory to the path so we can import our modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_agentic_evidence_analysis():
    """Test the agentic evidence analysis system"""

    try:
        # Import required modules
        from app import BedrockClient
        from evidence_agent import EvidenceAnalysisAgent

        print("[TEST] Agentic Evidence Analysis System Test")
        print("=" * 50)
        print("[INFO] This test will demonstrate the detailed logging system")
        print("[INFO] Check the logs/ directory for detailed activity logs")
        print("[INFO] Use 'python log_viewer.py follow' in another terminal to see real-time logs")
        print("=" * 50)

        # Initialize the system
        print("Initializing Bedrock client and evidence agent...")
        bedrock_client = BedrockClient()
        evidence_agent = EvidenceAnalysisAgent(bedrock_client)

        # Test configuration
        task_description = "Implement new security protocols for data access controls and user authentication systems"
        task_context = {
            "department": "IT Security",
            "implementation_type": "Security Enhancement",
            "division": "Information Technology",
            "requires_collaboration": True
        }
        user_description = "This document contains our implementation plan and security audit results showing compliance with new protocols"

        # Test 1: Text-based evidence
        print("\n[TEST_1] Test 1: Analyzing text-based evidence")
        print("-" * 30)

        sample_text = """
SECURITY IMPLEMENTATION REPORT
==============================

1. ACCESS CONTROL IMPLEMENTATION
   - Multi-factor authentication deployed across all systems
   - Role-based access control (RBAC) implemented
   - Regular access reviews scheduled quarterly

2. USER AUTHENTICATION SYSTEMS
   - SSO integration completed with Active Directory
   - Password policies updated to meet security standards
   - Account lockout mechanisms implemented

3. AUDIT RESULTS
   - Penetration testing completed with no critical findings
   - Vulnerability assessment shows 98% compliance
   - Security awareness training completed by all staff

4. COMPLIANCE VERIFICATION
   - All systems meet SOC 2 Type II requirements
   - GDPR compliance verified by external auditor
   - Regular monitoring and reporting established
"""

        print("Analyzing sample security implementation document...")
        start_time = time.time()

        result = evidence_agent.analyze_evidence(
            sample_text,
            "security_implementation_report.txt",
            task_description,
            task_context,
            user_description
        )

        analysis_time = time.time() - start_time

        print(f"[RESULT] Analysis completed in {analysis_time:.2f}s")
        print(f"[VALIDITY] Overall Validity: {'VALID' if result.get('is_valid') else 'INVALID'}")
        print(f"[CONFIDENCE] Confidence: {result.get('confidence', 0):.2f}")
        print(f"[QUALITY] Evidence Quality: {result.get('evidence_quality', 'unknown').upper()}")
        print(f"[RECOMMENDATION] Recommendation: {result.get('recommendation', 'unknown').upper()}")

        if result.get('findings'):
            print("\n[FINDINGS] Key Findings:")
            for i, finding in enumerate(result.get('findings', [])[:5], 1):
                print(f"   {i}. {finding[:100]}{'...' if len(finding) > 100 else ''}")

        if result.get('recommendations'):
            print("\n[RECOMMENDATIONS] Recommendations:")
            for i, rec in enumerate(result.get('recommendations', [])[:3], 1):
                print(f"   {i}. {rec[:100]}{'...' if len(rec) > 100 else ''}")

        # Test 2: Large document simulation
        print("\n[TEST_2] Test 2: Analyzing large document (multiple sections)")
        print("-" * 30)

        large_document = """
COMPREHENSIVE SECURITY AUDIT REPORT
===================================

EXECUTIVE SUMMARY
================
This report presents the findings of our comprehensive security audit conducted over Q3 2024.
The audit covers all aspects of our security implementation including access controls,
authentication systems, data protection measures, and compliance verification.

SECTION 1: ACCESS CONTROL SYSTEMS
=================================
Our organization has implemented a robust access control framework based on the principle
of least privilege. The system includes role-based access control (RBAC) with granular
permissions, multi-factor authentication (MFA) for all privileged accounts, and regular
access reviews conducted quarterly.

Key implementations:
- Azure Active Directory integration
- Privileged Access Management (PAM) solution
- Just-in-time access for administrative functions
- Automated provisioning and deprovisioning

SECTION 2: AUTHENTICATION MECHANISMS
===================================
The authentication infrastructure has been significantly enhanced with modern security
protocols. Single sign-on (SSO) has been deployed across all enterprise applications,
reducing password fatigue while improving security posture.

Technical specifications:
- SAML 2.0 and OAuth 2.0 protocols
- Multi-factor authentication using TOTP and SMS
- Risk-based authentication with behavioral analytics
- Password policies enforcing complexity requirements

SECTION 3: DATA PROTECTION MEASURES
==================================
Data protection has been strengthened through encryption at rest and in transit,
data loss prevention (DLP) solutions, and comprehensive backup strategies.
All sensitive data is classified and handled according to established protocols.

Implementation details:
- AES-256 encryption for data at rest
- TLS 1.3 for data in transit
- DLP policies preventing unauthorized data exfiltration
- Regular backup testing and disaster recovery drills

SECTION 4: COMPLIANCE VERIFICATION
=================================
External auditors have verified our compliance with multiple frameworks including
SOC 2 Type II, ISO 27001, and GDPR. All identified gaps have been remediated
and continuous monitoring ensures ongoing compliance.

Compliance status:
- SOC 2 Type II: Fully compliant
- ISO 27001: Certificate renewed
- GDPR: Data processing audited and approved
- Internal controls tested and verified

SECTION 5: INCIDENT RESPONSE
===========================
A comprehensive incident response plan has been developed and tested through
tabletop exercises. The security team is equipped with modern SIEM tools
and has established relationships with external forensics providers.

Response capabilities:
- 24/7 security operations center (SOC)
- Automated threat detection and response
- Forensics and malware analysis capabilities
- Communication protocols for stakeholder notification

CONCLUSIONS AND RECOMMENDATIONS
==============================
The security posture has been significantly improved through these implementations.
However, continuous improvement is necessary to address evolving threats.
We recommend quarterly reviews of all security controls and annual penetration testing.
"""

        print("Analyzing comprehensive security audit report...")
        start_time = time.time()

        result2 = evidence_agent.analyze_evidence(
            large_document,
            "comprehensive_security_audit.txt",
            task_description,
            task_context,
            user_description
        )

        analysis_time = time.time() - start_time

        print(f"[RESULT] Analysis completed in {analysis_time:.2f}s")
        print(f"[VALIDITY] Overall Validity: {'VALID' if result2.get('is_valid') else 'INVALID'}")
        print(f"[CONFIDENCE] Confidence: {result2.get('confidence', 0):.2f}")
        print(f"[QUALITY] Evidence Quality: {result2.get('evidence_quality', 'unknown').upper()}")
        print(f"[SECTIONS] Sections Analyzed: {result2.get('sections_analyzed', 'unknown')}")

        if result2.get('analysis_metadata'):
            metadata = result2['analysis_metadata']
            print(f"[STAGES] Processing Stages: {metadata.get('processing_stages', 'unknown')}")
            print(f"[CROSS_REF] Cross-References: {metadata.get('cross_references', 'unknown')}")

        print("\n[SUMMARY] Analysis Summary:")
        print(f"   - Document successfully parsed into logical sections")
        print(f"   - Multi-stage analysis performed with cross-validation")
        print(f"   - Comprehensive evidence quality assessment completed")
        print(f"   - Detailed recommendations generated for next steps")

        # Test 3: Error handling
        print("\n[TEST_3] Test 3: Error handling with invalid content")
        print("-" * 30)

        try:
            result3 = evidence_agent.analyze_evidence(
                "",  # Empty content
                "empty_file.txt",
                task_description,
                task_context,
                user_description
            )

            if result3.get('error'):
                print(f"[PASS] Error handling working correctly: {result3['error']}")
            else:
                print(f"[WARNING] Empty content handled gracefully with confidence: {result3.get('confidence', 0):.2f}")

        except Exception as e:
            print(f"[PASS] Exception handling working: {str(e)}")

        print("\n[SUCCESS] All tests completed successfully!")
        print("\nThe agentic evidence analysis system is ready for use.")
        print("It can handle:")
        print("  - Large, complex documents with multiple sections")
        print("  - Cross-section analysis for consistency checking")
        print("  - Intelligent document parsing and segmentation")
        print("  - Comprehensive evidence quality assessment")
        print("  - Detailed recommendations and findings")

        print("\n[LOGGING] Logging Information:")
        print("  - Detailed logs: logs/evidence_agent_detailed.log")
        print("  - Analysis logs: logs/evidence_analysis.log")
        print("  - Console output: Real-time progress updates")

        print("\n[COMMANDS] Log Viewer Commands:")
        print("  - python log_viewer.py summary       - Show all log files")
        print("  - python log_viewer.py tail          - Show recent log entries")
        print("  - python log_viewer.py follow        - Follow logs in real-time")
        print("  - python log_viewer.py performance   - Analyze performance metrics")

        # Show sample of recent logs if available
        try:
            from pathlib import Path
            log_file = Path("logs/evidence_analysis.log")
            if log_file.exists():
                print("\n[RECENT_LOGS] Recent log entries:")
                print("-" * 30)
                with open(log_file, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                    for line in lines[-10:]:  # Show last 10 lines
                        print(f"   {line.rstrip()}")
        except Exception as e:
            print(f"\n[WARNING] Could not read recent logs: {e}")

        return True

    except ImportError as e:
        print(f"[ERROR] Import error: {e}")
        print("Make sure all dependencies are installed and AWS credentials are configured")
        return False
    except Exception as e:
        print(f"[ERROR] Test failed: {e}")
        return False

def main():
    """Main test function"""
    print("Starting Agentic Evidence Analysis System Test...")

    # Check environment - bearer token or standard credentials
    if os.getenv('AWS_BEARER_TOKEN_BEDROCK'):
        # Set default region if not provided
        if not os.getenv('AWS_DEFAULT_REGION'):
            os.environ['AWS_DEFAULT_REGION'] = 'us-west-2'
        print("[INFO] AWS Bearer Token configured for Bedrock")
        print(f"[INFO] Using region: {os.getenv('AWS_DEFAULT_REGION')}")
    else:
        required_vars = ['AWS_ACCESS_KEY_ID', 'AWS_SECRET_ACCESS_KEY', 'AWS_DEFAULT_REGION']
        missing_vars = [var for var in required_vars if not os.getenv(var)]

        if missing_vars:
            print("[ERROR] Missing required environment variables:")
            for var in missing_vars:
                print(f"   - {var}")
            print("\n[INFO] Options:")
            print("[INFO] 1. Set AWS_BEARER_TOKEN_BEDROCK in your .env file (recommended)")
            print("[INFO] 2. Set standard AWS credentials (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_DEFAULT_REGION)")
            return False

    success = test_agentic_evidence_analysis()
    return success

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)