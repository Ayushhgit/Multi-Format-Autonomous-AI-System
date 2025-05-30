"""
Multi-Format Autonomous AI System with Contextual Decisioning & Chained Actions
Main FastAPI application entry point
"""

import os
import uuid
from datetime import datetime
from typing import Optional, Dict, Any
import json

from fastapi import FastAPI, File, UploadFile, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from classifier_agent import ClassifierAgent
from memory_store import MemoryStore
from router import ActionRouter
from agents.email_agent import EmailAgent
from agents.json_agent import EnhancedJSONAgent
from agents.pdf_agent import PDFAgent

# Initialize FastAPI app
app = FastAPI(title="Multi-Agent System", version="1.0.0")

# Mount static files and templates
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Initialize components
memory_store = MemoryStore()
classifier = ClassifierAgent()
router = ActionRouter(memory_store)

# Initialize agents
email_agent = EmailAgent(memory_store)
json_agent = EnhancedJSONAgent(memory_store)
pdf_agent = PDFAgent(memory_store)

class ProcessingResult(BaseModel):
    trace_id: str
    format: str
    intent: str
    agent_output: Dict[str, Any]
    actions_taken: list
    status: str
    timestamp: str

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Main UI page"""
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    """
    Main upload endpoint that processes files through the multi-agent system
    """
    try:
        # Generate unique trace ID
        trace_id = str(uuid.uuid4())
        timestamp = datetime.now().isoformat()
        
        # Read file content
        content = await file.read()
        
        # Store initial upload info
        memory_store.store_log(trace_id, {
            "stage": "upload",
            "filename": file.filename,
            "content_type": file.content_type,
            "file_size": len(content),
            "timestamp": timestamp
        })
        
        # Step 1: Classify the input
        classification = await classifier.classify(content, file.filename, file.content_type)
        
        memory_store.store_log(trace_id, {
            "stage": "classification",
            "result": classification,
            "timestamp": datetime.now().isoformat()
        })
        
        # Step 2: Route to appropriate agent
        agent_output = {}
        actions_taken = []
        
        if classification["format"] == "Email":
            agent_output = await email_agent.process(content.decode('utf-8'), trace_id)
        elif classification["format"] == "JSON":
            agent_output = await json_agent.process(content.decode('utf-8'), trace_id)
        elif classification["format"] == "PDF":
            agent_output = await pdf_agent.process(content, trace_id)
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported format: {classification['format']}")
        
        # Step 3: Execute actions based on agent decisions
        if agent_output.get("actions"):
            for action in agent_output["actions"]:
                result = await router.execute_action(action, trace_id)
                actions_taken.append(result)
        
        # Step 4: Store final results
        final_result = {
            "trace_id": trace_id,
            "format": classification["format"],
            "intent": classification["intent"],
            "agent_output": agent_output,
            "actions_taken": actions_taken,
            "status": "completed",
            "timestamp": timestamp
        }
        
        memory_store.store_log(trace_id, {
            "stage": "completion",
            "result": final_result,
            "timestamp": datetime.now().isoformat()
        })
        
        return JSONResponse(content=final_result)
        
    except Exception as e:
        error_result = {
            "trace_id": trace_id if 'trace_id' in locals() else "unknown",
            "error": str(e),
            "status": "failed",
            "timestamp": datetime.now().isoformat()
        }
        
        if 'trace_id' in locals():
            memory_store.store_log(trace_id, {
                "stage": "error",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            })
        
        raise HTTPException(status_code=500, detail=error_result)

@app.get("/trace/{trace_id}")
async def get_trace(trace_id: str):
    """
    Get the complete trace for a processing run
    """
    try:
        trace_data = memory_store.get_trace(trace_id)
        if not trace_data:
            raise HTTPException(status_code=404, detail="Trace not found")
        
        return JSONResponse(content={
            "trace_id": trace_id,
            "trace_data": trace_data
        })
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/traces")
async def list_traces():
    """
    List all available traces
    """
    try:
        traces = memory_store.list_traces()
        return JSONResponse(content={"traces": traces})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)