"""
Enhanced JSON Agent with Groq API Integration
Processes JSON content, validates against schemas, and uses Groq for intelligent analysis
"""

import json
import jsonschema
import asyncio
import aiohttp
from datetime import datetime
from typing import Dict, Any, List, Optional
from memory_store import MemoryStore
from dotenv import load_dotenv
import os

load_dotenv()

class EnhancedJSONAgent:

    def __init__(self, memory_store: MemoryStore):
        self.memory_store = memory_store
        self.groq_api_key = os.getenv("GROQ_API_KEY")
        self.groq_base_url = "https://api.groq.com/openai/v1/chat/completions"
        self.schemas = self._load_schemas()
        self.groq_headers = {
            "Authorization": f"Bearer {self.groq_api_key}",
            "Content-Type": "application/json"
        } if self.groq_api_key else {}
    
    def _load_schemas(self) -> Dict[str, Dict[str, Any]]:
        """Define validation schemas for different JSON types"""
        return {
            "rfq": {
                "type": "object",
                "required": ["customer_id", "items", "deadline"],
                "properties": {
                    "customer_id": {"type": "string"},
                    "items": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "required": ["product", "quantity"],
                            "properties": {
                                "product": {"type": "string"},
                                "quantity": {"type": "number", "minimum": 1},
                                "specifications": {"type": "string"}
                            }
                        }
                    },
                    "deadline": {"type": "string"},
                    "budget_range": {"type": "number", "minimum": 0},
                    "contact_email": {"type": "string", "format": "email"}
                }
            },
            "webhook": {
                "type": "object",
                "required": ["event", "timestamp", "data"],
                "properties": {
                    "event": {"type": "string"},
                    "timestamp": {"type": "string"},
                    "data": {"type": "object"},
                    "source": {"type": "string"},
                    "version": {"type": "string"}
                }
            },
            "transaction": {
                "type": "object",
                "required": ["transaction_id", "amount", "currency"],
                "properties": {
                    "transaction_id": {"type": "string"},
                    "amount": {"type": "number"},
                    "currency": {"type": "string", "enum": ["USD", "EUR", "GBP", "INR"]},
                    "merchant": {"type": "string"},
                    "timestamp": {"type": "string"},
                    "customer_id": {"type": "string"}
                }
            }
        }
    
    async def _call_groq_api(self, messages: List[Dict[str, str]], model: str = "llama-3.3-70b-versatile") -> Optional[str]:
        """Make async call to Groq API for JSON analysis"""
        payload = {
            "model": model,
            "messages": messages,
            "temperature": 0.1,
            "max_tokens": 2048,
            "top_p": 1,
            "stream": False
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.groq_base_url,
                    headers=self.groq_headers,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        return result["choices"][0]["message"]["content"]
                    else:
                        error_text = await response.text()
                        print(f"Groq API error {response.status}: {error_text}")
                        return None
        except Exception as e:
            print(f"Error calling Groq API: {str(e)}")
            return None
    
    async def _analyze_with_groq(self, data: Dict[str, Any], json_type: str, anomalies: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Use Groq API for intelligent JSON analysis"""
        
        # Prepare context for Groq
        context = {
            "json_type": json_type,
            "data_summary": {
                "total_keys": len(data),
                "has_nested_objects": any(isinstance(v, (dict, list)) for v in data.values()),
                "anomaly_count": len(anomalies)
            },
            "anomalies": anomalies[:5]  # Limit to first 5 anomalies to avoid token limits
        }
        
        # Create sample of data (first 1000 chars to avoid token limits)
        data_sample = json.dumps(data, indent=2)[:1000]
        if len(json.dumps(data, indent=2)) > 1000:
            data_sample += "...[truncated]"
        
        messages = [
            {
                "role": "system",
                "content": """You are an expert JSON analyst. Analyze the provided JSON data and provide insights in the following JSON format:
{
    "risk_assessment": {
        "risk_level": "low|medium|high",
        "risk_factors": ["factor1", "factor2"],
        "confidence_score": 0.85
    },
    "business_insights": {
        "key_patterns": ["pattern1", "pattern2"],
        "recommendations": ["rec1", "rec2"],
        "urgency": "low|medium|high"
    },
    "data_quality": {
        "completeness_score": 0.9,
        "consistency_issues": ["issue1"],
        "data_integrity": "good|fair|poor"
    },
    "suggested_actions": [
        {
            "action": "action_type",
            "priority": "low|medium|high",
            "reason": "explanation"
        }
    ]
}"""
            },
            {
                "role": "user",
                "content": f"""Analyze this JSON data:

Type: {json_type}
Context: {json.dumps(context, indent=2)}
Data Sample: {data_sample}

Provide detailed analysis focusing on business value, risks, and actionable recommendations."""
            }
        ]
        
        groq_response = await self._call_groq_api(messages)
        
        if groq_response:
            try:
                # Try to parse the JSON response from Groq
                analysis = json.loads(groq_response)
                return analysis
            except json.JSONDecodeError:
                # If Groq returns non-JSON, wrap it in a structure
                return {
                    "risk_assessment": {"risk_level": "medium", "confidence_score": 0.5},
                    "business_insights": {"recommendations": [groq_response[:200]]},
                    "data_quality": {"data_integrity": "unknown"},
                    "suggested_actions": []
                }
        
        # Fallback analysis if Groq is unavailable
        return self._fallback_analysis(json_type, anomalies)
    
    def _fallback_analysis(self, json_type: str, anomalies: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Fallback analysis when Groq API is unavailable"""
        high_severity_count = len([a for a in anomalies if a["severity"] == "high"])
        
        risk_level = "high" if high_severity_count > 0 else "medium" if len(anomalies) > 0 else "low"
        
        return {
            "risk_assessment": {
                "risk_level": risk_level,
                "risk_factors": [a["type"] for a in anomalies[:3]],
                "confidence_score": 0.7
            },
            "business_insights": {
                "key_patterns": [f"Standard {json_type} processing"],
                "recommendations": ["Standard validation completed"],
                "urgency": "medium" if anomalies else "low"
            },
            "data_quality": {
                "completeness_score": 0.8,
                "consistency_issues": [a["description"] for a in anomalies[:2]],
                "data_integrity": "fair" if anomalies else "good"
            },
            "suggested_actions": []
        }
    
    async def process(self, json_content: str, trace_id: str) -> Dict[str, Any]:
        """Enhanced JSON processing with Groq AI analysis"""
        self.memory_store.store_log(trace_id, {
            "stage": "enhanced_json_processing_start", 
            "content_length": len(json_content),
            "timestamp": datetime.now().isoformat()
        })
        
        try:
            # Parse JSON
            data = json.loads(json_content)
            
            # Determine JSON type
            json_type = self._determine_json_type(data)
            
            # Validate against schema
            validation_result = self._validate_json(data, json_type)
            
            # Detect anomalies
            anomalies = self._detect_anomalies(data, json_type, validation_result)
            
            # Extract key information
            extracted_data = self._extract_key_data(data, json_type)
            
            # Enhanced analysis with Groq AI
            ai_analysis = await self._analyze_with_groq(data, json_type, anomalies)
            
            # Make enhanced decisions with AI insights
            actions = self._make_enhanced_decisions(data, json_type, anomalies, extracted_data, ai_analysis)
            
            result = {
                "agent_type": "enhanced_json",
                "json_type": json_type,
                "validation_result": validation_result,
                "anomalies": anomalies,
                "extracted_data": extracted_data,
                "ai_analysis": ai_analysis,
                "actions": actions,
                "processing_timestamp": datetime.now().isoformat(),
                "enhancement_level": "groq_powered"
            }
            
            self.memory_store.store_log(trace_id, {
                "stage": "enhanced_json_processing_complete",
                "result": result,
                "ai_analysis_included": True,
                "timestamp": datetime.now().isoformat()
            })
            
            return result
            
        except json.JSONDecodeError as e:
            error_result = {
                "agent_type": "enhanced_json",
                "error": f"Invalid JSON format: {str(e)}",
                "error_type": "parse_error",
                "processing_timestamp": datetime.now().isoformat()
            }
            
            self.memory_store.store_log(trace_id, {
                "stage": "enhanced_json_processing_error",
                "error": str(e),
                "error_type": "parse_error",
                "timestamp": datetime.now().isoformat()
            })
            
            return error_result
            
        except Exception as e:
            error_result = {
                "agent_type": "enhanced_json",
                "error": str(e),
                "error_type": "processing_error",
                "processing_timestamp": datetime.now().isoformat()
            }
            
            self.memory_store.store_log(trace_id, {
                "stage": "enhanced_json_processing_error",
                "error": str(e),
                "error_type": "processing_error",
                "timestamp": datetime.now().isoformat()
            })
            
            return error_result
    
    def _determine_json_type(self, data: Dict[str, Any]) -> str:
        """Determine the type of JSON based on structure and content"""
        # Check for RFQ indicators
        if any(key in data for key in ["customer_id", "items", "deadline", "rfq_id"]):
            return "rfq"
        
        # Check for webhook indicators
        if any(key in data for key in ["event", "webhook", "payload"]) and "timestamp" in data:
            return "webhook"
        
        # Check for transaction indicators
        if any(key in data for key in ["transaction_id", "amount", "payment", "charge"]):
            return "transaction"
        
        # Check for API response indicators
        if "status" in data and any(key in data for key in ["data", "response", "result"]):
            return "api_response"
        
        # Default to generic
        return "generic"
    
    def _validate_json(self, data: Dict[str, Any], json_type: str) -> Dict[str, Any]:
        """Validate JSON against appropriate schema"""
        if json_type not in self.schemas:
            return {
                "is_valid": True,
                "message": f"No schema defined for type: {json_type}",
                "errors": []
            }
        
        try:
            schema = self.schemas[json_type]
            jsonschema.validate(instance=data, schema=schema)
            
            return {
                "is_valid": True,
                "message": "Validation successful",
                "errors": []
            }
            
        except jsonschema.ValidationError as e:
            return {
                "is_valid": False,
                "message": f"Schema validation failed: {e.message}",
                "errors": [e.message],
                "failed_path": list(e.path) if e.path else []
            }
        
        except Exception as e:
            return {
                "is_valid": False,
                "message": f"Validation error: {str(e)}",
                "errors": [str(e)]
            }
    
    def _detect_anomalies(self, data: Dict[str, Any], json_type: str, validation_result: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Detect anomalies in JSON data"""
        anomalies = []
        
        # Schema validation failures are anomalies
        if not validation_result["is_valid"]:
            anomalies.append({
                "type": "schema_violation",
                "severity": "high",
                "description": validation_result["message"],
                "details": validation_result["errors"]
            })
        
        # Type-specific anomaly detection
        if json_type == "rfq":
            anomalies.extend(self._detect_rfq_anomalies(data))
        elif json_type == "transaction":
            anomalies.extend(self._detect_transaction_anomalies(data))
        elif json_type == "webhook":
            anomalies.extend(self._detect_webhook_anomalies(data))
        
        # General anomalies
        anomalies.extend(self._detect_general_anomalies(data))
        
        return anomalies
    
    def _detect_rfq_anomalies(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Detect RFQ-specific anomalies"""
        anomalies = []
        
        # Check for unrealistic quantities
        if "items" in data:
            for item in data.get("items", []):
                quantity = item.get("quantity", 0)
                if quantity > 10000:
                    anomalies.append({
                        "type": "unusual_quantity",
                        "severity": "medium",
                        "description": f"Very high quantity requested: {quantity}",
                        "details": {"product": item.get("product"), "quantity": quantity}
                    })
        
        # Check for missing contact information
        if not data.get("contact_email") and not data.get("phone"):
            anomalies.append({
                "type": "missing_contact",
                "severity": "high",
                "description": "No contact information provided",
                "details": {}
            })
        
        return anomalies
    
    def _detect_transaction_anomalies(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Detect transaction-specific anomalies"""
        anomalies = []
        
        amount = data.get("amount", 0)
        
        # High value transactions
        if amount > 10000:
            anomalies.append({
                "type": "high_value_transaction",
                "severity": "high",
                "description": f"High value transaction: {amount}",
                "details": {"amount": amount, "currency": data.get("currency")}
            })
        
        # Negative amounts
        if amount < 0:
            anomalies.append({
                "type": "negative_amount",
                "severity": "high",
                "description": "Transaction with negative amount",
                "details": {"amount": amount}
            })
        
        return anomalies
    
    def _detect_webhook_anomalies(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Detect webhook-specific anomalies"""
        anomalies = []
        
        # Check for suspicious events
        suspicious_events = ["account_deletion", "admin_access", "data_export"]
        event = data.get("event", "").lower()
        
        if any(suspicious in event for suspicious in suspicious_events):
            anomalies.append({
                "type": "suspicious_event",
                "severity": "high",
                "description": f"Potentially suspicious event: {event}",
                "details": {"event": event}
            })
        
        return anomalies
    
    def _detect_general_anomalies(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Detect general anomalies applicable to any JSON"""
        anomalies = []
        
        # Check for very large objects
        if len(str(data)) > 50000:  # 50KB
            anomalies.append({
                "type": "large_payload",
                "severity": "medium",
                "description": "Unusually large JSON payload",
                "details": {"size_bytes": len(str(data))}
            })
        
        # Check for deeply nested structures
        def get_depth(obj, current_depth=0):
            if isinstance(obj, dict):
                return max(get_depth(v, current_depth + 1) for v in obj.values()) if obj else current_depth
            elif isinstance(obj, list):
                return max(get_depth(item, current_depth + 1) for item in obj) if obj else current_depth
            return current_depth
        
        depth = get_depth(data)
        if depth > 10:
            anomalies.append({
                "type": "deep_nesting",
                "severity": "low",
                "description": f"Deeply nested JSON structure (depth: {depth})",
                "details": {"nesting_depth": depth}
            })
        
        return anomalies
    
    def _extract_key_data(self, data: Dict[str, Any], json_type: str) -> Dict[str, Any]:
        """Extract key information based on JSON type"""
        extracted = {"json_type": json_type}
        
        if json_type == "rfq":
            extracted.update({
                "customer_id": data.get("customer_id"),
                "item_count": len(data.get("items", [])),
                "deadline": data.get("deadline"),
                "budget_range": data.get("budget_range"),
                "total_quantity": sum(item.get("quantity", 0) for item in data.get("items", []))
            })
        
        elif json_type == "transaction":
            extracted.update({
                "transaction_id": data.get("transaction_id"),
                "amount": data.get("amount"),
                "currency": data.get("currency"),
                "merchant": data.get("merchant")
            })
        
        elif json_type == "webhook":
            extracted.update({
                "event": data.get("event"),
                "source": data.get("source"),
                "timestamp": data.get("timestamp")
            })
        
        # General metadata
        extracted.update({
            "total_keys": len(data),
            "has_nested_objects": any(isinstance(v, (dict, list)) for v in data.values())
        })
        
        return extracted
    
    def _make_enhanced_decisions(
        self, 
        data: Dict[str, Any], 
        json_type: str, 
        anomalies: List[Dict[str, Any]], 
        extracted_data: Dict[str, Any],
        ai_analysis: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Enhanced decision making with AI insights"""
        actions = []
        
        # Get AI-suggested actions
        ai_suggested_actions = ai_analysis.get("suggested_actions", [])
        
        # Convert AI suggestions to actions
        for suggestion in ai_suggested_actions:
            if suggestion.get("priority") == "high":
                actions.append({
                    "type": "ai_recommended_action",
                    "endpoint": "/ai_action",
                    "data": {
                        "action": suggestion.get("action"),
                        "reason": suggestion.get("reason"),
                        "priority": suggestion.get("priority"),
                        "ai_confidence": ai_analysis.get("risk_assessment", {}).get("confidence_score", 0.5)
                    }
                })
        
        # Risk-based actions
        risk_level = ai_analysis.get("risk_assessment", {}).get("risk_level", "medium")
        
        if risk_level == "high":
            actions.append({
                "type": "high_risk_alert",
                "endpoint": "/risk_alert",
                "data": {
                    "json_type": json_type,
                    "risk_level": risk_level,
                    "risk_factors": ai_analysis.get("risk_assessment", {}).get("risk_factors", []),
                    "confidence_score": ai_analysis.get("risk_assessment", {}).get("confidence_score", 0.5),
                    "requires_immediate_attention": True
                }
            })
        
        # Business insights actions
        urgency = ai_analysis.get("business_insights", {}).get("urgency", "low")
        
        if urgency in ["high", "medium"]:
            actions.append({
                "type": "business_insight",
                "endpoint": "/business_insight",
                "data": {
                    "urgency": urgency,
                    "key_patterns": ai_analysis.get("business_insights", {}).get("key_patterns", []),
                    "recommendations": ai_analysis.get("business_insights", {}).get("recommendations", []),
                    "extracted_data": extracted_data
                }
            })
        
        # Traditional anomaly-based actions (enhanced with AI context)
        high_severity_anomalies = [a for a in anomalies if a["severity"] == "high"]
        
        if high_severity_anomalies:
            actions.append({
                "type": "enhanced_alert",
                "endpoint": "/enhanced_alert",
                "data": {
                    "json_type": json_type,
                    "anomaly_count": len(high_severity_anomalies),
                    "anomalies": high_severity_anomalies,
                    "ai_risk_assessment": ai_analysis.get("risk_assessment", {}),
                    "data_quality": ai_analysis.get("data_quality", {}),
                    "alert_level": "high"
                }
            })
        
        # If no specific actions needed, log with AI insights
        if not actions:
            actions.append({
                "type": "enhanced_log",
                "endpoint": "/enhanced_log",
                "data": {
                    "action": "processed_with_ai",
                    "json_type": json_type,
                    "anomaly_count": len(anomalies),
                    "ai_risk_level": risk_level,
                    "data_quality_score": ai_analysis.get("data_quality", {}).get("completeness_score", 0.8),
                    "status": "completed_with_ai_analysis"
                }
            })
        
        return actions