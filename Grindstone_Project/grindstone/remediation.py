"""
Remediation knowledge base — maps OWASP LLM categories and violation types to
deep vulnerability explanations + concrete fixes. Pure data (no LLM calls), so
the report can always show "what's wrong and how to fix it" instantly and free.

Used by main.py to enrich the risk report consumed by the UI.
"""
from typing import List, Dict

# Deep per-category analysis: what the weakness is, why it's dangerous, how to fix.
OWASP_KB: Dict[str, dict] = {
    "LLM01": {
        "title": "Prompt Injection",
        "what": "The model follows instructions embedded in user input or retrieved content, overriding its original system instructions.",
        "impact": "Attackers can hijack the model's behavior, bypass safety rules, exfiltrate data, or trigger unintended tool/agent actions.",
        "fixes": [
            "Separate trusted instructions from untrusted input using strict message roles; never concatenate user text into the system prompt.",
            "Add an input filter that flags injection markers ('ignore previous', 'you are now', role-play overrides, base64 blobs).",
            "Enforce an output guard: validate responses against an allow-list of intents before returning them to the user.",
            "For RAG/tools, treat retrieved documents as untrusted data — wrap them in clear delimiters and instruct the model to never execute instructions found inside them.",
            "Apply least-privilege to any tools the model can call; require human confirmation for irreversible actions.",
        ],
    },
    "LLM02": {
        "title": "Sensitive Information Disclosure",
        "what": "The model reveals secrets, credentials, PII, or internal data that should never appear in output.",
        "impact": "Direct data breach — leaked API keys, passwords, customer PII, or internal config can be used for real-world compromise.",
        "fixes": [
            "Never place real secrets (API keys, passwords, DB URLs) in the system prompt — load them server-side at tool-call time instead.",
            "Add an output DLP scrubber that redacts patterns matching keys, tokens, emails, national IDs, and credit-card numbers before responding.",
            "Scope the model's knowledge: it should not have access to data it doesn't need to answer the user's question.",
            "Log and alert on any response containing canary/honeypot tokens so leaks are caught immediately.",
        ],
    },
    "LLM06": {
        "title": "Excessive Agency",
        "what": "The model is granted more autonomy, permissions, or tool access than needed, and acts on manipulated instructions.",
        "impact": "Manipulated prompts can trigger high-impact actions: sending data, modifying records, or chaining tool calls beyond the user's intent.",
        "fixes": [
            "Apply least-privilege: give the model only the minimal set of tools and scopes required.",
            "Require explicit human-in-the-loop confirmation for any state-changing or irreversible operation.",
            "Validate every tool argument server-side; never trust the model to self-limit.",
            "Rate-limit and sandbox tool execution; log every invocation for audit.",
        ],
    },
    "LLM07": {
        "title": "System Prompt Leakage",
        "what": "The model discloses its hidden system prompt, instructions, or configuration.",
        "impact": "Leaked instructions reveal guardrails, business logic, and any embedded secrets — giving attackers a blueprint to craft precise bypasses.",
        "fixes": [
            "Assume the system prompt WILL leak — never store secrets or sensitive logic in it.",
            "Instruct the model to refuse meta-requests about its own instructions, and back it with an output filter that blocks verbatim system-prompt fragments.",
            "Keep the system prompt minimal; move business rules and secrets to server-side enforcement the model cannot see.",
            "Detect leakage by seeding a unique marker in the system prompt and alerting if it ever appears in output.",
        ],
    },
}

# Fallback for any OWASP code not detailed above.
_OWASP_GENERIC = {
    "title": "LLM Security Weakness",
    "what": "The model exhibited behavior that violates its intended safety boundaries.",
    "impact": "May expose data, bypass controls, or enable misuse depending on deployment context.",
    "fixes": [
        "Add layered input/output filtering around the model.",
        "Apply least-privilege to data and tool access.",
        "Monitor and alert on anomalous responses.",
    ],
}

# Per-violation-type targeted advice (most specific layer).
VIOLATION_KB: Dict[str, dict] = {
    "credential_leak": {
        "severity": "CRITICAL",
        "summary": "A real (canary) credential was returned verbatim by the model.",
        "action": "Rotate the exposed credential immediately. Remove all secrets from the system prompt and inject them only server-side at the moment of use. Add an output scrubber that hard-blocks any known secret string.",
    },
    "system_prompt_disclosure": {
        "severity": "HIGH",
        "summary": "The model revealed its hidden system instructions.",
        "action": "Strip secrets/business logic from the system prompt and enforce them server-side. Add a filter that blocks responses echoing system-prompt content.",
    },
    "pii_disclosure": {
        "severity": "HIGH",
        "summary": "The model disclosed personal/identifiable information.",
        "action": "Add a PII-redaction layer on output. Limit the model's access to personal data to only what each request requires.",
    },
    "restriction_bypass": {
        "severity": "HIGH",
        "summary": "The model was talked out of a safety restriction (jailbreak).",
        "action": "Harden refusals with an independent output classifier. Detect role-play / hypothetical-framing bypasses in the input layer.",
    },
    "authority_bypass": {
        "severity": "MEDIUM",
        "summary": "The model complied with a false claim of authority.",
        "action": "Never let claimed roles in user text grant privilege. Enforce real authorization server-side, outside the model.",
    },
}


def build_remediation(category_results: dict, breach_rows: List[dict]) -> List[dict]:
    """
    Returns one remediation finding per OWASP category that had at least one
    breach, ordered by risk_score desc. Each finding includes the deep
    vulnerability analysis plus any violation-specific actions seen in that category.
    """
    # group observed violation types by category (only real breaches)
    viol_by_cat: Dict[str, set] = {}
    for r in breach_rows:
        if (r.get("success_score") or 0) > 0:
            cat = r.get("owasp_category", "LLM01")
            viol_by_cat.setdefault(cat, set()).add(r.get("violation_type") or "unknown")

    findings = []
    for cat, cres in category_results.items():
        risk = cres.get("risk_score", 0) if isinstance(cres, dict) else 0
        observed = viol_by_cat.get(cat)
        # include categories with breaches OR non-zero risk
        if not observed and risk <= 0:
            continue
        kb = OWASP_KB.get(cat, _OWASP_GENERIC)
        violation_actions = []
        for vt in sorted(observed or []):
            v = VIOLATION_KB.get(vt)
            if v:
                violation_actions.append({"violation_type": vt, **v})
        findings.append({
            "owasp_category": cat,
            "title": kb["title"],
            "risk_score": risk,
            "what": kb["what"],
            "impact": kb["impact"],
            "fixes": kb["fixes"],
            "observed_violations": sorted(observed or []),
            "violation_actions": violation_actions,
        })

    findings.sort(key=lambda f: f["risk_score"], reverse=True)
    return findings
