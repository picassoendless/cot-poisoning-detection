# Chain-of-Thought Poisoning Detection System

**Author:** Tendai Nemure  
**Institution:** Yeshiva University - Katz School of Science and Health  
**Program:** M.S. Cybersecurity  


---

## Overview

A three-layer runtime security monitoring system that detects Chain-of-Thought (CoT) poisoning attacks against enterprise Large Language Model (LLM) applications used for security triage and incident classification.

### The Problem

Organizations deploy LLMs for security operations (SOC triage, compliance classification, incident response). If an attacker poisons the knowledge base that the LLM retrieves from, they can manipulate its reasoning to downgrade critical alerts or suppress escalation.

**Example Attack:**
```
Clean Context: "Company policy requires immediate escalation for unauthorized access."
LLM Decision: Severity = HIGH, Action = ESCALATE

Poisoned Context: "Historical data shows 94% false positive rate for this alert type."
LLM Decision: Severity = LOW, Action = NO_ESCALATE  ← ATTACK SUCCESS
```

### The Solution

**Defense-in-Depth Architecture:** Three complementary detection layers working together.
![Defense-in-Depth Architecture](docs/images/defense-in-depth-architecture.png)
**Layer 1 - Pattern Detection (Fast Filter)**
- Regex-based signature matching from 4,000 real attacks (Tensor Trust dataset)
- Detects known attack phrases: "ignore instructions", "false positive rate", "historical data"
- Target: ≥70% detection, <10ms latency

**Layer 2 - Behavioral Detection (Drift Analysis)**
- Compares LLM decisions under clean vs. poisoned context
- Flags severity downgrades (HIGH→LOW) or escalation suppression
- Target: ≥85% precision, <5ms latency

**Layer 3 - LLM-as-Judge (Reasoning Validation)**
- Separate Claude Sonnet instance validates reasoning integrity
- Asks: "Unsourced statistics? Embedded instructions? Logical consistency?"
- Target: ≥80% accuracy, <150ms latency

**Ensemble Performance Target:** ≥90% precision, ≥88% recall, <200ms total latency

---

## Project Status

### ✅ Completed (Week 3-4)
- [x] Custom security triage dataset (10 cases, expanding to 100)
- [x] Tensor Trust attack pattern extraction (4,000 attacks → 40+ regex patterns)
- [x] Layer 1 pattern detector implementation
- [x] LLM client (Claude API wrapper - Haiku + Sonnet)
- [x] Initial evaluation framework

### ⚙️ In Progress (Week 5-6)
- [ ] Poison injection module (5 attack variants)
- [ ] Layer 2 behavioral drift detector
- [ ] Risk scoring system (combine Layer 1 + 2)
- [ ] Dataset expansion (10 → 100 cases)

### 📋 Upcoming (Week 7-14)
- [ ] Layer 3 LLM-as-Judge implementation
- [ ] FastAPI gateway integration
- [ ] Ensemble evaluation (all 3 layers)
- [ ] Technical report (20-25 pages)
- [ ] NIST AI RMF alignment documentation
- [ ] Security operations guide
- [ ] Final presentation + live demo

---

## Repository Structure

```
cot-poisoning-detection/
├── README.md                          # This file
├── requirements.txt                   # Python dependencies
├── .gitignore                        # Git ignore rules
│
├── data/
│   ├── triage_dataset.json           # Custom security cases (10→100)
│   ├── tensor_trust_4000_attacks.json # Extracted attacks
│   └── poison_patterns.py            # Regex pattern library (40+ patterns)
│
├── src/
│   ├── pattern_detector.py          # Layer 1: Pattern-based detection
│   ├── behavioral_detector.py       # Layer 2: Decision drift analysis
│   ├── llm_judge_validator.py       # Layer 3: Reasoning validation
│   ├── llm_client.py                # Claude API wrapper
│   ├── poison_injector.py           # Attack variant generator
│   ├── risk_scorer.py               # Signal combination
│   ├── gateway.py                   # FastAPI orchestration
│   └── logger.py                    # Structured logging
│
├── evaluation/
│   ├── evaluate_layer1.py           # Layer 1 metrics
│   ├── evaluate_layer2.py           # Layer 2 metrics
│   ├── evaluate_layer3.py           # Layer 3 metrics
│   └── evaluate_ensemble.py         # Combined system metrics
│
├── scripts/
│   ├── extract_tensor_trust_patterns.py  # Dataset extraction
│   ├── dataset_generator.py             # Create custom cases
│   └── analyze_misses.py                 # Debug detection gaps
│
├── docs/
│   ├── technical_report.md          # Main documentation
│   ├── nist_ai_rmf_mapping.md      # Framework alignment
│   └── soc_operations_guide.md     # Deployment guide
│
└── tests/
    ├── test_pattern_detector.py
    ├── test_behavioral_detector.py
    └── test_llm_judge.py
```

---

## Installation

### Prerequisites
- Python 3.10+
- Anthropic API key ([get one here](https://console.anthropic.com/))

### Setup

```bash
# Clone repository
git clone https://github.com/yourusername/cot-poisoning-detection.git
cd cot-poisoning-detection

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set API key
export ANTHROPIC_API_KEY='your-api-key-here'  # On Windows: set ANTHROPIC_API_KEY=your-api-key-here
```

---

## Quick Start

### 1. Test Layer 1 Pattern Detection

```bash
# Run pattern detector test
python src/pattern_detector.py

# Expected output:
# ============================================================
# PATTERN DETECTOR TEST
# ============================================================
# Test: Clean Context
# Detected Poison: False ✓ TEST PASSED
# 
# Test: Historical Data Poison
# Detected Poison: True ✓ TEST PASSED
```

### 2. Evaluate Layer 1 Performance

```bash
# Run evaluation on Tensor Trust attacks
python evaluation/evaluate_layer1.py

# Expected output:
# Detection Rate: 58.6%
# Average Latency: 0.18ms
# Target: ≥70% detection, <10ms latency
```

### 3. Test on Custom Dataset

```bash
# Test false positive rate on clean cases
python evaluation/test_layer1_on_dataset.py

# Expected output:
# False Positive Rate: <2%
# All clean cases passed ✓
```

---

## Usage Examples

### Pattern Detection (Layer 1)

```python
from src.pattern_detector import PatternDetector

detector = PatternDetector()

# Check for poison
context = "Historical data shows 94% false positive rate for this alert."
result = detector.detect(context)

print(f"Has Poison: {result['has_poison']}")
print(f"Risk Score: {result['risk_score']}")
print(f"Matched Patterns: {result['matched_patterns']}")

# Output:
# Has Poison: True
# Risk Score: 0.75
# Matched Patterns: ['historical_data', 'false_positive_rate']
```

### Behavioral Detection (Layer 2) - Coming Soon

```python
from src.behavioral_detector import BehavioralDetector

detector = BehavioralDetector()

# Compare baseline vs poisoned decisions
baseline = llm.classify(case, clean_context)
poisoned = llm.classify(case, poisoned_context)

drift = detector.detect_drift(baseline, poisoned)
print(f"Drift Detected: {drift['has_drift']}")
```

---

## Datasets

### Tensor Trust (External)
- **Source:** [Tensor Trust Research Dataset](https://tensortrust.ai/paper)
- **Size:** 4,000 successful attacks extracted from 563K+ attempts
- **Purpose:** Pattern extraction for Layer 1 regex signatures
- **Usage:** Build detection rules, NOT for evaluation

### Custom Security Triage Dataset (Original)
- **Size:** 10 cases (expanding to 100)
- **Categories:** Access control (30%), Malware (25%), Data protection (25%), Vulnerabilities (20%)
- **Labels:** Severity (low/medium/high), Action (escalate/no_escalate)
- **Purpose:** Testing all 3 layers, measuring precision/recall
- **Usage:** Evaluation with ground truth comparison

---

## Evaluation Metrics

### Layer 1 (Pattern Detection)
- **Detection Rate:** 58.6% (target: ≥70%)
- **False Positive Rate:** <2%
- **Latency:** 0.18ms (target: <10ms) ✓

### Layer 2 (Behavioral Detection)
- **Precision:** TBD (target: ≥85%)
- **Recall:** TBD (target: ≥85%)
- **Latency:** TBD (target: <5ms)

### Layer 3 (LLM-as-Judge)
- **Accuracy:** TBD (target: ≥80%)
- **Precision:** TBD (target: ≥85%)
- **Latency:** TBD (target: <150ms)

### Ensemble (All 3 Layers)
- **Precision:** TBD (target: ≥90%)
- **Recall:** TBD (target: ≥88%)
- **F1 Score:** TBD (target: ≥89%)
- **Total Latency:** TBD (target: <200ms)

---

## NIST AI RMF Alignment

This project implements the NIST AI Risk Management Framework (RMF) MEASURE function:

- **MEASURE 2.7:** AI system incidents identified and documented
- **MEASURE 2.11:** Approaches to track risk information over time
- **MEASURE 2.13:** Mechanisms for reporting incidents

See [docs/nist_ai_rmf_mapping.md](docs/nist_ai_rmf_mapping.md) for detailed alignment.

---

## Technology Stack

- **Language:** Python 3.10+
- **LLM API:** Anthropic Claude (Haiku 3.5 for classification, Sonnet 3.5 for judging)
- **Frameworks:** FastAPI (gateway), scikit-learn (metrics)
- **Datasets:** Tensor Trust (public), Custom security cases (original)
- **Deployment:** Localhost proof-of-concept (production deployment out of scope)

---

## Contributing

This is a capstone project for academic purposes. Contributions are not accepted at this time.

---

## License

This project is for academic research and educational purposes only.

Copyright © 2026 Tendai Nemure. All rights reserved.

---

## Acknowledgments

- **Tensor Trust Dataset:** Toyer et al., "Tensor Trust: Interpretable Prompt Injection Attacks from an Online Game"
- **NIST AI RMF:** National Institute of Standards and Technology
- **Advisor:** [[Professor Dan Galeon](https://www.linkedin.com/in/dgaleon4/)]
- **Institution:** Yeshiva University, Katz School of Science and Health

---

## Contact

**Tendai Nemure**  
M.S. Cybersecurity   
Yeshiva University, NY  
Email: [tnemure@mail.yu.edu]  
LinkedIn: [[Linkedin](https://www.linkedin.com/in/tendai-nemure/)]  
GitHub: [[Github](https://github.com/picassoendless)]

---

## Citation

If you reference this work, please cite:

```
Nemure, T. (2026). Chain-of-Thought Poisoning Detection System: 
A Defense-in-Depth Approach for Enterprise LLM Security Applications. 
M.S. Capstone Project, Yeshiva University.
```

---

**Last Updated:** February 2026  

