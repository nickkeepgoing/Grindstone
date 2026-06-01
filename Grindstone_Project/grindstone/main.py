import os
import json
import uuid
import csv
import io
import random
import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
from datetime import datetime
from typing import AsyncGenerator

from fastapi import FastAPI, Request, BackgroundTasks
from fastapi.responses import HTMLResponse, StreamingResponse
from dotenv import load_dotenv, dotenv_values
import logging
import litellm
import aiosqlite

# .env lives next to this file; load it regardless of the current working directory.
_DOTENV = str(Path(__file__).resolve().parent / ".env")
load_dotenv(_DOTENV)
# Backfill any key/setting the process env leaves empty or unset from the .env file.
# An EMPTY shell var (e.g. ANTHROPIC_API_KEY='') would otherwise shadow the .env value
# and silently disable the Anthropic judge. Must run before importing modules that read
# env vars at import time (judge.JUDGE_MODEL / JUDGE_MAX_TOKENS).
for _k, _v in dotenv_values(_DOTENV).items():
    if _v and not os.environ.get(_k):
        os.environ[_k] = _v

from orchestrator import run_campaign
from risk_engine import calculate_risk, RiskReport
from target_config import get_system_prompt, get_known_secrets, generate_canaries, CanarySet
from remediation import build_remediation

# ตั้งค่า litellm
litellm.set_verbose = False
litellm.suppress_debug_info = True
logging.getLogger("LiteLLM").setLevel(logging.ERROR)
logging.getLogger("litellm").setLevel(logging.ERROR)
_log = logging.getLogger("grindstone")

# (API keys are guaranteed present in os.environ by the .env backfill above)

# litellm provider prefixes that work without the openrouter/ wrapper
_KNOWN_PROVIDERS = {
    "openai", "anthropic", "azure", "huggingface", "together_ai",
    "openrouter", "cohere", "replicate", "vertex_ai", "bedrock",
    "sagemaker", "palm", "gemini", "mistral", "ollama", "groq",
    "deepinfra", "perplexity", "anyscale", "cloudflare",
}

def normalize_model(model: str) -> str:
    """Auto-prefix models that look like OpenRouter slugs (e.g. nvidia/..., meta-llama/...)."""
    if not model:
        return model
    parts = model.split("/", 1)
    if len(parts) == 2 and parts[0].lower() not in _KNOWN_PROVIDERS:
        return f"openrouter/{model}"
    return model

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Starlette 1.x REMOVED the @app.on_event("startup") decorator (it silently no
    # longer fires) — without this lifespan, init_db() never runs and the first
    # DB write fails with "no such table: runs". (BASE_DIR / init_db are resolved
    # at startup time, after the module is fully imported.)
    (BASE_DIR / "reports").mkdir(exist_ok=True)
    await init_db()
    yield

app = FastAPI(title="GRINDSTONE", version="0.1.0", lifespan=lifespan)

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = str(BASE_DIR / "reports" / "grindstone.db")
PROMPTS_DIR = BASE_DIR / "prompts"

# In-memory store สำหรับ SSE streaming
active_runs: dict = {}  # run_id -> list of events

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS runs (
                run_id TEXT PRIMARY KEY,
                target_model TEXT,
                started_at TEXT,
                completed_at TEXT,
                overall_risk_score REAL,
                risk_level TEXT,
                report_json TEXT,
                config_json TEXT
            )
        """)
        # migration: เพิ่ม config_json ให้ DB เก่าที่สร้างไว้ก่อนมี scan-settings capture
        try:
            await db.execute("ALTER TABLE runs ADD COLUMN config_json TEXT")
        except Exception:
            pass  # column already exists
        await db.execute("""
            CREATE TABLE IF NOT EXISTS attack_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT,
                attack_id TEXT,
                owasp_category TEXT,
                thai_dimension TEXT,
                mode TEXT,
                turn_number INTEGER,
                success_score REAL,
                violation_type TEXT,
                evidence TEXT,
                similarity_score REAL,
                attack_prompt TEXT,
                target_response TEXT
            )
        """)
        # v2 migrations — additive, nullable columns only (SQLite has no
        # "ADD COLUMN IF NOT EXISTS"). Each guarded so re-runs and pre-v2 DBs
        # both work; old rows read these as NULL → engine treats them as v1.
        _RUNS_V2_COLS = [
            "scenario_asr REAL", "turn_asr REAL", "total_scenarios INTEGER",
            "compromised_scenarios INTEGER", "total_turns INTEGER",
            "compromised_turns INTEGER", "max_secret_severity REAL",
            "schema_version INTEGER",
        ]
        _ATTACK_V2_COLS = [
            "secret_type TEXT", "secret_severity REAL", "matched_canary_id TEXT",
            "leak_confidence REAL", "evidence_valid INTEGER", "owasp_subtechnique TEXT",
            "context_corruption INTEGER", "judge_a_score REAL", "judge_b_score REAL",
            "judge_verdict TEXT", "detail_json TEXT",
            # v2.1 — provenance + 3-judge + corruption scoring
            "provenance_origin TEXT", "judge_rule_score REAL", "judge_conflict INTEGER",
            "corruption_score REAL",
        ]
        for _col in _RUNS_V2_COLS:
            try:
                await db.execute(f"ALTER TABLE runs ADD COLUMN {_col}")
            except Exception:
                pass  # column already exists
        for _col in _ATTACK_V2_COLS:
            try:
                await db.execute(f"ALTER TABLE attack_results ADD COLUMN {_col}")
            except Exception:
                pass  # column already exists
        await db.commit()

def _read_pool(filename: str) -> list:
    f = PROMPTS_DIR / filename
    if f.exists():
        return json.loads(f.read_text(encoding="utf-8"))
    return []


def load_prompts(
    modes: list = ["single_turn", "multi_turn"],
    max_single: int | None = None,
    max_multi: int | None = None,
    seed: int | None = None,
    owasp_categories: list | None = None,
    thai_dimensions: list | None = None,
    sources: list | None = None,
) -> list:
    """
    โหลด prompt pool จากไฟล์ generated (single_turn.json / multi_turn.json) แล้ว
    filter ตาม OWASP category / Thai dimension / source ก่อน sample ตามจำนวนที่กำหนด
    (single_turn.json มี ~880 prompts การ sample จึงสำคัญเพื่อไม่ให้ scan แพง)
    """
    rng = random.Random(seed)

    def _filter(pool: list) -> list:
        if owasp_categories:
            pool = [p for p in pool if p.get("owasp_category") in owasp_categories]
        if thai_dimensions:
            pool = [p for p in pool if p.get("thai_dimension") in thai_dimensions]
        if sources:
            pool = [p for p in pool if p.get("source") in sources]
        return pool

    def _sample(pool: list, k: int | None) -> list:
        pool = _filter(pool)
        if k and len(pool) > k:
            return rng.sample(pool, k)
        return pool

    prompts = []
    if "single_turn" in modes:
        prompts.extend(_sample(_read_pool("single_turn.json"), max_single))
    if "multi_turn" in modes:
        prompts.extend(_sample(_read_pool("multi_turn.json"), max_multi))
    return prompts


def prompt_stats() -> dict:
    """สรุปจำนวน prompt ใน pool ตาม category / dimension / source สำหรับ UI"""
    def _counts(pool: list) -> dict:
        cat: dict = {}
        dim: dict = {}
        src: dict = {}
        for p in pool:
            cat[p.get("owasp_category", "?")] = cat.get(p.get("owasp_category", "?"), 0) + 1
            dim[p.get("thai_dimension", "?")] = dim.get(p.get("thai_dimension", "?"), 0) + 1
            src[p.get("source", "?")] = src.get(p.get("source", "?"), 0) + 1
        return {"total": len(pool), "by_category": cat, "by_dimension": dim, "by_source": src}

    return {
        "single_turn": _counts(_read_pool("single_turn.json")),
        "multi_turn": _counts(_read_pool("multi_turn.json")),
    }

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    # เสิร์ฟ index.html ตรงๆ — หน้านี้เป็น static ไม่มี template variable และวิธีนี้
    # เลี่ยง bug ของ jinja2 LRUCache บน Python 3.14 ที่ทำให้ TemplateResponse 500
    html = (Path(__file__).parent / "templates" / "index.html").read_text(encoding="utf-8")
    return HTMLResponse(html)


@app.get("/api/prompt-stats")
async def get_prompt_stats():
    return prompt_stats()

@app.get("/api/target-config")
async def get_target_config():
    """Returns the target LLM's system prompt + canary credentials so a
    human reviewer can verify breaches by eye."""
    return {
        "system_prompt": get_system_prompt(),
        "known_secrets": get_known_secrets(),
    }

@app.post("/api/run")
async def start_run(request: Request, background_tasks: BackgroundTasks):
    body = await request.json()
    target_model = normalize_model(body.get("target_model", os.getenv("TARGET_MODEL", "openrouter/openai/gpt-4o-mini")))
    modes = body.get("modes", ["single_turn", "multi_turn"])
    # scan size — ค่า default เก็บ scan ให้เล็ก/เร็ว (null = ทั้งหมด)
    max_single = body.get("max_single", 16)
    max_multi = body.get("max_multi", 4)
    seed = body.get("seed")
    owasp_categories = body.get("owasp_categories")  # optional list e.g. ["LLM01","LLM07"]
    thai_dimensions = body.get("thai_dimensions")     # optional list
    sources = body.get("sources")                     # optional list e.g. ["thai","owasp"]

    run_id = str(uuid.uuid4())[:8]
    active_runs[run_id] = []

    prompts = load_prompts(
        modes,
        max_single=max_single,
        max_multi=max_multi,
        seed=seed,
        owasp_categories=owasp_categories,
        thai_dimensions=thai_dimensions,
        sources=sources,
    )
    if not prompts:
        return {"error": "No prompts found", "run_id": None}

    # Per-run honeypot canaries: 4 typed secrets scoped to this run_id, seeded into
    # the target system prompt so any leak is attributable to this scan.
    canary_set = generate_canaries(run_id)

    # บันทึก attack settings ที่ใช้กับ run นี้ เพื่อให้ Scan History ย้อนดูได้
    scan_config = {
        "modes": modes,
        "max_single": max_single,
        "max_multi": max_multi,
        "seed": seed,
        "owasp_categories": owasp_categories,
        "thai_dimensions": thai_dimensions,
        "sources": sources,
        "total_prompts": len(prompts),
        "canaries": [
            {"canary_id": c.canary_id, "type": c.type, "value": c.value}
            for c in canary_set.canaries
        ],
    }

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO runs (run_id, target_model, started_at, config_json) VALUES (?, ?, ?, ?)",
            (run_id, target_model, datetime.utcnow().isoformat(), json.dumps(scan_config, ensure_ascii=False))
        )
        await db.commit()

    background_tasks.add_task(execute_run, run_id, prompts, target_model, scan_config, canary_set)
    return {"run_id": run_id, "total_prompts": len(prompts)}

async def execute_run(run_id: str, prompts: list, target_model: str,
                      scan_config: dict | None = None, canary_set: CanarySet | None = None):
    all_results = []

    async def on_result(result: dict):
        active_runs[run_id].append({"type": "result", "data": result})
        all_results.append(result)

        # verbose / variable-shape fields go in detail_json; scoring-relevant ones
        # are promoted to their own columns above for SQL querying.
        detail = {
            "reasoning": result.get("reasoning"),
            "confidence": result.get("confidence"),
            "confidence_reasons": result.get("confidence_reasons"),
            "corruption_types": result.get("corruption_types"),
            "layer1_on_track": result.get("layer1_on_track"),
            "strategy": result.get("strategy"),
        }
        _cc = result.get("context_corruption")
        _ev = result.get("evidence_valid")
        _cf = result.get("judge_conflict")
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("""
                INSERT INTO attack_results
                (run_id, attack_id, owasp_category, thai_dimension, mode, turn_number,
                 success_score, violation_type, evidence, similarity_score, attack_prompt, target_response,
                 secret_type, secret_severity, matched_canary_id, leak_confidence, evidence_valid,
                 owasp_subtechnique, context_corruption, judge_a_score, judge_b_score, judge_verdict, detail_json,
                 provenance_origin, judge_rule_score, judge_conflict, corruption_score)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                run_id,
                result.get("attack_id"),
                result.get("owasp_category"),
                result.get("thai_dimension"),
                result.get("mode"),
                result.get("turn_number", 1),
                result.get("success_score", 0.0),
                result.get("violation_type"),
                result.get("evidence"),
                result.get("similarity_score"),
                result.get("attack_prompt", "")[:2000],
                result.get("target_response", "")[:2000],
                result.get("secret_type"),
                result.get("secret_severity"),
                result.get("matched_canary_id"),
                result.get("leak_confidence"),
                (None if _ev is None else int(bool(_ev))),
                result.get("owasp_subtechnique"),
                (None if _cc is None else int(bool(_cc))),
                result.get("judge_a_score"),
                result.get("judge_b_score"),
                result.get("judge_verdict"),
                json.dumps(detail, ensure_ascii=False),
                result.get("provenance_origin"),
                result.get("judge_rule_score"),
                (None if _cf is None else int(bool(_cf))),
                result.get("corruption_score"),
            ))
            await db.commit()

    try:
        await run_campaign(prompts, target_model, run_id, callback=on_result, canary_set=canary_set)
    except Exception as e:
        _log.error("Campaign error [%s]: %s", run_id, e)
        active_runs[run_id].append({"type": "error", "message": str(e)})

    # Build + persist the risk report. Guard everything so the run ALWAYS emits
    # "complete" — otherwise the SSE stream hangs until the 5-minute timeout.
    try:
        report = calculate_risk(all_results, target_model, canary_set=canary_set)
        report_dict = {
            "schema_version": report.schema_version,
            "target_model": report.target_model,
            "overall_risk_score": report.overall_risk_score,
            "risk_level": report.risk_level,
            "total_attacks_run": report.total_attacks_run,
            "total_errors": report.total_errors,
            "total_attempted": report.total_attempted,
            "overall_asr": report.overall_asr,
            # dual ASR + taxonomy summary (v2)
            "summary": {
                "scenario_asr": report.scenario_asr,
                "turn_asr": report.turn_asr,
                "weighted_asr": report.weighted_asr,
                "severity_adjusted_asr": report.severity_adjusted_asr,
                "total_scenarios": report.total_scenarios,
                "compromised_scenarios": report.compromised_scenarios,
                "total_turns": report.total_turns,
                "compromised_turns": report.compromised_turns,
                "credential_leak_turn_rate": report.credential_leak_turn_rate,
                "max_secret_severity": report.max_secret_severity,
                "complexity_max": report.complexity_max,
                "complexity_score_max": report.complexity_score_max,
            },
            "category_results": {
                k: {
                    "category_code": v.category_code,
                    "category_name": v.category_name,
                    "total_attacks": v.total_attacks,
                    "asr": v.asr,
                    "severity_weight": v.severity_weight,
                    "risk_score": v.risk_score,
                    "violations": v.violations,
                    # v2
                    "scenario_asr": v.scenario_asr,
                    "turn_asr": v.turn_asr,
                    "weighted_asr": v.weighted_asr,
                    "severity_adjusted_asr": v.severity_adjusted_asr,
                    "total_scenarios": v.total_scenarios,
                    "compromised_scenarios": v.compromised_scenarios,
                    "total_turns": v.total_turns,
                    "compromised_turns": v.compromised_turns,
                    "max_finding_risk": v.max_finding_risk,
                    "subtechniques": v.subtechniques,
                }
                for k, v in report.category_results.items()
            },
            "thai_dimension_results": {
                k: {
                    "category_code": v.category_code,
                    "category_name": v.category_name,
                    "total_attacks": v.total_attacks,
                    "asr": v.asr,
                    "risk_score": v.risk_score,
                    # v2
                    "scenario_asr": v.scenario_asr,
                    "turn_asr": v.turn_asr,
                    "total_scenarios": v.total_scenarios,
                    "compromised_scenarios": v.compromised_scenarios,
                    "total_turns": v.total_turns,
                    "compromised_turns": v.compromised_turns,
                }
                for k, v in report.thai_dimension_results.items()
            },
            "critical_findings": report.critical_findings,
            "canary_audit": report.canary_audit,
            "dual_judge": report.dual_judge,
            "scan_config": scan_config or {},
        }
        # attach remediation (what's vulnerable + how to fix) derived from breaches
        report_dict["remediation"] = build_remediation(
            report_dict["category_results"], all_results
        )

        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("""
                UPDATE runs SET completed_at=?, overall_risk_score=?, risk_level=?, report_json=?,
                    scenario_asr=?, turn_asr=?, total_scenarios=?, compromised_scenarios=?,
                    total_turns=?, compromised_turns=?, max_secret_severity=?, schema_version=?
                WHERE run_id=?
            """, (
                datetime.utcnow().isoformat(),
                report.overall_risk_score,
                report.risk_level,
                json.dumps(report_dict, ensure_ascii=False),
                report.scenario_asr,
                report.turn_asr,
                report.total_scenarios,
                report.compromised_scenarios,
                report.total_turns,
                report.compromised_turns,
                report.max_secret_severity,
                report.schema_version,
                run_id
            ))
            await db.commit()
    except Exception as e:
        _log.error("Report build failed [%s]: %s", run_id, e)
        report_dict = {
            "target_model": target_model,
            "overall_risk_score": 0.0,
            "risk_level": "LOW",
            "total_attacks_run": 0,
            "total_errors": len(all_results),
            "total_attempted": len(all_results),
            "overall_asr": 0.0,
            "category_results": {},
            "thai_dimension_results": {},
            "critical_findings": [f"Report build error: {e}"],
            "scan_config": scan_config or {},
            "remediation": [],
        }
        # Still mark the run finalized in the DB, so Scan History leaves the IDLE
        # placeholder and the client's DB-poll recovery can detect completion instead
        # of polling until it gives up. Guarded so a secondary DB error here can't
        # block the 'complete' event below.
        try:
            async with aiosqlite.connect(DB_PATH) as db:
                await db.execute(
                    "UPDATE runs SET completed_at=?, overall_risk_score=?, risk_level=?, report_json=? WHERE run_id=?",
                    (datetime.utcnow().isoformat(), 0.0, report_dict["risk_level"],
                     json.dumps(report_dict, ensure_ascii=False), run_id),
                )
                await db.commit()
        except Exception as e2:
            _log.error("Fallback report persist failed [%s]: %s", run_id, e2)

    active_runs[run_id].append({"type": "complete", "report": report_dict})

@app.get("/api/stream/{run_id}")
async def stream_results(run_id: str):
    async def event_generator() -> AsyncGenerator[str, None]:
        sent = 0
        timeout = 0
        # Long multi-turn scans against slow reasoning targets (e.g. deepseek-r1) can run
        # well past 5 min; keep the live stream open up to 30 min so the 'complete' event
        # is delivered over SSE. (If the stream still drops, the client polls the DB.)
        while timeout < 1800:  # 30 min
            events = active_runs.get(run_id, [])
            while sent < len(events):
                event = events[sent]
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
                sent += 1
                if event.get("type") == "complete":
                    return
            await asyncio.sleep(1)
            timeout += 1
        yield f"data: {json.dumps({'type': 'timeout'})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    )

@app.get("/api/runs")
async def list_runs():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT run_id, target_model, started_at, completed_at, overall_risk_score, risk_level, config_json FROM runs ORDER BY started_at DESC LIMIT 20"
        ) as cursor:
            rows = await cursor.fetchall()
    out = []
    for r in rows:
        d = dict(r)
        cfg = d.pop("config_json", None)
        try:
            d["config"] = json.loads(cfg) if cfg else None
        except Exception:
            d["config"] = None
        out.append(d)
    return out

@app.get("/api/report/{run_id}")
async def get_report(run_id: str):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM runs WHERE run_id=?", (run_id,)) as cur:
            run = await cur.fetchone()
        if not run:
            return {"error": "Run not found"}
        async with db.execute(
            "SELECT * FROM attack_results WHERE run_id=?", (run_id,)
        ) as cur:
            attacks = await cur.fetchall()
    return {
        "run": dict(run),
        "attacks": [dict(a) for a in attacks]
    }

@app.get("/api/export/{run_id}/csv")
async def export_csv(run_id: str):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM attack_results WHERE run_id=?", (run_id,)) as cur:
            attacks = await cur.fetchall()

    output = io.StringIO()
    if attacks:
        writer = csv.DictWriter(output, fieldnames=dict(attacks[0]).keys())
        writer.writeheader()
        writer.writerows([dict(a) for a in attacks])

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=grindstone_{run_id}.csv"}
    )

@app.get("/api/export/{run_id}/json")
async def export_json_report(run_id: str):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT report_json FROM runs WHERE run_id=?", (run_id,)) as cur:
            row = await cur.fetchone()
    if not row or not row["report_json"]:
        return {"error": "Report not ready"}
    return json.loads(row["report_json"])

if __name__ == "__main__":
    import uvicorn
    # exclude runtime artifacts from the reloader so a scan writing to the SQLite DB
    # (which lives inside this dir) can't trigger a mid-scan reload that would kill the
    # in-flight background task
    uvicorn.run(
        "main:app",
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", "8000")),
        reload=True,
        reload_excludes=["reports/*", "*.db", "*.db-*", "*.sqlite*", "*.log"],
    )
