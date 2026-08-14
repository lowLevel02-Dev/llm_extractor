import json
import os
import uuid
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional, List
from fastapi import FastAPI, BackgroundTasks, HTTPException, Security, status, Depends
from fastapi.security import APIKeyHeader
from google import genai
from google.genai import types
from pydantic import BaseModel, Field
from sqlalchemy import create_engine, Column, String, Text, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker

CLIENT_API_KEY = os.getenv("CLIENT_API_KEY", "default_secret_dev_key")
api_key_header_scheme = APIKeyHeader(name="X-API-Key", auto_error=False)

RATE_LIMIT_DB: Dict[str, List[float]] = {}
MAX_REQUESTS_PER_MINUTE = 5

async def verify_client_api_key(api_key: Optional[str] = Security(api_key_header_scheme)):
    # 1. Authentication Checks
    if not api_key:
        raise HTTPException(status_code=401, detail="Missing API Key.", headers={"WWW-Authenticate": "ApiKey"})
    if api_key != CLIENT_API_KEY:
        raise HTTPException(status_code=403, detail="Forbidden: Invalid client API key.")

    # 2. Rate Limiting Logic (Sliding Window)
    current_time = time.time()
    
    # Initialize the queue for a new API key
    if api_key not in RATE_LIMIT_DB:
        RATE_LIMIT_DB[api_key] = []
        
    # Clean up stale timestamps older than 60 seconds
    RATE_LIMIT_DB[api_key] = [t for t in RATE_LIMIT_DB[api_key] if current_time - t < 60]
    
    # Check if the limit is exceeded
    if len(RATE_LIMIT_DB[api_key]) >= MAX_REQUESTS_PER_MINUTE:
        oldest_request = RATE_LIMIT_DB[api_key][0]
        retry_after = int(60 - (current_time - oldest_request))
        
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded. Maximum 5 requests per minute.",
            headers={"Retry-After": str(retry_after)}
        )
        
    # Log the successful request timestamp
    RATE_LIMIT_DB[api_key].append(current_time)
    
    return api_key

os.makedirs("./data", exist_ok=True)
DATABASE_URL = "sqlite:///./data/tasks.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class TaskRecord(Base):
    __tablename__ = "tasks"
    task_id = Column(String, primary_key=True, index=True)
    status = Column(String, nullable=False, default="pending")
    result = Column(Text, nullable=True)
    error = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Secured & Rate Limited Extraction API")
client = genai.Client()

class DynamicExtractRequest(BaseModel):
    text: str = Field(..., min_length=1)
    extraction_schema: dict[str, str] = Field(...)

class TaskSubmissionResponse(BaseModel):
    task_id: str
    status: str

class TaskStatusResponse(BaseModel):
    task_id: str
    status: str
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    created_at: Optional[datetime] = None

def process_extraction_task(task_id: str, text: str, extraction_schema: dict[str, str]):
    db = SessionLocal()
    schema_str = json.dumps(extraction_schema, indent=2)
    system_prompt = (
        "You are a rigid data extraction engine. Extract information from the text "
        "and map it strictly to the keys and data types specified below.\n\n"
        f"--- TARGET SCHEMA ---\n{schema_str}\n---------------------"
    )

    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=text,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                response_mime_type="application/json"
            ),
        )
        parsed_json = json.loads(response.text)

        task = db.query(TaskRecord).filter(TaskRecord.task_id == task_id).first()
        if task:
            task.status = "completed"
            task.result = json.dumps(parsed_json)
            db.commit()
    except Exception as e:
        task = db.query(TaskRecord).filter(TaskRecord.task_id == task_id).first()
        if task:
            task.status = "failed"
            task.error = str(e)
            db.commit()
    finally:
        db.close()

@app.post("/api/extract-async", response_model=TaskSubmissionResponse, status_code=status.HTTP_202_ACCEPTED, dependencies=[Depends(verify_client_api_key)])
async def extract_async(payload: DynamicExtractRequest, background_tasks: BackgroundTasks):
    task_id = str(uuid.uuid4())
    db = SessionLocal()
    try:
        new_task = TaskRecord(task_id=task_id, status="pending")
        db.add(new_task)
        db.commit()
    finally:
        db.close()

    background_tasks.add_task(process_extraction_task, task_id=task_id, text=payload.text, extraction_schema=payload.extraction_schema)
    return TaskSubmissionResponse(task_id=task_id, status="pending")

@app.get("/api/results/{task_id}", response_model=TaskStatusResponse, dependencies=[Depends(verify_client_api_key)])
async def get_task_result(task_id: str):
    db = SessionLocal()
    try:
        task = db.query(TaskRecord).filter(TaskRecord.task_id == task_id).first()
        if not task:
            raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found.")
        return TaskStatusResponse(task_id=task.task_id, status=task.status, result=json.loads(task.result) if task.result else None, error=task.error, created_at=task.created_at)
    finally:
        db.close()