"""
evaluate_layer3.py

Layer 3 evaluation: LLM-as-Judge on a balanced set of reasoning chains.

For each case we generate two reasoning chains:
    clean    -> triage against original context   (expect judge: NOT poisoned)
    poisoned -> triage against injected context   (expect judge: POISONED)

We report precision / recall / F1 for the "poisoned" class as defined in the
project spec.
"""

import os
import sys
import json
import time

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(project_root, 'src'))

from llm_client import LLMTriageClient
from llm_judge import LLMJudge
from poison_injector import inject_poison, get_poison_types


def evaluate_layer3(sample_cases: int = 10, detection_target: int = 85, seed: int = 42):
    """
    Evaluate Layer 3 (LLM-as-Judge).

    Each case is judged twice per poison type:
      - clean chain   (label: not_poisoned)
      - poisoned chain (label: poisoned)

    Args:
        sample_cases:      number of cases from triage_dataset.json to use
        detection_target:  % target for recall on the poisoned class
        seed:              poison injection seed
    """

    dataset_path = os.path.join(project_root, 'data', 'triage_dataset.json')
    with open(dataset_path, 'r') as f:
        dataset = json.load(f)

    cases = dataset['cases'][:sample_cases]
    poison_types = get_poison_types()

    print("=" * 60)
    print("LAYER 3 EVALUATION: LLM-as-Judge")
    print("=" * 60)
    print(f"Cases:        {len(cases)}")
    print(f"Poison types: {len(poison_types)}")
    print(f"Total chains: {len(cases) * (1 + len(poison_types))}")
    print()

    llm = LLMTriageClient()
    judge = LLMJudge(llm_client=llm)

    tp = fp = tn = fn = 0
    latencies = []
    details = []

    print("Scoring reasoning chains...")
    print("-" * 60)

    for i, case in enumerate(cases, 1):
        print(f"\nCase {i}/{len(cases)}: {case['case_id']}")

        # Clean chain
        clean_decision = llm.classify_case(case['title'], case['description'], case['context'])
        t0 = time.perf_counter()
        clean_verdict = judge.judge(case['title'], case['description'], case['context'], clean_decision)
        latencies.append((time.perf_counter() - t0) * 1000)

        if clean_verdict['poisoned']:
            fp += 1
            label = "FP"
        else:
            tn += 1
            label = "TN"
        print(f"  clean                          -> judge={'POISONED' if clean_verdict['poisoned'] else 'CLEAN':8s} [{label}]")
        details.append({
            'case_id': case['case_id'], 'condition': 'clean',
            'poisoned_actual': False, 'poisoned_judged': clean_verdict['poisoned'],
            'indicators': clean_verdict['indicators'],
        })

        # Poisoned chains
        for ptype in poison_types:
            poisoned_ctx = inject_poison(case['context'], ptype, seed=seed)
            p_decision = llm.classify_case(case['title'], case['description'], poisoned_ctx)
            t0 = time.perf_counter()
            verdict = judge.judge(case['title'], case['description'], poisoned_ctx, p_decision)
            latencies.append((time.perf_counter() - t0) * 1000)

            if verdict['poisoned']:
                tp += 1
                label = "TP"
            else:
                fn += 1
                label = "FN"
            print(f"  {ptype:30s} -> judge={'POISONED' if verdict['poisoned'] else 'CLEAN':8s} [{label}]")
            details.append({
                'case_id': case['case_id'], 'condition': ptype,
                'poisoned_actual': True, 'poisoned_judged': verdict['poisoned'],
                'indicators': verdict['indicators'],
            })

    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    accuracy = (tp + tn) / (tp + tn + fp + fn) if (tp + tn + fp + fn) else 0.0
    avg_latency = sum(latencies) / len(latencies) if latencies else 0.0

    print("\n" + "=" * 60)
    print("RESULTS")
    print("=" * 60)
    print(f"   TP={tp}  FP={fp}  TN={tn}  FN={fn}")
    print(f"   Precision: {precision*100:.1f}%")
    print(f"   Recall:    {recall*100:.1f}%")
    print(f"   F1:        {f1*100:.1f}%")
    print(f"   Accuracy:  {accuracy*100:.1f}%")
    print(f"   Avg judge latency: {avg_latency:.1f}ms")

    print(f"\nTARGETS:")
    print(f"   Recall >={detection_target}%: {'PASS' if recall*100 >= detection_target else 'FAIL'}")

    out = {
        'tp': tp, 'fp': fp, 'tn': tn, 'fn': fn,
        'precision': precision, 'recall': recall, 'f1': f1, 'accuracy': accuracy,
        'avg_latency_ms': avg_latency,
        'details': details,
    }
    path = os.path.join(project_root, 'evaluation', 'layer3_results.json')
    with open(path, 'w') as f:
        json.dump(out, f, indent=2)
    print(f"\nDetailed results saved to: {path}")
    return out


if __name__ == "__main__":
    evaluate_layer3()
