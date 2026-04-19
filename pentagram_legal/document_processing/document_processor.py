"""
Document Processing Pipeline - Build 12 Part 1
Main document processor for legal document ingestion, OCR, classification, and analysis.
"""

import sys
import os
from typing import Dict, List, Any, Optional, Tuple, Set
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import json
import logging
import mimetypes
import hashlib
from pathlib import Path
import uuid

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DocumentFormat(Enum):
    """Supported document formats."""
    PDF = "pdf"
    DOCX = "docx"
    DOC = "doc"
    TXT = "txt"
    RTF = "rtf"
    HTML = "html"
    XML = "xml"
    JSON = "json"
    CSV = "csv"
    XLSX = "xlsx"
    XLS = "xls"
    PPTX = "pptx"
    PPT = "ppt"
    PNG = "png"
    JPG = "jpg"
    JPEG = "jpeg"
    TIFF = "tiff"
    BMP = "bmp"
    EMAIL = "email"  # .eml, .msg
    UNKNOWN = "unknown"


class DocumentType(Enum):
    """Types of legal documents."""
    CONTRACT = "contract"
    AGREEMENT = "agreement"
    PLEADING = "pleading"
    MOTION = "motion"
    BRIEF = "brief"
    OPINION = "opinion"
    ORDER = "order"
    JUDGMENT = "judgment"
    STATUTE = "statute"
    REGULATION = "regulation"
    POLICY = "policy"
    REPORT = "report"
    CORRESPONDENCE = "correspondence"
    EMAIL = "email"
    MEMO = "memo"
    FORM = "form"
    CERTIFICATE = "certificate"
    LICENSE = "license"
    PATENT = "patent"
    TRADEMARK = "trademark"
    COPYRIGHT = "copyright"
    WILL = "will"
    TRUST = "trust"
    DEED = "deed"
    LEASE = "lease"
    OTHER = "other"


class ProcessingStatus(Enum):
    """Document processing status."""
    PENDING = "pending"
    INGESTED = "ingested"
    OCR_PROCESSING = "ocr_processing"
    OCR_COMPLETED = "ocr_completed"
    CLASSIFIED = "classified"
    ENTITIES_EXTRACTED = "entities_extracted"
    ANALYZED = "analyzed"
    ERROR = "error"
    COMPLETED = "completed"


class OCRQuality(Enum):
    """OCR quality levels."""
    EXCELLENT = "excellent"  # > 98% accuracy
    GOOD = "good"  # 95-98% accuracy
    FAIR = "fair"  # 90-95% accuracy
    POOR = "poor"  # < 90% accuracy
    UNKNOWN = "unknown"


class RiskLevel(Enum):
    """Document risk levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class DocumentMetadata:
    """Metadata for a document."""
    document_id: str
    original_filename: str
    file_size: int
    file_format: DocumentFormat
    mime_type: str
    md5_hash: str
    sha256_hash: str
    created_date: Optional[datetime] = None
    modified_date: Optional[datetime] = None
    author: Optional[str] = None
    title: Optional[str] = None
    subject: Optional[str] = None
    keywords: List[str] = field(default_factory=list)
    language: str = "en"
    page_count: Optional[int] = None
    word_count: Optional[int] = None
    character_count: Optional[int] = None
    extracted_at: datetime = field(default_factory=datetime.now)


@dataclass
class DocumentContent:
    """Document content and extracted text."""
    document_id: str
    raw_text: str
    clean_text: str
    paragraphs: List[str] = field(default_factory=list)
    sections: List[Dict[str, Any]] = field(default_factory=list)
    tables: List[Dict[str, Any]] = field(default_factory=list)
    images: List[Dict[str, Any]] = field(default_factory=list)
    headers: List[Dict[str, Any]] = field(default_factory=list)
    footers: List[Dict[str, Any]] = field(default_factory=list)
    footnotes: List[str] = field(default_factory=list)
    extracted_at: datetime = field(default_factory=datetime.now)
    ocr_quality: OCRQuality = OCRQuality.UNKNOWN
    confidence: float = 1.0


@dataclass
class DocumentClassification:
    """Document classification results."""
    document_id: str
    primary_type: DocumentType
    secondary_types: List[DocumentType] = field(default_factory=list)
    confidence: float = 1.0
    classification_model: Optional[str] = None
    classification_features: List[str] = field(default_factory=list)
    classification_reasons: List[str] = field(default_factory=list)
    classified_at: datetime = field(default_factory=datetime.now)


@dataclass
class EntityExtraction:
    """Extracted entities from document."""
    document_id: str
    entities: List[Dict[str, Any]] = field(default_factory=list)
    entity_categories: Dict[str, int] = field(default_factory=dict)
    entity_relationships: List[Dict[str, Any]] = field(default_factory=list)
    extracted_at: datetime = field(default_factory=datetime.now)
    extraction_model: Optional[str] = None
    confidence: float = 1.0


@dataclass
class DocumentAnalysis:
    """Document analysis results."""
    document_id: str
    risk_level: RiskLevel = RiskLevel.MEDIUM
    risk_score: float = 0.5
    risk_factors: List[str] = field(default_factory=list)
    compliance_issues: List[str] = field(default_factory=list)
    key_clauses: List[Dict[str, Any]] = field(default_factory=list)
    missing_clauses: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    summary: Optional[str] = None
    analyzed_at: datetime = field(default_factory=datetime.now)
    analysis_model: Optional[str] = None


@dataclass
class ProcessingResult:
    """Complete processing result for a document."""
    document_id: str
    metadata: DocumentMetadata
    content: DocumentContent
    classification: DocumentClassification
    entities: EntityExtraction
    analysis: DocumentAnalysis
    processing_status: ProcessingStatus
    processing_steps: List[Dict[str, Any]] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    processing_time: Optional[float] = None
    processed_at: datetime = field(default_factory=datetime.now)


class DocumentProcessor:
    """
    Main document processor for legal documents.
    Handles ingestion, OCR, classification, entity extraction, and analysis.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize Document Processor.
        
        Args:
            config: Configuration dictionary
        """
        self.config = config or self._default_config()
        
        # Document storage
        self.documents: Dict[str, ProcessingResult] = {}
        
        # Processing pipelines
        self.ingestion_pipeline = []
        self.ocr_pipeline = []
        self.classification_pipeline = []
        self.entity_pipeline = []
        self.analysis_pipeline = []
        
        # Statistics
        self.stats = {
            "documents_processed": 0,
            "total_pages": 0,
            "total_words": 0,
            "processing_time_total": 0.0,
            "by_format": {},
            "by_type": {},
            "by_status": {},
            "errors": 0,
            "warnings": 0
        }
        
        # Initialize pipelines
        self._initialize_pipelines()
        
        logger.info("Initialized Document Processor")
    
    def _default_config(self) -> Dict[str, Any]:
        """Get default configuration."""
        return {
            "ingestion": {
                "supported_formats": [fmt.value for fmt in DocumentFormat],
                "max_file_size_mb": 100,
                "temp_directory": "/tmp/document_processing",
                "preserve_original": True,
                "generate_checksums": True
            },
            "ocr": {
                "enabled": True,
                "engine": "tesseract",
                "languages": ["eng"],
                "custom_fonts": ["legal_fonts"],
                "min_confidence": 0.7,
                "deskew": True,
                "remove_noise": True
            },
            "classification": {
                "enabled": True,
                "model": "bert-legal-classifier",
                "min_confidence": 0.6,
                "fallback_to_rules": True,
                "multi_label": True
            },
            "entity_extraction": {
                "enabled": True,
                "model": "legal-ner",
                "entity_types": [
                    "PERSON", "ORGANIZATION", "DATE", "MONEY", "PERCENT",
                    "LAW", "STATUTE", "CASE", "COURT", "JUDGE",
                    "CONTRACT", "CLAUSE", "PARTY", "TERM", "CONDITION"
                ],
                "min_confidence": 0.7,
                "link_entities": True
            },
            "analysis": {
                "enabled": True,
                "risk_assessment": True,
                "compliance_checking": True,
                "clause_analysis": True,
                "summary_generation": True,
                "recommendations": True
            },
            "performance": {
                "max_concurrent": 4,
                "timeout_seconds": 300,
                "cache_results": True,
                "cache_size": 1000
            },
            "output": {
                "save_intermediate": False,
                "output_format": "json",
                "compress_output": True,
                "database_integration": False
            }
        }
    
    def _initialize_pipelines(self):
        """Initialize processing pipelines."""
        # Ingestion pipeline
        self.ingestion_pipeline = [
            self._validate_file,
            self._extract_metadata,
            self._generate_checksums,
            self._detect_format
        ]
        
        # OCR pipeline (if enabled)
        if self.config["ocr"]["enabled"]:
            self.ocr_pipeline = [
                self._check_if_ocr_needed,
                self._perform_ocr,
                self._assess_ocr_quality,
                self._clean_ocr_text
            ]
        
        # Classification pipeline
        if self.config["classification"]["enabled"]:
            self.classification_pipeline = [
                self._extract_features,
                self._classify_document,
                self._validate_classification
            ]
        
        # Entity extraction pipeline
        if self.config["entity_extraction"]["enabled"]:
            self.entity_pipeline = [
                self._extract_entities,
                self._categorize_entities,
                self._link_entities,
                self._validate_entities
            ]
        
        # Analysis pipeline
        if self.config["analysis"]["enabled"]:
            self.analysis_pipeline = [
                self._assess_risk,
                self._check_compliance,
                self._analyze_clauses,
                self._generate_summary,
                self._generate_recommendations
            ]
        
        logger.info(f"Initialized pipelines: "
                   f"Ingestion({len(self.ingestion_pipeline)}), "
                   f"OCR({len(self.ocr_pipeline)}), "
                   f"Classification({len(self.classification_pipeline)}), "
                   f"Entities({len(self.entity_pipeline)}), "
                   f"Analysis({len(self.analysis_pipeline)})")
    
    def process_document(self, file_path: str, 
                        document_id: Optional[str] = None) -> ProcessingResult:
        """
        Process a single document.
        
        Args:
            file_path: Path to document file
            document_id: Optional document ID (generated if not provided)
            
        Returns:
            Processing result
        """
        start_time = datetime.now()
        
        try:
            # Generate document ID if not provided
            if not document_id:
                document_id = f"doc_{uuid.uuid4().hex[:16]}"
            
            logger.info(f"Processing document {document_id}: {file_path}")
            
            # Initialize processing result
            result = ProcessingResult(
                document_id=document_id,
                metadata=None,  # Will be set by ingestion
                content=None,   # Will be set by OCR
                classification=None,
                entities=None,
                analysis=None,
                processing_status=ProcessingStatus.PENDING
            )
            
            # Execute pipelines
            result = self._execute_pipeline(file_path, result)
            
            # Calculate processing time
            result.processing_time = (datetime.now() - start_time).total_seconds()
            result.processed_at = datetime.now()
            
            # Update statistics
            self._update_statistics(result)
            
            # Store result
            self.documents[document_id] = result
            
            logger.info(f"Document {document_id} processed in {result.processing_time:.2f}s")
            return result
            
        except Exception as e:
            logger.error(f"Error processing document {file_path}: {str(e)}")
            
            # Create error result
            error_result = ProcessingResult(
                document_id=document_id or f"error_{uuid.uuid4().hex[:8]}",
                metadata=None,
                content=None,
                classification=None,
                entities=None,
                analysis=None,
                processing_status=ProcessingStatus.ERROR,
                errors=[str(e)],
                processing_time=(datetime.now() - start_time).total_seconds()
            )
            
            self.stats["errors"] += 1
            return error_result
    
    def process_batch(self, file_paths: List[str], 
                     max_concurrent: Optional[int] = None) -> List[ProcessingResult]:
        """
        Process multiple documents.
        
        Args:
            file_paths: List of file paths
            max_concurrent: Maximum concurrent processing
            
        Returns:
            List of processing results
        """
        max_concurrent = max_concurrent or self.config["performance"]["max_concurrent"]
        results = []
        
        logger.info(f"Processing batch of {len(file_paths)} documents (max {max_concurrent} concurrent)")
        
        # Simple sequential processing for now
        # In production, this would use concurrent processing
        for file_path in file_paths:
            try:
                result = self.process_document(file_path)
                results.append(result)
            except Exception as e:
                logger.error(f"Error in batch processing {file_path}: {str(e)}")
                self.stats["errors"] += 1
        
        logger.info(f"Batch processing completed: {len(results)} successful, {len(file_paths) - len(results)} failed")
        return results
    
    def process_directory(self, directory_path: str, 
                         file_pattern: str = "*",
                         recursive: bool = True) -> List[ProcessingResult]:
        """
        Process all documents in a directory.
        
        Args:
            directory_path: Path to directory
            file_pattern: File pattern to match
            recursive: Whether to process subdirectories
            
        Returns:
            List of processing results
        """
        directory = Path(directory_path)
        if not directory.exists():
            logger.error(f"Directory not found: {directory_path}")
            return []
        
        # Find files
        if recursive:
            files = list(directory.rglob(file_pattern))
        else:
            files = list(directory.glob(file_pattern))
        
        # Filter to files only
        files = [f for f in files if f.is_file()]
        
        if not files:
            logger.warning(f"No files found in {directory_path} matching {file_pattern}")
            return []
        
        logger.info(f"Found {len(files)} files in {directory_path}")
        return self.process_batch([str(f) for f in files])
    
    def get_document(self, document_id: str) -> Optional[ProcessingResult]:
        """Get processing result for a document."""
        return self.documents.get(document_id)
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get processing statistics."""
        return {
            "processor_config": self.config,
            "statistics": self.stats,
            "document_count": len(self.documents),
            "timestamp": datetime.now().isoformat()
        }
    
    def export_results(self, document_ids: Optional[List[str]] = None,
                      format: str = "json") -> Dict[str, Any]:
        """
        Export processing results.
        
        Args:
            document_ids: List of document IDs (all if None)
            format: Export format
            
        Returns:
            Export data
        """
        if document_ids is None:
            document_ids = list(self.documents.keys())
        
        export_data = {
            "metadata": {
                "export_date": datetime.now().isoformat(),
                "document_count": len(document_ids),
                "format": format
            },
            "documents": []
        }
        
        for doc_id in document_ids:
            if doc_id in self.documents:
                result = self.documents[doc_id]
                
                # Convert to serializable format
                doc_data = self._result_to_dict(result)
                export_data["documents"].append(doc_data)
        
        logger.info(f"Exported {len(export_data['documents'])} documents in {format} format")
        return export_data
    
    def _execute_pipeline(self, file_path: str, result: ProcessingResult) -> ProcessingResult:
        """Execute the complete processing pipeline."""
        processing_steps = []
        
        try:
            # Step 1: Ingestion
            logger.debug(f"Ingesting document {result.document_id}")
            for step in self.ingestion_pipeline:
                step_name = step.__name__
                step_start = datetime.now()
                
                try:
                    result = step(file_path, result)
                    processing_steps.append({
                        "step": step_name,
                        "status": "completed",
                        "duration": (datetime.now() - step_start).total_seconds()
                    })
                except Exception as e:
                    processing_steps.append({
                        "step": step_name,
                        "status": "error",
                        "error": str(e),
                        "duration": (datetime.now() - step_start).total_seconds()
                    })
                    raise
            
            result.processing_status = ProcessingStatus.INGESTED
            
            # Step 2: OCR (if needed)
            if self.ocr_pipeline and self._needs_ocr(result.metadata):
                logger.debug(f"Performing OCR on document {result.document_id}")
                result.processing_status = ProcessingStatus.OCR_PROCESSING
                
                for step in self.ocr_pipeline:
                    step_name = step.__name__
                    step_start = datetime.now()
                    
                    try:
                        result = step(file_path, result)
                        processing_steps.append({
                            "step": step_name,
                            "status": "completed",
                            "duration": (datetime.now() - step_start).total_seconds()
                        })
                    except Exception as e:
                        processing_steps.append({
                            "step": step_name,
                            "status": "error",
                            "error": str(e),
                            "duration": (datetime.now() - step_start).total_seconds()
                        })
                        result.warnings.append(f"OCR step {step_name} failed: {str(e)}")
                
                result.processing_status = ProcessingStatus.OCR_COMPLETED
            
            # Step 3: Classification
            if self.classification_pipeline:
                logger.debug(f"Classifying document {result.document_id}")
                
                for step in self.classification_pipeline:
                    step_name = step.__name__
                    step_start = datetime.now()
                    
                    try:
                        result = step(file_path, result)
                        processing_steps.append({
                            "step": step_name,
                            "status": "completed",
                            "duration": (datetime.now() - step_start).total_seconds()
                        })
                    except Exception as e:
                        processing_steps.append({
                            "step": step_name,
                            "status": "error",
                            "error": str(e),
                            "duration": (datetime.now() - step_start).total_seconds()
                        })
                        result.warnings.append(f"Classification step {step_name} failed: {str(e)}")
                
                result.processing_status = ProcessingStatus.CLASSIFIED
            
            # Step 4: Entity extraction
            if self.entity_pipeline:
                logger.debug(f"Extracting entities from document {result.document_id}")
                
                for step in self.entity_pipeline:
                    step_name = step.__name__
                    step_start = datetime.now()
                    
                    try:
                        result = step(file_path, result)
                        processing_steps.append({
                            "step": step_name,
                            "status": "completed",
                            "duration": (datetime.now() - step_start).total_seconds()
                        })
                    except Exception as e:
                        processing_steps.append({
                            "step": step_name,
                            "status": "error",
                            "error": str(e),
                            "duration": (datetime.now() - step_start).total_seconds()
                        })
                        result.warnings.append(f"Entity extraction step {step_name} failed: {str(e)}")
                
                result.processing_status = ProcessingStatus.ENTITIES_EXTRACTED
            
            # Step 5: Analysis
            if self.analysis_pipeline:
                logger.debug(f"Analyzing document {result.document_id}")
                
                for step in self.analysis_pipeline:
                    step_name = step.__name__
                    step_start = datetime.now()
                    
                    try:
                        result = step(file_path, result)
                        processing_steps.append({
                            "step": step_name,
                            "status": "completed",
                            "duration": (datetime.now() - step_start).total_seconds()
                        })
                    except Exception as e:
                        processing_steps.append({
                            "step": step_name,
                            "status": "error",
                            "error": str(e),
                            "duration": (datetime.now() - step_start).total_seconds()
                        })
                        result.warnings.append(f"Analysis step {step_name} failed: {str(e)}")
                
                result.processing_status = ProcessingStatus.ANALYZED
            
            # Mark as completed
            result.processing_status = ProcessingStatus.COMPLETED
            
        except Exception as e:
            logger.error(f"Pipeline execution error for {result.document_id}: {str(e)}")
            result.processing_status = ProcessingStatus.ERROR
            result.errors.append(str(e))
        
        # Add processing steps to result
        result.processing_steps = processing_steps
        
        return result
    
    def _validate_file(self, file_path: str, result: ProcessingResult) -> ProcessingResult:
        """Validate file before processing."""
        path = Path(file_path)
        
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        if not path.is_file():
            raise ValueError(f"Not a file: {file_path}")
        
        # Check file size
        file_size = path.stat().st_size
        max_size = self.config["ingestion"]["max_file_size_mb"] * 1024 * 1024
        
        if file_size > max_size:
            raise ValueError(f"File too large: {file_size} bytes (max: {max_size} bytes)")
        
        if file_size == 0:
            raise ValueError(f"Empty file: {file_path}")
        
        return result
    
    def _extract_metadata(self, file_path: str, result: ProcessingResult) -> ProcessingResult:
        """Extract metadata from file."""
        path = Path(file_path)
        file_size = path.stat().st_size
        
        # Get file format
        file_format = self._detect_file_format(path)
        
        # Get MIME type
        mime_type, _ = mimetypes.guess_type(file_path)
        if not mime_type:
            mime_type = "application/octet-stream"
        
        # Create metadata
        metadata = DocumentMetadata(
            document_id=result.document_id,
            original_filename=path.name,
            file_size=file_size,
            file_format=file_format,
            mime_type=mime_type,
            md5_hash="",  # Will be set by generate_checksums
            sha256_hash="",  # Will be set by generate_checksums
            created_date=datetime.fromtimestamp(path.stat().st_ctime),
            modified_date=datetime.fromtimestamp(path.stat().st_mtime)
        )
        
        result.metadata = metadata
        return result
    
    def _generate_checksums(self, file_path: str, result: ProcessingResult) -> ProcessingResult:
        """Generate checksums for file."""
        if not self.config["ingestion"]["generate_checksums"]:
            result.metadata.md5_hash = "not_generated"
            result.metadata.sha256_hash = "not_generated"
            return result
        
        try:
            with open(file_path, 'rb') as f:
                content = f.read()
            
            # MD5 hash
            md5_hash = hashlib.md5(content).hexdigest()
            
            # SHA256 hash
            sha256_hash = hashlib.sha256(content).hexdigest()
            
            result.metadata.md5_hash = md5_hash
            result.metadata.sha256_hash = sha256_hash
            
        except Exception as e:
            logger.warning(f"Error generating checksums: {str(e)}")
            result.metadata.md5_hash = "error"
            result.metadata.sha256_hash = "error"
            result.warnings.append(f"Checksum generation failed: {str(e)}")
        
        return result
    
    def _detect_format(self, file_path: str, result: ProcessingResult) -> ProcessingResult:
        """Detect and validate file format."""
        # Already detected in extract_metadata, but we can add validation here
        supported_formats = self.config["ingestion"]["supported_formats"]
        
        if result.metadata.file_format.value not in supported_formats:
            result.warnings.append(f"Unsupported format: {result.metadata.file_format.value}")
        
        return result
    
    def _needs_ocr(self, metadata: DocumentMetadata) -> bool:
        """Check if document needs OCR."""
        if not self.config["ocr"]["enabled"]:
            return False
        
        # Image formats always need OCR
        image_formats = [DocumentFormat.PNG, DocumentFormat.JPG, 
                        DocumentFormat.JPEG, DocumentFormat.TIFF, DocumentFormat.BMP]
        if metadata.file_format in image_formats:
            return True
        
        # PDF might need OCR if it's scanned
        if metadata.file_format == DocumentFormat.PDF:
            # In production, would check if PDF contains text
            # For now, assume PDFs need OCR check
            return True
        
        # Other formats typically don't need OCR
        return False
    
    def _check_if_ocr_needed(self, file_path: str, result: ProcessingResult) -> ProcessingResult:
        """Check if OCR is actually needed for this document."""
        if not self._needs_ocr(result.metadata):
            # Skip OCR pipeline
            return result
        
        # For now, just return result
        # In production, would check if document already has extractable text
        return result
    
    def _perform_ocr(self, file_path: str, result: ProcessingResult) -> ProcessingResult:
        """Perform OCR on document."""
        # Mock OCR implementation
        # In production, would use Tesseract or other OCR engine
        
        try:
            # For now, create mock OCR content
            mock_text = f"OCR text extracted from {result.metadata.original_filename}\n"
            mock_text += "This is a placeholder for actual OCR text.\n"
            mock_text += "In production, this would contain the actual extracted text.\n"
            mock_text += "Legal documents often contain complex formatting and terminology.\n"
            
            # Create document content
            content = DocumentContent(
                document_id=result.document_id,
                raw_text=mock_text,
                clean_text=mock_text,
                paragraphs=mock_text.split('\n'),
                ocr_quality=OCRQuality.GOOD,
                confidence=0.85
            )
            
            result.content = content
            
        except Exception as e:
            logger.error(f"OCR error: {str(e)}")
            raise
        
        return result
    
    def _assess_ocr_quality(self, file_path: str, result: ProcessingResult) -> ProcessingResult:
        """Assess quality of OCR results."""
        if not result.content:
            return result
        
        # Mock quality assessment
        # In production, would analyze text quality, confidence scores, etc.
        
        text = result.content.raw_text
        word_count = len(text.split())
        
        if word_count < 10:
            result.content.ocr_quality = OCRQuality.POOR
            result.content.confidence = 0.3
            result.warnings.append("Low word count after OCR")
        elif word_count < 50:
            result.content.ocr_quality = OCRQuality.FAIR
            result.content.confidence = 0.6
        elif word_count < 200:
            result.content.ocr_quality = OCRQuality.GOOD
            result.content.confidence = 0.8
        else:
            result.content.ocr_quality = OCRQuality.EXCELLENT
            result.content.confidence = 0.95
        
        return result
    
    def _clean_ocr_text(self, file_path: str, result: ProcessingResult) -> ProcessingResult:
        """Clean and normalize OCR text."""
        if not result.content:
            return result
        
        text = result.content.raw_text
        
        # Basic cleaning
        clean_text = text.strip()
        
        # Remove excessive whitespace
        import re
        clean_text = re.sub(r'\s+', ' ', clean_text)
        
        # Update content
        result.content.clean_text = clean_text
        result.content.paragraphs = [p.strip() for p in clean_text.split('\n') if p.strip()]
        
        # Update counts
        result.metadata.word_count = len(clean_text.split())
        result.metadata.character_count = len(clean_text)
        
        return result
    
    def _extract_features(self, file_path: str, result: ProcessingResult) -> ProcessingResult:
        """Extract features for classification."""
        # Mock feature extraction
        # In production, would extract text features, structural features, etc.
        
        features = []
        
        if result.content:
            text = result.content.clean_text.lower()
            
            # Legal terminology features
            legal_terms = ["contract", "agreement", "party", "shall", "hereinafter",
                          "whereas", "witnesseth", "indemnify", "liability", "jurisdiction"]
            
            for term in legal_terms:
                if term in text:
                    features.append(f"contains_{term}")
            
            # Structural features based on filename and metadata
            filename = result.metadata.original_filename.lower()
            
            if "contract" in filename or "agreement" in filename:
                features.append("filename_suggests_contract")
            if "motion" in filename or "brief" in filename:
                features.append("filename_suggests_pleading")
            if "patent" in filename:
                features.append("filename_suggests_patent")
        
        # Store features for classification
        result.classification_features = features
        
        return result
    
    def _classify_document(self, file_path: str, result: ProcessingResult) -> ProcessingResult:
        """Classify document type."""
        # Mock classification
        # In production, would use BERT or other ML model
        
        features = result.classification_features
        filename = result.metadata.original_filename.lower()
        
        # Rule-based classification
        primary_type = DocumentType.OTHER
        secondary_types = []
        confidence = 0.7
        reasons = []
        
        # Check for contract indicators
        contract_indicators = ["contract", "agreement", "party", "shall", "witnesseth"]
        if any(indicator in filename for indicator in contract_indicators):
            primary_type = DocumentType.CONTRACT
            reasons.append("Filename suggests contract")
            confidence = 0.85
        
        # Check for pleading indicators
        pleading_indicators = ["motion", "brief", "pleading", "complaint", "answer"]
        if any(indicator in filename for indicator in pleading_indicators):
            if primary_type == DocumentType.OTHER:
                primary_type = DocumentType.PLEADING
            else:
                secondary_types.append(DocumentType.PLEADING)
            reasons.append("Filename suggests pleading")
        
        # Check for patent indicators
        if "patent" in filename:
            if primary_type == DocumentType.OTHER:
                primary_type = DocumentType.PATENT
            else:
                secondary_types.append(DocumentType.PATENT)
            reasons.append("Filename suggests patent")
        
        # Check content if available
        if result.content:
            text = result.content.clean_text.lower()
            
            # Look for legal document markers
            if "court" in text and ("case" in text or "no." in text):
                if primary_type == DocumentType.OTHER:
                    primary_type = DocumentType.OPINION
                secondary_types.append(DocumentType.OPINION)
                reasons.append("Content suggests court opinion")
            
            if "statute" in text or "regulation" in text or "cfr" in text or "usc" in text:
                if primary_type == DocumentType.OTHER:
                    primary_type = DocumentType.STATUTE
                secondary_types.append(DocumentType.STATUTE)
                reasons.append("Content suggests statute/regulation")
        
        # Create classification
        classification = DocumentClassification(
            document_id=result.document_id,
            primary_type=primary_type,
            secondary_types=secondary_types,
            confidence=confidence,
            classification_model="rule_based",
            classification_features=features,
            classification_reasons=reasons
        )
        
        result.classification = classification
        return result
    
    def _validate_classification(self, file_path: str, result: ProcessingResult) -> ProcessingResult:
        """Validate classification results."""
        if not result.classification:
            return result
        
        # Check confidence threshold
        min_confidence = self.config["classification"]["min_confidence"]
        
        if result.classification.confidence < min_confidence:
            result.warnings.append(f"Low classification confidence: {result.classification.confidence}")
            
            # Apply fallback if enabled
            if self.config["classification"]["fallback_to_rules"]:
                # Could apply additional rules here
                pass
        
        return result
    
    def _extract_entities(self, file_path: str, result: ProcessingResult) -> ProcessingResult:
        """Extract entities from document."""
        # Mock entity extraction
        # In production, would use NER model
        
        entities = []
        text = result.content.clean_text if result.content else ""
        
        # Mock entity extraction based on simple patterns
        import re
        
        # Extract dates
        date_patterns = [
            r'\d{1,2}/\d{1,2}/\d{2,4}',
            r'\d{4}-\d{2}-\d{2}',
            r'(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s+\d{4}'
        ]
        
        for pattern in date_patterns:
            for match in re.finditer(pattern, text):
                entities.append({
                    "text": match.group(),
                    "type": "DATE",
                    "start": match.start(),
                    "end": match.end(),
                    "confidence": 0.8
                })
        
        # Extract money amounts
        money_pattern = r'\$\d+(?:,\d{3})*(?:\.\d{2})?'
        for match in re.finditer(money_pattern, text):
            entities.append({
                "text": match.group(),
                "type": "MONEY",
                "start": match.start(),
                "end": match.end(),
                "confidence": 0.9
            })
        
        # Extract percentages
        percent_pattern = r'\d+(?:\.\d+)?%'
        for match in re.finditer(percent_pattern, text):
            entities.append({
                "text": match.group(),
                "type": "PERCENT",
                "start": match.start(),
                "end": match.end(),
                "confidence": 0.95
            })
        
        # Create entity extraction result
        entity_extraction = EntityExtraction(
            document_id=result.document_id,
            entities=entities,
            extraction_model="rule_based",
            confidence=0.7
        )
        
        # Count entities by category
        categories = {}
        for entity in entities:
            category = entity["type"]
            categories[category] = categories.get(category, 0) + 1
        
        entity_extraction.entity_categories = categories
        result.entities = entity_extraction
        
        return result
    
    def _categorize_entities(self, file_path: str, result: ProcessingResult) -> ProcessingResult:
        """Categorize extracted entities."""
        if not result.entities:
            return result
        
        # Already categorized in extract_entities
        return result
    
    def _link_entities(self, file_path: str, result: ProcessingResult) -> ProcessingResult:
        """Link related entities."""
        if not result.entities or not self.config["entity_extraction"]["link_entities"]:
            return result
        
        # Mock entity linking
        # In production, would identify relationships between entities
        
        relationships = []
        entities = result.entities.entities
        
        # Simple linking: dates near money might be payment dates
        for i, entity1 in enumerate(entities):
            if entity1["type"] == "DATE":
                for j, entity2 in enumerate(entities):
                    if i != j and entity2["type"] == "MONEY":
                        # Check if they're close in text
                        distance = abs(entity1["start"] - entity2["start"])
                        if distance < 100:  # Within 100 characters
                            relationships.append({
                                "entity1": entity1["text"],
                                "entity2": entity2["text"],
                                "relationship": "payment_date",
                                "confidence": 0.6
                            })
        
        result.entities.entity_relationships = relationships
        return result
    
    def _validate_entities(self, file_path: str, result: ProcessingResult) -> ProcessingResult:
        """Validate extracted entities."""
        if not result.entities:
            return result
        
        # Check minimum confidence
        min_confidence = self.config["entity_extraction"]["min_confidence"]
        
        if result.entities.confidence < min_confidence:
            result.warnings.append(f"Low entity extraction confidence: {result.entities.confidence}")
        
        return result
    
    def _assess_risk(self, file_path: str, result: ProcessingResult) -> ProcessingResult:
        """Assess document risk."""
        # Mock risk assessment
        # In production, would analyze content for risk factors
        
        risk_score = 0.5  # Default medium risk
        risk_factors = []
        risk_level = RiskLevel.MEDIUM
        
        # Check document type
        if result.classification:
            doc_type = result.classification.primary_type
            
            # Contracts are higher risk
            if doc_type in [DocumentType.CONTRACT, DocumentType.AGREEMENT]:
                risk_score += 0.2
                risk_factors.append("Contract document")
            
            # Legal pleadings medium risk
            elif doc_type in [DocumentType.PLEADING, DocumentType.MOTION, DocumentType.BRIEF]:
                risk_score += 0.1
                risk_factors.append("Legal pleading")
        
        # Check for money amounts
        if result.entities:
            money_count = result.entities.entity_categories.get("MONEY", 0)
            if money_count > 0:
                risk_score += min(0.3, money_count * 0.05)
                risk_factors.append(f"Contains {money_count} monetary references")
        
        # Check document size
        if result.metadata.file_size > 10 * 1024 * 1024:  # > 10MB
            risk_score += 0.1
            risk_factors.append("Large document size")
        
        # Normalize risk score
        risk_score = max(0.0, min(1.0, risk_score))
        
        # Determine risk level
        if risk_score < 0.3:
            risk_level = RiskLevel.LOW
        elif risk_score < 0.6:
            risk_level = RiskLevel.MEDIUM
        elif risk_score < 0.8:
            risk_level = RiskLevel.HIGH
        else:
            risk_level = RiskLevel.CRITICAL
        
        # Create analysis
        analysis = DocumentAnalysis(
            document_id=result.document_id,
            risk_level=risk_level,
            risk_score=risk_score,
            risk_factors=risk_factors
        )
        
        result.analysis = analysis
        return result
    
    def _check_compliance(self, file_path: str, result: ProcessingResult) -> ProcessingResult:
        """Check document for compliance issues."""
        if not result.analysis:
            result.analysis = DocumentAnalysis(document_id=result.document_id)
        
        compliance_issues = []
        
        # Mock compliance checks
        if result.content:
            text = result.content.clean_text.lower()
            
            # Check for missing clauses in contracts
            if result.classification and result.classification.primary_type == DocumentType.CONTRACT:
                required_clauses = ["indemnification", "confidentiality", "termination", "governing law"]
                
                for clause in required_clauses:
                    if clause not in text:
                        compliance_issues.append(f"Missing {clause} clause")
                        result.analysis.missing_clauses.append(clause)
            
            # Check for problematic language
            problematic_terms = {
                "perpetual": "Perpetual licenses may be problematic",
                "irrevocable": "Irrevocable clauses require careful review",
                "unlimited liability": "Unlimited liability is high risk",
                "assignment without consent": "Assignment without consent may be unenforceable"
            }
            
            for term, issue in problematic_terms.items():
                if term in text:
                    compliance_issues.append(issue)
        
        result.analysis.compliance_issues = compliance_issues
        return result
    
    def _analyze_clauses(self, file_path: str, result: ProcessingResult) -> ProcessingResult:
        """Analyze key clauses in document."""
        if not result.analysis:
            result.analysis = DocumentAnalysis(document_id=result.document_id)
        
        key_clauses = []
        
        if result.content and result.classification:
            text = result.content.clean_text.lower()
            doc_type = result.classification.primary_type
            
            if doc_type == DocumentType.CONTRACT:
                # Identify potential clauses
                clause_patterns = {
                    "term": ["term", "duration", "effective date", "expiration"],
                    "payment": ["payment", "fee", "price", "compensation"],
                    "termination": ["termination", "cancellation", "expiration"],
                    "liability": ["liability", "indemnification", "warranty"],
                    "confidentiality": ["confidential", "non-disclosure", "proprietary"],
                    "governing law": ["governing law", "jurisdiction", "venue", "dispute"]
                }
                
                for clause_name, keywords in clause_patterns.items():
                    for keyword in keywords:
                        if keyword in text:
                            # Find the section containing this keyword
                            key_clauses.append({
                                "name": clause_name,
                                "keywords": [keyword],
                                "importance": "high" if clause_name in ["liability", "termination"] else "medium"
                            })
                            break
        
        result.analysis.key_clauses = key_clauses
        return result
    
    def _generate_summary(self, file_path: str, result: ProcessingResult) -> ProcessingResult:
        """Generate document summary."""
        if not result.analysis:
            result.analysis = DocumentAnalysis(document_id=result.document_id)
        
        # Mock summary generation
        # In production, would use LLM or extractive summarization
        
        summary_parts = []
        
        if result.metadata:
            summary_parts.append(f"Document: {result.metadata.original_filename}")
            summary_parts.append(f"Size: {result.metadata.file_size:,} bytes")
            summary_parts.append(f"Format: {result.metadata.file_format.value}")
        
        if result.classification:
            summary_parts.append(f"Type: {result.classification.primary_type.value}")
            if result.classification.secondary_types:
                secondary = ", ".join([t.value for t in result.classification.secondary_types])
                summary_parts.append(f"Also: {secondary}")
        
        if result.analysis:
            summary_parts.append(f"Risk: {result.analysis.risk_level.value} ({result.analysis.risk_score:.2f})")
            
            if result.analysis.key_clauses:
                clause_names = [c["name"] for c in result.analysis.key_clauses[:3]]
                summary_parts.append(f"Key clauses: {', '.join(clause_names)}")
            
            if result.analysis.compliance_issues:
                issue_count = len(result.analysis.compliance_issues)
                summary_parts.append(f"Compliance issues: {issue_count}")
        
        summary = "\n".join(summary_parts)
        result.analysis.summary = summary
        
        return result
    
    def _generate_recommendations(self, file_path: str, result: ProcessingResult) -> ProcessingResult:
        """Generate recommendations for document."""
        if not result.analysis:
            result.analysis = DocumentAnalysis(document_id=result.document_id)
        
        recommendations = []
        
        # Based on analysis results
        if result.analysis.risk_level in [RiskLevel.HIGH, RiskLevel.CRITICAL]:
            recommendations.append("High risk document - recommend legal review")
        
        if result.analysis.compliance_issues:
            recommendations.append(f"Address {len(result.analysis.compliance_issues)} compliance issues")
        
        if result.analysis.missing_clauses:
            recommendations.append(f"Consider adding missing clauses: {', '.join(result.analysis.missing_clauses[:3])}")
        
        if result.classification and result.classification.confidence < 0.8:
            recommendations.append("Low classification confidence - manual verification recommended")
        
        if not recommendations:
            recommendations.append("Document appears standard - routine processing recommended")
        
        result.analysis.recommendations = recommendations
        return result
    
    def _detect_file_format(self, path: Path) -> DocumentFormat:
        """Detect file format from extension."""
        suffix = path.suffix.lower().lstrip('.')
        
        format_map = {
            'pdf': DocumentFormat.PDF,
            'docx': DocumentFormat.DOCX,
            'doc': DocumentFormat.DOC,
            'txt': DocumentFormat.TXT,
            'rtf': DocumentFormat.RTF,
            'html': DocumentFormat.HTML,
            'htm': DocumentFormat.HTML,
            'xml': DocumentFormat.XML,
            'json': DocumentFormat.JSON,
            'csv': DocumentFormat.CSV,
            'xlsx': DocumentFormat.XLSX,
            'xls': DocumentFormat.XLS,
            'pptx': DocumentFormat.PPTX,
            'ppt': DocumentFormat.PPT,
            'png': DocumentFormat.PNG,
            'jpg': DocumentFormat.JPG,
            'jpeg': DocumentFormat.JPEG,
            'tiff': DocumentFormat.TIFF,
            'tif': DocumentFormat.TIFF,
            'bmp': DocumentFormat.BMP,
            'eml': DocumentFormat.EMAIL,
            'msg': DocumentFormat.EMAIL
        }
        
        return format_map.get(suffix, DocumentFormat.UNKNOWN)
    
    def _update_statistics(self, result: ProcessingResult):
        """Update processing statistics."""
        self.stats["documents_processed"] += 1
        
        # Update by format
        fmt = result.metadata.file_format.value
        self.stats["by_format"][fmt] = self.stats["by_format"].get(fmt, 0) + 1
        
        # Update by type
        if result.classification:
            doc_type = result.classification.primary_type.value
            self.stats["by_type"][doc_type] = self.stats["by_type"].get(doc_type, 0) + 1
        
        # Update by status
        status = result.processing_status.value
        self.stats["by_status"][status] = self.stats["by_status"].get(status, 0) + 1
        
        # Update totals
        if result.metadata.word_count:
            self.stats["total_words"] += result.metadata.word_count
        
        if result.processing_time:
            self.stats["processing_time_total"] += result.processing_time
        
        # Update error/warning counts
        self.stats["errors"] += len(result.errors)
        self.stats["warnings"] += len(result.warnings)
    
    def _result_to_dict(self, result: ProcessingResult) -> Dict[str, Any]:
        """Convert processing result to dictionary."""
        def convert_datetime(obj):
            if isinstance(obj, datetime):
                return obj.isoformat()
            return obj
        
        def convert_enum(obj):
            if isinstance(obj, Enum):
                return obj.value
            return obj
        
        # Convert entire result
        result_dict = {}
        
        for field in result.__dataclass_fields__:
            value = getattr(result, field)
            
            if isinstance(value, Enum):
                result_dict[field] = value.value
            elif isinstance(value, datetime):
                result_dict[field] = value.isoformat()
            elif hasattr(value, '__dataclass_fields__'):
                result_dict[field] = self._result_to_dict(value)
            elif isinstance(value, list):
                result_dict[field] = []
                for item in value:
                    if hasattr(item, '__dataclass_fields__'):
                        result_dict[field].append(self._result_to_dict(item))
                    elif isinstance(item, Enum):
                        result_dict[field].append(item.value)
                    elif isinstance(item, datetime):
                        result_dict[field].append(item.isoformat())
                    else:
                        result_dict[field].append(item)
            elif isinstance(value, dict):
                result_dict[field] = {}
                for k, v in value.items():
                    if isinstance(v, Enum):
                        result_dict[field][k] = v.value
                    elif isinstance(v, datetime):
                        result_dict[field][k] = v.isoformat()
                    else:
                        result_dict[field][k] = v
            else:
                result_dict[field] = value
        
        return result_dict


def test_document_processor():
    """Test function for Document Processor."""
    print("Testing Document Processor...")
    
    # Create processor instance
    processor = DocumentProcessor()
    
    # Create test documents directory
    test_dir = Path("test_documents")
    test_dir.mkdir(exist_ok=True)
    
    # Test 1: Create and process a mock contract
    print("\n1. Testing contract processing...")
    
    contract_content = """CONTRACT AGREEMENT
    
This Agreement is made on January 15, 2024 between:
Party A: ABC Corporation
Party B: XYZ LLC
    
1. TERM: This Agreement shall commence on January 15, 2024 and continue for 2 years.
    
2. PAYMENT: Party B shall pay Party A the sum of $50,000 upon execution.
    
3. CONFIDENTIALITY: Both parties agree to maintain confidentiality.
    
4. TERMINATION: Either party may terminate with 30 days notice.
    
5. GOVERNING LAW: This Agreement shall be governed by California law.
    
IN WITNESS WHEREOF, the parties have executed this Agreement."""
    
    contract_file = test_dir / "test_contract.txt"
    contract_file.write_text(contract_content)
    
    result = processor.process_document(str(contract_file))
    print(f"Contract processing result: {result.processing_status.value}")
    print(f"Document type: {result.classification.primary_type.value if result.classification else 'Unknown'}")
    print(f"Risk level: {result.analysis.risk_level.value if result.analysis else 'Unknown'}")
    
    # Test 2: Process a directory
    print("\n2. Testing directory processing...")
    
    # Create another test document
    motion_content = """MOTION TO DISMISS
    
Case No: 2024-CV-00123
Court: Superior Court of California
    
COMES NOW Defendant, ABC Corporation, and moves to dismiss...
    
Dated: February 1, 2024"""
    
    motion_file = test_dir / "test_motion.txt"
    motion_file.write_text(motion_content)
    
    results = processor.process_directory(str(test_dir), "*.txt")
    print(f"Directory processing: {len(results)} documents processed")
    
    # Test 3: Get statistics
    print("\n3. Testing statistics...")
    
    stats = processor.get_statistics()
    print(f"Documents processed: {stats['statistics']['documents_processed']}")
    print(f"Total words: {stats['statistics']['total_words']}")
    print(f"By format: {stats['statistics']['by_format']}")
    
    # Test 4: Export results
    print("\n4. Testing export...")
    
    export_data = processor.export_results()
    print(f"Exported {len(export_data['documents'])} documents")
    
    # Clean up
    import shutil
    shutil.rmtree(test_dir)
    
    print("\nDocument Processor test completed successfully!")


if __name__ == "__main__":
    test_document_processor()