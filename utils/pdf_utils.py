"""
PDF Utility functions for text extraction and processing
"""

import fitz
import re
from typing import Dict, List, Optional

def extract_tables_from_pdf(pdf_content: bytes) -> List[List[str]]:
    """Extract tables from PDF content"""
    try:
        doc = fitz.open(stream=pdf_content, filetype="pdf")
        tables = []
        
        for page_num in range(doc.page_count):
            page = doc[page_num]
            # Simple table extraction - can be enhanced
            tables_on_page = page.find_tables()
            for table in tables_on_page:
                table_data = table.extract()
                tables.append(table_data)
        
        doc.close()
        return tables
    except:
        return []

def extract_metadata_from_pdf(pdf_content: bytes) -> Dict[str, str]:
    """Extract PDF metadata"""
    try:
        doc = fitz.open(stream=pdf_content, filetype="pdf")
        metadata = doc.metadata
        doc.close()
        return metadata
    except:
        return {}

def find_monetary_amounts(text: str) -> List[float]:
    """Find all monetary amounts in text"""
    patterns = [
        r'\$([0-9,]+\.?[0-9]*)',  # $1,234.56
        r'([0-9,]+\.?[0-9]*)\s*(?:USD|dollars?)',  # 1234.56 USD
        r'(?:total|amount|sum)[\s:]*([0-9,]+\.?[0-9]*)'  # Total: 1234.56
    ]
    
    amounts = []
    for pattern in patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        for match in matches:
            try:
                amount = float(match.replace(',', ''))
                amounts.append(amount)
            except ValueError:
                continue
    
    return amounts


