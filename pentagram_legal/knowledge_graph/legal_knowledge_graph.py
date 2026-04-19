"""
Legal Knowledge Graph Engine - Build 11
Graph database system for storing and querying legal relationships.
Connects statutes, cases, contracts, entities, and legal concepts.
"""

import sys
import os
from typing import Dict, List, Any, Optional, Tuple, Set
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import json
import logging
from pathlib import Path
import uuid

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class NodeType(Enum):
    """Types of nodes in the legal knowledge graph."""
    STATUTE = "statute"
    REGULATION = "regulation"
    CASE = "case"
    CONTRACT = "contract"
    CLAUSE = "clause"
    ENTITY = "entity"
    JURISDICTION = "jurisdiction"
    COURT = "court"
    AGENCY = "agency"
    LEGAL_CONCEPT = "legal_concept"
    PRECEDENT = "precedent"
    AMENDMENT = "amendment"
    DOCUMENT = "document"
    PERSON = "person"
    ORGANIZATION = "organization"


class RelationshipType(Enum):
    """Types of relationships in the legal knowledge graph."""
    CITES = "cites"  # One document cites another
    INTERPRETS = "interprets"  # Case interprets statute
    AMENDS = "amends"  # Amendment amends statute
    CONTRADICTS = "contradicts"  # One source contradicts another
    SUPPORTS = "supports"  # One source supports another
    PRECEDENT = "precedent"  # Case sets precedent for another
    OVERRULES = "overrules"  # Case overrules another
    DISTINGUISHES = "distinguishes"  # Case distinguishes from another
    APPLIES_TO = "applies_to"  # Law applies to entity/jurisdiction
    INVOLVES = "involves"  # Case involves entity
    CONTAINS = "contains"  # Document contains clause
    REFERENCES = "references"  # Document references concept
    SIMILAR_TO = "similar_to"  # Similar legal concepts
    PARENT_CHILD = "parent_child"  # Parent-child relationship
    RELATED_TO = "related_to"  # General relatedness


class CitationStrength(Enum):
    """Strength of citation relationships."""
    STRONG = "strong"  # Direct, explicit citation
    MODERATE = "moderate"  # Indirect citation
    WEAK = "weak"  # Implied or tangential reference
    NEGATIVE = "negative"  # Negative citation (criticism)


@dataclass
class GraphNode:
    """Node in the legal knowledge graph."""
    node_id: str
    node_type: NodeType
    label: str
    properties: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    version: int = 1
    source: Optional[str] = None
    confidence: float = 1.0  # 0.0 to 1.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert node to dictionary."""
        return {
            "node_id": self.node_id,
            "node_type": self.node_type.value,
            "label": self.label,
            "properties": self.properties,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "version": self.version,
            "source": self.source,
            "confidence": self.confidence
        }


@dataclass
class GraphRelationship:
    """Relationship between nodes in the legal knowledge graph."""
    relationship_id: str
    source_node_id: str
    target_node_id: str
    relationship_type: RelationshipType
    properties: Dict[str, Any] = field(default_factory=dict)
    strength: CitationStrength = CitationStrength.MODERATE
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    confidence: float = 1.0  # 0.0 to 1.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert relationship to dictionary."""
        return {
            "relationship_id": self.relationship_id,
            "source_node_id": self.source_node_id,
            "target_node_id": self.target_node_id,
            "relationship_type": self.relationship_type.value,
            "properties": self.properties,
            "strength": self.strength.value,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "confidence": self.confidence
        }


@dataclass
class GraphQuery:
    """Query for the knowledge graph."""
    query_id: str
    query_type: str  # pattern, traversal, similarity, etc.
    parameters: Dict[str, Any]
    results: List[Dict[str, Any]] = field(default_factory=list)
    execution_time: Optional[float] = None
    created_at: datetime = field(default_factory=datetime.now)


class LegalKnowledgeGraph:
    """
    Legal Knowledge Graph Engine.
    Manages nodes and relationships for legal knowledge representation.
    """
    
    def __init__(self, graph_name: str = "legal_knowledge_graph"):
        """
        Initialize Legal Knowledge Graph.
        
        Args:
            graph_name: Name of the graph database
        """
        self.graph_name = graph_name
        
        # Storage for nodes and relationships
        self.nodes: Dict[str, GraphNode] = {}
        self.relationships: Dict[str, GraphRelationship] = {}
        
        # Indexes for faster lookup
        self.node_type_index: Dict[NodeType, Set[str]] = {node_type: set() for node_type in NodeType}
        self.relationship_type_index: Dict[RelationshipType, Set[str]] = {rel_type: set() for rel_type in RelationshipType}
        self.source_target_index: Dict[Tuple[str, str], Set[str]] = {}
        
        # Statistics
        self.stats = {
            "total_nodes": 0,
            "total_relationships": 0,
            "nodes_by_type": {},
            "relationships_by_type": {},
            "last_updated": datetime.now().isoformat()
        }
        
        # Query cache
        self.query_cache: Dict[str, GraphQuery] = {}
        
        logger.info(f"Initialized Legal Knowledge Graph: {graph_name}")
    
    def add_node(self, node: GraphNode) -> bool:
        """
        Add a node to the graph.
        
        Args:
            node: Node to add
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Generate ID if not provided
            if not node.node_id:
                node.node_id = f"node_{uuid.uuid4().hex[:16]}"
            
            # Check if node already exists
            if node.node_id in self.nodes:
                logger.warning(f"Node {node.node_id} already exists, updating")
                return self.update_node(node.node_id, node.properties)
            
            # Add to storage
            self.nodes[node.node_id] = node
            
            # Update indexes
            self.node_type_index[node.node_type].add(node.node_id)
            
            # Update statistics
            self.stats["total_nodes"] += 1
            node_type_str = node.node_type.value
            self.stats["nodes_by_type"][node_type_str] = self.stats["nodes_by_type"].get(node_type_str, 0) + 1
            self.stats["last_updated"] = datetime.now().isoformat()
            
            logger.info(f"Added node {node.node_id}: {node.label} ({node.node_type.value})")
            return True
            
        except Exception as e:
            logger.error(f"Error adding node: {str(e)}")
            return False
    
    def add_relationship(self, relationship: GraphRelationship) -> bool:
        """
        Add a relationship to the graph.
        
        Args:
            relationship: Relationship to add
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Check if source and target nodes exist
            if relationship.source_node_id not in self.nodes:
                logger.error(f"Source node {relationship.source_node_id} not found")
                return False
            if relationship.target_node_id not in self.nodes:
                logger.error(f"Target node {relationship.target_node_id} not found")
                return False
            
            # Generate ID if not provided
            if not relationship.relationship_id:
                relationship.relationship_id = f"rel_{uuid.uuid4().hex[:16]}"
            
            # Check if relationship already exists
            if relationship.relationship_id in self.relationships:
                logger.warning(f"Relationship {relationship.relationship_id} already exists")
                return False
            
            # Add to storage
            self.relationships[relationship.relationship_id] = relationship
            
            # Update indexes
            self.relationship_type_index[relationship.relationship_type].add(relationship.relationship_id)
            
            key = (relationship.source_node_id, relationship.target_node_id)
            if key not in self.source_target_index:
                self.source_target_index[key] = set()
            self.source_target_index[key].add(relationship.relationship_id)
            
            # Update statistics
            self.stats["total_relationships"] += 1
            rel_type_str = relationship.relationship_type.value
            self.stats["relationships_by_type"][rel_type_str] = self.stats["relationships_by_type"].get(rel_type_str, 0) + 1
            self.stats["last_updated"] = datetime.now().isoformat()
            
            logger.info(f"Added relationship {relationship.relationship_id}: {relationship.source_node_id} -> {relationship.target_node_id} ({relationship.relationship_type.value})")
            return True
            
        except Exception as e:
            logger.error(f"Error adding relationship: {str(e)}")
            return False
    
    def get_node(self, node_id: str) -> Optional[GraphNode]:
        """Get a node by ID."""
        return self.nodes.get(node_id)
    
    def get_relationship(self, relationship_id: str) -> Optional[GraphRelationship]:
        """Get a relationship by ID."""
        return self.relationships.get(relationship_id)
    
    def update_node(self, node_id: str, properties: Dict[str, Any]) -> bool:
        """
        Update node properties.
        
        Args:
            node_id: ID of node to update
            properties: New properties
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if node_id not in self.nodes:
                logger.error(f"Node {node_id} not found")
                return False
            
            node = self.nodes[node_id]
            node.properties.update(properties)
            node.updated_at = datetime.now()
            node.version += 1
            
            logger.info(f"Updated node {node_id}, version {node.version}")
            return True
            
        except Exception as e:
            logger.error(f"Error updating node: {str(e)}")
            return False
    
    def delete_node(self, node_id: str) -> bool:
        """
        Delete a node and all its relationships.
        
        Args:
            node_id: ID of node to delete
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if node_id not in self.nodes:
                logger.error(f"Node {node_id} not found")
                return False
            
            # Find and delete all relationships involving this node
            relationships_to_delete = []
            for rel_id, relationship in self.relationships.items():
                if (relationship.source_node_id == node_id or 
                    relationship.target_node_id == node_id):
                    relationships_to_delete.append(rel_id)
            
            for rel_id in relationships_to_delete:
                self.delete_relationship(rel_id)
            
            # Remove from indexes
            node = self.nodes[node_id]
            self.node_type_index[node.node_type].discard(node_id)
            
            # Remove from storage
            del self.nodes[node_id]
            
            # Update statistics
            self.stats["total_nodes"] -= 1
            node_type_str = node.node_type.value
            if node_type_str in self.stats["nodes_by_type"]:
                self.stats["nodes_by_type"][node_type_str] -= 1
                if self.stats["nodes_by_type"][node_type_str] <= 0:
                    del self.stats["nodes_by_type"][node_type_str]
            
            self.stats["last_updated"] = datetime.now().isoformat()
            
            logger.info(f"Deleted node {node_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error deleting node: {str(e)}")
            return False
    
    def delete_relationship(self, relationship_id: str) -> bool:
        """
        Delete a relationship.
        
        Args:
            relationship_id: ID of relationship to delete
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if relationship_id not in self.relationships:
                logger.error(f"Relationship {relationship_id} not found")
                return False
            
            relationship = self.relationships[relationship_id]
            
            # Remove from indexes
            self.relationship_type_index[relationship.relationship_type].discard(relationship_id)
            
            key = (relationship.source_node_id, relationship.target_node_id)
            if key in self.source_target_index:
                self.source_target_index[key].discard(relationship_id)
                if not self.source_target_index[key]:
                    del self.source_target_index[key]
            
            # Remove from storage
            del self.relationships[relationship_id]
            
            # Update statistics
            self.stats["total_relationships"] -= 1
            rel_type_str = relationship.relationship_type.value
            if rel_type_str in self.stats["relationships_by_type"]:
                self.stats["relationships_by_type"][rel_type_str] -= 1
                if self.stats["relationships_by_type"][rel_type_str] <= 0:
                    del self.stats["relationships_by_type"][rel_type_str]
            
            self.stats["last_updated"] = datetime.now().isoformat()
            
            logger.info(f"Deleted relationship {relationship_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error deleting relationship: {str(e)}")
            return False
    
    def find_nodes_by_type(self, node_type: NodeType, limit: int = 100) -> List[GraphNode]:
        """
        Find nodes by type.
        
        Args:
            node_type: Type of nodes to find
            limit: Maximum number of nodes to return
            
        Returns:
            List of nodes
        """
        node_ids = list(self.node_type_index.get(node_type, set()))[:limit]
        return [self.nodes[node_id] for node_id in node_ids if node_id in self.nodes]
    
    def find_relationships(self, source_id: Optional[str] = None, 
                          target_id: Optional[str] = None,
                          rel_type: Optional[RelationshipType] = None) -> List[GraphRelationship]:
        """
        Find relationships with optional filters.
        
        Args:
            source_id: Filter by source node ID
            target_id: Filter by target node ID
            rel_type: Filter by relationship type
            
        Returns:
            List of relationships
        """
        results = []
        
        if source_id and target_id:
            # Look for specific source-target pair
            key = (source_id, target_id)
            if key in self.source_target_index:
                rel_ids = self.source_target_index[key]
                for rel_id in rel_ids:
                    if rel_id in self.relationships:
                        rel = self.relationships[rel_id]
                        if not rel_type or rel.relationship_type == rel_type:
                            results.append(rel)
        else:
            # Search through all relationships
            for rel_id, relationship in self.relationships.items():
                matches = True
                if source_id and relationship.source_node_id != source_id:
                    matches = False
                if target_id and relationship.target_node_id != target_id:
                    matches = False
                if rel_type and relationship.relationship_type != rel_type:
                    matches = False
                
                if matches:
                    results.append(relationship)
        
        return results
    
    def query_pattern(self, pattern: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Query the graph using a pattern.
        
        Args:
            pattern: Query pattern with node and relationship specifications
            
        Returns:
            List of matching subgraphs
        """
        start_time = datetime.now()
        query_id = f"query_{uuid.uuid4().hex[:8]}"
        
        try:
            # Parse pattern
            nodes_pattern = pattern.get("nodes", {})
            relationships_pattern = pattern.get("relationships", [])
            limit = pattern.get("limit", 100)
            
            results = []
            
            # Simple pattern matching implementation
            # For production, this would use a proper graph query language
            
            # Match nodes first
            candidate_nodes = self._match_nodes(nodes_pattern)
            
            # Then match relationships
            for node_set in candidate_nodes:
                if self._match_relationships(node_set, relationships_pattern):
                    # Construct result subgraph
                    subgraph = {
                        "nodes": [node.to_dict() for node in node_set.values()],
                        "relationships": []
                    }
                    
                    # Find relationships between these nodes
                    node_ids = set(node_set.keys())
                    for rel in self.relationships.values():
                        if (rel.source_node_id in node_ids and 
                            rel.target_node_id in node_ids):
                            subgraph["relationships"].append(rel.to_dict())
                    
                    results.append(subgraph)
                    
                    if len(results) >= limit:
                        break
            
            # Cache the query
            execution_time = (datetime.now() - start_time).total_seconds()
            query = GraphQuery(
                query_id=query_id,
                query_type="pattern",
                parameters=pattern,
                results=results,
                execution_time=execution_time
            )
            self.query_cache[query_id] = query
            
            logger.info(f"Pattern query executed in {execution_time:.3f}s, found {len(results)} results")
            return results
            
        except Exception as e:
            logger.error(f"Error executing pattern query: {str(e)}")
            return []
    
    def traverse(self, start_node_id: str, max_depth: int = 3, 
                direction: str = "both") -> Dict[str, Any]:
        """
        Traverse the graph from a starting node.
        
        Args:
            start_node_id: ID of starting node
            max_depth: Maximum traversal depth
            direction: "outgoing", "incoming", or "both"
            
        Returns:
            Traversal results
        """
        start_time = datetime.now()
        query_id = f"traversal_{uuid.uuid4().hex[:8]}"
        
        try:
            if start_node_id not in self.nodes:
                logger.error(f"Start node {start_node_id} not found")
                return {"error": "Start node not found"}
            
            visited = set()
            traversal_tree = {}
            
            def dfs(node_id: str, depth: int, path: List[str]):
                if depth > max_depth or node_id in visited:
                    return
                
                visited.add(node_id)
                node = self.nodes[node_id]
                
                # Get relationships based on direction
                relationships = []
                if direction in ["outgoing", "both"]:
                    relationships.extend(self.find_relationships(source_id=node_id))
                if direction in ["incoming", "both"]:
                    relationships.extend(self.find_relationships(target_id=node_id))
                
                # Process relationships
                children = []
                for rel in relationships:
                    other_id = rel.target_node_id if rel.source_node_id == node_id else rel.source_node_id
                    if other_id not in visited:
                        child_info = {
                            "node_id": other_id,
                            "relationship": rel.to_dict(),
                            "depth": depth + 1
                        }
                        children.append(child_info)
                        
                        # Recursive traversal
                        dfs(other_id, depth + 1, path + [node_id])
                
                traversal_tree[node_id] = {
                    "node": node.to_dict(),
                    "depth": depth,
                    "children": children
                }
            
            # Start traversal
            dfs(start_node_id, 0, [])
            
            # Cache the query
            execution_time = (datetime.now() - start_time).total_seconds()
            query = GraphQuery(
                query_id=query_id,
                query_type="traversal",
                parameters={
                    "start_node_id": start_node_id,
                    "max_depth": max_depth,
                    "direction": direction
                },
                results=[traversal_tree],
                execution_time=execution_time
            )
            self.query_cache[query_id] = query
            
            logger.info(f"Traversal from {start_node_id} completed in {execution_time:.3f}s, visited {len(visited)} nodes")
            return traversal_tree
            
        except Exception as e:
            logger.error(f"Error during traversal: {str(e)}")
            return {"error": str(e)}
    
    def find_similar_nodes(self, node_id: str, similarity_threshold: float = 0.7) -> List[Dict[str, Any]]:
        """
        Find nodes similar to a given node.
        
        Args:
            node_id: ID of reference node
            similarity_threshold: Minimum similarity score (0.0 to 1.0)
            
        Returns:
            List of similar nodes with similarity scores
        """
        if node_id not in self.nodes:
            logger.error(f"Node {node_id} not found")
            return []
        
        reference_node = self.nodes[node_id]
        similar_nodes = []
        
        for other_id, other_node in self.nodes.items():
            if other_id == node_id:
                continue
            
            # Calculate similarity based on node properties
            similarity = self._calculate_node_similarity(reference_node, other_node)
            
            if similarity >= similarity_threshold:
                similar_nodes.append({
                    "node": other_node.to_dict(),
                    "similarity_score": similarity,
                    "similarity_reasons": self._get_similarity_reasons(reference_node, other_node)
                })
        
        # Sort by similarity score
        similar_nodes.sort(key=lambda x: x["similarity_score"], reverse=True)
        
        logger.info(f"Found {len(similar_nodes)} nodes similar to {node_id}")
        return similar_nodes
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get graph statistics."""
        return {
            "graph_name": self.graph_name,
            "statistics": self.stats,
            "cache_size": len(self.query_cache),
            "timestamp": datetime.now().isoformat()
        }
    
    def export_graph(self, format: str = "json") -> Dict[str, Any]:
        """
        Export the graph to a specified format.
        
        Args:
            format: Export format ("json", "graphml", "csv")
            
        Returns:
            Exported graph data
        """
        try:
            if format == "json":
                export_data = {
                    "metadata": {
                        "graph_name": self.graph_name,
                        "export_date": datetime.now().isoformat(),
                        "node_count": len(self.nodes),
                        "relationship_count": len(self.relationships)
                    },
                    "nodes": [node.to_dict() for node in self.nodes.values()],
                    "relationships": [rel.to_dict() for rel in self.relationships.values()]
                }
                
                logger.info(f"Exported graph in JSON format: {len(self.nodes)} nodes, {len(self.relationships)} relationships")
                return export_data
                
            else:
                logger.error(f"Unsupported export format: {format}")
                return {"error": f"Unsupported format: {format}"}
                
        except Exception as e:
            logger.error(f"Error exporting graph: {str(e)}")
            return {"error": str(e)}
    
    def import_graph(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Import graph data.
        
        Args:
            data: Graph data to import
            
        Returns:
            Import results
        """
        try:
            nodes_data = data.get("nodes", [])
            relationships_data = data.get("relationships", [])
            
            imported_nodes = 0
            imported_relationships = 0
            
            # Import nodes
            for node_data in nodes_data:
                try:
                    node = GraphNode(
                        node_id=node_data.get("node_id"),
                        node_type=NodeType(node_data.get("node_type")),
                        label=node_data.get("label", ""),
                        properties=node_data.get("properties", {}),
                        created_at=datetime.fromisoformat(node_data.get("created_at").replace('Z', '+00:00')),
                        updated_at=datetime.fromisoformat(node_data.get("updated_at").replace('Z', '+00:00')),
                        version=node_data.get("version", 1),
                        source=node_data.get("source"),
                        confidence=node_data.get("confidence", 1.0)
                    )
                    
                    if self.add_node(node):
                        imported_nodes += 1
                        
                except Exception as e:
                    logger.warning(f"Error importing node: {str(e)}")
            
            # Import relationships
            for rel_data in relationships_data:
                try:
                    relationship = GraphRelationship(
                        relationship_id=rel_data.get("relationship_id"),
                        source_node_id=rel_data.get("source_node_id"),
                        target_node_id=rel_data.get("target_node_id"),
                        relationship_type=RelationshipType(rel_data.get("relationship_type")),
                        properties=rel_data.get("properties", {}),
                        strength=CitationStrength(rel_data.get("strength", "moderate")),
                        created_at=datetime.fromisoformat(rel_data.get("created_at").replace('Z', '+00:00')),
                        updated_at=datetime.fromisoformat(rel_data.get("updated_at").replace('Z', '+00:00')),
                        confidence=rel_data.get("confidence", 1.0)
                    )
                    
                    if self.add_relationship(relationship):
                        imported_relationships += 1
                        
                except Exception as e:
                    logger.warning(f"Error importing relationship: {str(e)}")
            
            logger.info(f"Imported {imported_nodes} nodes and {imported_relationships} relationships")
            return {
                "imported_nodes": imported_nodes,
                "imported_relationships": imported_relationships,
                "total_nodes": len(self.nodes),
                "total_relationships": len(self.relationships)
            }
            
        except Exception as e:
            logger.error(f"Error importing graph: {str(e)}")
            return {"error": str(e)}
    
    def _match_nodes(self, pattern: Dict[str, Any]) -> List[Dict[str, GraphNode]]:
        """Match nodes against a pattern."""
        # Simplified implementation
        # In production, this would be more sophisticated
        results = []
        
        for node in self.nodes.values():
            matches = True
            
            for key, value in pattern.items():
                if key == "node_type":
                    if node.node_type.value != value:
                        matches = False
                        break
                elif key in node.properties:
                    if node.properties[key] != value:
                        matches = False
                        break
                else:
                    matches = False
                    break
            
            if matches:
                results.append({node.node_id: node})
        
        return results
    
    def _match_relationships(self, nodes: Dict[str, GraphNode], 
                           pattern: List[Dict[str, Any]]) -> bool:
        """Check if relationships match the pattern."""
        # Simplified implementation
        # In production, this would check actual relationships
        return True  # For now, accept all
    
    def _calculate_node_similarity(self, node1: GraphNode, node2: GraphNode) -> float:
        """Calculate similarity between two nodes."""
        similarity = 0.0
        
        # Type similarity
        if node1.node_type == node2.node_type:
            similarity += 0.3
        
        # Property similarity
        common_props = set(node1.properties.keys()) & set(node2.properties.keys())
        if common_props:
            prop_similarity = 0.0
            for prop in common_props:
                if node1.properties[prop] == node2.properties[prop]:
                    prop_similarity += 1.0
            similarity += (prop_similarity / len(common_props)) * 0.4
        
        # Label similarity (simple string comparison)
        if node1.label.lower() == node2.label.lower():
            similarity += 0.3
        elif any(word in node2.label.lower() for word in node1.label.lower().split()):
            similarity += 0.15
        
        return min(similarity, 1.0)
    
    def _get_similarity_reasons(self, node1: GraphNode, node2: GraphNode) -> List[str]:
        """Get reasons why two nodes are similar."""
        reasons = []
        
        if node1.node_type == node2.node_type:
            reasons.append(f"Same node type: {node1.node_type.value}")
        
        common_props = set(node1.properties.keys()) & set(node2.properties.keys())
        for prop in common_props:
            if node1.properties[prop] == node2.properties[prop]:
                reasons.append(f"Same property value: {prop} = {node1.properties[prop]}")
        
        return reasons


def test_legal_knowledge_graph():
    """Test function for Legal Knowledge Graph."""
    print("Testing Legal Knowledge Graph Engine...")
    
    # Create graph instance
    graph = LegalKnowledgeGraph("test_legal_graph")
    
    # Test 1: Add nodes
    print("\n1. Testing node addition...")
    
    # Add a statute node
    statute_node = GraphNode(
        node_id="statute_001",
        node_type=NodeType.STATUTE,
        label="Civil Rights Act of 1964",
        properties={
            "jurisdiction": "US",
            "year": 1964,
            "title": "Civil Rights Act",
            "section": "Title VII"
        }
    )
    
    graph.add_node(statute_node)
    print(f"Added statute node: {statute_node.label}")
    
    # Add a case node
    case_node = GraphNode(
        node_id="case_001",
        node_type=NodeType.CASE,
        label="Griggs v. Duke Power Co.",
        properties={
            "court": "US Supreme Court",
            "year": 1971,
            "citation": "401 U.S. 424",
            "topic": "Employment Discrimination"
        }
    )
    
    graph.add_node(case_node)
    print(f"Added case node: {case_node.label}")
    
    # Test 2: Add relationship
    print("\n2. Testing relationship addition...")
    
    relationship = GraphRelationship(
        relationship_id="rel_001",
        source_node_id="case_001",
        target_node_id="statute_001",
        relationship_type=RelationshipType.INTERPRETS,
        properties={
            "interpretation": "Established disparate impact theory",
            "significance": "landmark"
        },
        strength=CitationStrength.STRONG
    )
    
    graph.add_relationship(relationship)
    print(f"Added relationship: {case_node.label} interprets {statute_node.label}")
    
    # Test 3: Query graph
    print("\n3. Testing graph query...")
    
    pattern = {
        "nodes": {
            "node_type": "case"
        },
        "limit": 10
    }
    
    results = graph.query_pattern(pattern)
    print(f"Pattern query found {len(results)} results")
    
    # Test 4: Traversal
    print("\n4. Testing graph traversal...")
    
    traversal = graph.traverse("case_001", max_depth=2)
    print(f"Traversal visited {len(traversal)} nodes")
    
    # Test 5: Statistics
    print("\n5. Testing statistics...")
    
    stats = graph.get_statistics()
    print(f"Graph statistics: {stats['statistics']['total_nodes']} nodes, {stats['statistics']['total_relationships']} relationships")
    
    # Test 6: Export
    print("\n6. Testing graph export...")
    
    export_data = graph.export_graph("json")
    print(f"Exported {export_data['metadata']['node_count']} nodes and {export_data['metadata']['relationship_count']} relationships")
    
    print("\nLegal Knowledge Graph Engine test completed successfully!")


if __name__ == "__main__":
    test_legal_knowledge_graph()