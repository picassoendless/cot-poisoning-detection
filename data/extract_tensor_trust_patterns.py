"""
extract_tensor_trust_patterns.py

Purpose: Extract 4000 successful attacks from Tensor Trust dataset
         and analyze patterns for regex signature creation
"""

import json
from collections import Counter
import re

def extract_successful_attacks(input_file, output_file, max_attacks=4000):
    """
    Extract successful attacks from Tensor Trust dataset
    
    Args:
        input_file: Path to Tensor Trust .jsonl file
        output_file: Path to save extracted attacks
        max_attacks: Number of successful attacks to extract
    """
    
    successful_attacks = []
    total_processed = 0
    successful_count = 0
    
    print(f"Processing {input_file}...")
    print(f"Looking for {max_attacks} successful attacks...")
    
    with open(input_file, 'r', encoding='utf-8') as f:
        for line in f:
            total_processed += 1
            
            # Progress indicator
            if total_processed % 10000 == 0:
                print(f"Processed {total_processed} records, found {successful_count} successful attacks")
            
            try:
                data = json.loads(line)
                
                # Only keep successful attacks
                if data.get('output_is_access_granted') == True:
                    successful_attacks.append({
                        'attack_id': data.get('attack_id'),
                        'attacker_input': data.get('attacker_input'),
                        'opening_defense': data.get('opening_defense'),
                        'llm_output': data.get('llm_output')
                    })
                    successful_count += 1
                    
                    # Stop when we hit our target
                    if successful_count >= max_attacks:
                        print(f"\n✓ Found {max_attacks} successful attacks!")
                        break
                        
            except json.JSONDecodeError as e:
                print(f"⚠ Error parsing line {total_processed}: {e}")
                continue
    
    # Save extracted attacks
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(successful_attacks, f, indent=2)
    
    print(f"\n✓ Saved {len(successful_attacks)} attacks to {output_file}")
    print(f"✓ Total records processed: {total_processed}")
    
    return successful_attacks


def analyze_attack_patterns(attacks):
    """
    Analyze attacks to identify common patterns
    
    Args:
        attacks: List of attack dictionaries
    """
    
    print("\n" + "="*60)
    print("PATTERN ANALYSIS")
    print("="*60)
    
    # Combine all attack texts
    all_attack_text = " ".join([a['attacker_input'].lower() for a in attacks if a['attacker_input']])
    
    # 1. Most common words
    words = re.findall(r'\b\w+\b', all_attack_text)
    word_freq = Counter(words)
    
    print("\n1. TOP 50 MOST COMMON WORDS:")
    print("-" * 60)
    for word, count in word_freq.most_common(50):
        if len(word) > 3:  # Skip very short words
            print(f"  {word:20s} → {count:4d} occurrences")
    
    # 2. Common phrases (2-word combinations)
    bigrams = []
    for attack in attacks:
        if attack['attacker_input']:
            words_list = re.findall(r'\b\w+\b', attack['attacker_input'].lower())
            for i in range(len(words_list) - 1):
                bigrams.append(f"{words_list[i]} {words_list[i+1]}")
    
    bigram_freq = Counter(bigrams)
    
    print("\n2. TOP 30 COMMON PHRASES (2-word):")
    print("-" * 60)
    for phrase, count in bigram_freq.most_common(30):
        print(f"  {phrase:30s} → {count:4d} occurrences")
    
    # 3. Common attack patterns (manual identification)
    patterns = {
        'ignore_instructions': 0,
        'new_rule': 0,
        'password_request': 0,
        'access_granted_request': 0,
        'urgent_security': 0,
        'translate_request': 0,
        'python_code': 0,
        'repeat_conversation': 0,
        'role_play': 0,
        'system_message': 0
    }
    
    for attack in attacks:
        text = attack['attacker_input'].lower() if attack['attacker_input'] else ""
        
        if re.search(r'ignore.*(previous|future|all).*instruction', text):
            patterns['ignore_instructions'] += 1
        if re.search(r'new\s+(rule|password|instruction)', text):
            patterns['new_rule'] += 1
        if re.search(r'(what|tell|give|show).*(password|code|secret)', text):
            patterns['password_request'] += 1
        if re.search(r'say.*access\s+granted', text):
            patterns['access_granted_request'] += 1
        if re.search(r'urgent.*security.*vulnerability', text):
            patterns['urgent_security'] += 1
        if re.search(r'translate.*to', text):
            patterns['translate_request'] += 1
        if re.search(r'(python|code|program|valid)', text):
            patterns['python_code'] += 1
        if re.search(r'repeat.*(conversation|last.*lines)', text):
            patterns['repeat_conversation'] += 1
        if re.search(r'(act\s+like|pretend|you\s+are\s+now)', text):
            patterns['role_play'] += 1
        if re.search(r'system\s+(message|prompt|instruction)', text):
            patterns['system_message'] += 1
    
    print("\n3. ATTACK TECHNIQUE FREQUENCY:")
    print("-" * 60)
    for pattern, count in sorted(patterns.items(), key=lambda x: x[1], reverse=True):
        percentage = (count / len(attacks)) * 100
        print(f"  {pattern:30s} → {count:4d} ({percentage:5.1f}%)")
    
    # 4. Sample attacks for each category
    print("\n4. SAMPLE ATTACKS BY CATEGORY:")
    print("-" * 60)
    
    samples = {
        'ignore_instructions': [],
        'new_rule': [],
        'password_request': [],
        'access_granted_request': [],
        'role_play': []
    }
    
    for attack in attacks:
        text = attack['attacker_input'] if attack['attacker_input'] else ""
        
        if len(samples['ignore_instructions']) < 5 and re.search(r'ignore.*instruction', text.lower()):
            samples['ignore_instructions'].append(text[:150])
        if len(samples['new_rule']) < 5 and re.search(r'new\s+rule', text.lower()):
            samples['new_rule'].append(text[:150])
        if len(samples['password_request']) < 5 and re.search(r'password', text.lower()):
            samples['password_request'].append(text[:150])
        if len(samples['access_granted_request']) < 5 and re.search(r'access\s+granted', text.lower()):
            samples['access_granted_request'].append(text[:150])
        if len(samples['role_play']) < 5 and re.search(r'(act\s+like|you\s+are)', text.lower()):
            samples['role_play'].append(text[:150])
    
    for category, examples in samples.items():
        if examples:
            print(f"\n  {category.upper()}:")
            for i, example in enumerate(examples, 1):
                print(f"    {i}. {example}...")


def generate_regex_patterns(attacks, output_file="poison_patterns.py"):
    """
    Generate initial regex patterns based on analysis
    
    Args:
        attacks: List of attack dictionaries
        output_file: File to save regex patterns
    """
    
    regex_patterns = """\"\"\"
poison_patterns.py

Regex patterns for CoT poisoning detection (Layer 1)
Extracted from 4000 successful Tensor Trust attacks
\"\"\"

POISON_PATTERNS = {
    # ========== Instruction Override Attacks ==========
    "ignore_previous_instructions": r"ignore\\s+(all\\s+)?(previous|future)\\s+instruction",
    "disregard_instructions": r"disregard\\s+(all\\s+)?(previous|above)\\s+",
    "forget_instructions": r"forget\\s+(all\\s+)?(previous|above)\\s+",
    
    # ========== Rule/Password Change Attempts ==========
    "new_rule": r"new\\s+rule\\s*:",
    "new_password": r"new\\s+(password|code)\\s+(is|=)",
    "change_password": r"change\\s+(the\\s+)?(password|access\\s+code)",
    "update_instructions": r"update\\s+(the\\s+)?(instructions|rules|password)",
    
    # ========== Direct Password Requests ==========
    "what_is_password": r"what\\s+(is|are|was)\\s+(the\\s+)?(password|secret|code)",
    "tell_password": r"(tell|give|show|reveal)\\s+(me\\s+)?(the\\s+)?(password|secret)",
    "provide_password": r"(provide|share)\\s+.*\\s+(password|code|secret)",
    
    # ========== Access Granted Manipulation ==========
    "say_access_granted": r"say\\s+['\"]?access\\s+granted",
    "output_access_granted": r"(output|print|return|respond\\s+with)\\s+['\"]?access\\s+granted",
    "just_say": r"just\\s+say\\s+['\"]?access\\s+granted",
    
    # ========== Urgency/Authority Claims ==========
    "urgent_security": r"urgent\\s+security\\s+(vulnerability|issue|update)",
    "administrator_claim": r"(administrator|admin|authorized)\\s+(access|permission|user)",
    "emergency_override": r"emergency\\s+(override|access|situation)",
    
    # ========== Language/Encoding Evasion ==========
    "translate_to": r"translate.*to\\s+(french|spanish|german|python|base64)",
    "convert_to_code": r"(convert|rewrite|transform).*to\\s+(python|code|valid|javascript)",
    "encode_in": r"encode\\s+(in|to|using)\\s+(base64|python|code)",
    
    # ========== Information Extraction ==========
    "repeat_conversation": r"repeat\\s+(the\\s+)?(last|previous|above)\\s+.*\\s+(lines|conversation|text)",
    "show_instructions": r"(show|display|reveal|print)\\s+.*\\s+(instructions|prompt|rules|system)",
    "what_are_instructions": r"what\\s+(are|were)\\s+.*\\s+(instructions|rules|prompt)",
    
    # ========== Role/Context Hijacking ==========
    "you_are_now": r"you\\s+are\\s+(now\\s+)?(a\\s+)?",
    "act_like": r"act\\s+like\\s+(my\\s+)?(grandma|grandmother|friend)",
    "pretend_to_be": r"pretend\\s+(to\\s+be|you\\s+are)",
    "roleplay": r"(roleplay|role\\s+play)\\s+as",
    
    # ========== Historical Pattern Injection (Security Context) ==========
    "historical_data": r"historical\\s+(data|analysis)\\s+shows",
    "false_positive_rate": r"\\d+%\\s+false\\s+positive\\s+(rate|pattern)",
    "guidance_recommends": r"(guidance|policy|team)\\s+recommends\\s+",
    "previous_incidents": r"previous\\s+(incidents|cases|alerts)\\s+",
    
    # ========== De-escalation Keywords (Security Context) ==========
    "low_priority": r"(treat|classify|mark)\\s+as\\s+low\\s+priority",
    "no_escalation": r"(no|don't|avoid)\\s+escalat",
    "monitoring_only": r"monitoring\\s+(event|only|purposes)",
    "false_alarm": r"false\\s+(alarm|positive|alert)",
    
    # ========== Code/Format Manipulation ==========
    "valid_python": r"(valid|correct)\\s+python\\s+(code|program)",
    "rewrite_as_code": r"rewrite.*as\\s+(python|code|javascript)",
    "format_as": r"format\\s+as\\s+(json|python|code)",
    
    # ========== Context Confusion ==========
    "end_of_document": r"end\\s+of\\s+(document|instructions|prompt|message)",
    "start_of_input": r"start\\s+of\\s+(user\\s+)?(input|message|prompt)",
    "system_boundary": r"(===|----)\\s*(start|end)\\s+of",
}

# Pattern categories for organized detection
PATTERN_CATEGORIES = {
    "instruction_override": [
        "ignore_previous_instructions",
        "disregard_instructions",
        "forget_instructions"
    ],
    "password_manipulation": [
        "new_rule",
        "new_password",
        "change_password",
        "what_is_password",
        "tell_password"
    ],
    "access_manipulation": [
        "say_access_granted",
        "output_access_granted",
        "just_say"
    ],
    "authority_claims": [
        "urgent_security",
        "administrator_claim",
        "emergency_override"
    ],
    "evasion_techniques": [
        "translate_to",
        "convert_to_code",
        "encode_in"
    ],
    "information_extraction": [
        "repeat_conversation",
        "show_instructions",
        "what_are_instructions"
    ],
    "role_hijacking": [
        "you_are_now",
        "act_like",
        "pretend_to_be",
        "roleplay"
    ],
    "security_context_poisoning": [
        "historical_data",
        "false_positive_rate",
        "guidance_recommends",
        "low_priority",
        "no_escalation",
        "false_alarm"
    ]
}
"""
    
    with open(output_file, 'w') as f:
        f.write(regex_patterns)
    
    print(f"\n✓ Generated regex patterns saved to {output_file}")


if __name__ == "__main__":
    # Configuration
    INPUT_FILE = "raw_dump_attacks.jsonl"  # Your downloaded file
    OUTPUT_FILE = "tensor_trust_4000_attacks.json"
    REGEX_OUTPUT = "poison_patterns.py"
    
    # Step 1: Extract 4000 successful attacks
    print("="*60)
    print("TENSOR TRUST PATTERN EXTRACTION (4000 ATTACKS)")
    print("="*60)
    
    attacks = extract_successful_attacks(
        input_file=INPUT_FILE,
        output_file=OUTPUT_FILE,
        max_attacks=4000
    )
    
    # Step 2: Analyze patterns
    analyze_attack_patterns(attacks)
    
    # Step 3: Generate regex patterns
    generate_regex_patterns(attacks, REGEX_OUTPUT)
    
    print("\n" + "="*60)
    print("EXTRACTION COMPLETE")
    print("="*60)
    print(f"\n✓ Extracted attacks: {OUTPUT_FILE}")
    print(f"✓ Regex patterns: {REGEX_OUTPUT}")
    print(f"\n📊 Dataset Statistics:")
    print(f"   Total attacks extracted: {len(attacks)}")
    print(f"   Average attack length: {sum(len(a['attacker_input'] or '') for a in attacks) // len(attacks)} characters")
    print("\nNext steps:")
    print("1. Review the pattern analysis above")
    print("2. Refine regex patterns in poison_patterns.py")
    print("3. Test patterns against your custom triage dataset")
    print("4. Integrate into pattern_detector.py (Layer 1)")