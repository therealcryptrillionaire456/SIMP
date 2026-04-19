"""
Document Processing Pipeline Package.
"""

from document_processing.document_processor import (
    DocumentProcessor, ProcessingResult,
    DocumentFormat, DocumentType, ProcessingStatus,
    OCRQuality, RiskLevel
)

from document_processing.ocr_engine import (
    OCREngine, OCRResult, OCRConfig
)

from document_processing.document_classifier import (
    DocumentClassifier, ClassificationResult, ClassifierConfig
)

from document_processing.entity_extractor import (
    EntityExtractor, ExtractionResult, ExtractorConfig, Entity
)

__version__ = "1.0.0"
__author__ = "Pentagram Legal Department"
__description__ = "Document Processing Pipeline for legal document ingestion, OCR, classification, and analysis"

__all__ = [
    # Main processor
    "DocumentProcessor",
    "ProcessingResult",
    
    # Enums
    "DocumentFormat",
    "DocumentType", 
    "ProcessingStatus",
    "OCRQuality",
    "RiskLevel",
    
    # OCR engine
    "OCREngine",
    "OCRResult",
    "OCRConfig",
    
    # Document classifier
    "DocumentClassifier",
    "ClassificationResult",
    "ClassifierConfig",
    
    # Entity extractor
    "EntityExtractor",
    "ExtractionResult",
    "ExtractorConfig",
    "Entity"
]