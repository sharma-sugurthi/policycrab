"""
HIPAA Document Scrubber (Microsoft Presidio)

Replaces the basic regex scrubber with an Enterprise-grade NLP de-identification
pipeline. Uses the open-source Presidio Analyzer (with spaCy `en_core_web_sm`)
and Presidio Anonymizer to redact PHI from extracted markdown BEFORE it is
sent to the LLM.

Redacts:
- PERSON (Patient, Provider names)
- LOCATION (Addresses)
- PHONE_NUMBER
- EMAIL_ADDRESS
- MEDICAL_LICENSE
- SSN
- DATE_TIME (DOBs, DOS) - We actually need DOS for claims, but we will configure
  it to redact explicit DOB patterns while keeping service dates intact if possible,
  or just let Presidio redact dates and the LLM can infer from context. Wait,
  claims require dates of service. We will disable DATE_TIME redaction because
  insurance documents rely heavily on Dates of Service and Denial Dates.
"""

import logging
from presidio_analyzer import AnalyzerEngine
from presidio_analyzer.nlp_engine import NlpEngineProvider
from presidio_anonymizer import AnonymizerEngine
from presidio_anonymizer.entities import OperatorConfig

logger = logging.getLogger(__name__)

class HIPAADocumentScrubber:
    def __init__(self):
        # We explicitly specify the entities we want to redact.
        # We intentionally EXCLUDE "DATE_TIME" because EOBs and policies
        # require Dates of Service, Denial Dates, and Effective Dates for accurate
        # analysis by the LLM. 
        self.entities_to_redact = [
            "PERSON",
            "LOCATION",
            "PHONE_NUMBER",
            "EMAIL_ADDRESS",
            "MEDICAL_LICENSE",
            "US_SSN",
            "US_BANK_NUMBER",
            "CREDIT_CARD"
        ]
        
        # Initialize the engines
        try:
            # Use Presidio's slim SpaCy pipeline so we avoid the default large-model download.
            nlp_provider = NlpEngineProvider(
                nlp_configuration={
                    "nlp_engine_name": "slim",
                    "models": [{"lang_code": "en", "model_name": "en_core_web_sm"}],
                }
            )
            self.analyzer = AnalyzerEngine(
                nlp_engine=nlp_provider.create_engine(),
                supported_languages=["en"],
            )
            self.anonymizer = AnonymizerEngine()
            logger.info("HIPAADocumentScrubber initialized with Microsoft Presidio.")
        except Exception as e:
            logger.error(f"Failed to initialize Presidio: {e}")
            raise

    def scrub(self, text: str) -> tuple[str, int]:
        """
        Analyzes and anonymizes the provided text, removing PHI.
        Returns the scrubbed text and the number of redactions made.
        """
        if not text or not text.strip():
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
                logger.info(f"HIPAADocumentScrubber: Applied {redaction_count} NLP redactions.")
                
            return anonymized_result.text, redaction_count
            
        except Exception as e:
            logger.error(f"Error during Presidio scrubbing: {e}")
            # Failsafe: if the scrubber crashes, we return empty string to prevent PHI leak
            return "", 0

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
