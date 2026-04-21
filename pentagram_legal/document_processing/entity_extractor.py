"""
Entity Extractor for Document Processing Pipeline.
Extracts legal entities from documents using NER and rule-based approaches.
"""

import sys
import os
from typing import Dict, List, Any, Optional, Tuple, Set
from dataclasses import dataclass, field
from datetime import datetime
import logging
import re
import json

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class Entity:
    """Extracted entity."""
    text: str
    type: str
    start: int
    end: int
    confidence: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ExtractionResult:
    """Entity extraction result."""
    document_id: str
    entities: List[Entity] = field(default_factory=list)
    entity_categories: Dict[str, int] = field(default_factory=dict)
    entity_relationships: List[Dict[str, Any]] = field(default_factory=list)
    processing_time: float = 0.0
    model: str = "rule_based"
    language: str = "en"
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


@dataclass
class ExtractorConfig:
    """Entity extractor configuration."""
    model_type: str = "hybrid"  # rule_based, ml, hybrid
    ml_model_path: Optional[str] = None
    entity_types: List[str] = field(default_factory=lambda: [
        "PERSON", "ORGANIZATION", "DATE", "MONEY", "PERCENT",
        "LAW", "STATUTE", "CASE", "COURT", "JUDGE",
        "CONTRACT", "CLAUSE", "PARTY", "TERM", "CONDITION",
        "LOCATION", "EMAIL", "PHONE", "URL"
    ])
    min_confidence: float = 0.7
    link_entities: bool = True
    normalize_entities: bool = True
    language: str = "en"


class EntityExtractor:
    """
    Entity extractor for legal documents.
    Extracts entities using NER and rule-based approaches.
    """
    
    def __init__(self, config: Optional[ExtractorConfig] = None):
        """
        Initialize Entity Extractor.
        
        Args:
            config: Extractor configuration
        """
        self.config = config or ExtractorConfig()
        self.patterns = self._load_extraction_patterns()
        self.ml_model = self._load_ml_model() if self.config.ml_model_path else None
        
        logger.info(f"Initialized Entity Extractor with {self.config.model_type} model")
    
    def _load_extraction_patterns(self) -> Dict[str, List[Dict[str, Any]]]:
        """Load entity extraction patterns."""
        return {
            "DATE": [
                {"pattern": r'\d{1,2}/\d{1,2}/\d{2,4}', "confidence": 0.9},
                {"pattern": r'\d{4}-\d{2}-\d{2}', "confidence": 0.95},
                {"pattern": r'(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s+\d{4}', "confidence": 0.85},
                {"pattern": r'\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{4}', "confidence": 0.8}
            ],
            "MONEY": [
                {"pattern": r'\$\d+(?:,\d{3})*(?:\.\d{2})?', "confidence": 0.95},
                {"pattern": r'\d+(?:,\d{3})*(?:\.\d{2})?\s+dollars', "confidence": 0.85},
                {"pattern": r'\d+(?:,\d{3})*(?:\.\d{2})?\s+USD', "confidence": 0.9}
            ],
            "PERCENT": [
                {"pattern": r'\d+(?:\.\d+)?%', "confidence": 0.98},
                {"pattern": r'\d+(?:\.\d+)?\s+percent', "confidence": 0.9}
            ],
            "PHONE": [
                {"pattern": r'\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}', "confidence": 0.9},
                {"pattern": r'\+\d{1,3}[-.\s]?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}', "confidence": 0.85}
            ],
            "EMAIL": [
                {"pattern": r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', "confidence": 0.95}
            ],
            "URL": [
                {"pattern": r'https?://(?:www\.)?[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}(?:/\S*)?', "confidence": 0.9}
            ],
            "LAW": [
                {"pattern": r'\d+\s+U\.?S\.?C\.?\s+\d+', "confidence": 0.9},
                {"pattern": r'\d+\s+C\.?F\.?R\.?\s+\d+', "confidence": 0.9},
                {"pattern": r'Section\s+\d+', "confidence": 0.8},
                {"pattern": r'§\s*\d+', "confidence": 0.85}
            ],
            "CASE": [
                {"pattern": r'[A-Z][a-z]+\s+v\.\s+[A-Z][a-z]+', "confidence": 0.8},
                {"pattern": r'\d+\s+[A-Z]+\s+\d+', "confidence": 0.75}
            ],
            "ORGANIZATION": [
                {"pattern": r'[A-Z][a-z]+\s+(?:Inc|Corp|Corporation|LLC|L\.L\.C\.|Ltd|Company|Co\.)', "confidence": 0.7},
                {"pattern": r'[A-Z][a-z]+\s+[A-Z][a-z]+\s+(?:Inc|Corp|Corporation|LLC|L\.L\.C\.)', "confidence": 0.65}
            ]
        }
    
    def _load_ml_model(self):
        """Load ML model for entity extraction."""
        # This would load a pre-trained NER model
        # For now, return None (mock)
        logger.info(f"ML model loading not implemented, using rule-based fallback")
        return None
    
    def extract_entities(self, document_id: str, text: str, 
                        document_type: Optional[str] = None) -> ExtractionResult:
        """
        Extract entities from document text.
        
        Args:
            document_id: Document identifier
            text: Document text content
            document_type: Type of document (for type-specific extraction)
            
        Returns:
            Extraction result
        """
        start_time = datetime.now()
        
        try:
            # Extract entities based on model type
            if self.config.model_type == "ml" and self.ml_model:
                entities = self._extract_with_ml(text, document_type)
            elif self.config.model_type == "rule_based":
                entities = self._extract_with_rules(text, document_type)
            else:  # hybrid
                entities = self._extract_hybrid(text, document_type)
            
            # Filter by confidence
            filtered_entities = [
                entity for entity in entities 
                if entity.confidence >= self.config.min_confidence
            ]
            
            # Normalize entities if enabled
            if self.config.normalize_entities:
                filtered_entities = self._normalize_entities(filtered_entities)
            
            # Count entities by category
            entity_categories = {}
            for entity in filtered_entities:
                entity_categories[entity.type] = entity_categories.get(entity.type, 0) + 1
            
            # Link entities if enabled
            entity_relationships = []
            if self.config.link_entities:
                entity_relationships = self._link_entities(filtered_entities, text)
            
            # Create result
            result = ExtractionResult(
                document_id=document_id,
                entities=filtered_entities,
                entity_categories=entity_categories,
                entity_relationships=entity_relationships,
                processing_time=(datetime.now() - start_time).total_seconds(),
                model=self.config.model_type
            )
            
            # Add warnings for low-confidence entities
            low_conf_entities = [e for e in entities if e.confidence < self.config.min_confidence]
            if low_conf_entities:
                result.warnings.append(f"{len(low_conf_entities)} entities filtered due to low confidence")
            
            logger.info(f"Extracted {len(filtered_entities)} entities from {document_id}")
            return result
            
        except Exception as e:
            logger.error(f"Entity extraction error for {document_id}: {str(e)}")
            
            return ExtractionResult(
                document_id=document_id,
                entities=[],
                processing_time=(datetime.now() - start_time).total_seconds(),
                errors=[str(e)],
                model="error"
            )
    
    def _extract_with_rules(self, text: str, document_type: Optional[str]) -> List[Entity]:
        """Extract entities using rule-based patterns."""
        entities = []
        
        # Apply patterns for each entity type
        for entity_type, pattern_list in self.patterns.items():
            if entity_type not in self.config.entity_types:
                continue
            
            for pattern_info in pattern_list:
                pattern = pattern_info["pattern"]
                base_confidence = pattern_info["confidence"]
                
                for match in re.finditer(pattern, text, re.IGNORECASE):
                    # Adjust confidence based on context
                    confidence = self._adjust_confidence(base_confidence, match.group(), entity_type, document_type)
                    
                    entity = Entity(
                        text=match.group(),
                        type=entity_type,
                        start=match.start(),
                        end=match.end(),
                        confidence=confidence
                    )
                    entities.append(entity)
        
        # Additional rule-based extraction for legal entities
        entities.extend(self._extract_legal_entities(text, document_type))
        
        # Remove overlapping entities (keep higher confidence)
        entities = self._remove_overlapping_entities(entities)
        
        return entities
    
    def _extract_legal_entities(self, text: str, document_type: Optional[str]) -> List[Entity]:
        """Extract legal-specific entities."""
        entities = []
        
        # Extract party names (common in contracts)
        if document_type in ["contract", "agreement"]:
            # Look for "Party A:", "Party B:" patterns
            party_pattern = r'(?:Party\s+[A-Z]|[\'"]([^"\']+)[\'"])\s*(?:\(.*?\))?\s*(?:,|\.|$)'
            for match in re.finditer(party_pattern, text, re.IGNORECASE):
                if match.group(1):  # Captured group for quoted names
                    entity_text = match.group(1)
                    entities.append(Entity(
                        text=entity_text,
                        type="PARTY",
                        start=match.start(1),
                        end=match.end(1),
                        confidence=0.7
                    ))
        
        # Extract clause references
        clause_pattern = r'(?:Section|Article|Clause)\s+([IVXLCDM]+|\d+[a-z]?)'
        for match in re.finditer(clause_pattern, text, re.IGNORECASE):
            entities.append(Entity(
                text=match.group(),
                type="CLAUSE",
                start=match.start(),
                end=match.end(),
                confidence=0.8
            ))
        
        # Extract legal terms
        legal_terms = {
            "indemnification": "TERM",
            "confidentiality": "TERM", 
            "termination": "TERM",
            "governing law": "TERM",
            "jurisdiction": "TERM",
            "arbitration": "TERM"
        }
        
        for term, entity_type in legal_terms.items():
            if term in text.lower():
                # Find all occurrences
                for match in re.finditer(re.escape(term), text, re.IGNORECASE):
                    entities.append(Entity(
                        text=match.group(),
                        type=entity_type,
                        start=match.start(),
                        end=match.end(),
                        confidence=0.6
                    ))
        
        return entities
    
    def _extract_with_ml(self, text: str, document_type: Optional[str]) -> List[Entity]:
        """Extract entities using ML model."""
        # Mock ML extraction
        # In production, would use actual NER model
        
        logger.warning("ML entity extraction not implemented, using rule-based")
        return self._extract_with_rules(text, document_type)
    
    def _extract_hybrid(self, text: str, document_type: Optional[str]) -> List[Entity]:
        """Extract entities using hybrid approach."""
        # Get rule-based entities
        rule_entities = self._extract_with_rules(text, document_type)
        
        # If ML model is available, combine results
        if self.ml_model:
            ml_entities = self._extract_with_ml(text, document_type)
            
            # Combine entities, preferring higher confidence
            all_entities = rule_entities + ml_entities
            all_entities = self._merge_entities(all_entities)
            
            return all_entities
        else:
            return rule_entities
    
    def _adjust_confidence(self, base_confidence: float, text: str, 
                          entity_type: str, document_type: Optional[str]) -> float:
        """Adjust confidence based on context."""
        confidence = base_confidence
        
        # Adjust based on entity type and document type
        if document_type == "contract":
            if entity_type in ["MONEY", "DATE", "PARTY"]:
                confidence *= 1.1  # Higher confidence in contracts
            elif entity_type == "LAW":
                confidence *= 0.9  # Slightly lower for laws in contracts
        
        elif document_type == "pleading":
            if entity_type in ["CASE", "COURT", "JUDGE"]:
                confidence *= 1.2  # Much higher in pleadings
        
        # Adjust based on text quality
        if len(text.strip()) < 2:
            confidence *= 0.5  # Very short entities are less reliable
        
        # Cap at 1.0
        return min(confidence, 1.0)
    
    def _normalize_entities(self, entities: List[Entity]) -> List[Entity]:
        """Normalize entity text."""
        normalized = []
        
        for entity in entities:
            normalized_entity = Entity(
                text=entity.text.strip(),
                type=entity.type,
                start=entity.start,
                end=entity.end,
                confidence=entity.confidence,
                metadata=entity.metadata.copy()
            )
            
            # Normalize based on entity type
            if entity.type == "DATE":
                # Try to standardize date format
                normalized_entity.metadata["normalized"] = self._normalize_date(entity.text)
            
            elif entity.type == "MONEY":
                # Extract numeric value
                match = re.search(r'[\d,]+\.?\d*', entity.text)
                if match:
                    value_str = match.group().replace(',', '')
                    try:
                        value = float(value_str)
                        normalized_entity.metadata["value"] = value
                        normalized_entity.metadata["currency"] = "USD" if '$' in entity.text else "unknown"
                    except:
                        pass
            
            elif entity.type == "PERCENT":
                # Extract numeric value
                match = re.search(r'[\d.]+', entity.text)
                if match:
                    try:
                        value = float(match.group())
                        normalized_entity.metadata["value"] = value
                    except:
                        pass
            
            normalized.append(normalized_entity)
        
        return normalized
    
    def _normalize_date(self, date_str: str) -> Optional[str]:
        """Normalize date string to ISO format."""
        try:
            # Simple normalization for common formats
            # In production, would use dateutil or similar
            
            # MM/DD/YYYY or DD/MM/YYYY
            if '/' in date_str:
                parts = date_str.split('/')
                if len(parts) == 3:
                    if len(parts[2]) == 2:  # YY format
                        parts[2] = '20' + parts[2] if int(parts[2]) < 50 else '19' + parts[2]
                    return f"{parts[2]}-{parts[0].zfill(2)}-{parts[1].zfill(2)}"
            
            # YYYY-MM-DD
            if re.match(r'\d{4}-\d{2}-\d{2}', date_str):
                return date_str
            
            # Month name format
            month_map = {
                'january': '01', 'february': '02', 'march': '03', 'april': '04',
                'may': '05', 'june': '06', 'july': '07', 'august': '08',
                'september': '09', 'october': '10', 'november': '11', 'december': '12',
                'jan': '01', 'feb': '02', 'mar': '03', 'apr': '04',
                'jun': '06', 'jul': '07', 'aug': '08', 'sep': '09',
                'oct': '10', 'nov': '11', 'dec': '12'
            }
            
            for month_name, month_num in month_map.items():
                if month_name in date_str.lower():
                    # Extract year and day
                    year_match = re.search(r'\d{4}', date_str)
                    day_match = re.search(r'\b\d{1,2}\b', date_str)
                    
                    if year_match and day_match:
                        year = year_match.group()
                        day = day_match.group().zfill(2)
                        return f"{year}-{month_num}-{day}"
            
        except:
            pass
        
        return None
    
    def _remove_overlapping_entities(self, entities: List[Entity]) -> List[Entity]:
        """Remove overlapping entities, keeping higher confidence ones."""
        if not entities:
            return []
        
        # Sort by start position
        entities.sort(key=lambda e: e.start)
        
        filtered = []
        current = entities[0]
        
        for i in range(1, len(entities)):
            next_entity = entities[i]
            
            # Check for overlap
            if next_entity.start < current.end:
                # Overlap detected, keep higher confidence
                if next_entity.confidence > current.confidence:
                    current = next_entity
            else:
                # No overlap, add current and move to next
                filtered.append(current)
                current = next_entity
        
        # Add the last entity
        filtered.append(current)
        
        return filtered
    
    def _merge_entities(self, entities: List[Entity]) -> List[Entity]:
        """Merge duplicate or similar entities."""
        if not entities:
            return []
        
        # Group by text and type
        entity_map = {}
        
        for entity in entities:
            key = (entity.text.lower(), entity.type)
            
            if key not in entity_map:
                entity_map[key] = entity
            else:
                # Merge: keep higher confidence, combine metadata
                existing = entity_map[key]
                if entity.confidence > existing.confidence:
                    entity_map[key] = entity
        
        return list(entity_map.values())
    
    def _link_entities(self, entities: List[Entity], text: str) -> List[Dict[str, Any]]:
        """Link related entities."""
        relationships = []
        
        # Sort entities by position
        sorted_entities = sorted(entities, key=lambda e: e.start)
        
        # Look for relationships based on proximity
        for i, entity1 in enumerate(sorted_entities):
            for j, entity2 in enumerate(sorted_entities[i+1:], start=i+1):
                # Check if entities are close in text
                distance = entity2.start - entity1.end
                
                if 0 <= distance <= 100:  # Within 100 characters
                    # Determine relationship type based on entity types
                    rel_type = self._determine_relationship(entity1.type, entity2.type)
                    
                    if rel_type:
                        relationships.append({
                            "entity1": entity1.text,
                            "entity1_type": entity1.type,
                            "entity2": entity2.text,
                            "entity2_type": entity2.type,
                            "relationship": rel_type,
                            "distance": distance,
                            "confidence": min(entity1.confidence, entity2.confidence) * 0.8
                        })
        
        return relationships
    
    def _determine_relationship(self, type1: str, type2: str) -> Optional[str]:
        """Determine relationship between entity types."""
        relationship_map = {
            ("DATE", "MONEY"): "payment_date",
            ("PARTY", "MONEY"): "party_payment",
            ("PARTY", "DATE"): "party_date",
            ("ORGANIZATION", "MONEY"): "organization_payment",
            ("LAW", "CASE"): "law_cited_in_case",
            ("CASE", "COURT"): "case_in_court",
        }
        
        # Check both orders
        if (type1, type2) in relationship_map:
            return relationship_map[(type1, type2)]
        elif (type2, type1) in relationship_map:
            return relationship_map[(type2, type1)]
        
        return None
    
    def get_extractor_info(self) -> Dict[str, Any]:
        """Get information about the extractor."""
        return {
            "model_type": self.config.model_type,
            "entity_types": self.config.entity_types,
            "min_confidence": self.config.min_confidence,
            "link_entities": self.config.link_entities,
            "normalize_entities": self.config.normalize_entities,
            "ml_model_loaded": self.ml_model is not None,
            "pattern_count": sum(len(patterns) for patterns in self.patterns.values())
        }


def test_entity_extractor():
    """Test function for Entity Extractor."""
    print("Testing Entity Extractor...")
    
    # Create extractor
    config = ExtractorConfig(
        model_type="hybrid",
        entity_types=["DATE", "MONEY", "PERCENT", "LAW", "PARTY", "TERM"],
        min_confidence=0.7,
        link_entities=True
    )
    
    extractor = EntityExtractor(config)
    
    # Get extractor info
    info = extractor.get_extractor_info()
    print(f"Extractor info: {info}")
    
    # Test 1: Contract document
    print("\n1. Testing contract entity extraction...")
    
    contract_text = """EMPLOYMENT AGREEMENT
    
This Agreement is made on January 15, 2024 between:
Party A: ABC Corporation (the "Employer")
Party B: John Smith (the "Employee")
    
1. TERM: Employment shall commence on January 15, 2024.
2. COMPENSATION: Employee shall receive $100,000 annual salary.
3. BONUS: Employee may receive up to 20% bonus based on performance.
4. CONFIDENTIALITY: Employee agrees to maintain confidentiality.
5. GOVERNING LAW: This Agreement is governed by California law.
    
Contact: john.smith@email.com, Phone: (555) 123-4567"""
    
    result = extractor.extract_entities(
        document_id="test_contract_001",
        text=contract_text,
        document_type="contract"
    )
    
    print(f"Contract entities extracted: {len(result.entities)}")
    print(f"Entity categories: {result.entity_categories}")
    print(f"Relationships found: {len(result.entity_relationships)}")
    
    # Show sample entities
    print("\nSample entities:")
    for entity in result.entities[:5]:  # Show first 5
        print(f"  {entity.text} ({entity.type}, confidence: {entity.confidence:.2f})")
    
    # Test 2: Legal document with citations
    print("\n2. Testing legal citation extraction...")
    
    legal_text = """In Smith v. Jones, 123 F.3d 456 (2023), the court interpreted 42 U.S.C. § 2000e.
The decision was rendered on March 10, 2023. The plaintiff sought $1,000,000 in damages.
The court applied the standard from Brown v. Board, 347 U.S. 483 (1954)."""
    
    result = extractor.extract_entities(
        document_id="test_legal_001",
        text=legal_text,
        document_type="pleading"
    )
    
    print(f"Legal entities extracted: {len(result.entities)}")
    print(f"Entity categories: {result.entity_categories}")
    
    # Show LAW and CASE entities
    print("\nLegal entities:")
    for entity in result.entities:
        if entity.type in ["LAW", "CASE"]:
            print(f"  {entity.text} ({entity.type}, confidence: {entity.confidence:.2f})")
    
    # Test 3: Simple text
    print("\n3. Testing simple text extraction...")
    
    simple_text = """Meeting on 2024-03-15 to discuss budget of $50,000.
Contact: info@company.com, Phone: 555-987-6543."""
    
    result = extractor.extract_entities(
        document_id="test_simple_001",
        text=simple_text,
        document_type=None
    )
    
    print(f"Simple entities extracted: {len(result.entities)}")
    print(f"Entity categories: {result.entity_categories}")
    
    print("\nEntity Extractor test completed successfully!")


if __name__ == "__main__":
    test_entity_extractor()