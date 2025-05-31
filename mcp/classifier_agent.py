"""
Classifier Agent - Determines format and business intent of uploaded content
Uses Groq API with LangChain for intelligent classification
"""

import os
import json
from datetime import datetime
from typing import Dict, Any, Optional
from utils.logger import logging

from langchain_groq import ChatGroq
from langchain.schema import HumanMessage, SystemMessage
from dotenv import load_dotenv

load_dotenv()

class ClassifierAgent:
    def __init__(self):
        self.groq_api_key = os.getenv("GROQ_API_KEY")
        if not self.groq_api_key:
            print("Warning: GROQ_API_KEY not found. Using rule-based fallback.")
            self.llm = None
        else:
            self.llm = ChatGroq(
                groq_api_key=self.groq_api_key,
                model_name="meta-llama/llama-4-scout-17b-16e-instruct",
                temperature=0.1
            )
    
    async def classify(self, content: bytes, filename: str, content_type: str) -> Dict[str, Any]:
        """
        Classify the input format and business intent
        """
        try:
            # First, determine format based on file extension and content type
            format_type = self._determine_format(filename, content_type, content)
            
            # Convert content to text for intent analysis
            text_content = self._extract_text_content(content, format_type)
            
            # Determine business intent
            intent = await self._determine_intent(text_content, format_type)
            logging.info(f"Classifier Classified the format: {format_type} and intent: {intent}")
            return {
                "format": format_type,
                "intent": intent,
                "source": "user_upload",
                "timestamp": datetime.now().isoformat(),
                "confidence": self._calculate_confidence(format_type, intent, text_content)
            }
            
        except Exception as e:
            return {
                "format": "Unknown",
                "intent": "Unknown",
                "source": "user_upload",
                "timestamp": datetime.now().isoformat(),
                "error": str(e),
                "confidence": 0.0
            }
    
    def _determine_format(self, filename: str, content_type: str, content: bytes) -> str:
        """
        Determine file format based on extension, MIME type, and content analysis
        """
        filename_lower = filename.lower() if filename else ""
        
        # PDF detection
        if (filename_lower.endswith('.pdf') or 
            content_type == 'application/pdf' or 
            content.startswith(b'%PDF')):
            return "PDF"
        
        # JSON detection
        if (filename_lower.endswith('.json') or 
            content_type == 'application/json'):
            try:
                json.loads(content.decode('utf-8'))
                return "JSON"
            except:
                pass
        
        # Email detection 
        try:
            text = content.decode('utf-8')
            if ('From:' in text and 'To:' in text) or \
               ('Subject:' in text) or \
               (text.count('@') > 0 and ('Dear' in text or 'Hi' in text)):
                return "Email"
        except:
            pass
        
        # Try to parse as JSON if it looks like structured data
        try:
            json.loads(content.decode('utf-8'))
            return "JSON"
        except:
            pass
        return "Email"
    
    def _extract_text_content(self, content: bytes, format_type: str) -> str:
        """
        Extract text content based on format
        """
        if format_type == "PDF":
            return "PDF content for analysis"
        else:
            try:
                return content.decode('utf-8')
            except:
                return "Binary content"
    
    async def _determine_intent(self, text_content: str, format_type: str) -> str:
        """
        Determine business intent using LLM or rule-based fallback
        """
        if self.llm:
            return await self._llm_classify_intent(text_content, format_type)
        else:
            return self._rule_based_intent(text_content, format_type)
    
    async def _llm_classify_intent(self, text_content: str, format_type: str) -> str:
        """
        Use Groq LLM to classify business intent
        """
        try:
            system_prompt = """You are a business document classifier. Analyze the provided content and classify it into one of these business intents:

1. RFQ (Request for Quote) - Customer requesting pricing or proposals
2. Complaint - Customer complaint or dissatisfaction
3. Invoice - Billing or payment related documents
4. Regulation - Compliance, policy, or regulatory documents
5. Fraud Risk - Potentially fraudulent or suspicious content

Respond with ONLY the intent category (one word)."""

            human_prompt = f"""Format: {format_type}
Content: {text_content[:1000]}...

Intent:"""

            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=human_prompt)
            ]
            
            response = await self.llm.ainvoke(messages)
            intent = response.content.strip()
            
            # Validate response
            valid_intents = ["RFQ", "Complaint", "Invoice", "Regulation", "Fraud Risk"]
            if intent in valid_intents:
                return intent
            else:
                return self._rule_based_intent(text_content, format_type)
                
        except Exception as e:
            print(f"LLM classification failed: {e}")
            return self._rule_based_intent(text_content, format_type)
    
    def _rule_based_intent(self, text_content: str, format_type: str) -> str:
        """
        Rule-based intent classification as fallback
        """
        text_lower = text_content.lower()
        
        # RFQ indicators
        rfq_keywords = ['quote', 'proposal', 'pricing', 'rfq', 'request for quote', 'bid']
        if any(keyword in text_lower for keyword in rfq_keywords):
            return "RFQ"
        
        # Complaint indicators
        complaint_keywords = ['complaint', 'dissatisfied', 'unhappy', 'problem', 'issue', 'disappointed', 'angry']
        if any(keyword in text_lower for keyword in complaint_keywords):
            return "Complaint"
        
        # Invoice indicators
        invoice_keywords = ['invoice', 'bill', 'payment', 'amount due', 'total', '$', 'pay', 'billing']
        if any(keyword in text_lower for keyword in invoice_keywords):
            return "Invoice"
        
        # Regulation indicators
        regulation_keywords = ['gdpr', 'hipaa', 'fda', 'compliance', 'regulation', 'policy', 'legal']
        if any(keyword in text_lower for keyword in regulation_keywords):
            return "Regulation"
        
        # Fraud risk indicators
        fraud_keywords = ['urgent', 'verify account', 'click here', 'suspended', 'security alert', 'immediate action']
        if any(keyword in text_lower for keyword in fraud_keywords):
            return "Fraud Risk"
        
        # Default based on format
        if format_type == "PDF":
            return "Invoice"
        elif format_type == "JSON":
            return "RFQ"
        else:
            return "Complaint"
    
    def _calculate_confidence(self, format_type: str, intent: str, text_content: str) -> float:
        """
        Calculate confidence score for the classification
        """
        confidence = 0.4  # Base confidence
        
        # Increase confidence based on clear indicators
        if format_type == "PDF" and intent == "Invoice":
            confidence += 0.3
        elif format_type == "JSON" and intent == "RFQ":
            confidence += 0.3
        elif format_type == "Email" and intent in ["Complaint", "RFQ"]:
            confidence += 0.2
        
        # Increase confidence if using LLM
        if self.llm:
            confidence += 0.2
        
        return min(confidence, 1.0)