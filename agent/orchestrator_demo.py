"""Phase 3 Standalone Demo: End-to-End ReAct Orchestrator & Multi-Layer Reconciliation Run."""
import json
import time
from agent.config import config
from agent.tools.registry import ToolRegistry
from agent.tools.db_tool import DbTool
from agent.tools.api_tool import ApiTool
from agent.tools.browser_tool import BrowserTool
from agent.tools.log_tool import LogTool
from agent.guardrails import Guardrails
from agent.orchestrator import Orchestrator, ScriptedPlanner


def run_orchestrator_demo():
    print("=" * 70)
    print("🧠 AGENTIC QA LAB — PHASE 3 CORE ORCHESTRATOR & GUARDRAILS DEMO")
    print("=" * 70)
    print(f"Target Base URL : {config.base_url}")
    print(f"Target SQLite DB: {config.db_path}\n")

    # 1. Initialize Tools & Registry via Constructor DI
    b_tool = BrowserTool(base_url=config.base_url, headless=True)
    registry = ToolRegistry(
        tools=[
            DbTool(db_path=config.db_path),
            ApiTool(base_url=config.base_url),
            b_tool,
            LogTool(db_path=config.db_path),
        ]
    )

    # 2. Configure Strict Guardrails & Scripted ReAct Planner
    guardrails = Guardrails(
        max_turns=12,
        consecutive_identical_threshold=2,
        max_tokens=8000,
        max_timeout_ms=120000
    )
    planner = ScriptedPlanner()
    orchestrator = Orchestrator(
        registry=registry,
        guardrails=guardrails,
        planner=planner,
        max_turns=12
    )

    print("🚀 Running Autonomous E2E Test Scenario: 'Mechanical Keyboard Checkout + DISKON10'...")
    goal = "Execute end-to-end checkout flow for Mechanical Keyboard with promo voucher and verify cross-layer state reconciliation."

    start_time = time.time()
    try:
        verdict = orchestrator.run(goal=goal)
        elapsed = round(time.time() - start_time, 2)

        print("\n" + "-" * 70)
        print(f"📊 FINAL TEST VERDICT: [{'✅ PASS' if verdict.status == 'PASS' else '❌ ' + verdict.status}]")
        print(f"⏱️ Total Execution Time: {elapsed}s | Total Turns: {len(verdict.trace)}")
        print(f"📝 Reason: {verdict.reason}")
        print("-" * 70)

        print("\n🔍 Multi-Layer Evidence Captured:")
        print(f"  • UI Layer  : {json.dumps(verdict.evidence.ui, indent=4) if verdict.evidence.ui else 'None'}")
        print(f"  • DB Layer  : {json.dumps(verdict.evidence.db, indent=4) if verdict.evidence.db else 'None'}")
        print(f"  • API Layer : {json.dumps(verdict.evidence.api, indent=4) if verdict.evidence.api else 'None'}")

        print("\n📜 ReAct Execution Trace Summary:")
        for t in verdict.trace:
            obs = t['observation']
            status_icon = "✅" if obs['ok'] else "❌"
            print(f"  Turn {t['turn']} [{t['tool']}]: {t['thought']} -> {status_icon} ({obs['latency_ms']}ms)")

        print("\n" + "=" * 70)
        if verdict.status == "PASS":
            print("🏆 PHASE 3 ORCHESTRATOR & RECONCILIATION ENGINE VERIFIED SUCCESSFULLY!")
        else:
            print("⚠️ TEST SCENARIO DID NOT PASS.")
        print("=" * 70)

    finally:
        b_tool.close()


if __name__ == "__main__":
    run_orchestrator_demo()
