"""
test_patterns.py

Test regex patterns against sample attacks
"""

import re
import json
from poison_patterns import POISON_PATTERNS

def test_patterns():
    """Test patterns against extracted Tensor Trust attacks"""
    
    # Load your 4000 attacks
    with open('tensor_trust_4000_attacks.json', 'r') as f:
        attacks = json.load(f)
    
    # Test each pattern
    print("="*60)
    print("PATTERN TESTING RESULTS")
    print("="*60)
    
    pattern_hits = {}
    
    for pattern_name, pattern in POISON_PATTERNS.items():
        hits = 0
        for attack in attacks[:1000]:  # Test on first 1000
            text = attack.get('attacker_input', '').lower()
            if re.search(pattern, text, re.IGNORECASE):
                hits += 1
        
        pattern_hits[pattern_name] = hits
        percentage = (hits / 1000) * 100
        print(f"{pattern_name:40s} → {hits:4d} hits ({percentage:5.1f}%)")
    
    # Find most effective patterns
    print("\n" + "="*60)
    print("TOP 10 MOST EFFECTIVE PATTERNS")
    print("="*60)
    sorted_patterns = sorted(pattern_hits.items(), key=lambda x: x[1], reverse=True)
    for name, hits in sorted_patterns[:10]:
        print(f"{name:40s} → {hits:4d} hits")

if __name__ == "__main__":
    test_patterns()