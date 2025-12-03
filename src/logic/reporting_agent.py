import os
import sys
import json
from datetime import datetime
from typing import Dict, Any, List

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

try:
    from config.settings import LLM_RAG_MODEL
    from src.llm.litellm_gateway import LLMGateway
except ImportError as e:
    print(f"Error importing modules in reporting_agent.py: {e}")
    sys.exit(1)

def generate_report(
    invoice_data: Dict[str, Any], 
    validation_rules: List[Dict[str, Any]],
    model: str = None
) -> Dict[str, Any]:
    """
    Assembles the final, clean-schema report using LLM for analysis.
    
    This agent:
    1. Determines the overall validation status.
    2. Calls the LLM to get a structured JSON analysis.
    3. Assembles the final, structured report dictionary.
    
    Args:
        invoice_data: The dictionary of extracted invoice data.
        validation_rules: The list of rule results from the validation_agent.
        
    Returns:
        A dictionary containing the complete, structured report.
    """
    print(f"\n[ReportingAgent] Assembling final, structured report...")

    if not invoice_data:
        print("[ReportingAgent] Error: invoice_data is empty")
        return {"error": "Invalid invoice data"}
        
    if model is None:
        model = LLM_RAG_MODEL
    
    # Determine final validation status
    failed_checks_count = len([r for r in validation_rules if r.get('status') == 'FAILED'])
    if failed_checks_count == 0:
        overall_status = "PASSED"
    else:
        overall_status = "FAILED"

    try:
        print(f"[ReportingAgent] Initializing LLM Gateway with model: {model}")
        llm_gateway = LLMGateway(model=model)
        
        print(f"[ReportingAgent] Generating AI analysis...")
        ai_analysis = llm_gateway.generate_ai_analysis(
            invoice_data, 
            validation_rules
        )
        
        # Check if the gateway itself returned an error
        if "error" in ai_analysis:
            raise Exception(ai_analysis["error"])
            
        print("[ReportingAgent] LLM analysis complete")
    
    except Exception as e:
        print(f"[ReportingAgent] LLM generation failed: {e}")
        ai_analysis = {
            "analysis": "Failed to generate AI analysis. See error.",
            "discrepancy_summary": f"Error: {str(e)}",
            "recommendation": "REVIEW" # Default to REVIEW on error
        }

    final_report = {
        "invoice_data": invoice_data,
        "validation_status": overall_status,
        "validation_rules": validation_rules,
        "ai_analysis": ai_analysis, # This holds the {'analysis', 'discrepancy_summary', ...} dict
        "human_review": None,
        
        "report_generated_at": datetime.now().isoformat()
    }
    final_report["translation_confidence"] = invoice_data.get("translation_confidence")
    print(f"[ReportingAgent] Report assembled successfully. Final Status: {overall_status}")
   
    return final_report