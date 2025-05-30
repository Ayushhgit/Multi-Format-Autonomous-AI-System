"""
PDF Agent - Processes PDF content and extracts structured data
Handles invoices, regulations, and other document types
"""

import fitz  # PyMuPDF
import re
from datetime import datetime
from typing import Dict, Any, List, Optional
from memory_store import MemoryStore
from langchain_groq import ChatGroq
from langchain.schema import HumanMessage
from dotenv import load_dotenv
import os

load_dotenv()

class PDFAgent:
    def __init__(self, memory_store: MemoryStore):
        self.memory_store = memory_store
        self.llm = ChatGroq(
            groq_api_key=os.getenv("GROQ_API_KEY"),
            model_name="meta-llama/llama-4-scout-17b-16e-instruct"
        )
        
    async def process(self, pdf_content: bytes, trace_id: str, filename: str = "") -> Dict[str, Any]:
        """
        Process PDF content and return structured analysis with actions
        """
        self.memory_store.store_log(trace_id, {
            "stage": "pdf_processing_start",
            "filename": filename,
            "content_size": len(pdf_content),
            "timestamp": datetime.now().isoformat()
        })
        
        try:
            # Extract text from PDF
            text_content = self._extract_text_from_pdf(pdf_content)
            
            # Determine document type
            doc_type = await self._determine_document_type(text_content)
            
            # Extract structured data based on type
            extracted_data = await self._extract_structured_data(text_content, doc_type)
            
            # Detect anomalies and risks
            anomalies = self._detect_anomalies(extracted_data, doc_type, text_content)
            
            # Make decisions and create actions
            actions = self._make_decisions(extracted_data, doc_type, anomalies)
            
            result = {
                "agent_type": "pdf",
                "document_type": doc_type,
                "filename": filename,
                "text_length": len(text_content),
                "extracted_data": extracted_data,
                "anomalies": anomalies,
                "actions": actions,
                "processing_timestamp": datetime.now().isoformat()
            }
            
            self.memory_store.store_log(trace_id, {
                "stage": "pdf_processing_complete",
                "result": result,
                "timestamp": datetime.now().isoformat()
            })
            
            return result
            
        except Exception as e:
            error_result = {
                "agent_type": "pdf",
                "error": str(e),
                "error_type": "processing_error",
                "filename": filename,
                "processing_timestamp": datetime.now().isoformat()
            }
            
            self.memory_store.store_log(trace_id, {
                "stage": "pdf_processing_error",
                "error": str(e),
                "filename": filename,
                "timestamp": datetime.now().isoformat()
            })
            
            return error_result
    
    def _extract_text_from_pdf(self, pdf_content: bytes) -> str:
        """Extract text content from PDF using PyMuPDF"""
        try:
            doc = fitz.open(stream=pdf_content, filetype="pdf")
            text = ""
            
            for page_num in range(doc.page_count):
                page = doc[page_num]
                text += page.get_text()
                text += "\n\n"  # Add page break
            
            doc.close()
            return text.strip()
            
        except Exception as e:
            raise Exception(f"Failed to extract text from PDF: {str(e)}")
    
    async def _determine_document_type(self, text_content: str) -> str:
        """Use LangChain + Groq to determine document type"""
        prompt = f"""
        Analyze the following document text and classify it into one of these types:
        - invoice: Contains billing information, amounts, due dates
        - regulation: Contains policy, compliance, or regulatory information
        - contract: Contains agreement terms, signatures, legal language
        - report: Contains analysis, data, findings
        - manual: Contains instructions, procedures, guidelines
        - other: Doesn't fit other categories
        
        Document text (first 1000 characters):
        {text_content[:1000]}
        
        Respond with just the document type (one word):
        """
        
        try:
            response = await self.llm.ainvoke([HumanMessage(content=prompt)])
            doc_type = response.content.strip().lower()
            
            # Validate response
            valid_types = ["invoice", "regulation", "contract", "report", "manual", "other"]
            if doc_type in valid_types:
                return doc_type
            else:
                return "other"
                
        except Exception:
            # Fallback to rule-based classification
            return self._classify_document_fallback(text_content)
    
    def _classify_document_fallback(self, text_content: str) -> str:
        """Fallback rule-based document classification"""
        text_lower = text_content.lower()
        
        # Invoice indicators
        invoice_keywords = ["invoice", "bill", "amount due", "total:", "payment", "due date", "subtotal"]
        if any(keyword in text_lower for keyword in invoice_keywords):
            return "invoice"
        
        # Regulation indicators
        regulation_keywords = ["gdpr", "hipaa", "fda", "regulation", "compliance", "policy", "shall", "must not"]
        if any(keyword in text_lower for keyword in regulation_keywords):
            return "regulation"
        
        # Contract indicators
        contract_keywords = ["agreement", "contract", "terms and conditions", "signature", "party", "whereas"]
        if any(keyword in text_lower for keyword in contract_keywords):
            return "contract"
        
        return "other"
    
    async def _extract_structured_data(self, text_content: str, doc_type: str) -> Dict[str, Any]:
        """Extract structured data based on document type"""
        if doc_type == "invoice":
            return await self._extract_invoice_data(text_content)
        elif doc_type == "regulation":
            return await self._extract_regulation_data(text_content)
        elif doc_type == "contract":
            return await self._extract_contract_data(text_content)
        else:
            return await self._extract_general_data(text_content)
    
    async def _extract_invoice_data(self, text_content: str) -> Dict[str, Any]:
        """Extract invoice-specific data"""
        prompt = f"""
        Extract the following information from this invoice text:
        - total_amount: The final total amount (number only)
        - currency: Currency symbol or code
        - due_date: Payment due date
        - invoice_number: Invoice ID/number
        - vendor_name: Company/vendor name
        
        Invoice text:
        {text_content[:2000]}
        
        Respond in JSON format:
        """
        
        try:
            response = await self.llm.ainvoke([HumanMessage(content=prompt)])
            # Parse LLM response as JSON
            import json
            extracted = json.loads(response.content)
        except:
            # Fallback to regex extraction
            extracted = self._extract_invoice_regex(text_content)
        
        return extracted
    
    def _extract_invoice_regex(self, text: str) -> Dict[str, Any]:
        """Fallback regex-based invoice extraction"""
        # Extract monetary amounts
        amount_pattern = r'(?:total|amount|due)[\s:]*\$?([0-9,]+\.?[0-9]*)'
        amounts = re.findall(amount_pattern, text, re.IGNORECASE)
        
        # Extract invoice number
        invoice_pattern = r'(?:invoice|inv)[\s#:]*([A-Z0-9-]+)'
        invoice_matches = re.findall(invoice_pattern, text, re.IGNORECASE)
        
        return {
            "total_amount": float(amounts[-1].replace(',', '')) if amounts else 0,
            "currency": "USD",  # Default
            "invoice_number": invoice_matches[0] if invoice_matches else None,
            "vendor_name": None,
            "due_date": None
        }
    
    async def _extract_regulation_data(self, text_content: str) -> Dict[str, Any]:
        """Extract regulation-specific data"""
        # Check for specific regulation types
        regulation_types = []
        compliance_keywords = {
            "GDPR": ["gdpr", "general data protection", "data protection regulation"],
            "HIPAA": ["hipaa", "health insurance portability", "protected health information"],
            "FDA": ["fda", "food and drug administration", "drug approval"],
            "SOX": ["sarbanes-oxley", "sox", "financial reporting"],
            "PCI": ["pci", "payment card industry", "cardholder data"]
        }
        
        text_lower = text_content.lower()
        for reg_type, keywords in compliance_keywords.items():
            if any(keyword in text_lower for keyword in keywords):
                regulation_types.append(reg_type)
        
        return {
            "regulation_types": regulation_types,
            "compliance_areas": regulation_types,
            "risk_level": "high" if regulation_types else "low",
            "requires_review": len(regulation_types) > 0
        }
    
    async def _extract_contract_data(self, text_content: str) -> Dict[str, Any]:
        """Extract contract-specific data"""
        # Extract contract value
        value_pattern = r'\$([0-9,]+(?:\.[0-9]{2})?)'
        values = re.findall(value_pattern, text_content)
        
        # Extract dates
        date_pattern = r'(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})'
        dates = re.findall(date_pattern, text_content)
        
        return {
            "contract_values": [float(v.replace(',', '')) for v in values],
            "max_value": max([float(v.replace(',', '')) for v in values]) if values else 0,
            "important_dates": dates,
            "party_count": text_content.lower().count("party")
        }
    
    async def _extract_general_data(self, text_content: str) -> Dict[str, Any]:
        """Extract general document data"""
        return {
            "word_count": len(text_content.split()),
            "page_estimate": len(text_content) // 2000,  # Rough estimate
            "contains_numbers": bool(re.search(r'\d+', text_content)),
            "contains_dates": bool(re.search(r'\d{1,2}[/-]\d{1,2}[/-]\d{2,4}', text_content))
        }
    
    def _detect_anomalies(self, extracted_data: Dict[str, Any], doc_type: str, text_content: str) -> List[Dict[str, Any]]:
        """Detect anomalies in PDF content"""
        anomalies = []
        
        if doc_type == "invoice":
            # High value invoice
            total_amount = extracted_data.get("total_amount", 0)
            if total_amount > 10000:
                anomalies.append({
                    "type": "high_value_invoice",
                    "severity": "high",
                    "description": f"High value invoice: ${total_amount:,.2f}",
                    "details": {"amount": total_amount}
                })
        
        elif doc_type == "regulation":
            # Multiple compliance areas
            regulation_types = extracted_data.get("regulation_types", [])
            if len(regulation_types) > 2:
                anomalies.append({
                    "type": "multiple_regulations",
                    "severity": "medium",
                    "description": f"Document covers multiple regulations: {', '.join(regulation_types)}",
                    "details": {"regulations": regulation_types}
                })
        
        # General anomalies
        if len(text_content) > 100000:  # Very large document
            anomalies.append({
                "type": "large_document",
                "severity": "low",
                "description": "Unusually large document",
                "details": {"size": len(text_content)}
            })
        
        return anomalies
    
    def _make_decisions(self, extracted_data: Dict[str, Any], doc_type: str, anomalies: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Make decisions and create actions based on PDF analysis"""
        actions = []
        
        # Handle high severity anomalies
        high_severity_anomalies = [a for a in anomalies if a["severity"] == "high"]
        
        if high_severity_anomalies:
            actions.append({
                "type": "alert",
                "endpoint": "/alert",
                "data": {
                    "document_type": doc_type,
                    "anomaly_count": len(high_severity_anomalies),
                    "anomalies": high_severity_anomalies,
                    "extracted_data": extracted_data,
                    "alert_level": "high",
                    "reason": "High severity anomalies detected in PDF"
                }
            })
        
        # Document type specific actions
        if doc_type == "invoice":
            total_amount = extracted_data.get("total_amount", 0)
            if total_amount > 10000:
                actions.append({
                    "type": "finance_alert",
                    "endpoint": "/finance_alert",
                    "data": {
                        "invoice_number": extracted_data.get("invoice_number"),
                        "amount": total_amount,
                        "vendor": extracted_data.get("vendor_name"),
                        "requires_approval": True,
                        "reason": "High value invoice requires approval"
                    }
                })
        
        elif doc_type == "regulation":
            regulation_types = extracted_data.get("regulation_types", [])
            if regulation_types:
                actions.append({
                    "type": "compliance_alert",
                    "endpoint": "/compliance_alert",
                    "data": {
                        "regulation_types": regulation_types,
                        "risk_level": extracted_data.get("risk_level"),
                        "requires_review": True,
                        "reason": "Regulatory document requires compliance review"
                    }
                })
        
        # Default logging action
        if not actions:
            actions.append({
                "type": "log",
                "endpoint": "/log",
                "data": {
                    "action": "processed",
                    "document_type": doc_type,
                    "anomaly_count": len(anomalies),
                    "status": "completed"
                }
            })
        
        return actions