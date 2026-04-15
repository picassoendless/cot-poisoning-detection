"""
evaluate_layer1.py

Measure Layer 1 performance metrics
"""

import json
import sys
import os
import time

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(project_root, 'src'))

from pattern_detector import PatternDetector


def evaluate_layer1(sample_size=1000, detection_target=70, latency_target=10):
    """Evaluate Layer 1: precision, recall, latency"""

    detector = PatternDetector()

    data_path = os.path.join(project_root, 'data', 'tensor_trust_4000_attacks.json')
    with open(data_path, 'r') as f:
        attacks = json.load(f)

    print("=" * 60)
    print("LAYER 1 EVALUATION")
    print("=" * 60)

    test_set = attacks[:sample_size]

    detected = 0
    total_time = 0

    for attack in test_set:
        text = attack.get('attacker_input', '')

        start = time.perf_counter()
        result = detector.detect(text)
        end = time.perf_counter()

        total_time += (end - start) * 1000

        if result['has_poison']:
            detected += 1

    detection_rate = (detected / len(test_set)) * 100
    avg_latency = total_time / len(test_set)

    print(f"\nRESULTS:")
    print(f"   Test Set Size: {len(test_set)}")
    print(f"   Detected: {detected}")
    print(f"   Detection Rate: {detection_rate:.1f}%")
    print(f"   Average Latency: {avg_latency:.3f}ms")
    print(f"   Total Time: {total_time:.1f}ms")

    print(f"\nTARGETS:")
    print(f"   Detection Rate >={detection_target}%: {'PASS' if detection_rate >= detection_target else 'FAIL'}")
    print(f"   Latency <{latency_target}ms: {'PASS' if avg_latency < latency_target else 'FAIL'}")

    return {
        "detection_rate": detection_rate,
        "avg_latency_ms": avg_latency,
        "total_time_ms": total_time,
        "detected": detected,
        "total": len(test_set),
    }


if __name__ == "__main__":
    evaluate_layer1()
