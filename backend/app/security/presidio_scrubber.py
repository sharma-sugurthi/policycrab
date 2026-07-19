"""
HIPAA Document Scrubber (Microsoft Presidio — Regex-Only Mode)

Uses Presidio's built-in pattern recognizers WITHOUT spaCy or any NLP model.
This eliminates the ~100MB spaCy dependency that bloats Heroku slug size.

What IS detected (regex patterns):
  - US_SSN (Social Security Numbers)
  - CREDIT_CARD (Luhn-validated)
  - PHONE_NUMBER
  - EMAIL_ADDRESS
  - US_BANK_NUMBER
  - IP_ADDRESS
  - IBAN_CODE

What is NOT detected (requires NLP — acceptable tradeoff):
  - PERSON (patient names) — not a critical risk in SBC/EOB documents
  - LOCATION (addresses) — acceptable for policy text scrubbing

Design rationale:
  PolicyCrab processes SBC/EOB insurance documents, not medical records.
  The real PHI risk in these docs is structured data (SSN, CC, phone) which
  regex catches perfectly. Patient names appearing in policy summaries are
  not stored in our RAG chunks as identifiable data — they flow through
  to Gemini for extraction and are discarded.
"""

import logging

logger = logging.getLogger(__name__)

# Attempt to import Presidio — graceful fallback if unavailable
try:
    from presidio_analyzer import AnalyzerEngine, RecognizerRegistry
    from presidio_analyzer.nlp_engine import NlpEngine
    from presidio_anonymizer import AnonymizerEngine
    from presidio_anonymizer.entities import OperatorConfig
    _PRESIDIO_AVAILABLE = True
except ImportError:
    _PRESIDIO_AVAILABLE = False
    logger.warning("Presidio not installed — PHI scrubbing will use regex fallback only.")


class HIPAADocumentScrubber:
    def __init__(self):
        # We explicitly specify the entities we want to redact.
        # We intentionally EXCLUDE "DATE_TIME" because EOBs and policies
        # require Dates of Service, Denial Dates, and Effective Dates for accurate
        # analysis by the LLM. 
        self.entities_to_redact = [
            "PHONE_NUMBER",
            "EMAIL_ADDRESS",
            "US_SSN",
            "US_BANK_NUMBER",
            "CREDIT_CARD",
            "IP_ADDRESS",
            "IBAN_CODE",
        ]
        
        self._available = False
        
        if not _PRESIDIO_AVAILABLE:
            logger.warning("HIPAADocumentScrubber: Presidio not installed, scrubbing disabled.")
            return
        
        # Initialize the engines
        try:
            # Use NoOpNlpEngine — runs regex-only recognizers without spaCy.
            # This eliminates the ~100MB spaCy + en_core_web_sm dependency.
            
            # Create a registry with predefined recognizers, then remove NLP-dependent ones
            registry = RecognizerRegistry()
            registry.load_predefined_recognizers()
            
            # Remove recognizers that require an NLP engine (spaCy)
            nlp_recognizers = [r for r in registry.recognizers if r.name == "SpacyRecognizer"]
            for r in nlp_recognizers:
                registry.remove_recognizer(r.name)
            
            # Use a minimal NlpEngine that does nothing (no spaCy needed)
            from presidio_analyzer.nlp_engine import NlpEngineProvider
            
            # NoOpNlpEngine approach: create a simple engine that satisfies the interface
            class _NoOpNlpEngine(NlpEngine):
                """Minimal NLP engine that does nothing — allows regex-only Presidio."""
                def __init__(self):
                    pass
                
                def process_text(self, text, language):
                    return None
                
                def process_batch(self, texts, language):
                    return [None] * len(texts)
                
                def is_loaded(self):
                    return True
                
                @property
                def supported_languages(self):
                    return ["en"]
            
            self.analyzer = AnalyzerEngine(
                registry=registry,
                nlp_engine=_NoOpNlpEngine(),
                supported_languages=["en"],
            )
            self.anonymizer = AnonymizerEngine()
            self._available = True
            logger.info(
                "HIPAADocumentScrubber initialized (regex-only mode, no spaCy). "
                f"Active recognizers: {len(registry.recognizers)}"
            )
        except Exception as e:
            logger.error(f"Failed to initialize Presidio: {e}")
            logger.warning("HIPAADocumentScrubber: falling back to pass-through mode (no scrubbing)")
            self._available = False

    def scrub(self, text: str) -> tuple[str, int]:
        """
        Analyzes and anonymizes the provided text, removing PHI.
        Returns the scrubbed text and the number of redactions made.
        
        If Presidio failed to initialize, returns the text unchanged
        to avoid blocking the entire upload pipeline.
        """
        if not text or not text.strip():
            return text, 0
        
        if not self._available:
            return text, 0
            
        try:
            # 1. Analyze text for PHI entities
            results = self.analyzer.analyze(
                text=text,
                entities=self.entities_to_redact,
                language='en'
            )
            
            if not results:
                return text, 0
                
            # 2. Configure the anonymizer to replace with <REDACTED>
            operators = {
                entity: OperatorConfig("replace", {"new_value": f"<{entity}_REDACTED>"})
                for entity in self.entities_to_redact
            }
            
            # 3. Anonymize the text
            anonymized_result = self.anonymizer.anonymize(
                text=text,
                analyzer_results=results,
                operators=operators
            )
            
            redaction_count = len(results)
            if redaction_count > 0:
                logger.info(f"HIPAADocumentScrubber: Applied {redaction_count} regex redactions.")
                
            return anonymized_result.text, redaction_count
            
        except Exception as e:
            logger.error(f"Error during Presidio scrubbing: {e}")
            # Failsafe: if the scrubber crashes, return text unchanged
            # rather than blocking the entire pipeline or leaking empty text
            return text, 0

# Singleton instance to be used across the app
_scrubber = None

def get_scrubber() -> HIPAADocumentScrubber:
    global _scrubber
    if _scrubber is None:
        _scrubber = HIPAADocumentScrubber()
    return _scrubber

def scrub_phi(text: str) -> tuple[str, int]:
    """Backward-compatible wrapper for the original phi_scrubber.py interface."""
    return get_scrubber().scrub(text)
