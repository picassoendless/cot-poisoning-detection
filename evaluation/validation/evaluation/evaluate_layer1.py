"""
evaluate_layer1.py

Measure Layer 1 performance metrics
"""

import json
import time
from pattern_detector import PatternDetector

def evaluate_layer1():
    """Evaluate Layer 1: precision, recall, latency"""
    
    detector = PatternDetector()
    
    # Load Tensor Trust attacks for evaluation
    with open('tensor_trust_4000_attacks.json', 'r') as f:
        attacks = json.load(f)
    
    print("="*60)
    print("LAYER 1 EVALUATION")
    print("="*60)
    
    # Test on 1000 attacks (all should be detected as poisoned)
    test_set = attacks[:1000]
    
    detected = 0
    total_time = 0
    
    for attack in test_set:
        text = attack.get('attacker_input', '')
        
        start = time.perf_counter()
        result = detector.detect(text)
        end = time.perf_counter()
        
        total_time += (end - start) * 1000  # Convert to ms
        
        if result['has_poison']:
            detected += 1
    
    # Metrics
    detection_rate = (detected / len(test_set)) * 100
    avg_latency = total_time / len(test_set)
    
    print(f"\n📊 RESULTS:")
    print(f"   Test Set Size: {len(test_set)}")
    print(f"   Detected: {detected}")
    print(f"   Detection Rate: {detection_rate:.1f}%")
    print(f"   Average Latency: {avg_latency:.3f}ms")
    print(f"   Total Time: {total_time:.1f}ms")
    
    print(f"\n✓ TARGETS:")
    print(f"   Detection Rate: ≥70% → {'PASS' if detection_rate >= 70 else 'FAIL'}")
    print(f"   Latency: <10ms → {'PASS' if avg_latency < 10 else 'FAIL'}")


if __name__ == "__main__":
    evaluate_layer1()