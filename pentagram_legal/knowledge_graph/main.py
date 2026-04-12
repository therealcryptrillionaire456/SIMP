"""
Main entry point for Legal Knowledge Graph Engine.
"""

import sys
import os
import argparse
import json
import logging
from typing import Dict, Any
from pathlib import Path

# Add project root to path for imports
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

from knowledge_graph import (
    LegalKnowledgeGraph, LegalDataLoader,
    get_config, get_query_template
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def create_graph(args) -> LegalKnowledgeGraph:
    """Create and initialize knowledge graph."""
    logger.info(f"Creating Legal Knowledge Graph: {args.graph_name}")
    
    config = get_config(args.backend)
    graph = LegalKnowledgeGraph(args.graph_name)
    
    logger.info(f"Graph created with {args.backend} backend")
    return graph


def load_data(graph: LegalKnowledgeGraph, args):
    """Load data into knowledge graph."""
    if not args.data_path:
        logger.warning("No data path specified for loading")
        return
    
    data_path = Path(args.data_path)
    if not data_path.exists():
        logger.error(f"Data path not found: {args.data_path}")
        return
    
    loader = LegalDataLoader(graph)
    
    if data_path.is_file():
        logger.info(f"Loading data from file: {data_path}")
        
        if data_path.suffix.lower() == '.json':
            result = loader.load_json_file(str(data_path), args.source_type)
        elif data_path.suffix.lower() == '.csv':
            result = loader.load_csv_file(str(data_path), args.source_type)
        else:
            logger.error(f"Unsupported file format: {data_path.suffix}")
            return
        
        logger.info(f"File load result: {result}")
        
    elif data_path.is_dir():
        logger.info(f"Loading data from directory: {data_path}")
        
        file_pattern = args.file_pattern
        result = loader.load_from_directory(
            str(data_path), 
            file_pattern, 
            args.source_type
        )
        
        logger.info(f"Directory load result: {result}")
    
    else:
        logger.error(f"Invalid data path: {args.data_path}")


def query_graph(graph: LegalKnowledgeGraph, args):
    """Query the knowledge graph."""
    if args.query_type == "pattern":
        logger.info(f"Executing pattern query: {args.query_pattern}")
        
        try:
            pattern = json.loads(args.query_pattern)
            results = graph.query_pattern(pattern)
            
            print(f"\nQuery Results ({len(results)} found):")
            print(json.dumps(results, indent=2, default=str))
            
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON pattern: {str(e)}")
        except Exception as e:
            logger.error(f"Query execution error: {str(e)}")
    
    elif args.query_type == "traversal":
        logger.info(f"Executing traversal from {args.start_node} with depth {args.depth}")
        
        try:
            results = graph.traverse(
                args.start_node,
                max_depth=args.depth,
                direction=args.direction
            )
            
            print(f"\nTraversal Results:")
            print(json.dumps(results, indent=2, default=str))
            
        except Exception as e:
            logger.error(f"Traversal error: {str(e)}")
    
    elif args.query_type == "similar":
        logger.info(f"Finding nodes similar to {args.similar_node}")
        
        try:
            results = graph.find_similar_nodes(
                args.similar_node,
                similarity_threshold=args.similarity_threshold
            )
            
            print(f"\nSimilar Nodes ({len(results)} found):")
            for result in results[:args.limit]:
                node = result["node"]
                score = result["similarity_score"]
                print(f"  {node['label']} (ID: {node['node_id']}, Score: {score:.3f})")
            
        except Exception as e:
            logger.error(f"Similarity search error: {str(e)}")
    
    elif args.query_type == "template":
        logger.info(f"Executing template query: {args.template_name}")
        
        try:
            template = get_query_template(args.template_name)
            if not template:
                logger.error(f"Template not found: {args.template_name}")
                return
            
            # For now, just print the template
            # In a real implementation, this would execute the template with parameters
            print(f"\nQuery Template: {args.template_name}")
            print(json.dumps(template, indent=2))
            
        except Exception as e:
            logger.error(f"Template query error: {str(e)}")


def export_graph(graph: LegalKnowledgeGraph, args):
    """Export the knowledge graph."""
    logger.info(f"Exporting graph to {args.export_format} format")
    
    try:
        export_data = graph.export_graph(args.export_format)
        
        if "error" in export_data:
            logger.error(f"Export error: {export_data['error']}")
            return
        
        if args.export_file:
            with open(args.export_file, 'w', encoding='utf-8') as f:
                if args.export_format == "json":
                    json.dump(export_data, f, indent=2, default=str)
                else:
                    # For other formats, would need appropriate serialization
                    f.write(str(export_data))
            
            logger.info(f"Graph exported to {args.export_file}")
        else:
            # Print to console
            print(json.dumps(export_data, indent=2, default=str))
            
    except Exception as e:
        logger.error(f"Export error: {str(e)}")


def show_statistics(graph: LegalKnowledgeGraph, args):
    """Show graph statistics."""
    logger.info("Getting graph statistics")
    
    try:
        stats = graph.get_statistics()
        print("\nGraph Statistics:")
        print(json.dumps(stats, indent=2, default=str))
        
    except Exception as e:
        logger.error(f"Statistics error: {str(e)}")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Legal Knowledge Graph Engine",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Create a new graph
  python main.py create --name legal_graph
  
  # Load data from JSON file
  python main.py load --data data/cases.json --source pacer
  
  # Query the graph
  python main.py query --type pattern --pattern '{"nodes": {"node_type": "case"}}'
  
  # Export graph to JSON
  python main.py export --format json --file graph_export.json
  
  # Show statistics
  python main.py stats
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")
    
    # Create command
    create_parser = subparsers.add_parser("create", help="Create a new knowledge graph")
    create_parser.add_argument("--name", "-n", default="legal_knowledge_graph", 
                              help="Graph name (default: legal_knowledge_graph)")
    create_parser.add_argument("--backend", "-b", default="in_memory",
                              choices=["in_memory", "neo4j", "janusgraph"],
                              help="Graph backend (default: in_memory)")
    
    # Load command
    load_parser = subparsers.add_parser("load", help="Load data into the graph")
    load_parser.add_argument("--data", "-d", required=True, 
                            help="Path to data file or directory")
    load_parser.add_argument("--source", "-s", default="generic",
                            help="Data source type (default: generic)")
    load_parser.add_argument("--pattern", "-p", default="*.json",
                            help="File pattern for directory loading (default: *.json)")
    
    # Query command
    query_parser = subparsers.add_parser("query", help="Query the graph")
    query_parser.add_argument("--type", "-t", required=True,
                             choices=["pattern", "traversal", "similar", "template"],
                             help="Query type")
    query_parser.add_argument("--pattern", "-p",
                             help="JSON pattern for pattern queries")
    query_parser.add_argument("--start-node", "-s",
                             help="Start node ID for traversal queries")
    query_parser.add_argument("--depth", "-d", type=int, default=3,
                             help="Maximum depth for traversal (default: 3)")
    query_parser.add_argument("--direction", "-dir", default="both",
                             choices=["outgoing", "incoming", "both"],
                             help="Traversal direction (default: both)")
    query_parser.add_argument("--similar-node", "-sn",
                             help="Node ID for similarity search")
    query_parser.add_argument("--similarity-threshold", "-st", type=float, default=0.7,
                             help="Similarity threshold (default: 0.7)")
    query_parser.add_argument("--template-name", "-tn",
                             help="Template name for template queries")
    query_parser.add_argument("--limit", "-l", type=int, default=10,
                             help="Maximum results to return (default: 10)")
    
    # Export command
    export_parser = subparsers.add_parser("export", help="Export the graph")
    export_parser.add_argument("--format", "-f", default="json",
                              choices=["json", "graphml", "csv"],
                              help="Export format (default: json)")
    export_parser.add_argument("--file", "-o",
                              help="Output file (default: print to console)")
    
    # Statistics command
    stats_parser = subparsers.add_parser("stats", help="Show graph statistics")
    
    # Test command
    test_parser = subparsers.add_parser("test", help="Run tests")
    test_parser.add_argument("--test-type", "-t", default="all",
                            choices=["all", "graph", "loader", "config"],
                            help="Test type (default: all)")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    # Initialize graph (in-memory for now)
    graph = LegalKnowledgeGraph("legal_knowledge_graph")
    
    # Execute command
    if args.command == "create":
        create_graph(args)
        
    elif args.command == "load":
        load_data(graph, args)
        
    elif args.command == "query":
        query_graph(graph, args)
        
    elif args.command == "export":
        export_graph(graph, args)
        
    elif args.command == "stats":
        show_statistics(graph, args)
        
    elif args.command == "test":
        run_tests(args)
    
    logger.info("Command completed")


def run_tests(args):
    """Run tests."""
    logger.info(f"Running {args.test_type} tests")
    
    if args.test_type in ["all", "graph"]:
        logger.info("Testing Legal Knowledge Graph...")
        from knowledge_graph.legal_knowledge_graph import test_legal_knowledge_graph
        test_legal_knowledge_graph()
    
    if args.test_type in ["all", "loader"]:
        logger.info("Testing Legal Data Loader...")
        from knowledge_graph.data_loader import test_data_loader
        test_data_loader()
    
    if args.test_type in ["all", "config"]:
        logger.info("Testing configuration...")
        from knowledge_graph.config import (
            get_config, validate_node_type, validate_relationship_type
        )
        
        config = get_config()
        print(f"Default config: {json.dumps(config, indent=2)}")
        
        print(f"\nNode type validation:")
        print(f"  'statute' valid: {validate_node_type('statute')}")
        print(f"  'invalid' valid: {validate_node_type('invalid')}")
        
        print(f"\nRelationship type validation:")
        print(f"  'cites' valid: {validate_relationship_type('cites')}")
        print(f"  'invalid' valid: {validate_relationship_type('invalid')}")
    
    logger.info("Tests completed")


if __name__ == "__main__":
    main()