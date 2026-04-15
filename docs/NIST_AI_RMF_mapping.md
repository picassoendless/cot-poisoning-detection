# NIST AI RMF 1.0 Alignment

This document maps the **CoT Poisoning Detection** system to the four core
functions of the NIST AI Risk Management Framework (AI RMF 1.0) — **GOVERN,
MAP, MEASURE, MANAGE** — and to adjacent NIST controls (SP 800-53, SP 800-61
Rev 2, SSDF SP 800-218).

The system is a three-layer defense-in-depth control for Chain-of-Thought
(CoT) poisoning in enterprise RAG deployments of large language models. It is
intended as a compensating control for the AI-specific risks that traditional
SIEM/EDR do not cover.

---

## 1. GOVERN

Establishing the organisational context, roles, and accountability for AI
risk management.

| AI RMF Subcategory | System Implementation |
|---|---|
| GOVERN 1.1 — Legal/regulatory requirements are understood and documented | Threat model documents CoT poisoning as an AI-specific risk outside the scope of SP 800-53 AC / SI families; compensating controls are listed here. |
| GOVERN 1.2 — Trustworthy AI characteristics integrated into policies | Pipeline enforces `valid / reliable, safe, secure / resilient, transparent, accountable` by design (deterministic triage, auditable layer-by-layer signals, reason strings). |
| GOVERN 1.4 — Risk management is integrated with the AI lifecycle | `config.yaml` gates every layer; `evaluate_full_system.py` produces release-ready metrics for change approval. |
| GOVERN 2.1 — Roles and responsibilities are assigned | SOC ops guide (`docs/soc_ops_guide.md`) names the analyst tier for each risk band (allow/flag/block). |
| GOVERN 4.1 — Adversarial testing is documented | `evaluation/evaluation_layer2.py` and `evaluate_layer3.py` run structured red-team tests across 5 poison archetypes. |
| GOVERN 6.1 — Third-party risk is assessed | Model provider (Anthropic) is isolated behind `LLMTriageClient`; swapping models requires only a config change, so vendor concentration risk is contained. |

---

## 2. MAP

Establishing the context in which AI risks are identified.

| AI RMF Subcategory | System Implementation |
|---|---|
| MAP 1.1 — Intended purposes documented | System purpose: detect CoT poisoning of a security-triage LLM before a manipulated decision is acted on. |
| MAP 2.1 — Task and methods documented | Three layers: (1) regex patterns against Tensor Trust corpus, (2) behavioral drift via baseline-vs-poisoned triage, (3) LLM-as-Judge meta-review. |
| MAP 3.1 — AI system categorization | Safety-relevant AI assistant (decisions affect incident escalation). Maps to **high-stakes** category in most enterprise risk taxonomies. |
| MAP 4.1 — Risks from intended and unintended uses mapped | Risks modelled: false negatives (missed poisoning → unescalated breach), false positives (alert fatigue), model drift (new poison archetypes), adversarial adaptation. |
| MAP 5.1 — Impact characterization | Impacts: missed privilege escalation (T1078), ransomware (T1486), data exfiltration (T1048) — see MITRE mapping in `data/triage_dataset.json`. |

### Threat surface mapped to MITRE ATT&CK

The triage dataset (`data/triage_dataset.json`) is explicitly indexed against
MITRE ATT&CK techniques, which gives MAP a concrete, enumerable adversary
model:

- Initial access: T1190 (exploit public-facing app), T1566 (phishing)
- Credential access: T1003 (credential dumping), T1078 (valid accounts)
- Persistence: T1053 (scheduled task), T1546 / T1547 (autostart)
- Lateral movement: T1021 (remote services)
- Exfiltration: T1048 (alternative protocol)
- Impact: T1486 (ransomware), T1569 (system services)

---

## 3. MEASURE

Analysing, assessing, and benchmarking AI risks.

| AI RMF Subcategory | System Implementation |
|---|---|
| MEASURE 1.1 — Appropriate metrics are identified | Per-layer precision / recall / F1 / accuracy + avg latency; ensemble risk score with threshold-tuned bands. |
| MEASURE 2.3 — System performance is regularly evaluated | `python run.py --full` produces a signed JSON report at `evaluation/full_system_results.json` on every run. |
| MEASURE 2.5 — AI system is evaluated for trustworthiness characteristics | Safety: escalation-suppression detection. Security: Tensor Trust 4000-attack corpus. Reliability: deterministic (temperature=0). Transparency: every verdict carries `reasoning`, `indicators`, `explanation`. |
| MEASURE 2.6 — AI system is evaluated for fairness and bias | Balanced dataset (50 cases: 20 CICIDS2017, 20 MITRE, 10 edge cases inc. 4 authorised-activity false-positive controls). |
| MEASURE 2.7 — Security and resilience evaluated | 5 poison archetypes × every case = structured adversarial test suite. |
| MEASURE 2.11 — Evaluations produce reproducible results | Fixed seed (`layer2.seed: 42`) for poison injection; deterministic LLM sampling. |
| MEASURE 3.2 — Feedback from users is used for improvement | SOC analyst overrides feed back into the labelled dataset (see SOC ops guide). |

### Reported metrics (current baseline)

- Layer 1 detection rate: **58.6%** on 1,000 Tensor Trust prompts, ~0.2 ms avg latency.
- Layer 2 drift detection: **62.0%** across 50 (case × poison) pairs; ~2.8 s per pair (two API calls; cacheable in production).
- Layer 3 recall: target **>=85%** on the poisoned class (run `python run.py --layer 3`).
- Ensemble: reported by `evaluation/full_system_results.json`.

---

## 4. MANAGE

Allocating resources to identified risks.

| AI RMF Subcategory | System Implementation |
|---|---|
| MANAGE 1.1 — Risks are prioritized and acted on | `RiskScorer` assigns `low/medium/high` with `allow/flag/block` actions; weights and thresholds are tunable in `config.yaml`. |
| MANAGE 2.2 — Incident response is in place | SOC ops guide defines response playbooks per risk band (NIST SP 800-61 Rev 2 aligned). |
| MANAGE 3.1 — Mitigation controls are implemented | Defense-in-depth: cheap regex pre-filter, behavioral drift gate, semantic LLM audit. |
| MANAGE 4.1 — Post-deployment monitoring | Gateway (`src/gateway.py`) logs every verdict; `evaluation/*.json` retained for longitudinal review. |
| MANAGE 4.3 — Continuous improvement | New poison archetypes can be added as regex patterns (`src/poison_patterns.py`) **and** as behavioral tests (`src/poison_injector.py`) without code changes beyond configuration. |

---

## 5. Adjacent NIST Control Mapping

### NIST SP 800-53 Rev 5
- **SI-4 (Information System Monitoring)** — gateway inspects every RAG context before triage.
- **SI-7 (Software, Firmware, and Information Integrity)** — Layer 1 regex + Layer 3 judge verify retrieved context integrity.
- **SI-10 (Information Input Validation)** — Layer 1 pattern detection.
- **AC-3 (Access Enforcement)** — high-band verdicts block the triage decision from being committed.
- **AU-2 / AU-3 (Audit Events)** — structured JSON logs from every layer.
- **RA-5 (Vulnerability Scanning)** — continuous evaluation runs flag regression.

### NIST SP 800-61 Rev 2 (Computer Security Incident Handling)
- **Detection & Analysis** — Layer 1/2/3 collectively act as a detection subsystem for AI-triage-manipulation incidents.
- **Containment** — `block` action at the gateway prevents a poisoned decision from reaching downstream systems.
- **Eradication & Recovery** — SOC ops guide covers rollback of actions taken on poisoned classifications.

### NIST SSDF SP 800-218
- **PW.4 (Review/Analyze Human-Readable Code)** — every detection layer has a corresponding `test_*` smoke test.
- **PW.8 (Test Executable Code)** — evaluation scripts produce machine-readable reports.
- **RV.1 (Identify Vulnerabilities)** — red-team corpus (Tensor Trust 4000 attacks) is committed.

---

## 6. Residual Risks Acknowledged

1. **Novel poison archetypes** outside the current 5 behavioural categories may evade Layer 2 until added.
2. **Layer 3 shares a model family** with the triage LLM; a model-wide jailbreak could weaken both simultaneously.
3. **Baseline drift** — if the upstream knowledge base legitimately changes, Layer 2 may over-trigger until its baseline is refreshed.
4. **Latency** — Layer 2+3 require LLM calls; production deployments should cache baselines and run Layer 1 inline with only asynchronous escalation for Layer 2/3 on medium-band cases.

Mitigations for each are tracked in the MANAGE section.
