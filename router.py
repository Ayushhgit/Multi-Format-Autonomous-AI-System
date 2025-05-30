"""
Action Router - Routes and executes actions based on agent decisions
"""

import os
import asyncio
import aiohttp
import json
from datetime import datetime, timedelta
from typing import Dict, Any, List
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from utils.logger import logging

from memory_store import MemoryStore

class ActionRouter:
    def __init__(self, memory_store: MemoryStore):
        logging.info("Initializing ActionRouter")
        self.memory_store = memory_store
        self.base_urls = {
            "crm": "https://api.example-crm.com",
            "alert": "https://api.example-alerts.com",
            "risk_alert": "https://api.example-risk.com",
            "notification": "https://api.example-notify.com",
            "finance_alert": "https://api.example-finance.com"
        }
        
        # For demo purposes, we'll simulate these endpoints
        self.simulate_apis = True
        
        self.available_actions = self._load_available_actions()
        logging.info(f"Loaded {len(self.available_actions)} available actions")
    
    def _load_available_actions(self) -> Dict[str, Any]:
        """Load available actions from configuration"""
        logging.debug("Loading available actions")
        return {
            "send_email": self._send_email,
            "store_data": self._store_data,
            "notify": self._notify,
            "alert": self._alert,
            "risk_alert": self._risk_alert,
            "finance_alert": self._finance_alert
        }
    
    async def execute_action(self, action: Dict[str, Any], trace_id: str) -> Dict[str, Any]:
        """
        Execute an action with retry logic and logging
        """
        action_id = f"{trace_id}_{action.get('type', 'unknown')}_{datetime.now().timestamp()}"
        
        self.memory_store.store_log(trace_id, {
            "stage": "action_start",
            "action_id": action_id,
            "action": action,
            "timestamp": datetime.now().isoformat()
        })
        
        try:
            action_type = action.get("type")
            if not action_type:
                raise ValueError("Action type not specified")
            
            if action_type not in self.available_actions:
                raise ValueError(f"Unsupported action type: {action_type}")
            
            # Execute the action
            result = await self.available_actions[action_type](action.get("params", {}), trace_id)
            
            self.memory_store.store_log(trace_id, {
                "stage": "action_success",
                "action_id": action_id,
                "result": result,
                "timestamp": datetime.now().isoformat()
            })
            
            return {
                "action_id": action_id,
                "action": action,
                "result": result,
                "status": "success",
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            error_result = {
                "action_id": action_id,
                "action": action,
                "error": str(e),
                "status": "failed",
                "timestamp": datetime.now().isoformat()
            }
            
            self.memory_store.store_log(trace_id, {
                "stage": "action_failed",
                "action_id": action_id,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            })
            
            return error_result
    
    async def _send_email(self, params: Dict[str, Any], trace_id: str) -> Dict[str, Any]:
        """Send an email action"""
        logging.debug(f"Executing send_email action for trace {trace_id}")
        return {
            "status": "email_sent",
            "email_id": f"EMAIL-{datetime.now().timestamp()}",
            "recipient": params.get("recipient", "default@example.com"),
            "subject": params.get("subject", "No Subject")
        }
    
    async def _store_data(self, params: Dict[str, Any], trace_id: str) -> Dict[str, Any]:
        """Store data action"""
        logging.debug(f"Executing store_data action for trace {trace_id}")
        return {
            "status": "data_stored",
            "storage_id": f"STORE-{datetime.now().timestamp()}",
            "data_type": params.get("data_type", "unknown")
        }
    
    async def _notify(self, params: Dict[str, Any], trace_id: str) -> Dict[str, Any]:
        """Send notification action"""
        logging.debug(f"Executing notify action for trace {trace_id}")
        return {
            "status": "notification_sent",
            "notification_id": f"NOT-{datetime.now().timestamp()}",
            "channels": params.get("channels", ["email"]),
            "priority": params.get("priority", "normal")
        }
    
    async def _alert(self, params: Dict[str, Any], trace_id: str) -> Dict[str, Any]:
        """Send alert action"""
        logging.debug(f"Executing alert action for trace {trace_id}")
        return {
            "status": "alert_sent",
            "alert_id": f"ALT-{datetime.now().timestamp()}",
            "channels": params.get("channels", ["email", "slack"]),
            "recipients": params.get("recipients", ["admin@company.com"]),
            "severity": params.get("severity", "medium")
        }
    
    async def _risk_alert(self, params: Dict[str, Any], trace_id: str) -> Dict[str, Any]:
        """Send risk alert action"""
        logging.debug(f"Executing risk_alert action for trace {trace_id}")
        return {
            "status": "risk_alert_sent",
            "risk_id": f"RSK-{datetime.now().timestamp()}",
            "risk_level": params.get("risk_level", "medium"),
            "review_required": True,
            "review_deadline": (datetime.now() + timedelta(hours=24)).isoformat()
        }
    
    async def _finance_alert(self, params: Dict[str, Any], trace_id: str) -> Dict[str, Any]:
        """Send finance alert action"""
        logging.debug(f"Executing finance_alert action for trace {trace_id}")
        try:
            # Generate a unique finance alert ID
            alert_id = f"FIN-{datetime.now().timestamp()}"
            
            # Get parameters with defaults
            amount = params.get("amount", 0.0)
            currency = params.get("currency", "USD")
            alert_type = params.get("alert_type", "transaction")
            severity = params.get("severity", "medium")
            
            # Validate amount
            if not isinstance(amount, (int, float)) or amount < 0:
                raise ValueError("Invalid amount specified")
            
            # Create alert response
            response = {
                "status": "finance_alert_sent",
                "alert_id": alert_id,
                "amount": amount,
                "currency": currency,
                "alert_type": alert_type,
                "severity": severity,
                "timestamp": datetime.now().isoformat(),
                "requires_review": severity in ["high", "critical"],
                "review_deadline": (datetime.now() + timedelta(hours=24)).isoformat() if severity in ["high", "critical"] else None
            }
            
            return response
            
        except Exception as e:
            logging.error(f"Error in finance_alert: {str(e)}", exc_info=True)
            raise
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type((aiohttp.ClientError, asyncio.TimeoutError))
    )
    async def _execute_with_retry(self, action: Dict[str, Any], trace_id: str, action_id: str) -> Dict[str, Any]:
        """Execute action with automatic retry logic"""
        action_type = action.get("type")
        endpoint = action.get("endpoint")
        data = action.get("data", {})
        
        if self.simulate_apis:
            return await self._simulate_api_call(action_type, endpoint, data)
        else:
            return await self._make_real_api_call(action_type, endpoint, data)
    
    async def _simulate_api_call(self, action_type: str, endpoint: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Simulate API calls for demo purposes"""
        # Simulate network delay
        await asyncio.sleep(0.5)
        
        # Simulate occasional failures for demo
        import random
        if random.random() < 0.2:  # 20% failure rate for demo
            raise aiohttp.ClientError("Simulated API failure")
        
        # Return simulated responses
        responses = {
            "/crm/escalate": {
                "ticket_id": f"CRM-{random.randint(1000, 9999)}",
                "status": "escalated",
                "assigned_to": "support_manager",
                "priority": "high"
            },
            "/alert": {
                "alert_id": f"ALT-{random.randint(1000, 9999)}",
                "status": "sent",
                "channels": ["email", "slack"],
                "recipients": ["admin@company.com"]
            },
            "/risk_alert": {
                "risk_id": f"RSK-{random.randint(1000, 9999)}",
                "status": "flagged",
                "risk_level": "medium",
                "review_required": True
            },
            "/notification": {
                "notification_id": f"NOT-{random.randint(1000, 9999)}",
                "status": "delivered",
                "method": "email"
            }
        }
        
        return responses.get(endpoint, {
            "status": "processed",
            "message": f"Action {action_type} completed successfully"
        })
    
    async def _make_real_api_call(self, action_type: str, endpoint: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Make actual HTTP API calls"""
        # Determine base URL
        base_url = self.base_urls.get(action_type.split('/')[0], "https://api.example.com")
        full_url = f"{base_url}{endpoint}"
        
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "MultiAgentSystem/1.0"
        }
        
        timeout = aiohttp.ClientTimeout(total=30)
        
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(full_url, json=data, headers=headers) as response:
                response.raise_for_status()
                return await response.json()
    
    def create_action(self, action_type: str, endpoint: str, data: Dict[str, Any] = None) -> Dict[str, Any]:
        """Helper method to create action dictionaries"""
        return {
            "type": action_type,
            "endpoint": endpoint,
            "data": data or {},
            "created_at": datetime.now().isoformat()
        }
        