"""
Document Classifier for Document Processing Pipeline.
Classifies legal documents into types using ML and rule-based approaches.
"""

import sys
import os
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
import logging
import re
import json
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class ClassificationResult:
    """Document classification result."""
    document_id: str
    primary_type: str
    secondary_types: List[str] = field(default_factory=list)
    confidence: float = 1.0
    model: str = "rule_based"
    features: List[str] = field(default_factory=list)
    reasons: List[str] = field(default_factory=list)
    processing_time: float = 0.0
    errors: List[str] = field(default_factory=list)


@dataclass
class ClassifierConfig:
    """Classifier configuration."""
    model_type: str = "hybrid"  # rule_based, ml, hybrid
    ml_model_path: Optional[str] = None
    min_confidence: float = 0.6
    fallback_to_rules: bool = True
    multi_label: bool = True
    feature_extraction: bool = True
    language: str = "en"


class DocumentClassifier:
    """
    Document classifier for legal documents.
    Uses rule-based and ML approaches for classification.
    """
    
    def __init__(self, config: Optional[ClassifierConfig] = None):
        """
        Initialize Document Classifier.
        
        Args:
            config: Classifier configuration
        """
        self.config = config or ClassifierConfig()
        self.rules = self._load_classification_rules()
        self.ml_model = self._load_ml_model() if self.config.ml_model_path else None
        
        logger.info(f"Initialized Document Classifier with {self.config.model_type} model")
    
    def _load_classification_rules(self) -> Dict[str, Dict[str, Any]]:
        """Load classification rules."""
        return {
            "contract": {
                "keywords": [
                    "contract", "agreement", "license", "nda", "mou", "memorandum of understanding",
                    "party", "parties", "shall", "witnesseth", "whereas", "hereinafter",
                    "term", "termination", "indemnification", "confidentiality", "governing law"
                ],
                "filename_patterns": [r".*contract.*", r".*agreement.*", r".*license.*", r".*nda.*"],
                "confidence": 0.85,
                "priority": 1
            },
            "pleading": {
                "keywords": [
                    "motion", "brief", "pleading", "complaint", "answer", "reply",
                    "court", "case no", "docket", "plaintiff", "defendant",
                    "pursuant to", "respectfully", "prays", "relief"
                ],
                "filename_patterns": [r".*motion.*", r".*brief.*", r".*complaint.*", r".*pleading.*"],
                "confidence": 0.8,
                "priority": 2
            },
            "opinion": {
                "keywords": [
                    "opinion", "decision", "ruling", "judgment", "order",
                    "court", "justice", "judge", "held", "conclude", "affirm", "reverse",
                    "citation", "precedent", "statute", "regulation"
                ],
                "filename_patterns": [r".*opinion.*", r".*decision.*", r".*ruling.*", r".*order.*"],
                "confidence": 0.75,
                "priority": 3
            },
            "statute": {
                "keywords": [
                    "statute", "law", "act", "code", "regulation", "rule",
                    "section", "subsection", "paragraph", "usc", "cfr",
                    "enacted", "amended", "repealed", "effective date"
                ],
                "filename_patterns": [r".*statute.*", r".*law.*", r".*regulation.*", r".*cfr.*", r".*usc.*"],
                "confidence": 0.9,
                "priority": 4
            },
            "patent": {
                "keywords": [
                    "patent", "invention", "claims", "embodiment", "prior art",
                    "uspto", "application", "examination", "allowance",
                    "figure", "drawing", "specification"
                ],
                "filename_patterns": [r".*patent.*", r".*invention.*"],
                "confidence": 0.85,
                "priority": 5
            },
            "trademark": {
                "keywords": [
                    "trademark", "service mark", "brand", "logo",
                    "registration", "class", "goods", "services",
                    "tm", "®", "uspto"
                ],
                "filename_patterns": [r".*trademark.*", r".*brand.*"],
                "confidence": 0.8,
                "priority": 6
            },
            "correspondence": {
                "keywords": [
                    "dear", "sincerely", "regards", "email", "letter",
                    "to:", "from:", "subject:", "date:", "re:",
                    "please find", "attached", "enclosed"
                ],
                "filename_patterns": [r".*letter.*", r".*email.*", r".*correspondence.*"],
                "confidence": 0.7,
                "priority": 7
            },
            "report": {
                "keywords": [
                    "report", "analysis", "findings", "conclusion", "recommendation",
                    "summary", "introduction", "background", "methodology",
                    "table", "figure", "appendix"
                ],
                "filename_patterns": [r".*report.*", r".*analysis.*"],
                "confidence": 0.75,
                "priority": 8
            }
        }
    
    def _load_ml_model(self):
        """Load ML model for classification."""
        # This would load a pre-trained model
        # For now, return None (mock)
        logger.info(f"ML model loading not implemented, using rule-based fallback")
        return None
    
    def classify_document(self, document_id: str, text: str, 
                         filename: str = "", metadata: Optional[Dict[str, Any]] = None) -> ClassificationResult:
        """
        Classify a document.
        
        Args:
            document_id: Document identifier
            text: Document text content
            filename: Original filename
            metadata: Additional metadata
            
        Returns:
            Classification result
        """
        start_time = datetime.now()
        
        try:
            # Extract features
            features = self._extract_features(text, filename, metadata)
            
            # Classify based on model type
            if self.config.model_type == "ml" and self.ml_model:
                result = self._classify_with_ml(text, features)
            elif self.config.model_type == "rule_based":
                result = self._classify_with_rules(text, filename, features)
            else:  # hybrid
                result = self._classify_hybrid(text, filename, features)
            
            # Set document ID and processing time
            result.document_id = document_id
            result.processing_time = (datetime.now() - start_time).total_seconds()
            result.features = features
            
            # Validate confidence
            if result.confidence < self.config.min_confidence:
                result.errors.append(f"Low classification confidence: {result.confidence}")
                
                if self.config.fallback_to_rules and self.config.model_type != "rule_based":
                    # Fall back to rule-based classification
                    logger.warning(f"Falling back to rule-based classification for {document_id}")
                    fallback_result = self._classify_with_rules(text, filename, features)
                    result.primary_type = fallback_result.primary_type
                    result.secondary_types = fallback_result.secondary_types
                    result.confidence = fallback_result.confidence
                    result.reasons = fallback_result.reasons
                    result.model = "rule_based_fallback"
            
            logger.info(f"Classified {document_id} as {result.primary_type} with confidence {result.confidence:.3f}")
            return result
            
        except Exception as e:
            logger.error(f"Classification error for {document_id}: {str(e)}")
            
            return ClassificationResult(
                document_id=document_id,
                primary_type="unknown",
                confidence=0.0,
                processing_time=(datetime.now() - start_time).total_seconds(),
                errors=[str(e)],
                model="error"
            )
    
    def _extract_features(self, text: str, filename: str, metadata: Optional[Dict[str, Any]]) -> List[str]:
        """Extract features from document."""
        if not self.config.feature_extraction:
            return []
        
        features = []
        text_lower = text.lower()
        filename_lower = filename.lower()
        
        # Text-based features
        word_count = len(text.split())
        char_count = len(text)
        
        features.append(f"word_count_{self._bucket_count(word_count)}")
        features.append(f"char_count_{self._bucket_count(char_count)}")
        
        # Check for legal terminology
        legal_terms = ["shall", "whereas", "witnesseth", "hereinafter", "party", "parties"]
        for term in legal_terms:
            if term in text_lower:
                features.append(f"contains_{term}")
        
        # Check for document structure markers
        structure_markers = ["section", "subsection", "paragraph", "article", "clause"]
        for marker in structure_markers:
            if marker in text_lower:
                features.append(f"contains_{marker}")
        
        # Check for monetary references
        if re.search(r'\$\d+(?:,\d{3})*(?:\.\d{2})?', text):
            features.append("contains_money")
        
        # Check for date references
        date_patterns = [
            r'\d{1,2}/\d{1,2}/\d{2,4}',
            r'\d{4}-\d{2}-\d{2}',
            r'(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s+\d{4}'
        ]
        for pattern in date_patterns:
            if re.search(pattern, text):
                features.append("contains_dates")
                break
        
        # Filename-based features
        for doc_type, rules in self.rules.items():
            for pattern in rules["filename_patterns"]:
                if re.match(pattern, filename_lower, re.IGNORECASE):
                    features.append(f"filename_suggests_{doc_type}")
                    break
        
        # Metadata-based features (if available)
        if metadata:
            if metadata.get("author"):
                features.append("has_author")
            if metadata.get("title"):
                features.append("has_title")
            if metadata.get("page_count", 0) > 1:
                features.append("multi_page")
        
        return features
    
    def _classify_with_rules(self, text: str, filename: str, features: List[str]) -> ClassificationResult:
        """Classify document using rule-based approach."""
        text_lower = text.lower()
        filename_lower = filename.lower()
        
        scores = {}
        reasons = {}
        
        # Score each document type
        for doc_type, rules in self.rules.items():
            score = 0.0
            type_reasons = []
            
            # Keyword matching
            keyword_matches = 0
            for keyword in rules["keywords"]:
                if keyword in text_lower:
                    keyword_matches += 1
            
            if keyword_matches > 0:
                score += (keyword_matches / len(rules["keywords"])) * 0.6
                type_reasons.append(f"Matched {keyword_matches} keywords")
            
            # Filename pattern matching
            for pattern in rules["filename_patterns"]:
                if re.match(pattern, filename_lower, re.IGNORECASE):
                    score += 0.3
                    type_reasons.append("Filename matches pattern")
                    break
            
            # Feature matching
            feature_key = f"filename_suggests_{doc_type}"
            if feature_key in features:
                score += 0.1
                type_reasons.append("Filename feature suggests type")
            
            # Apply base confidence
            score *= rules["confidence"]
            
            if score > 0:
                scores[doc_type] = score
                reasons[doc_type] = type_reasons
        
        # Determine primary and secondary types
        if not scores:
            return ClassificationResult(
                document_id="",
                primary_type="unknown",
                confidence=0.0,
                reasons=["No rules matched"],
                model="rule_based"
            )
        
        # Sort by score
        sorted_types = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        
        primary_type, primary_score = sorted_types[0]
        primary_reasons = reasons.get(primary_type, [])
        
        # Get secondary types (if multi-label enabled)
        secondary_types = []
        if self.config.multi_label:
            for doc_type, score in sorted_types[1:]:
                if score >= self.config.min_confidence * 0.7:  # Lower threshold for secondary
                    secondary_types.append(doc_type)
        
        return ClassificationResult(
            document_id="",
            primary_type=primary_type,
            secondary_types=secondary_types,
            confidence=primary_score,
            reasons=primary_reasons,
            model="rule_based"
        )
    
    def _classify_with_ml(self, text: str, features: List[str]) -> ClassificationResult:
        """Classify document using ML model."""
        # Mock ML classification
        # In production, would use actual ML model
        
        # For now, use rule-based as fallback
        logger.warning("ML classification not implemented, using rule-based")
        return self._classify_with_rules(text, "", features)
    
    def _classify_hybrid(self, text: str, filename: str, features: List[str]) -> ClassificationResult:
        """Classify document using hybrid approach."""
        # Get rule-based classification
        rule_result = self._classify_with_rules(text, filename, features)
        
        # If ML model is available, combine results
        if self.ml_model:
            # Mock ML result
            ml_result = self._classify_with_ml(text, features)
            
            # Combine confidences (simple average for now)
            combined_confidence = (rule_result.confidence + ml_result.confidence) / 2
            
            # Use rule-based type if confidence is high enough
            if rule_result.confidence >= self.config.min_confidence:
                primary_type = rule_result.primary_type
                reasons = rule_result.reasons + [f"ML confidence: {ml_result.confidence:.3f}"]
            else:
                primary_type = ml_result.primary_type
                reasons = ml_result.reasons + [f"Rule confidence: {rule_result.confidence:.3f}"]
            
            # Combine secondary types
            secondary_types = list(set(rule_result.secondary_types + ml_result.secondary_types))
            
            return ClassificationResult(
                document_id="",
                primary_type=primary_type,
                secondary_types=secondary_types,
                confidence=combined_confidence,
                reasons=reasons,
                model="hybrid"
            )
        else:
            # No ML model, just use rule-based
            rule_result.model = "hybrid_rule_only"
            return rule_result
    
    def _bucket_count(self, count: int) -> str:
        """Bucket a count into categories."""
        if count < 100:
            return "very_short"
        elif count < 500:
            return "short"
        elif count < 2000:
            return "medium"
        elif count < 10000:
            return "long"
        else:
            return "very_long"
    
    def get_classifier_info(self) -> Dict[str, Any]:
        """Get information about the classifier."""
        return {
            "model_type": self.config.model_type,
            "min_confidence": self.config.min_confidence,
            "fallback_to_rules": self.config.fallback_to_rules,
            "multi_label": self.config.multi_label,
            "available_types": list(self.rules.keys()),
            "ml_model_loaded": self.ml_model is not None
        }


def test_document_classifier():
    """Test function for Document Classifier."""
    print("Testing Document Classifier...")
    
    # Create classifier
    config = ClassifierConfig(
        model_type="hybrid",
        min_confidence=0.6,
        fallback_to_rules=True,
        multi_label=True
    )
    
    classifier = DocumentClassifier(config)
    
    # Get classifier info
    info = classifier.get_classifier_info()
    print(f"Classifier info: {info}")
    
    # Test 1: Contract document
    print("\n1. Testing contract classification...")
    
    contract_text = """CONTRACT AGREEMENT
    
This Agreement is made between Party A and Party B.
    
1. TERM: This Agreement shall commence on January 1, 2024.
2. PAYMENT: Party B shall pay Party A the sum of $50,000.
3. CONFIDENTIALITY: The parties agree to maintain confidentiality.
4. GOVERNING LAW: This Agreement shall be governed by California law."""
    
    result = classifier.classify_document(
        document_id="test_contract_001",
        text=contract_text,
        filename="Employment_Agreement_2024.docx"
    )
    
    print(f"Contract classification:")
    print(f"  Primary type: {result.primary_type}")
    print(f"  Confidence: {result.confidence:.3f}")
    print(f"  Secondary types: {result.secondary_types}")
    print(f"  Reasons: {result.reasons[:3]}")  # Show first 3 reasons
    
    # Test 2: Legal pleading
    print("\n2. Testing pleading classification...")
    
    pleading_text = """MOTION TO DISMISS
    
Case No: 2024-CV-00123
Court: Superior Court of California
    
COMES NOW Defendant, ABC Corporation, and moves this Court to dismiss...
    
WHEREFORE, Defendant prays for dismissal with prejudice."""
    
    result = classifier.classify_document(
        document_id="test_pleading_001",
        text=pleading_text,
        filename="Motion_to_Dismiss.pdf"
    )
    
    print(f"Pleading classification:")
    print(f"  Primary type: {result.primary_type}")
    print(f"  Confidence: {result.confidence:.3f}")
    print(f"  Secondary types: {result.secondary_types}")
    
    # Test 3: Statute/regulation
    print("\n3. Testing statute classification...")
    
    statute_text = """UNITED STATES CODE
TITLE 42 - THE PUBLIC HEALTH AND WELFARE
CHAPTER 21 - CIVIL RIGHTS
    
§ 2000e. Definitions
    
For the purposes of this subchapter—
(a) The term "person" includes one or more individuals...
(b) The term "employer" means a person engaged in an industry..."""
    
    result = classifier.classify_document(
        document_id="test_statute_001",
        text=statute_text,
        filename="42_USC_2000e.txt"
    )
    
    print(f"Statute classification:")
    print(f"  Primary type: {result.primary_type}")
    print(f"  Confidence: {result.confidence:.3f}")
    print(f"  Secondary types: {result.secondary_types}")
    
    # Test 4: Unknown document
    print("\n4. Testing unknown document classification...")
    
    unknown_text = """Meeting Notes
    
Attendees: John, Sarah, Mike
Date: March 15, 2024
    
Discussion points:
- Project timeline
- Budget review
- Next steps"""
    
    result = classifier.classify_document(
        document_id="test_unknown_001",
        text=unknown_text,
        filename="Meeting_Notes.txt"
    )
    
    print(f"Unknown classification:")
    print(f"  Primary type: {result.primary_type}")
    print(f"  Confidence: {result.confidence:.3f}")
    
    print("\nDocument Classifier test completed successfully!")


if __name__ == "__main__":
    test_document_classifier()