from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field

from .service import ROOT, service


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    message: str = Field(min_length=1, max_length=2000)
    conversation_id: str | None = None
    execute: bool = False


class SegmentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query: str = Field(min_length=1, max_length=2000)
    execute: bool = False


app = FastAPI(title="Agentic Marketing", version="9.0")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"], allow_methods=["GET", "POST"], allow_headers=["Content-Type"])


@app.get("/api/health")
def health() -> dict[str, Any]:
    return {"status": "ok", "mode": service.database_mode(), "raw_sql_api": False}


@app.post("/api/chat")
def chat(request: ChatRequest) -> dict[str, Any]:
    return service.chat(request.message, request.conversation_id, request.execute)


@app.get("/api/conversations/{conversation_id}")
def conversation(conversation_id: str) -> dict[str, Any]:
    if conversation_id not in service.conversations:
        raise HTTPException(404, "conversation not found")
    return {"conversation_id": conversation_id, "messages": service.conversations[conversation_id]}


def _query_part(query_id: str, key: str):
    if query_id not in service.queries:
        raise HTTPException(404, "query not found")
    return {"query_id": query_id, key: service.queries[query_id].get(key)}


@app.get("/api/query/{query_id}/plan")
def query_plan(query_id: str):
    return _query_part(query_id, "query_plan")


@app.get("/api/query/{query_id}/sql")
def query_sql(query_id: str):
    value = service.queries.get(query_id)
    if value is None:
        raise HTTPException(404, "query not found")
    return {"query_id": query_id, "sql": value.get("sql"), "params": value.get("params")}


@app.get("/api/query/{query_id}/trace")
def query_trace(query_id: str):
    return _query_part(query_id, "trace")


@app.get("/api/customer/{customer_id}/profile")
def customer_profile(customer_id: str):
    return service.customer_analysis(customer_id)


@app.post("/api/segments/evaluate")
def evaluate_segment(request: SegmentRequest):
    result = service.chat(request.query, execute=request.execute)
    return {"status": result["status"], "mode": result["mode"], "query_id": result["query_id"], "query_plan": result["query_plan"], "result": result["result"], "guardrail": result["guardrail"], "message": result["message"]}


@app.get("/api/opportunities")
def opportunities(customer_id: str | None = None):
    if not customer_id:
        return {"status": "customer_required", "mode": service.database_mode(), "items": [], "strategies": [], "message": "请输入 Customer ID；不会使用演示客户替代。"}
    analysis = service.customer_analysis(customer_id)
    return {
        "status": analysis.get("status"), "mode": analysis.get("mode"), "customer_id": customer_id,
        "items": analysis.get("opportunities", []), "strategies": analysis.get("strategies", []),
        "trace": analysis.get("trace"), "message": analysis.get("message"),
    }


@app.get("/api/benchmark/summary")
def benchmark_summary():
    return service.benchmark_summary()


dist = ROOT / "frontend" / "dist"
if dist.exists():
    app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

    @app.get("/{path:path}")
    def frontend(path: str):
        candidate = dist / path
        return FileResponse(candidate if candidate.is_file() else dist / "index.html")
