from .invoice_utils import get_directory_structure, get_invoice_count_in_subdirs

def refresh_invoice_counts():
    dirs = get_directory_structure()
    for path in dirs.values():
        path.mkdir(parents=True, exist_ok=True)

    counts = {
        "auto_processed": get_invoice_count_in_subdirs(dirs["auto_processed"]),
        "pending_review": get_invoice_count_in_subdirs(dirs["pending_review"]),
        "approved": get_invoice_count_in_subdirs(dirs["approved"]),
        "rejected": get_invoice_count_in_subdirs(dirs["rejected"]),
    }

    total = sum(counts.values())
    counts["total_received"] = total
    counts["successfully_processed"] = counts["auto_processed"] + counts["approved"]

    if total > 0:
        counts["acceptance_rate"] = (counts["successfully_processed"] / total) * 100
        counts["auto_processing_rate"] = (counts["auto_processed"] / total) * 100
    else:
        counts["acceptance_rate"] = 0
        counts["auto_processing_rate"] = 0

    return counts
