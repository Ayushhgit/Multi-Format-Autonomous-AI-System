"""
Email Agent - Processes email content and makes contextual decisions
Extracts sender, urgency, issue, and tone analysis
"""

import os
import re
from datetime import datetime
from typing import Dict, Any, List
from langchain_groq import ChatGroq
from langchain.schema import HumanMessage, SystemMessage
from dotenv import load_dotenv
from utils.logger import logging

from memory_store import MemoryStore
from utils.tone_detector import ToneDetector

load_dotenv()

class EmailAgent:
    def __init__(self, memory_store: MemoryStore):
        self.memory_store = memory_store
        self.groq_api_key = os.getenv("GROQ_API_KEY")
        self.tone_detector = ToneDetector() if self.groq_api_key else None
        
        if self.groq_api_key:
            self.llm = ChatGroq(
                groq_api_key=self.groq_api_key,
                model_name="meta-llama/llama-4-scout-17b-16e-instruct",
                temperature=0.1
            )
        else:
            self.llm = None
            print("Warning: GROQ_API_KEY not found. Using rule-based processing.")
    
    async def process(self, email_content: str, trace_id: str) -> Dict[str, Any]:
        """
        Process email content and return structured data with actions
        """
        logging.info(f"Started processing email. Trace ID: {trace_id}, Content Length: {len(email_content)}")
        self.memory_store.store_log(trace_id, {
            "stage": "email_processing_start",
            "content_length": len(email_content),
            "timestamp": datetime.now().isoformat()
        })
        
        try:
            # Extract basic email information
            email_data = self._extract_email_data(email_content)
            
            # Analyze tone
            tone_analysis = await self._analyze_tone(email_content)
            email_data.update(tone_analysis)
            
            # Determine urgency
            urgency = self._determine_urgency(email_content, email_data)
            email_data["urgency"] = urgency
            
            # Make decisions and create actions
            actions = self._make_decisions(email_data)
            
            logging.info(f"Email Agent data {email_data}, action: {actions}")

            result = {
                "agent_type": "email",
                "extracted_data": email_data,
                "actions": actions,
                "processing_timestamp": datetime.now().isoformat()
            }
            
            self.memory_store.store_log(trace_id, {
                "stage": "email_processing_complete",
                "result": result,
                "timestamp": datetime.now().isoformat()
            })
            
            return result
            
        except Exception as e:
            error_result = {
                "agent_type": "email",
                "error": str(e),
                "processing_timestamp": datetime.now().isoformat()
            }
            
            self.memory_store.store_log(trace_id, {
                "stage": "email_processing_error",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            })
            
            return error_result
    
    def _extract_email_data(self, email_content: str) -> Dict[str, Any]:
        """
        Extract basic email information using regex patterns
        """
        data = {}
        
        # Extract sender
        sender_patterns = [
            r'From:\s*([^\r\n]+)',
            r'from:\s*([^\r\n]+)',
            r'From\s+([^\r\n]+)',
        ]
        
        for pattern in sender_patterns:
            match = re.search(pattern, email_content, re.IGNORECASE)
            if match:
                data["sender"] = match.group(1).strip()
                break
        
        if "sender" not in data:
            # Look for email addresses
            email_match = re.search(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', email_content)
            if email_match:
                data["sender"] = email_match.group(0)
            else:
                data["sender"] = "unknown"
        
        # Extract subject
        subject_patterns = [
            r'Subject:\s*([^\r\n]+)',
            r'subject:\s*([^\r\n]+)',
            r'Subject\s+([^\r\n]+)',
        ]
        
        for pattern in subject_patterns:
            match = re.search(pattern, email_content, re.IGNORECASE)
            if match:
                data["subject"] = match.group(1).strip()
                break
        
        if "subject" not in data:
            data["subject"] = "No subject"
        
        # Extract recipient
        to_patterns = [
            r'To:\s*([^\r\n]+)',
            r'to:\s*([^\r\n]+)',
        ]
        
        for pattern in to_patterns:
            match = re.search(pattern, email_content, re.IGNORECASE)
            if match:
                data["recipient"] = match.group(1).strip()
                break
        
        if "recipient" not in data:
            data["recipient"] = "unknown"
        
        # Extract main body (remove headers)
        body_start = email_content.find('\n\n')
        if body_start != -1:
            data["body"] = email_content[body_start+2:].strip()
        else:
            data["body"] = email_content.strip()
        
        # Extract issue/problem description
        data["issue"] = self._extract_issue(data["body"])
        
        return data
    
    def _extract_issue(self, body: str) -> str:
        """
        Extract the main issue or concern from email body
        """
        # Look for common issue indicators
        issue_patterns = [
            r'problem[:\s]+([^\n.!?]+)',
            r'issue[:\s]+([^\n.!?]+)',
            r'complaint[:\s]+([^\n.!?]+)',
            r'concern[:\s]+([^\n.!?]+)',
            r'difficulty[:\s]+([^\n.!?]+)',
        ]
        
        for pattern in issue_patterns:
            match = re.search(pattern, body, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        
        # If no specific issue pattern found, return first sentence
        sentences = re.split(r'[.!?]+', body)
        if sentences:
            return sentences[0].strip()[:200]  # Limit to 200 chars
        
        return "General inquiry"
    
    async def _analyze_tone(self, email_content: str) -> Dict[str, Any]:
        """
        Analyze email tone using LLM or rule-based approach
        """
        if self.llm:
            return await self._llm_analyze_tone(email_content)
        else:
            return self.tone_detector.analyze_tone(email_content)
    
    async def _llm_analyze_tone(self, email_content: str) -> Dict[str, Any]:
        """
        Use LLM to analyze email tone
        """
        try:
            system_prompt = """Analyze the tone of this email. Classify it as one of:
- angry: Clearly frustrated, upset, or aggressive
- polite: Professional, courteous, respectful
- neutral: Matter-of-fact, neither positive nor negative
- urgent: Time-sensitive, pressing, immediate action needed
- friendly: Warm, personal, positive

Also rate the emotion intensity from 1-10 (1=very mild, 10=very intense).
Respond in JSON format: {"tone": "category", "intensity": number, "confidence": 0.0-1.0}"""

            human_prompt = f"Email content:\n{email_content[:1000]}"

            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=human_prompt)
            ]
            
            response = await self.llm.ainvoke(messages)
            
            try:
                import json
                result = json.loads(response.content)
                return {
                    "tone": result.get("tone", "neutral"),
                    "tone_intensity": result.get("intensity", 5),
                    "tone_confidence": result.get("confidence", 0.7)
                }
            except:
                # Fallback to rule-based if JSON parsing fails
                return self.tone_detector.analyze_tone(email_content)
                
        except Exception as e:
            print(f"LLM tone analysis failed: {e}")
            return self.tone_detector.analyze_tone(email_content)
    
    def _determine_urgency(self, email_content: str, email_data: Dict[str, Any]) -> str:
        """
        Determine urgency level based on content and context
        """
        content_lower = email_content.lower()
        
        # High urgency indicators
        high_urgency_keywords = [
            'urgent', 'emergency', 'asap', 'immediately', 'critical',
            'system down', 'not working', 'broken', 'failed', 'error',
            'deadline', 'tomorrow', 'today', 'right now'
        ]
        
        # Medium urgency indicators
        medium_urgency_keywords = [
            'soon', 'quick', 'fast', 'priority', 'important',
            'issue', 'problem', 'concern', 'help needed'
        ]
        
        # Check for high urgency
        if any(keyword in content_lower for keyword in high_urgency_keywords):
            return "high"
        
        # Check for medium urgency
        if any(keyword in content_lower for keyword in medium_urgency_keywords):
            return "medium"
        
        # Check tone-based urgency
        if email_data.get("tone") in ["angry", "urgent"]:
            return "high" if email_data.get("tone_intensity", 5) > 7 else "medium"
        
        return "low"
    
    def _make_decisions(self, email_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Make decisions based on extracted email data and create actions
        """
        actions = []
        
        tone = email_data.get("tone", "neutral")
        urgency = email_data.get("urgency", "low")
        intensity = email_data.get("tone_intensity", 5)
        
        # Decision logic: angry tone + high urgency = escalate
        if tone == "angry" and urgency == "high":
            actions.append({
                "type": "crm",
                "endpoint": "/crm/escalate",
                "data": {
                    "sender": email_data.get("sender"),
                    "subject": email_data.get("subject"),
                    "issue": email_data.get("issue"),
                    "tone": tone,
                    "urgency": urgency,
                    "priority": "high",
                    "reason": "Angry customer with high urgency issue"
                }
            })
        
        # High intensity complaints get escalated
        elif tone == "angry" and intensity > 7:
            actions.append({
                "type": "crm",
                "endpoint": "/crm/escalate",
                "data": {
                    "sender": email_data.get("sender"),
                    "subject": email_data.get("subject"),
                    "issue": email_data.get("issue"),
                    "tone": tone,
                    "urgency": urgency,
                    "priority": "medium",
                    "reason": "High intensity complaint"
                }
            })
        
        # High urgency regardless of tone gets notification
        elif urgency == "high":
            actions.append({
                "type": "notification",
                "endpoint": "/notification",
                "data": {
                    "sender": email_data.get("sender"),
                    "subject": email_data.get("subject"),
                    "urgency": urgency,
                    "message": f"High urgency email from {email_data.get('sender')}"
                }
            })
        
        # If no specific action needed, just log
        if not actions:
            actions.append({
                "type": "log",
                "endpoint": "/log",
                "data": {
                    "action": "logged",
                    "sender": email_data.get("sender"),
                    "subject": email_data.get("subject"),
                    "tone": tone,
                    "urgency": urgency,
                    "status": "processed_and_filed"
                }
            })
        
        return actions