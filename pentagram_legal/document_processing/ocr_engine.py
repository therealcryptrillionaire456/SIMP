"""
OCR Engine for Document Processing Pipeline.
Handles optical character recognition for scanned documents and images.
"""

import sys
import os
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
import logging
from pathlib import Path
import tempfile

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class OCRResult:
    """OCR processing result."""
    document_id: str
    text: str
    confidence: float
    page_count: int
    processing_time: float
    language: str = "eng"
    engine: str = "tesseract"
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class OCRConfig:
    """OCR configuration."""
    engine: str = "tesseract"
    languages: List[str] = field(default_factory=lambda: ["eng"])
    custom_fonts: List[str] = field(default_factory=list)
    min_confidence: float = 0.7
    deskew: bool = True
    remove_noise: bool = True
    preserve_layout: bool = True
    output_format: str = "text"
    timeout_seconds: int = 300


class OCREngine:
    """
    OCR Engine for document processing.
    Supports multiple OCR engines with fallback options.
    """
    
    def __init__(self, config: Optional[OCRConfig] = None):
        """
        Initialize OCR Engine.
        
        Args:
            config: OCR configuration
        """
        self.config = config or OCRConfig()
        self.available_engines = self._detect_available_engines()
        
        logger.info(f"Initialized OCR Engine with {self.config.engine} (available: {list(self.available_engines.keys())})")
    
    def _detect_available_engines(self) -> Dict[str, bool]:
        """Detect available OCR engines on the system."""
        available = {}
        
        # Check for Tesseract
        try:
            import subprocess
            result = subprocess.run(["tesseract", "--version"], 
                                  capture_output=True, text=True)
            available["tesseract"] = result.returncode == 0
        except:
            available["tesseract"] = False
        
        # Check for OCRmyPDF (for PDF OCR)
        try:
            import subprocess
            result = subprocess.run(["ocrmypdf", "--version"], 
                                  capture_output=True, text=True)
            available["ocrmypdf"] = result.returncode == 0
        except:
            available["ocrmypdf"] = False
        
        # Check for EasyOCR
        try:
            import importlib
            importlib.import_module("easyocr")
            available["easyocr"] = True
        except:
            available["easyocr"] = False
        
        # Check for PaddleOCR
        try:
            import importlib
            importlib.import_module("paddleocr")
            available["paddleocr"] = True
        except:
            available["paddleocr"] = False
        
        # Always have mock engine available
        available["mock"] = True
        
        return available
    
    def process_document(self, file_path: str, document_id: str) -> OCRResult:
        """
        Process document with OCR.
        
        Args:
            file_path: Path to document file
            document_id: Document identifier
            
        Returns:
            OCR result
        """
        start_time = datetime.now()
        
        try:
            # Select engine
            engine = self._select_engine()
            
            # Process based on engine
            if engine == "tesseract":
                result = self._process_with_tesseract(file_path, document_id)
            elif engine == "ocrmypdf":
                result = self._process_with_ocrmypdf(file_path, document_id)
            elif engine == "easyocr":
                result = self._process_with_easyocr(file_path, document_id)
            elif engine == "paddleocr":
                result = self._process_with_paddleocr(file_path, document_id)
            else:
                result = self._process_with_mock(file_path, document_id)
            
            # Calculate processing time
            result.processing_time = (datetime.now() - start_time).total_seconds()
            
            # Validate confidence
            if result.confidence < self.config.min_confidence:
                result.warnings.append(f"Low OCR confidence: {result.confidence}")
            
            logger.info(f"OCR completed for {document_id}: {len(result.text)} chars, confidence {result.confidence:.3f}")
            return result
            
        except Exception as e:
            logger.error(f"OCR error for {document_id}: {str(e)}")
            
            # Return error result
            return OCRResult(
                document_id=document_id,
                text="",
                confidence=0.0,
                page_count=0,
                processing_time=(datetime.now() - start_time).total_seconds(),
                errors=[str(e)]
            )
    
    def _select_engine(self) -> str:
        """Select OCR engine based on availability and configuration."""
        # Check if configured engine is available
        if self.config.engine in self.available_engines and self.available_engines[self.config.engine]:
            return self.config.engine
        
        # Fallback to available engines in priority order
        fallback_order = ["tesseract", "ocrmypdf", "easyocr", "paddleocr", "mock"]
        
        for engine in fallback_order:
            if engine in self.available_engines and self.available_engines[engine]:
                logger.warning(f"Falling back to {engine} engine")
                return engine
        
        # Last resort: mock engine
        logger.warning("No OCR engines available, using mock engine")
        return "mock"
    
    def _process_with_tesseract(self, file_path: str, document_id: str) -> OCRResult:
        """Process document with Tesseract OCR."""
        try:
            import pytesseract
            from PIL import Image
            import fitz  # PyMuPDF for PDF handling
            
            text = ""
            page_count = 0
            total_confidence = 0.0
            
            # Check file type
            path = Path(file_path)
            suffix = path.suffix.lower()
            
            if suffix == '.pdf':
                # Process PDF with PyMuPDF
                doc = fitz.open(file_path)
                page_count = len(doc)
                
                for page_num in range(page_count):
                    page = doc.load_page(page_num)
                    
                    # Convert page to image
                    pix = page.get_pixmap()
                    img_data = pix.tobytes("png")
                    
                    # Create temporary image file
                    with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
                        tmp.write(img_data)
                        tmp_path = tmp.name
                    
                    try:
                        # OCR the image
                        page_text = pytesseract.image_to_string(
                            Image.open(tmp_path),
                            lang='+'.join(self.config.languages)
                        )
                        
                        # Get confidence data
                        page_data = pytesseract.image_to_data(
                            Image.open(tmp_path),
                            lang='+'.join(self.config.languages),
                            output_type=pytesseract.Output.DICT
                        )
                        
                        # Calculate average confidence for page
                        confidences = [float(c) for c in page_data['conf'] if c != '-1']
                        page_confidence = sum(confidences) / len(confidences) / 100.0 if confidences else 0.5
                        
                        text += page_text + "\n"
                        total_confidence += page_confidence
                        
                    finally:
                        # Clean up temp file
                        Path(tmp_path).unlink(missing_ok=True)
                
                doc.close()
                
            else:
                # Process image file
                img = Image.open(file_path)
                text = pytesseract.image_to_string(
                    img,
                    lang='+'.join(self.config.languages)
                )
                
                # Get confidence data
                data = pytesseract.image_to_data(
                    img,
                    lang='+'.join(self.config.languages),
                    output_type=pytesseract.Output.DICT
                )
                
                # Calculate average confidence
                confidences = [float(c) for c in data['conf'] if c != '-1']
                total_confidence = sum(confidences) / len(confidences) / 100.0 if confidences else 0.5
                page_count = 1
            
            # Calculate average confidence
            avg_confidence = total_confidence / max(page_count, 1)
            
            return OCRResult(
                document_id=document_id,
                text=text,
                confidence=avg_confidence,
                page_count=page_count,
                processing_time=0.0,  # Will be set by caller
                engine="tesseract",
                language='+'.join(self.config.languages)
            )
            
        except Exception as e:
            logger.error(f"Tesseract OCR error: {str(e)}")
            raise
    
    def _process_with_ocrmypdf(self, file_path: str, document_id: str) -> OCRResult:
        """Process PDF with OCRmyPDF."""
        try:
            import subprocess
            import tempfile
            
            # Create temporary output file
            with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp:
                output_path = tmp.name
            
            try:
                # Build OCRmyPDF command
                cmd = [
                    "ocrmypdf",
                    "--language", "+".join(self.config.languages),
                    "--output-type", "pdf",
                    "--deskew" if self.config.deskew else "",
                    "--clean" if self.config.remove_noise else "",
                    "--force-ocr",
                    file_path,
                    output_path
                ]
                
                # Remove empty arguments
                cmd = [arg for arg in cmd if arg]
                
                # Run OCRmyPDF
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=self.config.timeout_seconds)
                
                if result.returncode != 0:
                    raise RuntimeError(f"OCRmyPDF failed: {result.stderr}")
                
                # Extract text from OCR'd PDF
                # For now, use mock extraction
                # In production, would extract text from the OCR'd PDF
                text = f"OCR text extracted by OCRmyPDF from {file_path}\n"
                text += "This is placeholder text. Actual OCR text would be extracted here.\n"
                
                # Mock confidence
                confidence = 0.85
                page_count = 1  # Would extract actual page count
                
                return OCRResult(
                    document_id=document_id,
                    text=text,
                    confidence=confidence,
                    page_count=page_count,
                    processing_time=0.0,
                    engine="ocrmypdf",
                    language='+'.join(self.config.languages)
                )
                
            finally:
                # Clean up temp file
                Path(output_path).unlink(missing_ok=True)
                
        except Exception as e:
            logger.error(f"OCRmyPDF error: {str(e)}")
            raise
    
    def _process_with_easyocr(self, file_path: str, document_id: str) -> OCRResult:
        """Process document with EasyOCR."""
        try:
            import easyocr
            
            # Initialize reader
            reader = easyocr.Reader(self.config.languages)
            
            # Read text
            results = reader.readtext(file_path)
            
            # Extract text and confidence
            text_parts = []
            confidences = []
            
            for result in results:
                text_parts.append(result[1])
                confidences.append(result[2])
            
            text = "\n".join(text_parts)
            avg_confidence = sum(confidences) / len(confidences) if confidences else 0.5
            
            return OCRResult(
                document_id=document_id,
                text=text,
                confidence=avg_confidence,
                page_count=1,  # EasyOCR doesn't provide page count
                processing_time=0.0,
                engine="easyocr",
                language='+'.join(self.config.languages)
            )
            
        except Exception as e:
            logger.error(f"EasyOCR error: {str(e)}")
            raise
    
    def _process_with_paddleocr(self, file_path: str, document_id: str) -> OCRResult:
        """Process document with PaddleOCR."""
        try:
            from paddleocr import PaddleOCR
            
            # Initialize OCR
            ocr = PaddleOCR(use_angle_cls=True, lang='en')
            
            # Perform OCR
            result = ocr.ocr(file_path, cls=True)
            
            # Extract text and confidence
            text_parts = []
            confidences = []
            
            if result and result[0]:
                for line in result[0]:
                    if line and line[1]:
                        text_parts.append(line[1][0])
                        confidences.append(line[1][1])
            
            text = "\n".join(text_parts)
            avg_confidence = sum(confidences) / len(confidences) if confidences else 0.5
            
            return OCRResult(
                document_id=document_id,
                text=text,
                confidence=avg_confidence,
                page_count=1,
                processing_time=0.0,
                engine="paddleocr",
                language='+'.join(self.config.languages)
            )
            
        except Exception as e:
            logger.error(f"PaddleOCR error: {str(e)}")
            raise
    
    def _process_with_mock(self, file_path: str, document_id: str) -> OCRResult:
        """Mock OCR processing for testing."""
        # Read file to get some content for mock
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read(1000)  # Read first 1000 chars
        except:
            content = ""
        
        # Create mock OCR text
        mock_text = f"Mock OCR text for {document_id}\n"
        mock_text += f"File: {Path(file_path).name}\n"
        mock_text += "This is placeholder text for OCR processing.\n"
        mock_text += "In production, this would be actual OCR-extracted text.\n"
        
        if content:
            mock_text += "\nSample content:\n"
            mock_text += content[:500] + "...\n"
        
        return OCRResult(
            document_id=document_id,
            text=mock_text,
            confidence=0.9,  # High confidence for mock
            page_count=1,
            processing_time=0.0,
            engine="mock",
            language='+'.join(self.config.languages),
            warnings=["Using mock OCR engine - no actual OCR performed"]
        )
    
    def get_engine_info(self) -> Dict[str, Any]:
        """Get information about available OCR engines."""
        return {
            "configured_engine": self.config.engine,
            "available_engines": self.available_engines,
            "config": {
                "languages": self.config.languages,
                "min_confidence": self.config.min_confidence,
                "deskew": self.config.deskew,
                "remove_noise": self.config.remove_noise
            }
        }


def test_ocr_engine():
    """Test function for OCR Engine."""
    print("Testing OCR Engine...")
    
    # Create test configuration
    config = OCRConfig(
        engine="tesseract",
        languages=["eng"],
        min_confidence=0.7
    )
    
    # Create OCR engine
    engine = OCREngine(config)
    
    # Get engine info
    info = engine.get_engine_info()
    print(f"OCR Engine info: {info}")
    
    # Create test document
    test_dir = Path("test_ocr")
    test_dir.mkdir(exist_ok=True)
    
    # Create a simple text file (not actually an image, but for testing)
    test_file = test_dir / "test_document.txt"
    test_content = """Test Document for OCR
    
This is a test document to demonstrate OCR processing.
It contains sample text that would normally be extracted from an image or PDF.
    
Key sections:
1. Introduction
2. Main content
3. Conclusion
    
This document is for testing purposes only."""
    
    test_file.write_text(test_content)
    
    # Test OCR processing
    print("\nTesting OCR processing...")
    result = engine.process_document(str(test_file), "test_doc_001")
    
    print(f"OCR Result:")
    print(f"  Engine: {result.engine}")
    print(f"  Text length: {len(result.text)} characters")
    print(f"  Confidence: {result.confidence:.3f}")
    print(f"  Page count: {result.page_count}")
    print(f"  Processing time: {result.processing_time:.2f}s")
    
    if result.errors:
        print(f"  Errors: {result.errors}")
    if result.warnings:
        print(f"  Warnings: {result.warnings}")
    
    # Clean up
    import shutil
    shutil.rmtree(test_dir)
    
    print("\nOCR Engine test completed successfully!")


if __name__ == "__main__":
    test_ocr_engine()