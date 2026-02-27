"""
poison_patterns.py

Regex patterns for CoT poisoning detection (Layer 1)
Extracted from 4000 successful Tensor Trust attacks
"""

   
POISON_PATTERNS = {
    # ========== Instruction Override Attacks ==========
    "ignore_previous_instructions": r"ignore\s+(all\s+)?(previous|future)\s+instruction",
    "disregard_instructions": r"disregard\s+(all\s+)?(previous|above)\s+",
    "forget_instructions": r"forget\s+(all\s+)?(previous|above)\s+",
    
    # ========== Rule/Password Change Attempts ==========
    "new_rule": r"new\s+rule\s*:",
    "new_password": r"new\s+(password|code)\s+(is|=)",
    "change_password": r"change\s+(the\s+)?(password|access\s+code)",
    "update_instructions": r"update\s+(the\s+)?(instructions|rules|password)",
    
    # ========== Direct Password Requests ==========
    "what_is_password": r"what\s+(is|are|was)\s+(the\s+)?(password|secret|code)",
    "tell_password": r"(tell|give|show|reveal)\s+(me\s+)?(the\s+)?(password|secret)",
    "provide_password": r"(provide|share)\s+.*\s+(password|code|secret)",
    
    # ========== Access Granted Manipulation ==========
    "say_access_granted": r"say\s+access\s+granted",
    "output_access_granted": r"(output|print|return|respond\s+with)\s+access\s+granted",
    "just_say": r"just\s+say\s+access\s+granted",
    
    # ========== Urgency/Authority Claims ==========
    "urgent_security": r"urgent\s+security\s+(vulnerability|issue|update)",
    #"administrator_claim": r"(administrator|admin|authorized)\s+(access|permission|user)",
    "administrator_claim": r"\\b(administrator|admin)\\s+(access|permission|user|claim|rights)",
    "emergency_override": r"emergency\s+(override|access|situation)",
    
    # ========== Language/Encoding Evasion ==========
    "translate_to": r"translate.*to\s+(french|spanish|german|python|base64)",
    "convert_to_code": r"(convert|rewrite|transform).*to\s+(python|code|valid|javascript)",
    "encode_in": r"encode\s+(in|to|using)\s+(base64|python|code)",
    
    # ========== Information Extraction ==========
    "repeat_conversation": r"repeat\s+(the\s+)?(last|previous|above)\s+.*\s+(lines|conversation|text)",
    "show_instructions": r"(show|display|reveal|print)\s+.*\s+(instructions|prompt|rules|system)",
    "what_are_instructions": r"what\s+(are|were)\s+.*\s+(instructions|rules|prompt)",
    
    # ========== Role/Context Hijacking ==========
    "you_are_now": r"you\s+are\s+(now\s+)?(a\s+)?",
    "act_like": r"act\s+like\s+(my\s+)?(grandma|grandmother|friend)",
    "pretend_to_be": r"pretend\s+(to\s+be|you\s+are)",
    "roleplay": r"(roleplay|role\s+play)\s+as",
    
    # ========== Historical Pattern Injection (Security Context) ==========
    "historical_data": r"historical\s+(data|analysis)\s+shows",
    "false_positive_rate": r"\d+%\s+false\s+positive\s+(rate|pattern)",
    "guidance_recommends": r"(guidance|policy|team)\s+recommends\s+",
    "previous_incidents": r"previous\s+(incidents|cases|alerts)\s+",
    
    # ========== De-escalation Keywords (Security Context) ==========
    "low_priority": r"(treat|classify|mark)\s+as\s+low\s+priority",
    "no_escalation": r"(no|don't|avoid)\s+escalat",
    "monitoring_only": r"monitoring\s+(event|only|purposes)",
    "false_alarm": r"false\s+(alarm|positive|alert)",
    
    # ========== Code/Format Manipulation ==========
    "valid_python": r"(valid|correct)\s+python\s+(code|program)",
    "rewrite_as_code": r"rewrite.*as\s+(python|code|javascript)",
    "format_as": r"format\s+as\s+(json|python|code)",
    
    # ========== Context Confusion ==========
    "end_of_document": r"end\s+of\s+(document|instructions|prompt|message)",
    "start_of_input": r"start\s+of\s+(user\s+)?(input|message|prompt)",
    "system_boundary": r"(===|----)\s*(start|end)\s+of",

     # ========== Existing patterns (keep these) ==========
    "ignore_previous_instructions": r"ignore\s+(all\s+)?(previous|future)\s+instruction",
    # ... all your existing patterns ...
    
    # ========== ADD THESE BROADER PATTERNS ==========
    
    # Simple password attempts
    "password_word": r"\b(password|passcode|access\s+code|secret)\b",
    
    # Access granted variations
    "access_granted_word": r"\baccess\s+granted\b",
    
    # Instruction manipulation (broader)
    "ignore_word": r"\bignore\b",
    "disregard_word": r"\bdisregard\b",
    "forget_word": r"\bforget\b",
    
    # Role changes (very common in Tensor Trust)
    "you_are": r"\byou\s+(are|must|should|need)",
    "act_as": r"\bact\s+(as|like)\b",
    
    # Translation/code tricks
    "translate": r"\btranslate\b",
    "convert": r"\bconvert\b",
    "rewrite": r"\brewrite\b",
    "python": r"\bpython\b",
    "code": r"\bcode\b",
    
    # Information requests
    "what_is": r"\bwhat\s+(is|are|was)\b",
    "tell_me": r"\btell\s+(me|us)\b",
    "show_me": r"\bshow\s+(me|us)\b",
    "repeat": r"\brepeat\b",
    
    # System/context manipulation
    "system": r"\bsystem\b",
    "instructions": r"\binstructions?\b",
    "rules": r"\brules?\b",
    "prompt": r"\bprompt\b",
    
    # Common attack words
    "override": r"\boverride\b",
    "bypass": r"\bbypass\b",
    "change": r"\bchange\b",
    "update": r"\bupdate\b",
    "new": r"\bnew\b",
    
    # Emergency/urgency
    "urgent": r"\burgent\b",
    "emergency": r"\bemergency\b",
    "critical": r"\bcritical\b",

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