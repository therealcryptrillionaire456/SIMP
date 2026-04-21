"""
Configuration for Legal Knowledge Graph Engine.
"""

from typing import Dict, Any
from enum import Enum


class GraphBackend(Enum):
    """Supported graph database backends."""
    IN_MEMORY = "in_memory"
    NEO4J = "neo4j"
    JANUSGRAPH = "janusgraph"
    NEBULA = "nebula"
    TIGERGRAPH = "tigergraph"


class IndexType(Enum):
    """Types of indexes to maintain."""
    NODE_TYPE = "node_type"
    RELATIONSHIP_TYPE = "relationship_type"
    PROPERTY = "property"
    FULL_TEXT = "full_text"
    SPATIAL = "spatial"
    TEMPORAL = "temporal"


class CachePolicy(Enum):
    """Cache policies for query results."""
    LRU = "lru"  # Least Recently Used
    LFU = "lfu"  # Least Frequently Used
    FIFO = "fifo"  # First In First Out
    MRU = "mru"  # Most Recently Used


# Default configuration
DEFAULT_CONFIG: Dict[str, Any] = {
    # Graph settings
    "graph_name": "legal_knowledge_graph",
    "backend": GraphBackend.IN_MEMORY.value,
    "persistence": {
        "enabled": True,
        "auto_save": True,
        "save_interval_seconds": 300,  # 5 minutes
        "backup_count": 10,
        "compression": True
    },
    
    # Performance settings
    "cache": {
        "enabled": True,
        "policy": CachePolicy.LRU.value,
        "max_size": 10000,
        "ttl_seconds": 3600  # 1 hour
    },
    
    # Index settings
    "indexes": {
        IndexType.NODE_TYPE.value: True,
        IndexType.RELATIONSHIP_TYPE.value: True,
        IndexType.PROPERTY.value: True,
        IndexType.FULL_TEXT.value: False,
        IndexType.SPATIAL.value: False,
        IndexType.TEMPORAL.value: True
    },
    
    # Query settings
    "query": {
        "timeout_seconds": 30,
        "max_results": 1000,
        "enable_explain": True,
        "enable_profile": False
    },
    
    # Import/Export settings
    "import_export": {
        "default_format": "json",
        "supported_formats": ["json", "graphml", "csv", "rdf"],
        "batch_size": 1000,
        "validation": True
    },
    
    # Monitoring settings
    "monitoring": {
        "enabled": True,
        "metrics_interval_seconds": 60,
        "log_queries": True,
        "log_level": "INFO"
    },
    
    # Security settings
    "security": {
        "encryption": False,
        "access_control": False,
        "audit_logging": True
    },
    
    # Schema settings
    "schema": {
        "strict_validation": False,
        "allow_unknown_properties": True,
        "versioning": True
    }
}


# Neo4j specific configuration
NEO4J_CONFIG: Dict[str, Any] = {
    "uri": "bolt://localhost:7687",
    "username": "neo4j",
    "password": "password",
    "database": "legal_graph",
    "encrypted": False,
    "max_connection_lifetime": 3600,
    "max_connection_pool_size": 50,
    "connection_acquisition_timeout": 60,
    "connection_timeout": 30
}


# JanusGraph specific configuration
JANUSGRAPH_CONFIG: Dict[str, Any] = {
    "storage_backend": "cql",
    "storage_hostname": "localhost",
    "storage_port": 9042,
    "index_backend": "elasticsearch",
    "index_hostname": "localhost",
    "index_port": 9200,
    "cache": {
        "cache_db": True,
        "cache_tx": True
    }
}


# Node type definitions
NODE_TYPE_DEFINITIONS: Dict[str, Dict[str, Any]] = {
    "statute": {
        "description": "Legislative statute or act",
        "required_properties": ["title", "jurisdiction", "year"],
        "optional_properties": ["section", "chapter", "code", "effective_date", "repealed"],
        "indexed_properties": ["title", "jurisdiction", "year", "code"],
        "default_labels": ["Law", "Statute"]
    },
    "regulation": {
        "description": "Administrative regulation or rule",
        "required_properties": ["agency", "title", "effective_date"],
        "optional_properties": ["section", "part", "docket_number", "citation"],
        "indexed_properties": ["agency", "title", "effective_date"],
        "default_labels": ["Regulation", "Rule"]
    },
    "case": {
        "description": "Judicial case or decision",
        "required_properties": ["title", "court", "year", "citation"],
        "optional_properties": ["docket_number", "decision_date", "topic", "outcome"],
        "indexed_properties": ["title", "court", "year", "citation", "topic"],
        "default_labels": ["Case", "Decision", "Precedent"]
    },
    "contract": {
        "description": "Legal contract or agreement",
        "required_properties": ["title", "parties", "effective_date"],
        "optional_properties": ["expiration_date", "value", "jurisdiction", "type"],
        "indexed_properties": ["title", "parties", "effective_date", "type"],
        "default_labels": ["Contract", "Agreement"]
    },
    "clause": {
        "description": "Contract clause or provision",
        "required_properties": ["title", "contract_id"],
        "optional_properties": ["type", "content", "effective_date", "amended"],
        "indexed_properties": ["title", "type", "contract_id"],
        "default_labels": ["Clause", "Provision"]
    },
    "entity": {
        "description": "Legal entity (person or organization)",
        "required_properties": ["name", "type"],
        "optional_properties": ["jurisdiction", "registration_number", "address", "contact"],
        "indexed_properties": ["name", "type", "jurisdiction"],
        "default_labels": ["Entity"]
    },
    "jurisdiction": {
        "description": "Legal jurisdiction",
        "required_properties": ["name", "type"],
        "optional_properties": ["country", "region", "code", "court_system"],
        "indexed_properties": ["name", "type", "country"],
        "default_labels": ["Jurisdiction"]
    },
    "court": {
        "description": "Court or tribunal",
        "required_properties": ["name", "jurisdiction", "level"],
        "optional_properties": ["address", "website", "phone", "type"],
        "indexed_properties": ["name", "jurisdiction", "level"],
        "default_labels": ["Court", "Tribunal"]
    },
    "agency": {
        "description": "Government agency or department",
        "required_properties": ["name", "jurisdiction", "type"],
        "optional_properties": ["acronym", "website", "address", "authority"],
        "indexed_properties": ["name", "jurisdiction", "type", "acronym"],
        "default_labels": ["Agency", "Department"]
    },
    "legal_concept": {
        "description": "Legal concept or doctrine",
        "required_properties": ["name", "description"],
        "optional_properties": ["origin", "related_concepts", "examples"],
        "indexed_properties": ["name", "description"],
        "default_labels": ["Concept", "Doctrine", "Principle"]
    },
    "precedent": {
        "description": "Legal precedent",
        "required_properties": ["name", "source_case", "principle"],
        "optional_properties": ["strength", "jurisdiction", "application"],
        "indexed_properties": ["name", "principle", "source_case"],
        "default_labels": ["Precedent", "Authority"]
    },
    "amendment": {
        "description": "Amendment to a legal document",
        "required_properties": ["target_document", "date", "description"],
        "optional_properties": ["version", "effective_date", "changes"],
        "indexed_properties": ["target_document", "date", "description"],
        "default_labels": ["Amendment", "Revision"]
    },
    "document": {
        "description": "General legal document",
        "required_properties": ["title", "type", "date"],
        "optional_properties": ["author", "recipient", "status", "format"],
        "indexed_properties": ["title", "type", "date", "author"],
        "default_labels": ["Document"]
    },
    "person": {
        "description": "Individual person",
        "required_properties": ["name", "type"],
        "optional_properties": ["title", "organization", "contact", "expertise"],
        "indexed_properties": ["name", "type", "organization"],
        "default_labels": ["Person", "Individual"]
    },
    "organization": {
        "description": "Organization or company",
        "required_properties": ["name", "type"],
        "optional_properties": ["industry", "size", "founding_date", "location"],
        "indexed_properties": ["name", "type", "industry"],
        "default_labels": ["Organization", "Company", "Firm"]
    }
}


# Relationship type definitions
RELATIONSHIP_TYPE_DEFINITIONS: Dict[str, Dict[str, Any]] = {
    "cites": {
        "description": "One document cites another",
        "allowed_source_types": ["case", "regulation", "contract", "document"],
        "allowed_target_types": ["statute", "regulation", "case", "contract", "document"],
        "properties": ["page", "section", "context", "purpose"],
        "cardinality": "many_to_many"
    },
    "interprets": {
        "description": "Case interprets statute or regulation",
        "allowed_source_types": ["case"],
        "allowed_target_types": ["statute", "regulation"],
        "properties": ["interpretation", "significance", "scope"],
        "cardinality": "many_to_many"
    },
    "amends": {
        "description": "Amendment amends a document",
        "allowed_source_types": ["amendment"],
        "allowed_target_types": ["statute", "regulation", "contract", "document"],
        "properties": ["changes", "effective_date", "version"],
        "cardinality": "one_to_many"
    },
    "contradicts": {
        "description": "One source contradicts another",
        "allowed_source_types": ["case", "regulation", "document"],
        "allowed_target_types": ["case", "regulation", "document"],
        "properties": ["area", "severity", "resolution"],
        "cardinality": "many_to_many"
    },
    "supports": {
        "description": "One source supports another",
        "allowed_source_types": ["case", "regulation", "document"],
        "allowed_target_types": ["case", "regulation", "document"],
        "properties": ["basis", "strength", "application"],
        "cardinality": "many_to_many"
    },
    "precedent": {
        "description": "Case sets precedent for another",
        "allowed_source_types": ["case"],
        "allowed_target_types": ["case"],
        "properties": ["doctrine", "binding", "jurisdiction"],
        "cardinality": "one_to_many"
    },
    "overrules": {
        "description": "Case overrules another",
        "allowed_source_types": ["case"],
        "allowed_target_types": ["case"],
        "properties": ["reason", "scope", "date"],
        "cardinality": "one_to_one"
    },
    "distinguishes": {
        "description": "Case distinguishes from another",
        "allowed_source_types": ["case"],
        "allowed_target_types": ["case"],
        "properties": ["basis", "facts", "application"],
        "cardinality": "many_to_many"
    },
    "applies_to": {
        "description": "Law applies to entity or jurisdiction",
        "allowed_source_types": ["statute", "regulation"],
        "allowed_target_types": ["entity", "jurisdiction", "organization"],
        "properties": ["scope", "exceptions", "enforcement"],
        "cardinality": "many_to_many"
    },
    "involves": {
        "description": "Case involves entity",
        "allowed_source_types": ["case"],
        "allowed_target_types": ["entity", "person", "organization"],
        "properties": ["role", "outcome", "representation"],
        "cardinality": "many_to_many"
    },
    "contains": {
        "description": "Document contains clause",
        "allowed_source_types": ["contract", "document"],
        "allowed_target_types": ["clause"],
        "properties": ["position", "importance", "modified"],
        "cardinality": "one_to_many"
    },
    "references": {
        "description": "Document references concept",
        "allowed_source_types": ["document", "case", "contract"],
        "allowed_target_types": ["legal_concept", "precedent"],
        "properties": ["context", "application", "interpretation"],
        "cardinality": "many_to_many"
    },
    "similar_to": {
        "description": "Similar legal concepts or documents",
        "allowed_source_types": ["legal_concept", "document", "case"],
        "allowed_target_types": ["legal_concept", "document", "case"],
        "properties": ["similarity_score", "basis", "differences"],
        "cardinality": "many_to_many"
    },
    "parent_child": {
        "description": "Parent-child relationship",
        "allowed_source_types": ["entity", "organization", "document"],
        "allowed_target_types": ["entity", "organization", "document"],
        "properties": ["relationship_type", "ownership", "control"],
        "cardinality": "one_to_many"
    },
    "related_to": {
        "description": "General relatedness",
        "allowed_source_types": ["*"],  # All types
        "allowed_target_types": ["*"],  # All types
        "properties": ["relationship", "strength", "context"],
        "cardinality": "many_to_many"
    }
}


# Citation strength definitions
CITATION_STRENGTH_DEFINITIONS: Dict[str, Dict[str, Any]] = {
    "strong": {
        "description": "Direct, explicit citation",
        "weight": 1.0,
        "confidence_threshold": 0.9,
        "requires": ["explicit_reference", "contextual_support"]
    },
    "moderate": {
        "description": "Indirect citation",
        "weight": 0.7,
        "confidence_threshold": 0.7,
        "requires": ["implied_reference", "contextual_support"]
    },
    "weak": {
        "description": "Implied or tangential reference",
        "weight": 0.3,
        "confidence_threshold": 0.5,
        "requires": ["tangential_connection"]
    },
    "negative": {
        "description": "Negative citation (criticism)",
        "weight": -0.5,
        "confidence_threshold": 0.8,
        "requires": ["explicit_criticism", "contextual_opposition"]
    }
}


# Query templates
QUERY_TEMPLATES: Dict[str, Dict[str, Any]] = {
    "find_citations": {
        "description": "Find all citations from a document",
        "parameters": ["document_id", "citation_type", "limit"],
        "template": {
            "nodes": {
                "source": {"node_id": "{document_id}"}
            },
            "relationships": [
                {
                    "type": "{citation_type}",
                    "direction": "outgoing"
                }
            ],
            "limit": "{limit}"
        }
    },
    "find_precedents": {
        "description": "Find precedents for a case",
        "parameters": ["case_id", "jurisdiction", "limit"],
        "template": {
            "nodes": {
                "case": {"node_id": "{case_id}"}
            },
            "relationships": [
                {
                    "type": "precedent",
                    "direction": "incoming"
                }
            ],
            "filters": {
                "jurisdiction": "{jurisdiction}"
            },
            "limit": "{limit}"
        }
    },
    "find_related_cases": {
        "description": "Find cases related by topic or citation",
        "parameters": ["case_id", "topic", "depth", "limit"],
        "template": {
            "traversal": {
                "start_node": "{case_id}",
                "max_depth": "{depth}",
                "relationship_types": ["cites", "precedent", "similar_to"],
                "node_filters": {
                    "topic": "{topic}"
                }
            },
            "limit": "{limit}"
        }
    },
    "find_statute_applications": {
        "description": "Find how a statute has been applied",
        "parameters": ["statute_id", "jurisdiction", "time_range", "limit"],
        "template": {
            "nodes": {
                "statute": {"node_id": "{statute_id}"}
            },
            "relationships": [
                {
                    "type": "interprets",
                    "direction": "incoming"
                }
            ],
            "filters": {
                "jurisdiction": "{jurisdiction}",
                "date": "{time_range}"
            },
            "limit": "{limit}"
        }
    },
    "find_contract_clauses": {
        "description": "Find clauses in a contract",
        "parameters": ["contract_id", "clause_type", "limit"],
        "template": {
            "nodes": {
                "contract": {"node_id": "{contract_id}"}
            },
            "relationships": [
                {
                    "type": "contains",
                    "direction": "outgoing"
                }
            ],
            "filters": {
                "type": "{clause_type}"
            },
            "limit": "{limit}"
        }
    }
}


def get_config(backend: str = "in_memory") -> Dict[str, Any]:
    """
    Get configuration for specified backend.
    
    Args:
        backend: Graph backend name
        
    Returns:
        Configuration dictionary
    """
    config = DEFAULT_CONFIG.copy()
    config["backend"] = backend
    
    if backend == GraphBackend.NEO4J.value:
        config.update({"neo4j": NEO4J_CONFIG})
    elif backend == GraphBackend.JANUSGRAPH.value:
        config.update({"janusgraph": JANUSGRAPH_CONFIG})
    
    return config


def validate_node_type(node_type: str) -> bool:
    """
    Validate if node type is defined.
    
    Args:
        node_type: Node type to validate
        
    Returns:
        True if valid, False otherwise
    """
    return node_type in NODE_TYPE_DEFINITIONS


def validate_relationship_type(rel_type: str) -> bool:
    """
    Validate if relationship type is defined.
    
    Args:
        rel_type: Relationship type to validate
        
    Returns:
        True if valid, False otherwise
    """
    return rel_type in RELATIONSHIP_TYPE_DEFINITIONS


def get_node_definition(node_type: str) -> Dict[str, Any]:
    """
    Get definition for a node type.
    
    Args:
        node_type: Node type
        
    Returns:
        Node type definition
    """
    return NODE_TYPE_DEFINITIONS.get(node_type, {})


def get_relationship_definition(rel_type: str) -> Dict[str, Any]:
    """
    Get definition for a relationship type.
    
    Args:
        rel_type: Relationship type
        
    Returns:
        Relationship type definition
    """
    return RELATIONSHIP_TYPE_DEFINITIONS.get(rel_type, {})


def get_citation_strength_definition(strength: str) -> Dict[str, Any]:
    """
    Get definition for citation strength.
    
    Args:
        strength: Citation strength
        
    Returns:
        Citation strength definition
    """
    return CITATION_STRENGTH_DEFINITIONS.get(strength, {})


def get_query_template(template_name: str) -> Dict[str, Any]:
    """
    Get query template by name.
    
    Args:
        template_name: Template name
        
    Returns:
        Query template
    """
    return QUERY_TEMPLATES.get(template_name, {})