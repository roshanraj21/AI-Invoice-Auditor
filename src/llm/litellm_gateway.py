import os
import sys
from typing import Dict, Any, List, Literal
import json
import traceback 
from pydantic import BaseModel, Field
# from langchain_core.output_parsers import PydanticOutputParser
# --- Add project root to path ---
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

try:
    import litellm
    from litellm import completion, embedding
    import boto3
    from config.settings import LLM_EMBEDDING_MODEL, LLM_RAG_MODEL

except ImportError as e:
    print("="*50)
    print(f"ERROR: Missing dependency: {e}")
    print("Please run: pip install litellm boto3")
    print("="*50)
    sys.exit(1)

# --- Set AWS Credentials from boto3 to environment ---
def setup_aws_credentials():
    """
    Explicitly load AWS credentials from boto3 and set them as environment variables.
    This ensures LiteLLM can access them.
    """
    try:
        session = boto3.Session()
        credentials = session.get_credentials()
        
        if credentials is None:
            print("="*70)
            print("ERROR: No AWS credentials found!")
            print("Run: aws configure")
            print("="*70)
            return False
        
        frozen_creds = credentials.get_frozen_credentials()
        
        os.environ["AWS_ACCESS_KEY_ID"] = frozen_creds.access_key
        os.environ["AWS_SECRET_ACCESS_KEY"] = frozen_creds.secret_key
        if frozen_creds.token:
            os.environ["AWS_SESSION_TOKEN"] = frozen_creds.token
        
        region = session.region_name or "us-east-1"
        os.environ["AWS_REGION_NAME"] = region
        
        print(f"[LLMGateway] AWS credentials loaded from boto3")
        print(f"[LLMGateway] Region: {region}")
        print(f"[LLMGateway] Access Key: {frozen_creds.access_key[:10]}...")
        
        return True
        
    except Exception as e:
        print(f"[LLMGateway] ERROR loading AWS credentials: {e}")
        print("Make sure you've run: aws configure")
        return False

if not setup_aws_credentials():
    print("\n⚠️  WARNING: AWS credentials not configured properly!")
    print("The LLMGateway will fail when making Bedrock calls.\n")

# --- Internal Pydantic model for the AI Analysis output ---
class AIAnalysis(BaseModel):
    """
    Defines the structured JSON output for the AI analysis.
    This schema is shown to the LLM to force a JSON response.
    """
    analysis: str = Field(
        ..., 
        description="A 2-3 line summary of the audit's findings and business context."
    )
    discrepancy_summary: str = Field(
        ..., 
        description="A brief summary of all FAILED and WARNING checks, explaining what went wrong. If none, state 'No discrepancies found'."
    )
    recommendation: Literal["APPROVE", "REJECT", "REVIEW"] = Field(
        ..., 
        description="The system's final recommendation: APPROVE (no issues), REJECT (critical issues), or REVIEW (minor issues/warnings)."
    )

class LLMGateway:
    """
    A centralized gateway for all LLM calls, powered by LiteLLM.
    Handles invoice extraction, translation, RAG, and report generation.
    """

    def __init__(self, model: str):
        self.model = model
        print(f"[LLMGateway] Initialized with model: {self.model}")
    
        if not os.getenv("AWS_ACCESS_KEY_ID"):
            raise ValueError("AWS credentials not found.")
        
        litellm.set_verbose = False

    def _call_llm(self, messages: List[Dict[str, str]], temperature: float = 0.3, 
                  max_tokens: int = 2000, response_format: Dict = None) -> str:
        """
        Unified method to call LLM with error handling and fallbacks.
        """
        try:
            fallback_models = ["bedrock/amazon.nova-lite-v1:0"]
        
            response = completion(
                model=self.model, 
                fallbacks=fallback_models,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                response_format=response_format
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            error_msg = str(e)
            print(f"[LLMGateway] LLM call failed: {error_msg}")
            traceback.print_exc()
            if "BadRequestError" in error_msg:
                print("[LLMGateway] Try a different Bedrock model")
            elif "Authentication" in error_msg or "credentials" in error_msg.lower():
                print("[LLMGateway] AWS credentials invalid. Run: aws configure")
            elif "throttl" in error_msg.lower():
                print("[LLMGateway] Rate limit hit. Wait and retry.")            
            raise

    def call_for_structured_extraction(
        self, 
        invoice_text: str, 
        pydantic_schema: BaseModel,
        original_filename: str
    ) -> Dict[str, Any]:
        """
        Extracts structured data from invoice text using LLM with robust JSON parsing.
        
        Args:
            invoice_text: The extracted text from the invoice file
            pydantic_schema: The Pydantic model to validate against (e.g., InvoiceData)
            original_filename: The name of the source file
            
        Returns:
            Dictionary containing validated invoice data or error message
        """
        if not invoice_text:
            return {"error": "Empty content after text extraction"}
        # Get the full schema
        schema_json = json.dumps(pydantic_schema.model_json_schema(), indent=2)
        messages = [
            {
                "role": "system",
                "content": f"""You are an expert invoice data extractor. Extract information from the invoice text and return ONLY a valid JSON object matching this schema:

{schema_json}

CRITICAL INSTRUCTIONS:
1. Return ONLY the JSON object - no markdown code blocks, no explanations, no extra text
2. Do NOT include these fields (they will be added automatically):
   - "original_filename" 
   - "processing_status"
3. For ALL other fields, extract from the invoice or use null if not found
4. Date format: YYYY-MM-DD (e.g., "2025-11-07")
5. Numbers: Remove currency symbols (use 2100.50 not "$2,100.50")
6. Currency: Use 3-letter code (USD, EUR, GBP, etc.)
7. Line items: Extract ALL items with their details

Example of correct output structure:
{{
  "invoice_id": "INV-2025-001",
  "vendor_name": "Company Name",
  "customer_name": null,
  "invoice_date": "2025-11-07",
  "due_date": null,
  "subtotal": 1000.00,
  "tax_amount": 100.00,
  "discount_amount": null,
  "total_amount": 1100.00,
  "currency": "USD",
  "po_number": null,
  "line_items": [
    {{
      "item_id": "SKU-001",
      "description": "Product description",
      "quantity": 1,
      "unit_price": 1000.00,
      "line_total": 1000.00
    }}
  ]
}}"""
            },
            {
                "role": "user",
                "content": f"Extract data from this invoice:\n\n{invoice_text}"
            }
        ]
        
        print(f"[LLMGateway] Extracting data from: {original_filename}")
        try:
            # Call the LLM
            content = self._call_llm(
                messages, 
                temperature=0.1, 
                max_tokens=2000
            )
            
            print(f"[LLMGateway] Raw LLM response length: {len(content)} chars")
            
            # Extract JSON from response (handles markdown, extra text, etc.)
            structured_data = self._extract_json_from_text(content)
     
            # This ensures these fields are present when Pydantic validates
            structured_data["original_filename"] = original_filename
            structured_data["processing_status"] = "Extracted"
            
            # Validate the complete data with Pydantic
            validated = pydantic_schema.model_validate(structured_data)
            
            print(f"[LLMGateway] ✓ Extraction successful")
            # Convert to dict with proper serialization (dates -> strings)
            return validated.model_dump(mode='json')
            
        except json.JSONDecodeError as e:
            print(f"[LLMGateway] ✗ JSON parse error: {e}")
            print(f"[LLMGateway] Raw content preview: {content[:300]}...")
            return {"error": f"Failed to parse JSON: {str(e)}"}
        except Exception as e:
            print(f"[LLMGateway] ✗ Extraction failed: {e}")
            import traceback
            traceback.print_exc()
            return {"error": f"Extraction failed: {str(e)}"}
    
    def _extract_json_from_text(self, content: str) -> Dict[str, Any]:
        """
        Robust JSON extraction that handles:
        - Markdown code blocks (```json or ```)
        - Extra text before/after JSON
        - Common formatting issues
        Args:
            content: Raw text from LLM that may contain JSON 
        Returns:
            Parsed JSON as dictionary       
        Raises:
            ValueError: If valid JSON cannot be found
        """
        original_content = content
        content = content.strip()
        
        # Remove markdown code blocks if present
        if "```json" in content.lower():
            # Handle ```json ... ```
            start = content.lower().find("```json") + 7
            end = content.find("```", start)
            if end > start:
                content = content[start:end].strip()
                print(f"[LLMGateway] Extracted from ```json``` block")
        elif "```" in content:
            # Handle ``` ... ``` (generic code block)
            start = content.find("```") + 3
            end = content.find("```", start)
            if end > start:
                content = content[start:end].strip()
                print(f"[LLMGateway] Extracted from ``` ``` block")
        
        # Find JSON object boundaries
        start_idx = content.find('{')
        end_idx = content.rfind('}') + 1
        
        if start_idx == -1 or end_idx <= start_idx:
            print(f"[LLMGateway] Could not find JSON boundaries in content")
            print(f"[LLMGateway] Content preview: {original_content[:500]}...")
            raise ValueError(f"Could not find valid JSON object in LLM response")
        
        json_str = content[start_idx:end_idx]
        
        # parse the JSON
        try:
            parsed = json.loads(json_str)
            print(f"[LLMGateway] ✓ Successfully parsed JSON")
            return parsed
        except json.JSONDecodeError as e:
            # Step 4: Try cleaning common issues
            print(f"[LLMGateway] First parse failed, attempting cleanup...")
            cleaned = json_str.replace('\n', ' ').replace('\r', '').replace('\t', ' ')
   
            try:
                parsed = json.loads(cleaned)
                print(f"[LLMGateway] ✓ Successfully parsed JSON after cleanup")
                return parsed
            except json.JSONDecodeError as e2:
                print(f"[LLMGateway] ✗ JSON parsing failed even after cleanup")
                print(f"[LLMGateway] JSON string preview: {json_str[:300]}...")
                raise ValueError(f"Could not parse JSON: {e2}")


    def call_for_translation(self, text_to_translate: str) -> Dict[str, Any]:
        """
        Translates text to English using LLM and returns a dict:
        {"text": <translated_or_original>, "confidence": <0..1 or None>}
        """
        if not text_to_translate or not isinstance(text_to_translate, str):
            return {"text": text_to_translate, "confidence": None}
        messages = [
            {
                "role": "system",
                "content": (
                    "You are a precise translator. "
                    "Translate the user text to English. If it is already English, return it unchanged. "
                    "Return ONLY a valid JSON object with exactly these keys:\n"
                    '{ "text": "<translated text>", "confidence": <number between 0 and 1> }\n'
                    "Notes:\n"
                    "- confidence reflects your certainty the translation preserves meaning and tone.\n"
                    "- Do not include markdown or code fences."
                ),
            },
            {"role": "user", "content": text_to_translate},
        ]

        print(f"[LLMGateway] Translating text...")
        try:
            content = self._call_llm(messages, temperature=0.1, max_tokens=500)
            #parse JSON; if the model returned raw text, treat it as text with None confidence
            try:
                parsed = self._extract_json_from_text(content)
                text = parsed.get("text", "")
                conf = parsed.get("confidence", None)
                if isinstance(conf, (int, float)):
                    conf = max(0.0, min(1.0, float(conf)))
                else:
                    conf = None
                # fallback
                if not isinstance(text, str) or not text.strip():
                    text = text_to_translate

                print(f"[LLMGateway] ✓ Translation successful")
                return {"text": text, "confidence": conf}

            except Exception:
                # Model didn't return JSON; treat output as the translated text
                translated = content.strip() if isinstance(content, str) else text_to_translate
                print(f"[LLMGateway] ✓ Translation parsed as plain text (no JSON).")
                return {"text": translated, "confidence": None}

        except Exception as e:
            print(f"[LLMGateway] ✗ Translation failed: {e}")
            return {"text": text_to_translate, "confidence": None}

        
    def get_embedding(self, text: str) -> List[float]:
        """
        Generates embeddings for text.
        """
        print(f"[LLMGateway] Generating embedding...")
        try:
            response = embedding(model=LLM_EMBEDDING_MODEL, input=[text])
            print(f"[LLMGateway] ✓ Embedding successful")
            return response.data[0]['embedding']
        except Exception as e:
            print(f"[LLMGateway] ✗ Embedding failed: {e}")
            return []
 
    def generate_ai_analysis(self,invoice_data: Dict[str, Any],validation_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Generates a structured JSON analysis of the audit results.
        It forces the LLM to return a JSON object matching the AIAnalysis Pydantic model.
        Args:
            invoice_data: Extracted invoice data dictionary
            validation_results: List of validation rule results  
        Returns:
            Dictionary matching AIAnalysis schema or an error dictionary
        """
        schema_json = json.dumps(AIAnalysis.model_json_schema(), indent=2)

        failed = [r for r in validation_results if r.get('status') == 'FAILED']
        warnings = [r for r in validation_results if r.get('status') == 'WARNING']
        
        failed_checks_json = json.dumps(
            [{'rule': r.get('rule_name'), 'issue': r.get('message')} for r in failed],
            indent=2
        )
        warning_checks_json = json.dumps(
            [{'rule': r.get('rule_name'), 'issue': r.get('message')} for r in warnings],
            indent=2
        )
        invoice_summary = json.dumps({
            "vendor": invoice_data.get('vendor_name'),
            "total": invoice_data.get('total_amount'),
            "invoice_date": invoice_data.get('invoice_date'),
            "po_number": invoice_data.get('po_number')
        }, indent=2)

        prompt = f"""You are an expert financial auditor. Your job is to analyze an invoice audit and provide a structured JSON response.
Here is the invoice summary:
{invoice_summary}

Here are the audit validation results:
FAILED CHECKS:
{failed_checks_json}

WARNINGS:
{warning_checks_json}

Please generate a structured analysis based *only* on the data provided. Follow these rules:
1.  **analysis**: Write a 2-3 line executive summary of the audit.
2.  **discrepancy_summary**: Briefly summarize the FAILED and WARNING checks. If none, say "No discrepancies found."
3.  **recommendation**:
    - "APPROVE": ONLY if there are 0 FAILED checks and 0 WARNING checks.
    - "REJECT": If there are critical FAILED checks (e.g., 'ERP Connection', 'Total Check', 'PO-Vendor Match', 'ERP Vendor Check').
    - "REVIEW": If there are any FAILED checks (e.g., 'Price Check', 'Qty Check') or *any* WARNING checks.

CRITICAL: Return ONLY a valid JSON object. No markdown code blocks, no explanations, just the JSON.

SCHEMA:
{schema_json}
"""
        messages = [
            {"role": "system", "content": "You are a financial auditor that *only* responds with valid JSON objects. Never use markdown code blocks."},
            {"role": "user", "content": prompt}
        ]
        print("[LLMGateway] Generating structured AI analysis...")
        try:
            content = self._call_llm(
                messages,
                temperature=0.1,
                max_tokens=1500 
            )
            print(f"[LLMGateway] Raw AI analysis response length: {len(content)} chars")
            # Use the robust JSON extraction method
            structured_data = self._extract_json_from_text(content)
            # Validate with Pydantic
            validated_data = AIAnalysis.model_validate(structured_data)
            
            print("[LLMGateway] ✓ AI analysis generated and validated.")
            return validated_data.model_dump()

        except json.JSONDecodeError as e:
            print(f"[LLMGateway] ✗ JSON parse error in AI analysis: {e}")
            print(f"[LLMGateway] Raw content preview: {content[:300]}...")
            return {"error": f"Failed to parse AI analysis JSON: {str(e)}"}
        except Exception as e:
            print(f"[LLMGateway] ✗ AI analysis generation failed: {e}")
            traceback.print_exc()
            return {"error": f"Failed to generate/parse AI analysis: {str(e)}"}