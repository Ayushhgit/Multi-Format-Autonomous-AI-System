# Multi-Format Autonomous AI System

This system is designed to process uploaded content in various formats (Email, JSON, PDF), classify its business intent, extract relevant information, analyze characteristics like tone and risk, and automatically trigger contextual actions.

## Architecture Overview

The system follows a modular, agent-based architecture orchestrated by a central FastAPI application.

1.  **File Upload:** The `main.py` FastAPI application receives uploaded files via the `/upload` endpoint.
2.  **Classification:** The `ClassifierAgent` determines the file's format (e.g., Email, JSON, PDF) and its core business intent (e.g., RFQ, Complaint, Invoice, Regulation, Fraud Risk) using a Groq LLM with a rule-based fallback.
3.  **Routing to Format Agent:** Based on the classified format, the request is routed to the appropriate specialized agent (`EmailAgent`, `EnhancedJSONAgent`, `PDFAgent`).
4.  **Format-Specific Processing:** The designated agent processes the content:
    *   Extracts structured and unstructured data.
    *   Performs format-specific analysis (e.g., tone analysis for emails, anomaly detection for JSON/PDFs).
    *   Determines relevant actions based on the analysis.
5.  **Action Execution:** The `ActionRouter` receives the recommended actions from the format agent and executes them. This involves potentially calling external APIs (simulated or real) with retry logic.
6.  **Memory and Logging:** The `MemoryStore` is used throughout the process to store traces and logs for each uploaded file and subsequent actions, providing visibility into the processing flow.

## Agent Flow and Chaining

The processing of an uploaded file follows a specific chain of agents and components:

1.  **File Upload (`main.py`):** A file is uploaded to the `/upload` endpoint. A unique `trace_id` is generated for tracking.
2.  **Classification (`ClassifierAgent`):** The raw file content, filename, and content type are passed to the `ClassifierAgent`.
    *   It determines the `format` (Email, JSON, PDF, etc.) and `intent` (RFQ, Complaint, etc.).
    *   The classification result is logged in the `MemoryStore`.
3.  **Routing to Format Agent (`main.py`):** Based on the `format` determined by the `ClassifierAgent`, the `main.py` application routes the raw or decoded content to the appropriate agent:
    *   If `format` is "Email", `EmailAgent.process` is called with the decoded text content.
    *   If `format` is "JSON", `EnhancedJSONAgent.process` is called with the decoded text content.
    *   If `format` is "PDF", `PDFAgent.process` is called with the raw bytes content.
    *   If the format is unsupported, an error is returned.
4.  **Format Agent Processing (e.g., `EmailAgent`):** The selected format agent processes the content.
    *   It performs format-specific data extraction and analysis (e.g., calling `ToneDetector.analyze_tone` in the case of the `EmailAgent`).
    *   It generates a list of proposed `actions` based on its analysis.
    *   The agent's processing result and generated actions are logged in the `MemoryStore`.
    *   The agent returns its results, including the `actions` list, back to `main.py`.
5.  **Action Execution (`ActionRouter`):** The `main.py` application passes the list of `actions` received from the format agent to the `ActionRouter`.
    *   The `ActionRouter.execute_action` method is called for each action in the list.
    *   `execute_action` uses `_execute_with_retry` to handle the action execution, which involves simulating or making real API calls based on the action type and endpoint.
    *   The result and status (success/failed) of each action execution are logged in the `MemoryStore`.
    *   The results of the actions are collected.
6.  **Final Response (`main.py`):** The `main.py` application compiles the initial classification, the output from the format agent, and the results of the executed actions into a final response, which is returned to the user interface. All steps and results are persisted in the `MemoryStore` for later review (e.g., on the `/traces` page).

This flow illustrates the sequential processing pipeline, where the output of one stage (classification) determines the next stage (routing to a format agent), and the output of the format agent (actions) drives the final stage (action execution). The `MemoryStore` acts as a central point for logging and tracing the entire process.

## Agent Logic

Each agent has a specific role and internal logic:

*   **Classifier Agent (`mcp/classifier_agent.py`):**
    *   Analyzes file extension, MIME type, and initial content bytes to determine the format (PDF, JSON, Email, etc.).
    *   If an LLM is available, it uses a Groq model to classify the business intent based on text content.
    *   Includes a rule-based fallback for intent classification if the LLM is not available or fails.

*   **Email Agent (`agents/email_agent.py`):**
    *   Extracts standard email fields (sender, subject, recipient) and the main body using regex.
    *   Identifies a core "issue" or concern from the email body.
    *   Uses the `ToneDetector` to analyze the emotional tone and intensity of the email content.
    *   Determines the urgency level based on keywords and tone analysis.
    *   Makes decisions based on tone, intensity, and urgency (e.g., escalate angry/high-urgency emails, send notifications for high-urgency emails).
    *   Generates a list of actions (like `crm` escalation, `notification`, `log`) to be sent to the `ActionRouter`.

*   **Tone Detector (`utils/tone_detector.py`):**
    *   Provides a method (`analyze_tone`) to classify text tone (angry, polite, neutral, urgent) and estimate intensity.
    *   Attempts to use a Groq LLM for tone analysis if configured.
    *   Includes a rule-based fallback mechanism that counts occurrences of pre-defined keywords.

*   **PDF Agent (`agents/pdf_agent.py`):**
    *   Extracts text content from PDF files using PyMuPDF.
    *   Uses an LLM (with a rule-based fallback) to determine the document type (invoice, regulation, contract, report, manual, other).
    *   Extracts structured data based on the determined document type (e.g., invoice details).
    *   Performs anomaly detection based on extracted data and document type.
    *   Generates actions based on the extracted data, document type, and detected anomalies.

*   **Enhanced JSON Agent (`agents/json_agent.py`):**
    *   (Based on context, this agent likely) Parses JSON content.
    *   Extracts data based on expected JSON structures.
    *   May perform analysis or validation specific to the JSON data's purpose (e.g., RFQ details).
    *   Generates actions based on the JSON content and analysis.

*   **Memory Store (`memory_store.py`):**
    *   Handles the storage and retrieval of processing traces and associated logs.
    *   Supports both SQLite (for simple file-based storage) and Redis (for in-memory or persistent key-value storage).
    *   Provides methods to store log entries linked to a unique trace ID.

*   **Action Router (`router.py`):**
    *   Receives action dictionaries from agents.
    *   Maps action types to internal handling functions or simulated/real API endpoints.
    *   Executes actions using an internal `_execute_with_retry` mechanism that incorporates retry logic for potentially unreliable external calls.
    *   Includes a simulation mode (`simulate_apis`) for testing without external dependencies.
    *   Logs the start, success, or failure of each action.

## Running with Docker

The project includes a `Dockerfile` to easily build and run the application within a containerized environment, ensuring all dependencies and services (like Redis) are set up correctly.

To build the image:
```bash
docker build -t my-ai-app .
```

To run the container:
```bash
docker run -d -p 8000:8000 my-ai-app
```

Access the application at `http://127.0.0.1:8000` in your browser.