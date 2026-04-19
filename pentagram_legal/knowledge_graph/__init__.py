"""
Legal Knowledge Graph Engine Package.
"""

from knowledge_graph.legal_knowledge_graph import (
    LegalKnowledgeGraph, GraphNode, GraphRelationship,
    NodeType, RelationshipType, CitationStrength
)

from knowledge_graph.config import (
    get_config, validate_node_type, validate_relationship_type,
    get_node_definition, get_relationship_definition,
    get_citation_strength_definition, get_query_template
)

from knowledge_graph.data_loader import LegalDataLoader

__version__ = "1.0.0"
__author__ = "Pentagram Legal Department"
__description__ = "Legal Knowledge Graph Engine for storing and querying legal relationships"

__all__ = [
    # Main classes
    "LegalKnowledgeGraph",
    "GraphNode",
    "GraphRelationship",
    "LegalDataLoader",
    
    # Enums
    "NodeType",
    "RelationshipType",
    "CitationStrength",
    
    # Configuration functions
    "get_config",
    "validate_node_type",
    "validate_relationship_type",
    "get_node_definition",
    "get_relationship_definition",
    "get_citation_strength_definition",
    "get_query_template"
]