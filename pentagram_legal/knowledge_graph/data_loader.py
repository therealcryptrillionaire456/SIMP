"""
Data loader for Legal Knowledge Graph.
Loads legal data from various sources into the knowledge graph.
"""

import sys
import os
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
import json
import csv
import logging
from pathlib import Path
import uuid

# Add project root to path for imports
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

from knowledge_graph.legal_knowledge_graph import (
    LegalKnowledgeGraph, GraphNode, GraphRelationship,
    NodeType, RelationshipType, CitationStrength
)
from knowledge_graph.config import (
    get_node_definition, get_relationship_definition,
    validate_node_type, validate_relationship_type
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class LegalDataLoader:
    """
    Loader for legal data into the knowledge graph.
    Supports multiple data formats and sources.
    """
    
    def __init__(self, graph: LegalKnowledgeGraph):
        """
        Initialize Legal Data Loader.
        
        Args:
            graph: LegalKnowledgeGraph instance
        """
        self.graph = graph
        self.load_stats = {
            "nodes_loaded": 0,
            "relationships_loaded": 0,
            "errors": 0,
            "warnings": 0,
            "sources_processed": 0
        }
        
        # Source mappings
        self.source_mappings = self._initialize_source_mappings()
        
        logger.info("Initialized Legal Data Loader")
    
    def _initialize_source_mappings(self) -> Dict[str, Dict[str, Any]]:
        """Initialize source to node/relationship type mappings."""
        return {
            "pacer": {
                "case": NodeType.CASE,
                "relationship_types": {
                    "cites": RelationshipType.CITES,
                    "precedent": RelationshipType.PRECEDENT,
                    "overrules": RelationshipType.OVERRULES,
                    "distinguishes": RelationshipType.DISTINGUISHES
                }
            },
            "sec_edgar": {
                "filing": NodeType.DOCUMENT,
                "company": NodeType.ORGANIZATION,
                "relationship_types": {
                    "files": RelationshipType.RELATED_TO,
                    "references": RelationshipType.REFERENCES
                }
            },
            "uspto": {
                "patent": NodeType.DOCUMENT,
                "application": NodeType.DOCUMENT,
                "relationship_types": {
                    "cites": RelationshipType.CITES,
                    "related_to": RelationshipType.RELATED_TO
                }
            },
            "courtlistener": {
                "case": NodeType.CASE,
                "opinion": NodeType.DOCUMENT,
                "relationship_types": {
                    "cites": RelationshipType.CITES,
                    "precedent": RelationshipType.PRECEDENT
                }
            },
            "open_states": {
                "statute": NodeType.STATUTE,
                "bill": NodeType.DOCUMENT,
                "relationship_types": {
                    "amends": RelationshipType.AMENDS,
                    "cites": RelationshipType.CITES
                }
            },
            "contracts": {
                "contract": NodeType.CONTRACT,
                "clause": NodeType.CLAUSE,
                "relationship_types": {
                    "contains": RelationshipType.CONTAINS,
                    "references": RelationshipType.REFERENCES
                }
            }
        }
    
    def load_json_file(self, file_path: str, source_type: str = "generic") -> Dict[str, Any]:
        """
        Load data from JSON file.
        
        Args:
            file_path: Path to JSON file
            source_type: Type of data source
            
        Returns:
            Load statistics
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            if isinstance(data, list):
                return self.load_json_array(data, source_type)
            elif isinstance(data, dict):
                return self.load_json_object(data, source_type)
            else:
                logger.error(f"Unsupported JSON structure in {file_path}")
                return {"error": "Unsupported JSON structure"}
                
        except Exception as e:
            logger.error(f"Error loading JSON file {file_path}: {str(e)}")
            self.load_stats["errors"] += 1
            return {"error": str(e)}
    
    def load_json_array(self, data_array: List[Dict[str, Any]], source_type: str) -> Dict[str, Any]:
        """
        Load data from JSON array.
        
        Args:
            data_array: Array of JSON objects
            source_type: Type of data source
            
        Returns:
            Load statistics
        """
        start_time = datetime.now()
        
        for item in data_array:
            try:
                self._process_data_item(item, source_type)
            except Exception as e:
                logger.warning(f"Error processing item: {str(e)}")
                self.load_stats["errors"] += 1
        
        elapsed = (datetime.now() - start_time).total_seconds()
        self.load_stats["sources_processed"] += 1
        
        logger.info(f"Loaded {len(data_array)} items from {source_type} in {elapsed:.2f}s")
        return self._get_load_summary()
    
    def load_json_object(self, data_object: Dict[str, Any], source_type: str) -> Dict[str, Any]:
        """
        Load data from JSON object.
        
        Args:
            data_object: JSON object
            source_type: Type of data source
            
        Returns:
            Load statistics
        """
        start_time = datetime.now()
        
        try:
            self._process_data_item(data_object, source_type)
        except Exception as e:
            logger.error(f"Error processing object: {str(e)}")
            self.load_stats["errors"] += 1
        
        elapsed = (datetime.now() - start_time).total_seconds()
        self.load_stats["sources_processed"] += 1
        
        logger.info(f"Loaded object from {source_type} in {elapsed:.2f}s")
        return self._get_load_summary()
    
    def load_csv_file(self, file_path: str, source_type: str = "generic") -> Dict[str, Any]:
        """
        Load data from CSV file.
        
        Args:
            file_path: Path to CSV file
            source_type: Type of data source
            
        Returns:
            Load statistics
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                data = list(reader)
            
            return self.load_csv_data(data, source_type)
                
        except Exception as e:
            logger.error(f"Error loading CSV file {file_path}: {str(e)}")
            self.load_stats["errors"] += 1
            return {"error": str(e)}
    
    def load_csv_data(self, data: List[Dict[str, str]], source_type: str) -> Dict[str, Any]:
        """
        Load data from CSV records.
        
        Args:
            data: List of CSV records as dictionaries
            source_type: Type of data source
            
        Returns:
            Load statistics
        """
        start_time = datetime.now()
        
        for record in data:
            try:
                self._process_csv_record(record, source_type)
            except Exception as e:
                logger.warning(f"Error processing CSV record: {str(e)}")
                self.load_stats["errors"] += 1
        
        elapsed = (datetime.now() - start_time).total_seconds()
        self.load_stats["sources_processed"] += 1
        
        logger.info(f"Loaded {len(data)} records from {source_type} CSV in {elapsed:.2f}s")
        return self._get_load_summary()
    
    def load_from_directory(self, directory_path: str, 
                          file_pattern: str = "*.json",
                          source_type: str = "generic") -> Dict[str, Any]:
        """
        Load data from all files in a directory.
        
        Args:
            directory_path: Path to directory
            file_pattern: File pattern to match
            source_type: Type of data source
            
        Returns:
            Load statistics
        """
        directory = Path(directory_path)
        if not directory.exists():
            logger.error(f"Directory not found: {directory_path}")
            return {"error": "Directory not found"}
        
        files = list(directory.glob(file_pattern))
        if not files:
            logger.warning(f"No files found matching {file_pattern} in {directory_path}")
            return {"warning": "No files found"}
        
        start_time = datetime.now()
        total_items = 0
        
        for file_path in files:
            try:
                if file_pattern.endswith(".json"):
                    result = self.load_json_file(str(file_path), source_type)
                elif file_pattern.endswith(".csv"):
                    result = self.load_csv_file(str(file_path), source_type)
                else:
                    logger.warning(f"Unsupported file type: {file_path}")
                    continue
                
                if "items_loaded" in result:
                    total_items += result["items_loaded"]
                    
            except Exception as e:
                logger.error(f"Error loading file {file_path}: {str(e)}")
                self.load_stats["errors"] += 1
        
        elapsed = (datetime.now() - start_time).total_seconds()
        
        logger.info(f"Loaded {total_items} items from {len(files)} files in {elapsed:.2f}s")
        return {
            "files_processed": len(files),
            "total_items": total_items,
            **self._get_load_summary()
        }
    
    def _process_data_item(self, item: Dict[str, Any], source_type: str):
        """Process a data item based on source type."""
        if source_type in self.source_mappings:
            mapping = self.source_mappings[source_type]
            self._process_with_mapping(item, mapping, source_type)
        else:
            self._process_generic_item(item, source_type)
    
    def _process_with_mapping(self, item: Dict[str, Any], 
                            mapping: Dict[str, Any], 
                            source_type: str):
        """Process item using source-specific mapping."""
        # Determine node type
        node_type = None
        for key, mapped_type in mapping.items():
            if key in item.get("type", "").lower():
                node_type = mapped_type
                break
        
        if not node_type and "default_type" in mapping:
            node_type = mapping["default_type"]
        
        if not node_type:
            logger.warning(f"Cannot determine node type for item from {source_type}")
            self.load_stats["warnings"] += 1
            return
        
        # Create node
        node_id = item.get("id", f"{source_type}_{uuid.uuid4().hex[:16]}")
        label = item.get("title", item.get("name", f"{source_type} item"))
        
        node = GraphNode(
            node_id=node_id,
            node_type=node_type,
            label=label,
            properties=self._extract_properties(item, node_type),
            source=source_type,
            confidence=item.get("confidence", 0.8)
        )
        
        if self.graph.add_node(node):
            self.load_stats["nodes_loaded"] += 1
            
            # Process relationships if specified
            if "relationships" in item:
                self._process_relationships(item["relationships"], node_id, mapping, source_type)
    
    def _process_generic_item(self, item: Dict[str, Any], source_type: str):
        """Process generic data item."""
        # Try to infer node type from item properties
        node_type = self._infer_node_type(item)
        
        if not node_type:
            logger.warning(f"Cannot infer node type for generic item")
            self.load_stats["warnings"] += 1
            return
        
        # Create node
        node_id = item.get("id", f"generic_{uuid.uuid4().hex[:16]}")
        label = item.get("title", item.get("name", item.get("label", "Generic item")))
        
        node = GraphNode(
            node_id=node_id,
            node_type=node_type,
            label=label,
            properties=self._extract_properties(item, node_type),
            source=source_type,
            confidence=item.get("confidence", 0.7)
        )
        
        if self.graph.add_node(node):
            self.load_stats["nodes_loaded"] += 1
    
    def _process_csv_record(self, record: Dict[str, str], source_type: str):
        """Process CSV record."""
        # Convert CSV record to appropriate format
        item = {}
        for key, value in record.items():
            if value:
                # Try to parse JSON values
                if value.startswith('{') or value.startswith('['):
                    try:
                        item[key] = json.loads(value)
                    except:
                        item[key] = value
                else:
                    item[key] = value
        
        # Add type based on source
        item["type"] = source_type
        
        self._process_data_item(item, source_type)
    
    def _process_relationships(self, relationships_data: List[Dict[str, Any]], 
                             source_node_id: str,
                             mapping: Dict[str, Any],
                             source_type: str):
        """Process relationships from data."""
        relationship_mappings = mapping.get("relationship_types", {})
        
        for rel_data in relationships_data:
            try:
                rel_type_name = rel_data.get("type", "related_to")
                target_node_id = rel_data.get("target_id")
                
                # Get mapped relationship type
                rel_type = relationship_mappings.get(rel_type_name, RelationshipType.RELATED_TO)
                
                # Check if target node exists
                target_node = self.graph.get_node(target_node_id)
                if not target_node:
                    logger.warning(f"Target node {target_node_id} not found for relationship")
                    continue
                
                # Create relationship
                relationship = GraphRelationship(
                    relationship_id=f"rel_{uuid.uuid4().hex[:16]}",
                    source_node_id=source_node_id,
                    target_node_id=target_node_id,
                    relationship_type=rel_type,
                    properties=rel_data.get("properties", {}),
                    strength=CitationStrength(rel_data.get("strength", "moderate")),
                    confidence=rel_data.get("confidence", 0.8)
                )
                
                if self.graph.add_relationship(relationship):
                    self.load_stats["relationships_loaded"] += 1
                    
            except Exception as e:
                logger.warning(f"Error processing relationship: {str(e)}")
                self.load_stats["warnings"] += 1
    
    def _infer_node_type(self, item: Dict[str, Any]) -> Optional[NodeType]:
        """Infer node type from item properties."""
        item_type = item.get("type", "").lower()
        title = item.get("title", "").lower()
        content = item.get("content", "").lower()
        
        # Check for statute indicators
        if any(word in item_type for word in ["statute", "law", "act", "code"]):
            return NodeType.STATUTE
        if any(word in title for word in ["statute", "law", "act", "code", "usc", "cfr"]):
            return NodeType.STATUTE
        
        # Check for case indicators
        if any(word in item_type for word in ["case", "decision", "opinion", "ruling"]):
            return NodeType.CASE
        if any(word in title for word in ["v.", "vs.", "versus", "appeal", "supreme court"]):
            return NodeType.CASE
        
        # Check for regulation indicators
        if any(word in item_type for word in ["regulation", "rule", "directive"]):
            return NodeType.REGULATION
        if any(word in title for word in ["regulation", "rule", "directive", "cfr"]):
            return NodeType.REGULATION
        
        # Check for contract indicators
        if any(word in item_type for word in ["contract", "agreement", "license"]):
            return NodeType.CONTRACT
        if any(word in title for word in ["contract", "agreement", "license", "nda"]):
            return NodeType.CONTRACT
        
        # Check for entity indicators
        if any(word in item_type for word in ["entity", "company", "organization", "person"]):
            if "person" in item_type or "individual" in item_type:
                return NodeType.PERSON
            else:
                return NodeType.ORGANIZATION
        
        # Default to document
        return NodeType.DOCUMENT
    
    def _extract_properties(self, item: Dict[str, Any], node_type: NodeType) -> Dict[str, Any]:
        """Extract properties from data item based on node type."""
        properties = {}
        
        # Common properties
        common_fields = ["id", "title", "name", "description", "date", "year", 
                        "author", "source", "url", "jurisdiction", "confidence"]
        
        for field in common_fields:
            if field in item and item[field] is not None:
                properties[field] = item[field]
        
        # Type-specific properties
        if node_type == NodeType.STATUTE:
            type_fields = ["section", "chapter", "code", "effective_date", "repealed", 
                          "amended", "citation", "legislative_body"]
        elif node_type == NodeType.CASE:
            type_fields = ["court", "docket_number", "citation", "decision_date", 
                          "judge", "topic", "outcome", "holding"]
        elif node_type == NodeType.REGULATION:
            type_fields = ["agency", "part", "section", "effective_date", "docket_number", 
                          "citation", "compliance_date"]
        elif node_type == NodeType.CONTRACT:
            type_fields = ["parties", "effective_date", "expiration_date", "value", 
                          "type", "governing_law", "termination_clause"]
        elif node_type == NodeType.CLAUSE:
            type_fields = ["contract_id", "type", "content", "effective_date", "amended", 
                          "importance", "enforceability"]
        elif node_type in [NodeType.ENTITY, NodeType.ORGANIZATION]:
            type_fields = ["type", "registration_number", "address", "contact", 
                          "industry", "size", "founding_date"]
        elif node_type == NodeType.PERSON:
            type_fields = ["title", "organization", "contact", "expertise", "role", 
                          "qualifications", "affiliations"]
        elif node_type == NodeType.JURISDICTION:
            type_fields = ["type", "country", "region", "code", "court_system", 
                          "legal_system", "language"]
        elif node_type == NodeType.COURT:
            type_fields = ["level", "address", "website", "phone", "type", 
                          "jurisdiction", "judges"]
        elif node_type == NodeType.AGENCY:
            type_fields = ["acronym", "website", "address", "authority", "mission", 
                          "regulations", "contact"]
        elif node_type == NodeType.LEGAL_CONCEPT:
            type_fields = ["origin", "related_concepts", "examples", "application", 
                          "evolution", "criticism"]
        elif node_type == NodeType.PRECEDENT:
            type_fields = ["source_case", "principle", "strength", "application", 
                          "jurisdiction", "limitations"]
        elif node_type == NodeType.AMENDMENT:
            type_fields = ["target_document", "version", "changes", "effective_date", 
                          "rationale", "impact"]
        else:  # DOCUMENT or generic
            type_fields = ["type", "format", "status", "recipient", "language", 
                          "pages", "keywords"]
        
        for field in type_fields:
            if field in item and item[field] is not None:
                properties[field] = item[field]
        
        # Add any remaining fields that aren't already captured
        for key, value in item.items():
            if key not in properties and key not in ["id", "type", "relationships", "confidence"]:
                if value is not None:
                    properties[key] = value
        
        return properties
    
    def _get_load_summary(self) -> Dict[str, Any]:
        """Get summary of load statistics."""
        return {
            "nodes_loaded": self.load_stats["nodes_loaded"],
            "relationships_loaded": self.load_stats["relationships_loaded"],
            "errors": self.load_stats["errors"],
            "warnings": self.load_stats["warnings"],
            "sources_processed": self.load_stats["sources_processed"],
            "timestamp": datetime.now().isoformat()
        }
    
    def reset_stats(self):
        """Reset load statistics."""
        self.load_stats = {
            "nodes_loaded": 0,
            "relationships_loaded": 0,
            "errors": 0,
            "warnings": 0,
            "sources_processed": 0
        }
    
    def get_load_statistics(self) -> Dict[str, Any]:
        """Get current load statistics."""
        return self._get_load_summary()


def test_data_loader():
    """Test function for Legal Data Loader."""
    print("Testing Legal Data Loader...")
    
    # Create graph instance
    graph = LegalKnowledgeGraph("test_graph")
    
    # Create data loader
    loader = LegalDataLoader(graph)
    
    # Test 1: Load sample statute data
    print("\n1. Testing statute data loading...")
    
    statute_data = {
        "id": "statute_001",
        "type": "statute",
        "title": "Civil Rights Act of 1964",
        "year": 1964,
        "jurisdiction": "US",
        "section": "Title VII",
        "description": "Prohibits employment discrimination",
        "confidence": 0.95
    }
    
    result = loader.load_json_object(statute_data, "open_states")
    print(f"Statute loaded: {result}")
    
    # Test 2: Load sample case data
    print("\n2. Testing case data loading...")
    
    case_data = {
        "id": "case_001",
        "type": "case",
        "title": "Griggs v. Duke Power Co.",
        "year": 1971,
        "court": "US Supreme Court",
        "citation": "401 U.S. 424",
        "topic": "Employment Discrimination",
        "relationships": [
            {
                "type": "interprets",
                "target_id": "statute_001",
                "properties": {
                    "interpretation": "Established disparate impact theory",
                    "significance": "landmark"
                },
                "strength": "strong",
                "confidence": 0.9
            }
        ]
    }
    
    result = loader.load_json_object(case_data, "pacer")
    print(f"Case loaded: {result}")
    
    # Test 3: Load sample contract data
    print("\n3. Testing contract data loading...")
    
    contract_data = {
        "id": "contract_001",
        "type": "contract",
        "title": "Employment Agreement",
        "parties": ["Company Inc.", "John Doe"],
        "effective_date": "2024-01-01",
        "value": 100000,
        "governing_law": "California"
    }
    
    result = loader.load_json_object(contract_data, "contracts")
    print(f"Contract loaded: {result}")
    
    # Test 4: Get final statistics
    print("\n4. Getting final statistics...")
    
    stats = loader.get_load_statistics()
    print(f"Final load statistics: {stats}")
    
    # Test 5: Check graph statistics
    print("\n5. Checking graph statistics...")
    
    graph_stats = graph.get_statistics()
    print(f"Graph statistics: {graph_stats['statistics']}")
    
    print("\nLegal Data Loader test completed successfully!")


if __name__ == "__main__":
    test_data_loader()