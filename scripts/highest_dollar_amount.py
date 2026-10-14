import re
import requests
from io import BytesIO
from pypdf import PdfReader

import re
import requests
from io import BytesIO
from pypdf import PdfReader

# Statutory limits / boilerplate figures to ignore explicitly
BOILERPLATE_AMOUNTS = {50000.00, 35000.00, 100000.00}

def extract_actual_order_amount(pdf_url):
    """Downloads LTB PDF and extracts the actual ordered arrears/compensation,

    ignoring boilerplate statutory caps like $50,000.00.
    """
    if not pdf_url or pdf_url == "#" or not pdf_url.startswith("http"):
        return 0.0

    try:
        response = requests.get(pdf_url, timeout=15)
        if response.status_code != 200:
            return 0.0

        pdf_file = BytesIO(response.content)
        reader = PdfReader(pdf_file)

        full_text = ""
        for page in reader.pages:
            text = page.extract_text()
            if text:
                full_text += text + "\n"

        # 1. First Priority: Look for explicit 'Total amount owing' or 'shall pay' lines
        # Matches: "Total amount owing to the Landlord\n$8,456.71" or "Tenant shall pay... $8,456.71"
        target_patterns = [
            r"Total amount owing[^\n\$]*\$\s*([0-9]{1,3}(?:,[0-9]{3})*\.[0-9]{2})",
            r"Total amount of rent arrears[^\n\$]*\$\s*([0-9]{1,3}(?:,[0-9]{3})*\.[0-9]{2})",
            r"shall pay[^\n\$]*\$\s*([0-9]{1,3}(?:,[0-9]{3})*\.[0-9]{2})",
            r"Landlord is owed[^\n\$]*\$\s*([0-9]{1,3}(?:,[0-9]{3})*\.[0-9]{2})",
        ]

        for pattern in target_patterns:
            matches = re.findall(pattern, full_text, re.IGNORECASE)
            for m in matches:
                try:
                    val = float(m.replace(",", ""))
                    if val not in BOILERPLATE_AMOUNTS and 0 < val < 100000:
                        return val
                except ValueError:
                    continue

        # 2. Fallback: Find all dollar figures, excluding known boilerplate amounts
        all_amounts = re.findall(
            r"\$\s*([0-9]{1,3}(?:,[0-9]{3})*\.[0-9]{2})", full_text
        )
        parsed = []
        for amt_str in all_amounts:
            try:
                val = float(amt_str.replace(",", ""))
                if val not in BOILERPLATE_AMOUNTS and 0 < val < 100000:
                    parsed.append(val)
            except ValueError:
                continue

        return max(parsed) if parsed else 0.0

    except Exception:
        return 0.0

if __name__ == "__main__":
    print(
        extract_actual_order_amount('https://d3hf2qahezjxpx.cloudfront.net/attachments/exportedBinaries20260928_143512/069N30000154JK2IAM/LTB-L-004400-26-HR.pdf'))
