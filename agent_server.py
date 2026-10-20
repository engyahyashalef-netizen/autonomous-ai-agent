import json
import os
import subprocess
import sys
from typing import Any, Dict, List, Optional

import psycopg2
import requests
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from google import genai
from google.genai import types
from pydantic import BaseModel, Field
from psycopg2.extras import RealDictCursor

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
DATABASE_URL = os.getenv("DATABASE_URL", "")


class ConnectedAgentTools:
    @staticmethod
    def database_query(sql_query: str) -> str:
        conn = None
        try:
            conn = psycopg2.connect(DATABASE_URL)
            conn.autocommit = True
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(sql_query)
                if cursor.description:
                    rows = cursor.fetchall()
                    return f"SUCCESS (Rows: {len(rows)}):\n{json.dumps(rows, default=str, ensure_ascii=False)}"
                return f"SUCCESS: Rows affected: {cursor.rowcount}"
        except Exception as e:
            return f"SQL ERROR:\n{str(e)}"
        finally:
            if conn is not None:
                conn.close()

    @staticmethod
    def http_request(method: str, url: str, headers: Dict[str, str] = None, payload: Dict[str, Any] = None) -> str:
        try:
            method = method.upper()
            response = requests.request(
                method=method,
                url=url,
                headers=headers or {"Accept": "application/json"},
                json=payload if method in ["POST", "PUT", "PATCH"] else None,
                params=payload if method == "GET" else None,
                timeout=15,
            )
            return f"STATUS: {response.status_code}\nRESPONSE:\n{response.text[:2000]}"
        except Exception as e:
            return f"HTTP ERROR: {str(e)}"

    @staticmethod
    def execute_python_code(code: str) -> str:
        try:
            result = subprocess.run(
                [sys.executable, "-c", code],
                capture_output=True,
                text=True,
                timeout=30,
                encoding="utf-8",
            )
            return f"SUCCESS:\n{result.stdout}" if result.returncode == 0 else f"ERROR:\n{result.stderr}"
        except Exception as e:
            return f"ERROR: {str(e)}"

    @staticmethod
    def git_push_changes(commit_message: str, branch: str = "main") -> str:
        try:
            subprocess.run(["git", "add", "."], check=True, capture_output=True, text=True)
            subprocess.run(["git", "commit", "-m", commit_message], capture_output=True, text=True)
            push_res = subprocess.run(
                ["git", "push", "origin", branch],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if push_res.returncode == 0:
                return f"SUCCESS: Pushed to GitHub! Commit: {commit_message}"
            return f"GIT PUSH ERROR:\n{push_res.stderr}"
        except Exception as e:
            return f"GIT ERROR: {str(e)}"


TOOL_REGISTRY = {
    "database_query": ConnectedAgentTools.database_query,
    "http_request": ConnectedAgentTools.http_request,
    "execute_python_code": ConnectedAgentTools.execute_python_code,
    "git_push_changes": ConnectedAgentTools.git_push_changes,
}


class AgentStep(BaseModel):
    thought: str
    tool_name: Optional[str] = None
    tool_args: Optional[Dict[str, Any]] = None
    is_completed: bool = False
    final_answer: Optional[str] = None


SYSTEM_PROMPT = """
أنت وكيل ذكاء اصطناعي مستقل مربوط بقاعدة البيانات والـ APIs.
الأدوات المتاحة:
- database_query: {"sql_query": "SELECT ..."}
- http_request: {"method": "GET/POST", "url": "...", "headers": {}, "payload": {}}
- execute_python_code: {"code": "..."}
- git_push_changes: {"commit_message": "...", "branch": "main"}
"""


app = FastAPI(title="Autonomous AI Agent API", version="1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


class TaskRequest(BaseModel):
    goal: str
    max_steps: int = 8


@app.post("/api/agent/run")
def run_agent_task(request: TaskRequest):
    if not GEMINI_API_KEY:
        raise HTTPException(status_code=500, detail="GEMINI_API_KEY is not configured.")

    client = genai.Client(api_key=GEMINI_API_KEY)
    memory: List[str] = [f"الهدف المطلوب: {request.goal}"]
    execution_steps = []

    try:
        for step in range(1, request.max_steps + 1):
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents="\n---\n".join(memory),
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT,
                    response_mime_type="application/json",
                    response_schema=AgentStep,
                    temperature=0.1,
                ),
            )

            decision = AgentStep.model_validate_json(response.text)

            if decision.is_completed:
                return {
                    "status": "completed",
                    "final_answer": decision.final_answer,
                    "steps_taken": len(execution_steps),
                    "trace": execution_steps,
                }

            obs = "No tool called"
            if decision.tool_name in TOOL_REGISTRY:
                t_args = decision.tool_args or {}
                try:
                    obs = TOOL_REGISTRY[decision.tool_name](**t_args)
                except TypeError as exc:
                    obs = f"ERROR: Invalid arguments for {decision.tool_name}: {exc}"

            execution_steps.append(
                {
                    "step": step,
                    "thought": decision.thought,
                    "tool": decision.tool_name,
                    "args": decision.tool_args,
                    "observation": obs[:500],
                }
            )

            memory.append(
                f"Step {step}:\nThought: {decision.thought}\nTool: {decision.tool_name}\nResult: {obs}"
            )

        return {
            "status": "max_steps_reached",
            "final_answer": "Reached max steps.",
            "trace": execution_steps,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
