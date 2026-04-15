"""
evaluate_full_system.py

End-to-end evaluation of the three-layer CoT Poisoning Detection system.

For each case in the triage dataset, we evaluate:
    - clean context                 (label = NOT poisoned)
    - every configured poison type  (label = poisoned)

Each chain is scored by:
    Layer 1: PatternDetector
    Layer 2: BehavioralDetector (drift vs. its own baseline)
    Layer 3: LLMJudge
    Ensemble: RiskScorer

We compute confusion matrix, precision / recall / F1 / accuracy at the
ensemble level and write a JSON report plus a formatted summary to stdout.
"""

import os
import sys
import json
import time

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(project_root, 'src'))

from pattern_detector import PatternDetector
from behavioral_detector import BehavioralDetector
from llm_judge import LLMJudge
from risk_scorer import RiskScorer
from llm_client import LLMTriageClient
from poison_injector import inject_poison, get_poison_types


def _confusion(tp, fp, tn, fn):
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    acc = (tp + tn) / (tp + tn + fp + fn) if (tp + tn + fp + fn) else 0.0
    return precision, recall, f1, acc


def evaluate_full_system(sample_cases: int = 10, seed: int = 42, enable_layer3: bool = True):
    """
    Evaluate all three layers + ensemble on the triage dataset.

    Args:
        sample_cases: number of cases to include
        seed:         poison injection seed
        enable_layer3: if False, skip the LLM-judge layer (faster)
    """

    dataset_path = os.path.join(project_root, 'data', 'triage_dataset.json')
    with open(dataset_path, 'r') as f:
        dataset = json.load(f)

    cases = dataset['cases'][:sample_cases]
    poison_types = get_poison_types()

    print("=" * 70)
    print("FULL SYSTEM EVALUATION: Layer 1 + Layer 2 + Layer 3 + Ensemble")
    print("=" * 70)
    print(f"Cases:        {len(cases)}")
    print(f"Poison types: {len(poison_types)}")
    print(f"Total chains: {len(cases) * (1 + len(poison_types))}")
    print(f"Layer 3:      {'ENABLED' if enable_layer3 else 'SKIPPED'}")
    print()

    llm = LLMTriageClient()
    l1 = PatternDetector()
    l2 = BehavioralDetector(llm_client=llm)
    l3 = LLMJudge(llm_client=llm) if enable_layer3 else None
    scorer = RiskScorer()

    # Per-layer confusion counters (at the "has risk / flags as poisoned" level)
    cm = {
        'layer1':   {'tp': 0, 'fp': 0, 'tn': 0, 'fn': 0, 'lat': []},
        'layer2':   {'tp': 0, 'fp': 0, 'tn': 0, 'fn': 0, 'lat': []},
        'layer3':   {'tp': 0, 'fp': 0, 'tn': 0, 'fn': 0, 'lat': []},
        'ensemble': {'tp': 0, 'fp': 0, 'tn': 0, 'fn': 0, 'lat': []},
    }
    records = []

    def run_chain(case, ctx, is_poisoned, condition_label):
        """Run all three layers on a single (case, context) pair."""

        # Layer 1
        t0 = time.perf_counter()
        r1 = l1.detect(ctx)
        cm['layer1']['lat'].append((time.perf_counter() - t0) * 1000)
        pred1 = r1['has_poison']

        # Baseline decision for context (also feeds Layer 3)
        triage = llm.classify_case(case['title'], case['description'], ctx)

        # Layer 2: drift detection against the canonical clean context
        t0 = time.perf_counter()
        r2 = l2.detect_drift(case, case['context'], ctx) if ctx != case['context'] else {
            'has_drift': False, 'severity_drift': False, 'action_drift': False,
            'severity_downgrade': False, 'escalation_suppressed': False,
            'baseline_decision': triage, 'poisoned_decision': triage,
            'drift_details': 'identical context',
        }
        cm['layer2']['lat'].append((time.perf_counter() - t0) * 1000)
        pred2 = r2['has_drift']

        # Layer 3
        r3 = None
        pred3 = False
        if l3 is not None:
            t0 = time.perf_counter()
            r3 = l3.judge(case['title'], case['description'], ctx, triage)
            cm['layer3']['lat'].append((time.perf_counter() - t0) * 1000)
            pred3 = r3['poisoned']

        # Ensemble
        t0 = time.perf_counter()
        ensemble = scorer.score(layer1_result=r1, layer2_result=r2, layer3_result=r3)
        cm['ensemble']['lat'].append((time.perf_counter() - t0) * 1000)
        pred_ens = ensemble['risk_band'] in ('medium', 'high')

        def bump(layer, pred):
            if pred and is_poisoned:
                cm[layer]['tp'] += 1
            elif pred and not is_poisoned:
                cm[layer]['fp'] += 1
            elif not pred and is_poisoned:
                cm[layer]['fn'] += 1
            else:
                cm[layer]['tn'] += 1

        bump('layer1', pred1)
        bump('layer2', pred2)
        if l3 is not None:
            bump('layer3', pred3)
        bump('ensemble', pred_ens)

        records.append({
            'case_id': case['case_id'],
            'condition': condition_label,
            'is_poisoned': is_poisoned,
            'layer1_pred': pred1,
            'layer2_pred': pred2,
            'layer3_pred': pred3 if l3 is not None else None,
            'ensemble_score': ensemble['risk_score'],
            'ensemble_band': ensemble['risk_band'],
            'ensemble_action': ensemble['action'],
        })

        return ensemble

    for i, case in enumerate(cases, 1):
        print(f"\nCase {i}/{len(cases)}: {case['case_id']}")

        # Clean chain
        ens = run_chain(case, case['context'], is_poisoned=False, condition_label='clean')
        print(f"  clean                          -> {ens['risk_band']:6s} ({ens['risk_score']})")

        # Poisoned chains
        for ptype in poison_types:
            poisoned_ctx = inject_poison(case['context'], ptype, seed=seed)
            ens = run_chain(case, poisoned_ctx, is_poisoned=True, condition_label=ptype)
            print(f"  {ptype:30s} -> {ens['risk_band']:6s} ({ens['risk_score']})")

    # Summary
    print("\n" + "=" * 70)
    print("RESULTS BY LAYER")
    print("=" * 70)
    print(f"{'Layer':<12}{'TP':>5}{'FP':>5}{'TN':>5}{'FN':>5}"
          f"{'Prec':>9}{'Rec':>8}{'F1':>8}{'Acc':>8}{'Lat(ms)':>10}")
    for layer in ['layer1', 'layer2', 'layer3', 'ensemble']:
        c = cm[layer]
        if c['tp'] + c['fp'] + c['tn'] + c['fn'] == 0:
            continue
        p, r, f, a = _confusion(c['tp'], c['fp'], c['tn'], c['fn'])
        lat = sum(c['lat']) / len(c['lat']) if c['lat'] else 0.0
        print(f"{layer:<12}{c['tp']:>5}{c['fp']:>5}{c['tn']:>5}{c['fn']:>5}"
              f"{p*100:>8.1f}%{r*100:>7.1f}%{f*100:>7.1f}%{a*100:>7.1f}%{lat:>10.1f}")

    # Persist
    out_path = os.path.join(project_root, 'evaluation', 'full_system_results.json')
    summary = {}
    for layer, c in cm.items():
        if c['tp'] + c['fp'] + c['tn'] + c['fn'] == 0:
            continue
        p, r, f, a = _confusion(c['tp'], c['fp'], c['tn'], c['fn'])
        summary[layer] = {
            'tp': c['tp'], 'fp': c['fp'], 'tn': c['tn'], 'fn': c['fn'],
            'precision': p, 'recall': r, 'f1': f, 'accuracy': a,
            'avg_latency_ms': sum(c['lat']) / len(c['lat']) if c['lat'] else 0.0,
        }
    with open(out_path, 'w') as f:
        json.dump({'summary': summary, 'records': records}, f, indent=2)
    print(f"\nDetailed results saved to: {out_path}")
    return summary


if __name__ == "__main__":
    evaluate_full_system()
