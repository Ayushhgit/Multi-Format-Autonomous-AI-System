import asyncio
import aiohttp
import json
from datetime import datetime
from typing import Dict, Any, List
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from memory_store import MemoryStore

class ActionRouter:
    def __init__(self, memory_store: MemoryStore):
        self.memory_store = memory_store
        self.base_urls = {
            "crm": "https://api.example-crm.com",
            "alert": "https://api.example-alerts.com",
            "risk_alert": "https://api.example-risk.com",
            "notification": "https://api.example-notify.com"
        }
        
        # For demo purposes, we'll simulate these endpoints
        self.simulate_apis = True
    
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
            result = await self._execute_with_retry(action, trace_id, action_id)
            
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
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type((aiohttp.ClientError, asyncio.TimeoutError))
    )
    async def _execute_with_retry(self, action: Dict[str, Any], trace_id: str, action_id: str) -> Dict[str, Any]:
        """
        Execute action with automatic retry logic
        """
        action_type = action.get("type")
        endpoint = action.get("endpoint")
        data = action.get("data", {})
        
        self.memory_store.store_log(trace_id, {
            "stage": "action_attempt",
            "action_id": action_id,
            "attempt_timestamp": datetime.now().isoformat()
        })
        
        if self.simulate_apis:
            return await self._simulate_api_call(action_type, endpoint, data)
        else:
            return await self._make_real_api_call(action_type, endpoint, data)
    
    async def _simulate_api_call(self, action_type: str, endpoint: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Simulate API calls for demo purposes
        """
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
        """
        Make actual HTTP API calls
        """
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
        """
        Helper method to create action dictionaries
        """
        return {
            "type": action_type,
            "endpoint": endpoint,
            "data": data or {},
            "created_at": datetime.now().isoformat()
        }
        