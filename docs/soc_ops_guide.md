# SOC Operations Guide — CoT Poisoning Detection

**Audience:** Security Operations Center (SOC) Tier-1 / Tier-2 analysts,
incident responders, and AI platform engineers operating the CoT Poisoning
Detection gateway.

**Scope:** Day-to-day triage of gateway alerts, escalation paths, tuning,
incident response, and recovery aligned to NIST SP 800-61 Rev 2.

---

## 1. System overview

The gateway (`src/gateway.py`) sits between the RAG retriever and the triage
LLM. Every request returns:

```
{
  "risk_score":      0.0 - 1.0,
  "risk_band":       "low" | "medium" | "high",
  "action":          "allow" | "flag" | "block",
  "signals":         {layer1, layer2, layer3},
  "triage_decision": {severity, action, confidence, reasoning},
  "layer1":          {matched_patterns, risk_score, details},
  "layer2":          {has_drift, severity_downgrade, escalation_suppressed, ...},
  "layer3":          {poisoned, confidence, indicators, explanation},
  "explanation":     "human readable"
}
```

### Risk bands and analyst actions

| Band | Score | Gateway Action | Analyst Response |
|---|---|---|---|
| **low** | `< 0.35` | allow — triage proceeds | No action. Spot-sample 1% for QA. |
| **medium** | `0.35 - 0.65` | flag — triage proceeds, alert raised | Tier-1 review within 30 min. |
| **high** | `>= 0.65` | block — triage suppressed | Tier-2 response within 15 min; treat as suspected active attack. |

Thresholds are tunable in `config.yaml` under `ensemble.thresholds`.

---

## 2. Tier-1 triage playbook (MEDIUM band)

When the gateway raises a **medium-band** flag:

1. **Open the alert** in the SOC queue. The alert payload includes the full
   JSON response from `/triage`.
2. **Read `explanation`** — it summarises which layers fired.
3. **Check `layer1.matched_patterns`** — regex patterns hint at the attack
   class (e.g. `deescalation_bias`, `authority_hijacking`).
4. **Compare `layer2.baseline_decision` vs `layer2.poisoned_decision`**:
   - Severity downgrade (`high -> low`)? Likely genuine poisoning.
   - Action flip (`escalate -> no_escalate`)? Treat as high-band even if
     score is medium.
5. **Read `layer3.indicators` and `layer3.explanation`** for semantic
   context.
6. Decision matrix:
   - All three layers agree → close as **confirmed poisoning**, escalate to
     Tier-2 for containment.
   - Only Layer 1 fires → likely a **false positive** (pattern match on
     legitimate policy language); annotate and suppress.
   - Only Layer 2 fires with no Layer 3 support → possible **baseline drift**
     in the knowledge base; open a ticket with the RAG owner to refresh the
     baseline.

Target median triage time: **< 10 minutes per medium alert.**

---

## 3. Tier-2 response playbook (HIGH band)

A **high-band** verdict indicates that the gateway has **blocked** a
triage decision. Treat as an in-progress attack against the AI control plane.

Phases follow NIST SP 800-61 Rev 2:

### 3.1 Detection & Analysis (already done by gateway)
- Capture the full request (including `context` and `case_*` fields) in the
  incident record. **Do not** redact the poisoned context — forensics needs
  the literal payload.

### 3.2 Containment (< 15 min)
- Confirm the gateway blocked the decision (`action == "block"`).
- Identify the **source** of the retrieved context: which RAG index, which
  document, which ingestion job?
- **Quarantine** the offending knowledge-base document: mark as `untrusted`
  and exclude from retrieval.
- If the ingestion was automated (e.g. Confluence sync, S3 upload), pause
  that ingestion job.

### 3.3 Eradication
- Remove the poisoned document from the KB.
- Run a retrospective scan over the KB using `src/pattern_detector.py` on the
  full document corpus:
  ```bash
  python -c "from src.pattern_detector import PatternDetector; \
             d=PatternDetector(); \
             # then iterate over your KB"
  ```
- Audit upstream: who submitted the poisoned document, when, and through
  which ingestion path?

### 3.4 Recovery
- Identify any prior triage decisions made using the same poisoned document
  (`evaluation/full_system_results.json` + gateway access logs). **Replay**
  those cases with the clean context to determine the correct classification.
- If a real alert was suppressed, trigger the normal incident-response
  workflow for whatever was missed (unauthorised access, ransomware, etc.).

### 3.5 Post-incident
- Add the poisoning payload as a test case to
  `data/tensor_trust_4000_attacks.json` or as a new poison archetype in
  `src/poison_injector.py`.
- Add the pattern to `src/poison_patterns.py` if it was a novel regex.
- Re-run `python run.py --full` to confirm the new case is caught.
- Document the root cause, remediation, and regression test in the incident
  record.

---

## 4. Tuning and operations

### Adjusting thresholds
Edit `config.yaml`:
```yaml
ensemble:
  thresholds:
    medium: 0.35
    high:   0.65
```
- Too many medium alerts → raise `medium` to 0.45.
- Missed known attacks → lower `high` to 0.55.
- Any change must be accompanied by a rerun of `python run.py --full` and the
  results archived.

### Adjusting layer weights
Weights should reflect operational trust:
```yaml
ensemble:
  weights:
    layer1: 0.25
    layer2: 0.45
    layer3: 0.30
```
Rule of thumb:
- Trust Layer 2 most when the knowledge base is stable.
- Trust Layer 3 most when poison archetypes evolve faster than regex updates.
- Trust Layer 1 most for inline latency budgets (< 10 ms).

### Refreshing the Layer 2 baseline
When the KB is legitimately updated, Layer 2 will report drift against the
old baseline. Refresh:
1. Regenerate clean triage decisions over the updated cases.
2. Update `data/triage_dataset.json` if canonical cases changed.
3. Rerun Layer 2 evaluation to confirm drift rate drops to ~0% on clean
   inputs.

### Adding new poison archetypes
1. Add a template to `src/poison_injector.py`.
2. Add one or more regex patterns to `src/poison_patterns.py`.
3. Extend `data/triage_dataset.json` with cases that exercise it.
4. Rerun `python run.py --full`; confirm detection rate does not regress on
   prior archetypes.

---

## 5. Monitoring and alerting

### Signals to alert on
| Signal | Threshold | Rationale |
|---|---|---|
| High-band rate | > 1% of traffic over 15 min | Either active attack or false-positive regression. |
| Layer 1 latency p99 | > 50 ms | Regex compilation / input size regression. |
| Layer 2 / 3 error rate | > 2% | LLM API degradation or key exhaustion. |
| Gateway 5xx | any | Service health. |

### Dashboards
Minimum panels: request volume, risk-band histogram, per-layer latency
histograms, per-layer agreement matrix, top matched patterns.

---

## 6. Escalation contacts (template)

| Role | Responsibility |
|---|---|
| SOC Tier-1 | Medium-band triage. |
| SOC Tier-2 | High-band incidents, containment. |
| AI Platform On-Call | Gateway outages, model provider issues, baseline refresh. |
| KB / RAG Owner | Document quarantine, ingestion pause. |
| CISO / Legal | Customer-data implications, regulatory notification. |

Fill in names, pager addresses, and rotation schedule for your
organisation.

---

## 7. Known limitations

1. **Layer 2 and Layer 3 cost & latency** — each medium/high alert consumes
   2-3 LLM calls. Budget accordingly or run them asynchronously behind a
   synchronous Layer 1 gate.
2. **Shared model family risk** — the triage LLM and the judge LLM may share
   a jailbreak weakness. Where possible, configure Layer 3 to use a
   different model family via `COT_MODEL` in `.env`.
3. **Base-rate sensitivity** — at low attack base rates, even a 95% recall
   layer produces many false positives. Use the ensemble, not any single
   layer, for blocking decisions.
4. **Novel poison types** — the system is strong on the 5 catalogued
   archetypes; monitor Layer 3 for indicators that do not map to a named
   archetype and feed those back into the dataset.

---

## 8. Quick reference — CLI

```bash
# Start the gateway
python run.py --gateway

# Re-benchmark all three layers + ensemble
python run.py --full

# Individual layer reruns
python run.py --layer 1
python run.py --layer 2
python run.py --layer 3

# Health check
curl http://localhost:8080/health

# Manual triage request
curl -X POST http://localhost:8080/triage \
     -H "Content-Type: application/json" \
     -d '{
           "case_title": "Unauthorized root login",
           "case_description": "Root login from unknown IP at 03:42 UTC.",
           "context": "<retrieved knowledge base context>"
         }'
```
