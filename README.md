# Invoice Processing & Validation System

## Overview

This project automates the extraction, validation, and reporting of invoice data. It is designed to process multi-currency invoices, apply configurable validation rules, and integrate with ERP systems for workflow management.

## Features

- **Automated Invoice Extraction:** Processes PDF, PNG, Docs invoices and extracts required fields.
- **Configurable Validation Rules:** Uses `config/rules.yaml` for required fields, data types, tolerances, accepted currencies, and validation policies.
- **Multi-Currency Support:** Maps currency symbols and validates against accepted currencies.
- **Reporting:** Generates HTML reports with translation confidence and discrepancy summaries.
- **Audit Logging:** Tracks actions and validation events for compliance.

## Agents

The system is modular, with specialized agents handling different aspects of invoice processing:

### Extraction Agent (`src/logic/extraction_agent.py`)

- Extracts invoice data from PDF files using OCR and parsing techniques.
- Identifies header and line item fields as defined in `rules.yaml`.
- Handles multi-format invoices and normalizes extracted data.

### Validation Agent (`src/logic/validation_agent.py`)

- Validates extracted invoice data against rules in `rules.yaml`.
- Checks for missing fields, data type mismatches, currency validity, and total mismatches.
- Applies tolerances for rounding and price/quantity differences.
- Flags invoices for review or rejection based on validation policies.

### Translation Agent (`src/logic/translation_agent.py`)

- Translates invoice content to the required language if needed.
- Provides translation confidence scores for reporting.
- Ensures field values are consistent post-translation.

### Reporting Agent (`src/logic/reporting_agent.py`)

- Generates detailed HTML reports for each processed invoice.
- Includes translation confidence, discrepancy summaries, and validation results.
- Supports multiple report formats as configured in `rules.yaml`.

### RAG Agent (`src/rag/rag_agent.py`)

- Implements Retrieval-Augmented Generation for advanced document search and Q&A.
- Uses vector stores for semantic search over invoice and ERP data.
- Supports chatbot and review queue functionalities.

### Monitor Agent (`scripts/monitor_agent.py`)

- Monitors incoming invoices and triggers extraction and validation workflows.
- Tracks processing status and logs audit events.

## Project Structure

- `app.py`: Main application entry point.
- `config/`: Configuration files (`rules.yaml`, `settings.py`).
- `data/`: Incoming invoices, mock ERP data, and vector store.
- `pages/`: Streamlit UI pages for chatbot, review queue, monitoring, and invoice history.
- `reports/`: Generated reports (HTML, JSON, pending review).
- `scripts/`: Utility and test scripts.
- `src/`: Source code modules:
  - `erp/`: ERP integration and models.
  - `graph/`: Workflow logic.
  - `llm/`: LLM gateway integration.
  - `logic/`: Agents for extraction, validation, reporting, translation.
  - `models/`: Data models.
  - `rag/`: Retrieval-Augmented Generation components.
  - `utils/`: Utility functions.

## Configuration

All validation and processing rules are defined in `config/rules.yaml`, including:

- Required fields for header and line items
- Data types for each field
- Tolerances for financial calculations
- Accepted currencies and symbol mapping
- Validation policies for missing fields, mismatches, and invalid currencies
- Reporting and logging options

## Getting Started

1. **Install dependencies:**
   ```powershell
   pip install -r requirement.txt
   ```
2. **Configure settings:** Edit `config/settings.py` and `config/rules.yaml` as needed.
3. **Run the application:**
   ```powershell
   python app.py
   ```
4. **Access the UI:** Open the Streamlit pages in your browser for chatbot, review, monitoring, and history.

## Usage

- Place incoming invoices in `data/incoming_copy/`.
- Review processed invoices and reports in the `reports/` directory.
- Monitor workflow and validation status via the UI.
