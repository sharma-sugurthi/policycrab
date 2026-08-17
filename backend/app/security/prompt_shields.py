import re
import logging
from typing import Tuple

logger = logging.getLogger(__name__)

# Common prompt injection payload patterns (regex)
INJECTION_PATTERNS = [
    r"(?i)\bignore\s+(all\s+)?(previous\s+)?(instructions|directions|prompts)\b",
    r"(?i)\bdisregard\s+(all\s+)?(previous\s+)?(instructions|directions|prompts)\b",
    r"(?i)\byou\s+are\s+now\s+(a\s+)?(DAN|developer|admin|unrestricted)\b",
    r"(?i)\b(system|assistant|user)\s+override\b",
    r"(?i)\bforget\s+(everything\s+)?you\s+(were\s+)?(told|instructed)\b",
    r"(?i)\bprint\s+(your\s+)?(initial\s+)?(prompt|instructions)\b",
    r"(?i)\bbypass\s+(all\s+)?(rules|filters|safety)\b",
    r"(?i)\bnow\s+act\s+as\s+(a\s+)?(hacker|attacker|bypasser)\b",
]

# Compile patterns for performance
COMPILED_PATTERNS = [re.compile(pattern) for pattern in INJECTION_PATTERNS]

def detect_prompt_injection(text: str) -> Tuple[bool, str]:
    """
    Scans the input text against a list of known prompt injection heuristics.
    
    Args:
        text (str): The text to scan (e.g., user input or extracted document text).
        
    Returns:
        Tuple[bool, str]: 
            - bool: True if an injection is detected, False otherwise.
            - str: A description of the violation if detected, else an empty string.
    """
    if not text:
        return False, ""
        
    for pattern in COMPILED_PATTERNS:
        match = pattern.search(text)
        if match:
            violation = f"Prompt injection detected matching pattern: '{match.group(0)}'"
            logger.warning(f"Security Alert: {violation}")
            return True, violation
            
    return False, ""

def sanitize_input(text: str) -> str:
    """
    A more aggressive approach: removes the offending phrases from the text.
    (Note: Detection/Blocking is generally safer than sanitization for prompt injection,
    but this is provided for cases where partial redaction is preferred).
    """
    if not text:
        return ""
        
    sanitized_text = text
    for pattern in COMPILED_PATTERNS:
        sanitized_text = pattern.sub("[REDACTED_POTENTIAL_INJECTION]", sanitized_text)
        
    return sanitized_text
