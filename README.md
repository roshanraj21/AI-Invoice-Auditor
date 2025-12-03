# Invoice Processing & Validation System

## Overview

This project automates the extraction, validation, and reporting of invoice data. It is designed to process multi-currency invoices, apply configurable validation rules, and integrate with ERP systems for workflow management.

## Features

- **Automated Invoice Extraction:** Processes PDF invoices and extracts required fields.
- **Configurable Validation Rules:** Uses `config/rules.yaml` for required fields, data types, tolerances, accepted currencies, and validation policies.
- **Multi-Currency Support:** Maps currency symbols and validates against accepted currencies.
- **Reporting:** Generates HTML reports with translation confidence and discrepancy summaries.
- **Audit Logging:** Tracks actions and validation events for compliance.

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
