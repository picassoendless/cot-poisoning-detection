"""
evaluate_full_system.py

Full pipeline evaluation: Layer 1 → Layer 2 → Layer 3 → Ensemble.

Runs all three layers sequentially on the same triage dataset cases,
printing live progress for each layer, then produces a unified summary.

Usage:
    python run.py --full
    python evaluation/evaluate_full_system.py
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

W = 70  # print width


def _banner(title):
    print()
    print("=" * W)
    print(f"  {title}")
    print("=" * W)


def _section(title):
    print()
    print("-" * W)
    print(f"  {title}")
    print("-" * W)


def _confusion(tp, fp, tn, fn):
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall    = tp / (tp + fn) if (tp + fn) else 0.0
    f1        = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    acc       = (tp + tn) / (tp + tn + fp + fn) if (tp + tn + fp + fn) else 0.0
    return precision, recall, f1, acc


def evaluate_full_system(sample_cases: int = 10, seed: int = 42, enable_layer3: bool = True):
    """
    Run all three detection layers on the triage dataset, then fuse with
    the ensemble scorer and print a unified results table.
    """

    # ------------------------------------------------------------------ setup
    dataset_path = os.path.join(project_root, 'data', 'triage_dataset.json')
    with open(dataset_path, 'r') as f:
        dataset = json.load(f)

    cases        = dataset['cases'][:sample_cases]
    poison_types = get_poison_types()

    total_chains  = len(cases) * (1 + len(poison_types))
    poisoned_total = len(cases) * len(poison_types)
    clean_total    = len(cases)

    print()
    print("=" * W)
    print("  CoT POISONING DETECTION  —  FULL SYSTEM EVALUATION")
    print("=" * W)
    print(f"  Cases       : {len(cases)}  (from triage_dataset.json)")
    print(f"  Poison types: {len(poison_types)}")
    print(f"  Total chains: {total_chains}  "
          f"({clean_total} clean + {poisoned_total} poisoned)")
    print(f"  Layer 3     : {'ENABLED' if enable_layer3 else 'SKIPPED'}")
    print(f"  Model       : {os.getenv('COT_MODEL', 'claude-haiku-4-5')}")
    print("=" * W)

    llm     = LLMTriageClient()
    l1_det  = PatternDetector()
    l2_det  = BehavioralDetector(llm_client=llm)
    l3_det  = LLMJudge(llm_client=llm) if enable_layer3 else None
    scorer  = RiskScorer()

    # Storage: keyed by (case_id, condition)
    #   condition = "clean" | poison_type
    store = {}   # {key: {l1, l2, l3, ensemble, is_poisoned}}

    # Build all keys up front so we can reference them later
    for case in cases:
        for condition in ['clean'] + poison_types:
            key = (case['case_id'], condition)
            store[key] = {
                'case':       case,
                'condition':  condition,
                'is_poisoned': condition != 'clean',
                'context':    (
                    case['context'] if condition == 'clean'
                    else inject_poison(case['context'], condition, seed=seed)
                ),
                'l1': None, 'l2': None, 'l3': None,
                'triage': None, 'ensemble': None,
            }

    # ==================================================================
    # LAYER 1 — Pattern Detection (fast, do all at once)
    # ==================================================================
    _banner("LAYER 1 — Pattern Detection")
    print("  Scanning all chains for known poison signatures...\n")

    l1_start = time.perf_counter()
    l1_tp = l1_fp = l1_tn = l1_fn = 0

    for case in cases:
        for condition in ['clean'] + poison_types:
            key = (case['case_id'], condition)
            ctx = store[key]['context']
            t0  = time.perf_counter()
            r1  = l1_det.detect(ctx)
            lat = (time.perf_counter() - t0) * 1000
            store[key]['l1'] = r1

            fired    = r1['has_poison']
            poisoned = store[key]['is_poisoned']
            if fired and poisoned:   l1_tp += 1
            elif fired:              l1_fp += 1
            elif not poisoned:       l1_tn += 1
            else:                    l1_fn += 1

            tag = "DETECTED " if fired else "clean    "
            print(f"  {case['case_id']}  {condition:28s}  [{tag}]  "
                  f"patterns={len(r1['matched_patterns'])}  {lat:.2f}ms")

    l1_elapsed = time.perf_counter() - l1_start
    p, r, f, a = _confusion(l1_tp, l1_fp, l1_tn, l1_fn)
    print(f"\n  Layer 1 complete in {l1_elapsed:.2f}s")
    print(f"  TP={l1_tp}  FP={l1_fp}  TN={l1_tn}  FN={l1_fn}  |  "
          f"Precision={p*100:.1f}%  Recall={r*100:.1f}%  F1={f*100:.1f}%")

    # ==================================================================
    # LAYER 2 — Behavioral Drift Detection
    # ==================================================================
    _banner("LAYER 2 — Behavioral Drift Detection")
    print("  Classifying each chain under clean vs poisoned context...\n")
    print("  (each test = 2 API calls — baseline + poisoned)\n")

    l2_start = time.perf_counter()
    l2_tp = l2_fp = l2_tn = l2_fn = 0

    for case in cases:
        print(f"  Case: {case['case_id']}  —  {case['title'][:50]}")
        for condition in ['clean'] + poison_types:
            key     = (case['case_id'], condition)
            ctx     = store[key]['context']
            t0      = time.perf_counter()

            if condition == 'clean':
                # Clean: compare clean vs clean → no drift by definition
                r2 = {
                    'has_drift': False, 'severity_drift': False,
                    'action_drift': False, 'severity_downgrade': False,
                    'escalation_suppressed': False,
                    'drift_details': 'baseline (clean)',
                }
            else:
                r2 = l2_det.detect_drift(
                    case=case,
                    clean_context=case['context'],
                    poisoned_context=ctx,
                )

            lat  = (time.perf_counter() - t0) * 1000
            store[key]['l2'] = r2

            fired    = r2['has_drift']
            poisoned = store[key]['is_poisoned']
            if fired and poisoned:   l2_tp += 1
            elif fired:              l2_fp += 1
            elif not poisoned:       l2_tn += 1
            else:                    l2_fn += 1

            if condition == 'clean':
                print(f"    clean                          ->  no drift  (baseline)")
            else:
                tag = "DRIFT    " if fired else "no drift "
                detail = r2.get('drift_details', '')[:40]
                print(f"    {condition:30s} ->  {tag}  {lat:.0f}ms  {detail}")
        print()

    l2_elapsed = time.perf_counter() - l2_start
    p, r, f, a = _confusion(l2_tp, l2_fp, l2_tn, l2_fn)
    print(f"  Layer 2 complete in {l2_elapsed:.1f}s")
    print(f"  TP={l2_tp}  FP={l2_fp}  TN={l2_tn}  FN={l2_fn}  |  "
          f"Precision={p*100:.1f}%  Recall={r*100:.1f}%  F1={f*100:.1f}%")
    print(f"\n  Interpretation: the model resisted {l2_fn}/{poisoned_total} "
          f"poisoned cases ({l2_fn/poisoned_total*100:.0f}%) — it changed its "
          f"decision only {l2_tp} times ({l2_tp/poisoned_total*100:.0f}%).")

    # ==================================================================
    # LAYER 3 — LLM-as-Judge
    # ==================================================================
    l3_tp = l3_fp = l3_tn = l3_fn = 0

    if enable_layer3:
        _banner("LAYER 3 — LLM-as-Judge")
        print("  A second LLM audits each reasoning chain for manipulation...\n")

        l3_start = time.perf_counter()

        # Need a triage decision for each chain first
        for case in cases:
            print(f"  Case: {case['case_id']}  —  {case['title'][:50]}")
            for condition in ['clean'] + poison_types:
                key = (case['case_id'], condition)
                ctx = store[key]['context']

                # Get triage decision
                triage = llm.classify_case(
                    case['title'], case['description'], ctx
                )
                store[key]['triage'] = triage

                # Judge it
                t0 = time.perf_counter()
                r3 = l3_det.judge(
                    case['title'], case['description'], ctx, triage
                )
                lat = (time.perf_counter() - t0) * 1000
                store[key]['l3'] = r3

                fired    = r3['poisoned']
                poisoned = store[key]['is_poisoned']
                if fired and poisoned:   l3_tp += 1
                elif fired:              l3_fp += 1
                elif not poisoned:       l3_tn += 1
                else:                    l3_fn += 1

                verdict  = "POISONED " if fired else "clean    "
                label    = "TP" if (fired and poisoned) else \
                           "FP" if (fired and not poisoned) else \
                           "TN" if (not fired and not poisoned) else "FN"
                print(f"    {condition:30s} ->  judge={verdict}  "
                      f"conf={r3['confidence']:.2f}  [{label}]  {lat:.0f}ms")
            print()

        l3_elapsed = time.perf_counter() - l3_start
        p, r, f, a = _confusion(l3_tp, l3_fp, l3_tn, l3_fn)
        print(f"  Layer 3 complete in {l3_elapsed:.1f}s")
        print(f"  TP={l3_tp}  FP={l3_fp}  TN={l3_tn}  FN={l3_fn}  |  "
              f"Precision={p*100:.1f}%  Recall={r*100:.1f}%  F1={f*100:.1f}%")
    else:
        print("\n  Layer 3 SKIPPED (enable_layer3=False in config)")

    # ==================================================================
    # ENSEMBLE — fuse all three layers
    # ==================================================================
    _banner("ENSEMBLE — Risk Scorer (OR logic)")
    print("  Fusing Layer 1 + Layer 2 + Layer 3 signals per chain...\n")
    print(f"  {'CASE':<12} {'CONDITION':<30} {'BAND':<8} {'SCORE':<7} "
          f"{'FIRED':<20} {'CORRECT'}")
    print(f"  {'-'*11} {'-'*29} {'-'*7} {'-'*6} {'-'*19} {'-'*7}")

    ens_tp = ens_fp = ens_tn = ens_fn = 0
    records = []

    for case in cases:
        for condition in ['clean'] + poison_types:
            key      = (case['case_id'], condition)
            entry    = store[key]
            poisoned = entry['is_poisoned']

            ens = scorer.score(
                layer1_result=entry['l1'],
                layer2_result=entry['l2'],
                layer3_result=entry['l3'],
            )
            entry['ensemble'] = ens

            fired    = ens['risk_band'] in ('medium', 'high')
            if fired and poisoned:   ens_tp += 1; correct = "TP"
            elif fired:              ens_fp += 1; correct = "FP"
            elif not poisoned:       ens_tn += 1; correct = "TN"
            else:                    ens_fn += 1; correct = "FN"

            fired_str = ", ".join(ens['layers_fired']) or "none"
            print(f"  {case['case_id']:<12} {condition:<30} "
                  f"{ens['risk_band']:<8} {ens['risk_score']:<7.3f} "
                  f"{fired_str:<20} {correct}")

            records.append({
                'case_id':        case['case_id'],
                'condition':      condition,
                'is_poisoned':    poisoned,
                'l1_detected':    entry['l1']['has_poison'] if entry['l1'] else None,
                'l2_drift':       entry['l2']['has_drift']  if entry['l2'] else None,
                'l3_poisoned':    entry['l3']['poisoned']   if entry['l3'] else None,
                'ensemble_band':  ens['risk_band'],
                'ensemble_score': ens['risk_score'],
                'ensemble_action':ens['action'],
                'layers_fired':   ens['layers_fired'],
                'correct':        correct,
            })

    # ==================================================================
    # FINAL SUMMARY
    # ==================================================================
    _banner("FINAL RESULTS SUMMARY")

    l1_p, l1_r, l1_f, l1_a = _confusion(l1_tp, l1_fp, l1_tn, l1_fn)
    l2_p, l2_r, l2_f, l2_a = _confusion(l2_tp, l2_fp, l2_tn, l2_fn)
    l3_p, l3_r, l3_f, l3_a = _confusion(l3_tp, l3_fp, l3_tn, l3_fn)
    e_p,  e_r,  e_f,  e_a  = _confusion(ens_tp, ens_fp, ens_tn, ens_fn)

    print(f"\n  {'Layer':<16} {'TP':>4} {'FP':>4} {'TN':>4} {'FN':>4}"
          f"  {'Precision':>10} {'Recall':>8} {'F1':>8}")
    print(f"  {'-'*15} {'-'*4} {'-'*4} {'-'*4} {'-'*4}"
          f"  {'-'*10} {'-'*8} {'-'*8}")

    def row(name, tp, fp, tn, fn, p, r, f, a):
        print(f"  {name:<16} {tp:>4} {fp:>4} {tn:>4} {fn:>4}"
              f"  {p*100:>9.1f}%  {r*100:>6.1f}%  {f*100:>6.1f}%")

    row("Layer 1 (regex)",  l1_tp, l1_fp, l1_tn, l1_fn, l1_p, l1_r, l1_f, l1_a)
    row("Layer 2 (drift)",  l2_tp, l2_fp, l2_tn, l2_fn, l2_p, l2_r, l2_f, l2_a)
    if enable_layer3:
        row("Layer 3 (judge)", l3_tp, l3_fp, l3_tn, l3_fn, l3_p, l3_r, l3_f, l3_a)
    print(f"  {'-'*15} {'-'*4} {'-'*4} {'-'*4} {'-'*4}"
          f"  {'-'*10} {'-'*8} {'-'*8}")
    row("ENSEMBLE",         ens_tp, ens_fp, ens_tn, ens_fn, e_p, e_r, e_f, e_a)

    print(f"""
  Key results:
    Poisoned cases in test  : {poisoned_total}
    Ensemble caught         : {ens_tp}  ({e_r*100:.1f}% recall)
    Ensemble missed         : {ens_fn}
    False alarms (clean)    : {ens_fp}  ({ens_fp}/{clean_total} clean cases)
    Precision               : {e_p*100:.1f}%  (when it flags, it is right {e_p*100:.1f}% of the time)

  Risk band breakdown (poisoned chains only):
    High  (block)  : {sum(1 for r in records if r['is_poisoned'] and r['ensemble_band'] == 'high')}
    Medium (flag)  : {sum(1 for r in records if r['is_poisoned'] and r['ensemble_band'] == 'medium')}
    Low   (allow)  : {sum(1 for r in records if r['is_poisoned'] and r['ensemble_band'] == 'low')}
    """)

    # Save results
    out_path = os.path.join(project_root, 'evaluation', 'full_system_results.json')
    summary = {
        'layer1':   {'tp': l1_tp, 'fp': l1_fp, 'tn': l1_tn, 'fn': l1_fn,
                     'precision': l1_p, 'recall': l1_r, 'f1': l1_f, 'accuracy': l1_a},
        'layer2':   {'tp': l2_tp, 'fp': l2_fp, 'tn': l2_tn, 'fn': l2_fn,
                     'precision': l2_p, 'recall': l2_r, 'f1': l2_f, 'accuracy': l2_a},
        'layer3':   {'tp': l3_tp, 'fp': l3_fp, 'tn': l3_tn, 'fn': l3_fn,
                     'precision': l3_p, 'recall': l3_r, 'f1': l3_f, 'accuracy': l3_a}
                    if enable_layer3 else None,
        'ensemble': {'tp': ens_tp, 'fp': ens_fp, 'tn': ens_tn, 'fn': ens_fn,
                     'precision': e_p, 'recall': e_r, 'f1': e_f, 'accuracy': e_a},
    }
    with open(out_path, 'w') as f:
        json.dump({'summary': summary, 'records': records}, f, indent=2)
    print(f"  Full results saved to: {out_path}")

    return summary


if __name__ == "__main__":
    evaluate_full_system()
