import json

def generate_html_report(report_data: dict) -> str:
    """
    Converts the final report dictionary into a simple HTML string
    for saving as a .html file or displaying in a UI.
    """
    
    # --- 1. Get Key Data ---
    invoice = report_data.get("invoice_data", {})
    validation_status = report_data.get("validation_status", "UNKNOWN")
    rules = report_data.get("validation_rules", [])
    analysis = report_data.get("ai_analysis", {})
    translation_conf = report_data.get("translation_confidence", None)

    status_color = "green" if validation_status == "PASSED" else "red"
    rec_color = {
        "approve": "green",
        "review": "orange",
        "reject": "red"
    }.get(analysis.get("recommendation", "review"), "black")

    # --- 2. Build HTML String ---
    html = f"""
    <html>
    <head>
        <style>
            body {{ font-family: sans-serif; margin: 20px; }}
            .container {{ max-width: 800px; margin: auto; border: 1px solid #ccc; border-radius: 8px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); }}
            header {{ background: #f4f4f4; padding: 20px; border-bottom: 1px solid #ccc; }}
            h1 {{ margin: 0; color: #333; }}
            .status {{ font-size: 1.5em; font-weight: bold; color: {status_color}; }}
            .content {{ padding: 20px; }}
            h2 {{ border-bottom: 2px solid #eee; padding-bottom: 5px; }}
            .metric-grid {{ display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 15px; margin-bottom: 20px; }}
            .metric {{ background: #f9f9f9; padding: 15px; border-radius: 5px; }}
            .metric label {{ font-weight: bold; color: #555; display: block; }}
            .metric span {{ font-size: 1.2em; }}
            .analysis {{ background: #eef; border: 1px solid #cce; border-radius: 5px; padding: 15px; margin-bottom: 20px; }}
            .analysis .recommendation {{ font-size: 1.2em; font-weight: bold; color: {rec_color}; }}
            .findings table {{ width: 100%; border-collapse: collapse; }}
            .findings th, .findings td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
            .findings th {{ background: #f2f2f2; }}
            .findings .status-FAILED {{ color: red; font-weight: bold; }}
            .findings .status-PASSED {{ color: green; }}
        </style>
    </head>
    <body>
        <div class="container">
            <header>
                <h1>Invoice Audit Report</h1>
                <div class="status">STATUS: {validation_status}</div>
            </header>
            
            <div class="content">
                <h2>AI Analysis</h2>
                <div class="analysis">
                    <div class="recommendation">Recommendation: {analysis.get("recommendation", "review").upper()}</div>
                    <p><b>Summary:</b> {analysis.get("analysis", "N/A")}</p>
                    <p><b>Discrepancies:</b> <span style="color:red;">{analysis.get("discrepancy_summary", "None")}</span></p>
                </div>

                <h2>Translation</h2>
                <div class="analysis">
                    <p><b>Translation Confidence:</b> {round(translation_conf, 3) if translation_conf is not None else "N/A"}</p>
                </div>

                <h2>Invoice Details</h2>
                <div class="metric-grid">
                    <div class="metric"><label>Invoice ID</label><span>{invoice.get("invoice_id", "N/A")}</span></div>
                    <div class="metric"><label>Vendor</label><span>{invoice.get("vendor_name", "N/A")}</span></div>
                    <div class="metric"><label>PO Number</label><span>{invoice.get("po_number", "N/A")}</span></div>
                    <div class="metric"><label>Invoice Date</label><span>{invoice.get("invoice_date", "N/A")}</span></div>
                    <div class="metric"><label>Subtotal</label><span>{invoice.get("subtotal", 0)}</span></div>
                    <div class="metric"><label>Total Amount</label><span><b>{invoice.get("currency")} {invoice.get("total_amount", 0)}</b></span></div>
                </div>

                <h2>Validation Findings</h2>
                <div class="findings">
                    <table>
                        <tr><th>Rule Name</th><th>Status</th><th>Message</th><th>Source</th></tr>
    """

    if not rules:
        html += '<tr><td colspan="4">No validation rules were run.</td></tr>'
    else:
        for rule in rules:
            status = rule.get("status", "UNKNOWN")
            html += f"""
                <tr>
                    <td>{rule.get("rule_name", "N/A")}</td>
                    <td class="status-{status}">{status}</td>
                    <td>{rule.get("message", "N/A")}</td>
                    <td>{rule.get("source", "System")}</td>
                </tr>
            """

    html += """
                    </table>
                </div>
            </div>
        </div>
    </body>
    </html>
    """
    return html
