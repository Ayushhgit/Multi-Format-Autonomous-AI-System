"""
Tone detection utilities for email and text analysis
"""

import re
from typing import Dict, List
from langchain_groq import ChatGroq
from langchain.schema import HumanMessage
from utils.logger import logging
import os
from dotenv import load_dotenv

load_dotenv()

class ToneDetector:
    def __init__(self):
        self.llm = ChatGroq(
            groq_api_key=os.getenv("GROQ_API_KEY"),
            model_name="meta-llama/llama-4-scout-17b-16e-instruct"
        )
        
        # Define tone indicators
        self.angry_indicators = [
            "furious", "outraged", "disgusted", "unacceptable", "ridiculous",
            "terrible", "awful", "worst", "angry", "mad", "frustrated",
            "disappointed", "appalled", "shocked", "!!!", "URGENT", "IMMEDIATELY"
        ]
        
        self.polite_indicators = [
            "please", "thank you", "appreciate", "kindly", "grateful",
            "respect", "understand", "apologize", "sorry", "excuse me",
            "would you", "could you", "if possible"
        ]
        
        self.urgent_indicators = [
            "urgent", "asap", "immediately", "emergency", "critical",
            "time sensitive", "deadline", "rush", "priority", "soon as possible"
        ]
    
    async def analyze_tone(self, text: str) -> Dict[str, str]:
        """Detect tone using LLM with fallback to rule-based"""
        try:
            # Try LLM-based detection first
            return await self._detect_tone_llm(text)
        except:
            # Fallback to rule-based
            return self._detect_tone_rules(text)
    
    async def _detect_tone_llm(self, text: str) -> Dict[str, str]:
        """Use LLM to detect tone"""
        logging.info("Tone detection started")
        prompt = f"""
        Analyze the tone of this text and classify it:
        
        Tone options:
        - angry: Frustrated, upset, demanding
        - polite: Respectful, courteous, professional
        - neutral: Matter-of-fact, neither positive nor negative
        - urgent: Time-sensitive, pressing, requires immediate attention
        
        Text to analyze:
        {text[:1000]}
        
        Respond with JSON format:
        {{"tone": "angry/polite/neutral", "urgency": "high/medium/low", "confidence": "high/medium/low"}}
        """
        
        response = await self.llm.ainvoke([HumanMessage(content=prompt)])
        logging.info("Tone detection finished")
        # Parse response
        import json
        result = json.loads(response.content)
        return result
    
    def _detect_tone_rules(self, text: str) -> Dict[str, str]:
        """Rule-based tone detection"""
        text_lower = text.lower()
        
        # Count indicators
        angry_count = sum(1 for indicator in self.angry_indicators if indicator in text_lower)
        polite_count = sum(1 for indicator in self.polite_indicators if indicator in text_lower)
        urgent_count = sum(1 for indicator in self.urgent_indicators if indicator in text_lower)
        
        # Determine tone
        if angry_count > polite_count and angry_count > 0:
            tone = "angry"
        elif polite_count > 0:
            tone = "polite"
        else:
            tone = "neutral"
        
        # Determine urgency
        if urgent_count > 2 or "!!!" in text:
            urgency = "high"
        elif urgent_count > 0:
            urgency = "medium"
        else:
            urgency = "low"
        
        return {
            "tone": tone,
            "urgency": urgency,
            "confidence": "medium"
        }
    
    def extract_sentiment_keywords(self, text: str) -> List[str]:
        """Extract sentiment-related keywords"""
        keywords = []
        text_lower = text.lower()
        
        all_indicators = self.angry_indicators + self.polite_indicators + self.urgent_indicators
        for indicator in all_indicators:
            if indicator in text_lower:
                keywords.append(indicator)
        
        return keywords