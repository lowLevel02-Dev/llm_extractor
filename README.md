# LLM Extractor

> A production-oriented asynchronous REST API for extracting structured JSON from unstructured text using Google Gemini.

[![Python](https://img.shields.io/badge/Python-3.11-blue?logo=python)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-REST%20API-009688?logo=fastapi)](https://fastapi.tiangolo.com/)
[![Docker](https://img.shields.io/badge/Docker-Containerized-2496ED?logo=docker)](https://www.docker.com/)
[![Tests](https://img.shields.io/badge/Tests-Passing-success)](https://pytest.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

---

## Overview

**LLM Extractor** is a backend service that converts unstructured natural-language text into structured JSON using a Large Language Model.

Instead of creating a separate extraction function for every use case, the client provides:

1. The unstructured text.
2. A description of the desired output schema.

The API sends the request to Google Gemini, validates the response, persists the task state, and makes the result available through a polling endpoint.

The same service can be used for:

- Medical information extraction
- Invoice and financial document extraction
- Project and task information extraction
- Recipe and ingredient extraction
- Log and error extraction
- Contract information extraction
- Other schema-driven information extraction workflows

---

## Key Features

### Dynamic Schema-Based Extraction

Clients define the desired output structure at request time.

```json
{
  "text": "The patient is a 45-year-old male with mild fever and cough.",
  "extraction_schema": {
    "patient_age": "integer",
    "gender": "string",
    "symptoms": "array of strings"
  }
}
```

No new Python extraction function is required when the desired schema changes.

### Asynchronous Processing

LLM inference can take longer than a normal API operation. The service therefore uses an asynchronous job model:

```text
Client
  |
  | POST /api/extract-async
  v
FastAPI
  |
  | Create task
  v
SQLite
  |
  | status = pending
  v
HTTP 202 Accepted
  |
  v
Background Processing
  |
  v
Google Gemini
  |
  v
SQLite
  |
  | status = completed
  v
Client polls /api/results/{task_id}
```

The initial request returns immediately with a task ID.

### Persistent Task State

Task metadata and extraction results are stored using:

- SQLite
- SQLAlchemy

Task records contain fields such as:

```text
task_id
status
result
error
created_at
```

The database can be mounted to the host when running the application with Docker so task state survives container recreation.

### API-Key Authentication

Requests are authenticated using:

```http
X-API-Key: your_client_api_key
```

The key is supplied through the `CLIENT_API_KEY` environment variable rather than hardcoded into the application.

Authentication behavior:

| Situation | Response |
|---|---|
| Missing API key | `401 Unauthorized` |
| Invalid API key | `403 Forbidden` |
| Valid API key | Request proceeds |

### Sliding-Window Rate Limiting

The API limits requests per API key using a sliding-window log.

Current configuration:

```text
Maximum requests: 5
Time window:      60 seconds
```

When the limit is exceeded:

```text
HTTP 429 Too Many Requests
```

is returned together with a `Retry-After` header.

### Structured JSON Output

Gemini is configured to return JSON, allowing the application to parse and persist machine-readable extraction results instead of conversational text.

### Docker Support

The application includes a Dockerfile for reproducible deployment using Python 3.11.

### Automated Testing

The project uses Pytest and FastAPI's testing utilities to validate API behavior without making real Gemini API calls.

### GitHub Actions CI

The test suite can be executed automatically on pushes and pull requests through GitHub Actions.

---

# Architecture

```text
                    ┌───────────────────────┐
                    │        Client         │
                    │  cURL / Postman / App │
                    └───────────┬───────────┘
                                │
                                │ HTTP + X-API-Key
                                ▼
                    ┌───────────────────────┐
                    │       FastAPI         │
                    │       API Layer       │
                    └───────────┬───────────┘
                                │
                    ┌───────────▼───────────┐
                    │ Authentication &      │
                    │ Rate Limiting         │
                    └───────────┬───────────┘
                                │
                                ▼
                    ┌───────────────────────┐
                    │ Request Validation    │
                    │       Pydantic        │
                    └───────────┬───────────┘
                                │
                                ▼
                    ┌───────────────────────┐
                    │       SQLite          │
                    │      SQLAlchemy       │
                    │                       │
                    │ pending / completed   │
                    │ failed / result       │
                    └───────────┬───────────┘
                                │
                                │ Background Task
                                ▼
                    ┌───────────────────────┐
                    │    Gemini 3.6 Flash   │
                    │   Structured Output   │
                    └───────────┬───────────┘
                                │
                                │ JSON
                                ▼
                    ┌───────────────────────┐
                    │     SQLite Update     │
                    │                       │
                    │ status = completed   │
                    │ result = {...}       │
                    └───────────┬───────────┘
                                │
                                │ GET /api/results/{id}
                                ▼
                    ┌───────────────────────┐
                    │        Client         │
                    │   Structured JSON     │
                    └───────────────────────┘
```

---

# Technology Stack

| Component | Technology |
|---|---|
| Language | Python 3.11 |
| Web Framework | FastAPI |
| ASGI Server | Uvicorn |
| LLM | Google Gemini 3.6 Flash |
| LLM SDK | Google GenAI SDK |
| Validation | Pydantic |
| Database | SQLite |
| ORM | SQLAlchemy |
| Background Processing | FastAPI BackgroundTasks |
| Authentication | API Key |
| Rate Limiting | Sliding Window Log |
| Containerization | Docker |
| Testing | Pytest |
| API Testing | FastAPI TestClient / HTTPX |
| CI/CD | GitHub Actions |

---

# Project Structure

```text
llm-extractor/
│
├── .github/
│   └── workflows/
│       └── test.yml
│
├── data/
│   └── .gitkeep
│
├── .dockerignore
├── .gitignore
├── Dockerfile
├── main.py
├── requirements.txt
├── test_main.py
└── README.md
```

The local SQLite database should not be committed to Git.

For example:

```text
data/tasks.db
```

should remain ignored.

---

# API Reference

## 1. Submit Extraction Job

### `POST /api/extract-async`

Submits an extraction task for asynchronous processing.

### Headers

```http
Content-Type: application/json
X-API-Key: your_client_api_key
```

### Request Body

```json
{
  "text": "The patient, a 45-year-old male, presented with a mild fever and cough for 3 days. Prescribed 500mg Amoxicillin.",
  "extraction_schema": {
    "patient_age": "integer",
    "gender": "string",
    "symptoms": "array of strings",
    "medication": "string"
  }
}
```

### Response

```json
{
  "task_id": "cb7f1c5a-53cc-45ac-9baa-830e6e491097",
  "status": "pending"
}
```

### HTTP Status

```text
202 Accepted
```

The task is persisted before background processing begins.

---

# 2. Retrieve Task Result

### `GET /api/results/{task_id}`

Retrieves the current state of an extraction task.

### Headers

```http
X-API-Key: your_client_api_key
```

### Example

```http
GET /api/results/cb7f1c5a-53cc-45ac-9baa-830e6e491097
```

### Pending Response

```json
{
  "task_id": "cb7f1c5a-53cc-45ac-9baa-830e6e491097",
  "status": "pending",
  "result": null,
  "error": null
}
```

### Completed Response

```json
{
  "task_id": "cb7f1c5a-53cc-45ac-9baa-830e6e491097",
  "status": "completed",
  "result": {
    "patient_age": 45,
    "gender": "male",
    "symptoms": [
      "mild fever",
      "cough"
    ],
    "medication": "500mg Amoxicillin"
  },
  "error": null
}
```

### Unknown Task

If the task ID does not exist:

```text
404 Not Found
```

---

# Authentication

## Missing API Key

A request without the `X-API-Key` header receives:

```text
401 Unauthorized
```

Example:

```json
{
  "detail": "Missing API Key. Please provide the 'X-API-Key' header."
}
```

## Invalid API Key

A request with an invalid key receives:

```text
403 Forbidden
```

Example:

```json
{
  "detail": "Forbidden: Invalid client API key."
}
```

## Valid API Key

A valid request proceeds to the extraction workflow.

---

# Dynamic Extraction

The main design principle is that the extraction schema is **not hardcoded**.

For example:

```json
{
  "text": "Sarah will complete the backend migration by Friday with a budget of $5,000.",
  "extraction_schema": {
    "person": "string",
    "task": "string",
    "deadline": "string",
    "budget": "integer"
  }
}
```

The same API can handle a completely different schema:

```json
{
  "text": "Chocolate cake requires flour, eggs, sugar and 35 minutes of baking.",
  "extraction_schema": {
    "ingredients": "array of strings",
    "baking_time_minutes": "integer"
  }
}
```

No server-side extraction code needs to change.

Only the input schema changes.

---

# Gemini Integration

The service uses Google Gemini as the extraction engine.

The application constructs an extraction request using:

```text
Unstructured Text
        +
Dynamic Schema
        |
        v
Gemini 3.6 Flash
        |
        v
Structured JSON
```

The model is configured to produce:

```text
application/json
```

so the response can be parsed and stored programmatically.

The application also handles upstream LLM failures and marks unsuccessful tasks appropriately rather than returning an uncontrolled server exception.

---

# Persistence

The application uses SQLAlchemy with SQLite.

A simplified task model is:

```python
class TaskRecord(Base):
    __tablename__ = "tasks"

    task_id = Column(String, primary_key=True, index=True)
    status = Column(String, nullable=False, default="pending")
    result = Column(Text, nullable=True)
    error = Column(Text, nullable=True)
    created_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc)
    )
```

Conceptually:

```text
┌──────────────────────────────────────┐
│               tasks                  │
├──────────────────────────────────────┤
│ task_id                              │
│ status                               │
│ result                               │
│ error                                │
│ created_at                           │
└──────────────────────────────────────┘
```

This allows the API to retrieve task state after the initial request has completed.

---

# Rate Limiting

The current configuration is:

```text
5 requests
per
60 seconds
per API key
```

The sliding-window implementation stores request timestamps and removes timestamps that have fallen outside the configured window.

Conceptually:

```text
Request 1 ──┐
Request 2   │
Request 3   │  Within 60 seconds
Request 4   │
Request 5 ──┘
             │
             ▼
Request 6 ────────> HTTP 429
```

The response includes a `Retry-After` header so clients can determine when to retry.

---

# Error Handling

The API uses multiple validation and failure-handling layers.

## Request Validation

Pydantic validates the incoming request structure before unnecessary LLM processing.

## Authentication Errors

```text
401 → Missing API key
403 → Invalid API key
```

## Rate Limit Errors

```text
429 → Too many requests
```

## Missing Tasks

```text
404 → Task ID does not exist
```

## LLM Failures

Failures from the Gemini API are caught by the background processing layer and recorded against the task.

## Invalid Model Output

The model response is parsed as JSON before being stored as a successful result.

Conceptually:

```text
Gemini response
      |
      v
JSON parsing
      |
      ├── Invalid ──> status = failed
      |
      └── Valid ───> status = completed
```

---

# Environment Variables

The application uses runtime environment variables for secrets and configuration.

## Required Variables

### `GEMINI_API_KEY`

Google Gemini API key.

```text
GEMINI_API_KEY=your_google_gemini_api_key
```

### `CLIENT_API_KEY`

API key required by clients when calling the service.

```text
CLIENT_API_KEY=your_private_client_key
```

### Security

Never commit these values to GitHub.

Do not place real API keys inside:

- `main.py`
- `Dockerfile`
- `README.md`
- GitHub source files
- Test files

For local development, use environment variables or an ignored `.env` file.

---

# Running Locally

## 1. Clone the Repository

```bash
git clone https://github.com/YOUR_USERNAME/llm-extractor.git
cd llm-extractor
```

## 2. Create a Virtual Environment

### Windows PowerShell

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### Linux / macOS

```bash
python3 -m venv .venv
source .venv/bin/activate
```

## 3. Install Dependencies

```bash
pip install -r requirements.txt
```

## 4. Configure Environment Variables

### Windows PowerShell

```powershell
$env:GEMINI_API_KEY="YOUR_GEMINI_API_KEY"
$env:CLIENT_API_KEY="YOUR_CLIENT_API_KEY"
```

### Linux / macOS

```bash
export GEMINI_API_KEY="YOUR_GEMINI_API_KEY"
export CLIENT_API_KEY="YOUR_CLIENT_API_KEY"
```

## 5. Start the Server

```bash
uvicorn main:app --reload
```

The API will be available at:

```text
http://localhost:8000
```

Interactive Swagger documentation:

```text
http://localhost:8000/docs
```

OpenAPI schema:

```text
http://localhost:8000/openapi.json
```

---

# Docker Deployment

## 1. Build the Image

```bash
docker build -t llm-extractor:latest .
```

## 2. Create the Data Directory

### PowerShell

```powershell
mkdir data
```

### Linux / macOS

```bash
mkdir -p data
```

## 3. Run the Container

### PowerShell

```powershell
docker run -d `
  --name llm-extractor-service `
  -p 8000:8000 `
  -v "${PWD}\data:/app/data" `
  -e GEMINI_API_KEY="YOUR_GEMINI_API_KEY" `
  -e CLIENT_API_KEY="YOUR_CLIENT_API_KEY" `
  llm-extractor:latest
```

### Linux / macOS

```bash
docker run -d \
  --name llm-extractor-service \
  -p 8000:8000 \
  -v "$(pwd)/data:/app/data" \
  -e GEMINI_API_KEY="YOUR_GEMINI_API_KEY" \
  -e CLIENT_API_KEY="YOUR_CLIENT_API_KEY" \
  llm-extractor:latest
```

The API will be available at:

```text
http://localhost:8000
```

---

# Docker Persistence

The SQLite database is stored under:

```text
/app/data/tasks.db
```

The Docker volume maps:

```text
Host:
./data/

Container:
/app/data/
```

Therefore:

```text
┌──────────────────────┐
│ Docker Container     │
│                      │
│ /app/data/tasks.db   │
└──────────┬───────────┘
           │
           │ volume mount
           ▼
┌──────────────────────┐
│ Host                 │
│                      │
│ ./data/tasks.db      │
└──────────────────────┘
```

This allows task state to survive container removal and recreation.

---

# Example Workflow

## Step 1 — Submit a Job

```powershell
$body = @'
{
  "text": "The patient, a 45-year-old male, presented with a mild fever and cough for 3 days. Prescribed 500mg Amoxicillin.",
  "extraction_schema": {
    "patient_age": "integer",
    "gender": "string",
    "symptoms": "array of strings",
    "medication": "string"
  }
}
'@

$headers = @{
    "X-API-Key" = "YOUR_CLIENT_API_KEY"
}

$response = Invoke-RestMethod `
    -Uri "http://localhost:8000/api/extract-async" `
    -Method POST `
    -Headers $headers `
    -ContentType "application/json" `
    -Body $body

$response | ConvertTo-Json
```

Expected:

```json
{
  "task_id": "cb7f1c5a-53cc-45ac-9baa-830e6e491097",
  "status": "pending"
}
```

## Step 2 — Poll for the Result

```powershell
$result = Invoke-RestMethod `
    -Uri "http://localhost:8000/api/results/$($response.task_id)" `
    -Method GET `
    -Headers $headers

$result | ConvertTo-Json -Depth 5
```

Eventually:

```json
{
  "task_id": "cb7f1c5a-53cc-45ac-9baa-830e6e491097",
  "status": "completed",
  "result": {
    "patient_age": 45,
    "gender": "male",
    "symptoms": [
      "mild fever",
      "cough"
    ],
    "medication": "500mg Amoxicillin"
  },
  "error": null
}
```

---

# Testing

The project uses Pytest and FastAPI's testing utilities.

Run the test suite:

```bash
pytest test_main.py -v
```

Example output:

```text
collected 2 items

test_main.py::test_missing_api_key_returns_401 PASSED
test_main.py::test_valid_request_returns_202_and_task_id PASSED

2 passed
```

Tests are designed to avoid real Gemini API calls, making them faster, deterministic, and suitable for CI.

---

# Continuous Integration

The repository includes GitHub Actions for automated testing.

The CI pipeline performs:

```text
Git Push / Pull Request
        |
        v
Checkout Repository
        |
        v
Setup Python 3.11
        |
        v
Install Dependencies
        |
        v
Run Pytest
        |
        ├── PASS
        └── FAIL
```

This provides an automated quality gate before changes are merged.

---

# Design Decisions

## Why FastAPI?

FastAPI provides:

- Pydantic request validation
- Automatic OpenAPI documentation
- Dependency injection
- High-performance ASGI support
- Straightforward HTTP API development
- Native support for background tasks

## Why Background Tasks?

LLM inference should not unnecessarily block the client's HTTP connection.

The architecture separates:

```text
Request submission
```

from:

```text
LLM processing
```

This allows the API to return:

```text
202 Accepted
```

with a task ID immediately.

## Why SQLite?

SQLite provides:

- Persistent storage
- Zero external database server
- Simple deployment
- Low operational overhead
- SQL semantics through SQLAlchemy

For a horizontally scaled production environment, PostgreSQL would be a stronger choice.

## Why API Keys?

API keys provide a lightweight authentication boundary for machine-to-machine clients.

A larger platform could later introduce:

- OAuth 2.0
- JWT authentication
- API-key rotation
- Key hashing
- Per-client quotas
- Role-based access control

## Why Sliding-Window Rate Limiting?

The sliding-window log provides more precise request control than a fixed window because it considers the exact timestamps of recent requests.

The current implementation is intentionally lightweight and suitable for a single application instance.

For distributed deployment, rate-limit state should be moved to a shared store such as Redis.

---

# Current Limitations

This project is **production-oriented**, but it is not intended to claim full production-scale distributed infrastructure.

### In-memory rate limiting

Rate-limit state is local to the application process.

A multi-instance deployment should use Redis or another shared store.

### FastAPI BackgroundTasks

BackgroundTasks are suitable for this project's workload, but a large production system may require a dedicated distributed worker architecture such as:

```text
Celery + Redis
RQ + Redis
RabbitMQ
Kafka
Cloud Tasks
```

### SQLite

SQLite is appropriate for lightweight deployment but is not the ideal choice for high-concurrency distributed workloads.

A production deployment could migrate to PostgreSQL.

### Polling

Clients currently poll:

```text
GET /api/results/{task_id}
```

Future versions could support:

- Webhooks
- Server-Sent Events
- WebSockets
- Push-based completion notifications

---

# Future Roadmap

- [ ] PostgreSQL support
- [ ] Redis-based distributed rate limiting
- [ ] Dedicated background worker system
- [ ] Webhook-based task completion
- [ ] JWT/OAuth authentication
- [ ] API-key rotation
- [ ] Per-client quotas
- [ ] Structured application logging
- [ ] Request tracing
- [ ] Prometheus metrics
- [ ] Health/readiness endpoints
- [ ] Docker Compose deployment
- [ ] Kubernetes deployment
- [ ] Cloud deployment
- [ ] Extraction result caching
- [ ] Batch extraction API
- [ ] PDF/document ingestion
- [ ] Multi-model provider support

---

# Engineering Concepts Demonstrated

This project demonstrates several backend and AI engineering concepts.

### API Engineering

```text
HTTP methods
HTTP status codes
JSON contracts
Request validation
Error handling
OpenAPI documentation
```

### LLM Engineering

```text
Prompt construction
Dynamic schemas
Structured JSON output
External API integration
LLM failure handling
```

### Asynchronous Architecture

```text
Task IDs
Background processing
Polling
Task states
```

### Persistence

```text
SQLite
SQLAlchemy
Database transactions
Docker volume persistence
```

### Security

```text
API keys
Environment variables
Authentication dependencies
401 / 403 handling
```

### Reliability

```text
Input validation
Upstream failure handling
JSON parsing
Persistent task state
```

### Traffic Management

```text
Sliding Window Log
Request timestamps
HTTP 429
Retry-After
```

### DevOps

```text
Docker
Environment configuration
GitHub Actions
Automated testing
```

---

# Example Use Cases

## Medical Information Extraction

Input:

```text
"The patient is a 45-year-old male with fever and cough."
```

Schema:

```json
{
  "age": "integer",
  "gender": "string",
  "symptoms": "array of strings"
}
```

## Invoice Extraction

Input:

```text
"Invoice #INV-1042 from ACME Corp. Total amount is $2,450."
```

Schema:

```json
{
  "invoice_number": "string",
  "vendor": "string",
  "total_amount": "integer"
}
```

## Project Information Extraction

Input:

```text
"Sarah will finish the backend migration by Friday."
```

Schema:

```json
{
  "person": "string",
  "task": "string",
  "deadline": "string"
}
```

The extraction engine remains unchanged.

---

# API Lifecycle

```text
1. Client submits request
          |
          v
2. API key authentication
          |
          v
3. Rate-limit validation
          |
          v
4. Pydantic request validation
          |
          v
5. Generate UUID task ID
          |
          v
6. Persist pending task
          |
          v
7. Return HTTP 202
          |
          v
8. Background task starts
          |
          v
9. Build dynamic extraction prompt
          |
          v
10. Gemini processes text
          |
          v
11. Parse JSON response
          |
          v
12. Update SQLite task
          |
          v
13. Client polls task ID
          |
          v
14. Structured JSON returned
```

---

# Repository Hygiene

Recommended `.gitignore` entries:

```gitignore
# Python
__pycache__/
*.py[cod]

# Virtual environments
.venv/
venv/
env/

# Testing
.pytest_cache/
.coverage
htmlcov/

# Environment variables
.env
.env.*

# Local database
data/*.db

# IDE
.vscode/
.idea/

# OS
.DS_Store
Thumbs.db
```

Do **not** commit:

```text
.env
data/tasks.db
.venv/
__pycache__/
.pytest_cache/
```

---

# License

This project is licensed under the MIT License.

See [LICENSE](LICENSE) for details.

---

# Author

**Uthkarsh**

Computer Science Engineering

---

## Project Summary

LLM Extractor demonstrates how to evolve from a simple LLM API call into a structured backend service.

The final architecture combines:

```text
                ┌──────────────────────────┐
                │     Dynamic Schemas      │
                └────────────┬─────────────┘
                             |
                             v
┌────────────┐      ┌───────────────────────┐
│   Client   │─────>│       FastAPI        │
└────────────┘      └───────────┬───────────┘
                                |
                    ┌───────────v───────────┐
                    │ Authentication        │
                    │ + Rate Limiting       │
                    └───────────┬───────────┘
                                |
                    ┌───────────v───────────┐
                    │ Async Task Processing │
                    └───────────┬───────────┘
                                |
              ┌─────────────────┴────────────────┐
              v                                  v
      ┌───────────────┐                  ┌───────────────┐
      │ Gemini 3.6    │                  │ SQLite        │
      │ Flash         │                  │ + SQLAlchemy  │
      └───────┬───────┘                  └───────┬───────┘
              |                                  |
              └────────────────┬─────────────────┘
                               v
                       Structured JSON
                               |
                               v
                            Client
```

The result is a reusable LLM extraction backend with asynchronous execution, persistent task state, authentication, rate limiting, containerized deployment, and automated testing.
