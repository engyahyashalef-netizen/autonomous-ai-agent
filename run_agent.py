import json
import os
import subprocess
import sys
from typing import Any, Dict, List, Optional

import requests
from dotenv import load_dotenv
from google import genai
from google.genai import types
from pydantic import BaseModel, Field

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "PUT_YOUR_KEY_HERE")


class AgentTools:
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
            if result.returncode == 0:
                return f"SUCCESS:\n{result.stdout if result.stdout else 'Executed successfully.'}"
            return f"ERROR (Traceback):\n{result.stderr}"
        except Exception as e:
            return f"ERROR: {str(e)}"

    @staticmethod
    def file_manager(action: str, filepath: str, content: str = "") -> str:
        try:
            if action == "write":
                os.makedirs(os.path.dirname(filepath) or ".", exist_ok=True)
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(content)
                return f"SUCCESS: File saved '{filepath}'"

            if action == "read":
                if not os.path.exists(filepath):
                    return f"ERROR: File '{filepath}' not found."
                with open(filepath, "r", encoding="utf-8") as f:
                    return f"SUCCESS:\n{f.read()}"

            return f"ERROR: Unknown action '{action}'."
        except Exception as e:
            return f"ERROR: {str(e)}"

    @staticmethod
    def http_request(method: str, url: str) -> str:
        try:
            response = requests.request(method=method.upper(), url=url, timeout=15)
            return f"STATUS: {response.status_code}\nDATA:\n{response.text[:1500]}"
        except Exception as e:
            return f"ERROR: {str(e)}"


TOOL_REGISTRY = {
    "execute_python_code": AgentTools.execute_python_code,
    "file_manager": AgentTools.file_manager,
    "http_request": AgentTools.http_request,
}


class AgentStep(BaseModel):
    thought: str = Field(description="Logical analysis of the current step or error fix")
    tool_name: Optional[str] = Field(default=None, description="execute_python_code, file_manager, or http_request")
    tool_args: Optional[Dict[str, Any]] = Field(default=None, description="Tool arguments dictionary")
    is_completed: bool = Field(default=False, description="True only when goal is fully verified")
    final_answer: Optional[str] = Field(default=None, description="Final summary for the user")


SYSTEM_PROMPT = """
أنت وكيل ذكاء اصطناعي مستقل (Autonomous AI Agent).
تعمل وفق حلقة: تفكير -> أداة -> ملاحظة -> تصحيح ذاتي.
الأدوات المتاحة:
- execute_python_code: {"code": "..."}
- file_manager: {"action": "read/write", "filepath": "...", "content": "..."}
- http_request: {"method": "GET", "url": "..."}
إذا ظهر ERROR، اقرأ السبب، ثم صحح الكود أو المنطق في الخطوة التالية.
"""


class AutonomousAgent:
    def __init__(self, api_key: str):
        self.client = genai.Client(api_key=api_key)
        self.memory: List[str] = []

    def run(self, goal: str, max_steps: int = 8):
        print(f"\n🚀 [بدء تشغيل الوكيل]\n🎯 الهدف: {goal}\n" + "=" * 60)
        self.memory.append(f"Goal: {goal}")

        for step in range(1, max_steps + 1):
            print(f"\n⏳ [الخطوة {step}] جاري التفكير...")
            response = self.client.models.generate_content(
                model="gemini-2.5-flash",
                contents="\n---\n".join(self.memory),
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT,
                    response_mime_type="application/json",
                    response_schema=AgentStep,
                    temperature=0.1,
                ),
            )

            decision = AgentStep.model_validate_json(response.text)
            print(f"🧠 [التفكير]: {decision.thought}")

            if decision.is_completed:
                print("\n" + "=" * 60)
                print(f"✅ [اكتملت المهمة!]\n📋 [النتيجة]:\n{decision.final_answer}")
                return

            if decision.tool_name:
                t_name = decision.tool_name
                t_args = decision.tool_args or {}

                if t_name in TOOL_REGISTRY:
                    try:
                        obs = TOOL_REGISTRY[t_name](**t_args)
                    except TypeError as exc:
                        obs = f"ERROR: Invalid tool arguments for {t_name}: {exc}"
                else:
                    obs = "ERROR: Tool not found"

                print(f"🛠️  [الأداة]: {t_name}")
                print(f"👁️  [النتيجة]:\n{obs[:400]}")

                self.memory.append(
                    f"Step {step}:\nThought: {decision.thought}\nTool: {t_name}({json.dumps(t_args)})\nObservation: {obs}"
                )

        print("\n" + "=" * 60)
        print("⚠️  [تم الوصول إلى الحد الأقصى للخطوات دون إكمال المهمة]")


if __name__ == "__main__":
    corrupted_data = """[
        {"item": "Laptop", "price": 1200},
        {"item": "Mouse", "price": "FREE"},
        {"item": "Keyboard", "price": 80},
        {"item": "Monitor", "price": null}
    ]"""

    with open("sales_data.json", "w", encoding="utf-8") as f:
        f.write(corrupted_data)

    if GEMINI_API_KEY and GEMINI_API_KEY != "PUT_YOUR_KEY_HERE":
        agent = AutonomousAgent(api_key=GEMINI_API_KEY)
        agent.run(
            goal="اقرأ ملف sales_data.json واحسب مجموع الأسعار الصحيح (اعتبر القيم غير الرقمية 0) واحفظ التقرير في final_report.txt"
        )
    else:
        data = json.loads(corrupted_data)
        total = 0
        for item in data:
            value = item.get("price", 0)
            try:
                total += float(value)
            except (TypeError, ValueError):
                total += 0

        report = (
            "Sales Summary\n"
            "=============\n"
            f"Items processed: {len(data)}\n"
            f"Total valid price: {total}\n"
        )

        with open("final_report.txt", "w", encoding="utf-8") as f:
            f.write(report)

        print("✅ Fallback calculation complete. Report saved to final_report.txt")
        print(report)
