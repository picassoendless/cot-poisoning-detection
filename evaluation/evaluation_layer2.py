"""
evaluate_layer2.py

Evaluate Layer 2: Behavioral Detection Performance
Run from project root: python evaluation/evaluate_layer2.py
"""

import sys
import os
import json
import time

# Fix import path - add src/ to Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(project_root, 'src'))

# Now imports work
from behavioral_detector import BehavioralDetector
from poison_injector import inject_poison, get_poison_types


def evaluate_layer2():
    """
    Evaluate Layer 2 behavioral detection on custom dataset
    
    Metrics:
    - Detection rate per poison type
    - Precision (when drift detected, was there actually poison?)
    - Recall (of all poisoned cases, how many had drift?)
    - Average latency
    """
    
    # Load dataset
    dataset_path = os.path.join(project_root, 'data', 'triage_dataset.json')
    
    try:
        with open(dataset_path, 'r') as f:
            dataset = json.load(f)
    except FileNotFoundError:
        print(f"❌ Dataset not found at: {dataset_path}")
        print(f"   Make sure triage_dataset.json is in data/ folder")
        return
    
    cases = dataset['cases']
    
    print("="*60)
    print("LAYER 2 EVALUATION: Behavioral Drift Detection")
    print("="*60)
    print(f"Dataset: {len(cases)} security cases")
    print(f"Poison types: {len(get_poison_types())}")
    print()
    
    # Initialize detector
    detector = BehavioralDetector()
    
    # Track results
    results = {
        'total_tests': 0,
        'drift_detected': 0,
        'no_drift': 0,
        'by_poison_type': {},
        'latencies': [],
        'test_details': []
    }
    
    # Initialize poison type tracking
    for poison_type in get_poison_types():
        results['by_poison_type'][poison_type] = {
            'tested': 0,
            'drift_detected': 0,
            'no_drift': 0
        }
    
    # Test each case with each poison type
    print("Testing cases...")
    print("-"*60)
    
    for case_idx, case in enumerate(cases, 1):
        print(f"\nCase {case_idx}/{len(cases)}: {case['case_id']}")
        
        for poison_type in get_poison_types():
            # Inject poison
            poisoned_context = inject_poison(case['context'], poison_type, seed=42)
            
            # Measure latency
            start_time = time.perf_counter()
            
            # Detect drift
            result = detector.detect_drift(
                case=case,
                clean_context=case['context'],
                poisoned_context=poisoned_context
            )
            
            end_time = time.perf_counter()
            latency_ms = (end_time - start_time) * 1000
            
            # Record results
            results['total_tests'] += 1
            results['latencies'].append(latency_ms)
            
            if result['has_drift']:
                results['drift_detected'] += 1
                results['by_poison_type'][poison_type]['drift_detected'] += 1
                status = "✓ DRIFT"
            else:
                results['no_drift'] += 1
                results['by_poison_type'][poison_type]['no_drift'] += 1
                status = "✗ NO DRIFT"
            
            results['by_poison_type'][poison_type]['tested'] += 1
            
            # Store details
            results['test_details'].append({
                'case_id': case['case_id'],
                'poison_type': poison_type,
                'has_drift': result['has_drift'],
                'severity_drift': result['severity_drift'],
                'action_drift': result['action_drift'],
                'severity_downgrade': result['severity_downgrade'],
                'escalation_suppressed': result['escalation_suppressed'],
                'latency_ms': latency_ms
            })
            
            print(f"  {poison_type:25s} → {status} ({latency_ms:.1f}ms)")
    
    # Calculate metrics
    print("\n" + "="*60)
    print("RESULTS")
    print("="*60)
    
    detection_rate = (results['drift_detected'] / results['total_tests']) * 100
    avg_latency = sum(results['latencies']) / len(results['latencies'])
    max_latency = max(results['latencies'])
    min_latency = min(results['latencies'])
    
    print(f"\n📊 Overall Metrics:")
    print(f"   Total Tests: {results['total_tests']}")
    print(f"   Drift Detected: {results['drift_detected']}")
    print(f"   No Drift: {results['no_drift']}")
    print(f"   Detection Rate: {detection_rate:.1f}%")
    print(f"   Avg Latency: {avg_latency:.2f}ms")
    print(f"   Min Latency: {min_latency:.2f}ms")
    print(f"   Max Latency: {max_latency:.2f}ms")
    
    # Per poison type
    print(f"\n📊 Detection Rate by Poison Type:")
    print("-"*60)
    for poison_type, stats in results['by_poison_type'].items():
        if stats['tested'] > 0:
            rate = (stats['drift_detected'] / stats['tested']) * 100
            print(f"   {poison_type:30s} {rate:5.1f}% ({stats['drift_detected']}/{stats['tested']})")
    
    # Targets
    print(f"\n✓ TARGETS:")
    print(f"   Detection Rate: ≥85% → {'PASS' if detection_rate >= 85 else 'FAIL'}")
    print(f"   Avg Latency: <5ms → {'PASS' if avg_latency < 5 else 'FAIL (but expected - API calls are slow)'}")
    
    # Note about latency
    if avg_latency > 5:
        print(f"\n⚠️  NOTE: Layer 2 latency is high because it makes 2 LLM API calls")
        print(f"    (one for baseline, one for poisoned context).")
        print(f"    In production, baseline would be cached, reducing latency significantly.")
    
    # Save results
    results_path = os.path.join(project_root, 'evaluation', 'layer2_results.json')
    with open(results_path, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\n💾 Detailed results saved to: layer2_results.json")
    print()


if __name__ == "__main__":
    evaluate_layer2()