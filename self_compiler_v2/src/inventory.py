#!/usr/bin/env python3
"""
Inventory Scanner for Sovereign Self Compiler v2.

Discovers and catalogs codebase components for recursive self-compilation.
"""

import json
import logging
import os
import re
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set, Any
import hashlib

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


@dataclass
class Component:
    """A discovered codebase component."""
    path: str
    component_type: str
    size_bytes: int
    modified_time: str
    language: Optional[str] = None
    dependencies: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    classification: Optional[str] = None
    hash: Optional[str] = None
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)


@dataclass
class Inventory:
    """Complete inventory of codebase components."""
    inventory_id: str
    timestamp: str
    root_directories: List[str]
    total_components: int
    components_by_type: Dict[str, int]
    components: List[Component] = field(default_factory=list)
    dependencies: Dict[str, List[str]] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)
    
    def save(self, path: str) -> None:
        """Save inventory to JSON file."""
        with open(path, 'w') as f:
            json.dump(self.to_dict(), f, indent=2, default=str)
        logger.info(f"Inventory saved to {path}")


class InventoryScanner:
    """Scans directories and creates structured inventory."""
    
    # Component type patterns
    COMPONENT_PATTERNS = {
        # Python files
        r'.*\.py$': {
            'language': 'python',
            'types': {
                r'.*agent\.py$': 'agent',
                r'.*server\.py$': 'server',
                r'.*broker\.py$': 'broker',
                r'.*model\.py$': 'model',
                r'.*schema\.py$': 'schema',
                r'.*test_.*\.py$': 'test',
                r'.*test/.*\.py$': 'test',
                r'.*tests/.*\.py$': 'test',
                r'.*\.py$': 'module'  # default
            }
        },
        # Configuration files
        r'.*\.(json|yaml|yml|toml|ini|cfg)$': {
            'language': 'config',
            'types': {
                r'.*config\.(json|yaml|yml)$': 'config',
                r'.*\.toml$': 'config',
                r'.*\.(ini|cfg)$': 'config'
            }
        },
        # Documentation
        r'.*\.(md|rst|txt)$': {
            'language': 'markup',
            'types': {
                r'.*README\.md$': 'readme',
                r'.*\.md$': 'documentation'
            }
        },
        # Shell scripts
        r'.*\.(sh|bash)$': {
            'language': 'shell',
            'types': {
                r'.*\.sh$': 'script'
            }
        },
        # Data files
        r'.*\.(csv|jsonl|parquet)$': {
            'language': 'data',
            'types': {
                r'.*\.csv$': 'dataset',
                r'.*\.jsonl$': 'log',
                r'.*\.parquet$': 'dataset'
            }
        }
    }
    
    # Exclusion patterns
    EXCLUDE_PATTERNS = [
        r'\.git/',
        r'__pycache__/',
        r'\.pyc$',
        r'\.DS_Store$',
        r'\.swp$',
        r'\.bak$',
        r'node_modules/',
        r'venv/',
        r'env/',
        r'\.env',
        r'dist/',
        r'build/',
        r'tmp/',
        r'temp/'
    ]
    
    def __init__(self, config: Optional[Dict] = None):
        """Initialize scanner with configuration."""
        self.config = config or {}
        self.exclude_patterns = [re.compile(pattern) for pattern in self.EXCLUDE_PATTERNS]
        self.component_patterns = self._compile_patterns()
        
    def _compile_patterns(self) -> List[Dict]:
        """Compile regex patterns for component detection."""
        compiled = []
        for pattern_str, type_info in self.COMPONENT_PATTERNS.items():
            pattern = re.compile(pattern_str)
            type_patterns = {}
            for type_pattern_str, component_type in type_info['types'].items():
                type_patterns[re.compile(type_pattern_str)] = component_type
            compiled.append({
                'pattern': pattern,
                'language': type_info['language'],
                'type_patterns': type_patterns
            })
        return compiled
    
    def _should_exclude(self, path: str) -> bool:
        """Check if path should be excluded from scanning."""
        for pattern in self.exclude_patterns:
            if pattern.search(path):
                return True
        return False
    
    def _classify_component(self, file_path: str) -> Optional[Dict[str, str]]:
        """Classify a file based on its path and patterns."""
        for pattern_info in self.component_patterns:
            if pattern_info['pattern'].match(file_path):
                # Determine specific type
                component_type = 'unknown'
                for type_pattern, comp_type in pattern_info['type_patterns'].items():
                    if type_pattern.match(file_path):
                        component_type = comp_type
                        break
                
                return {
                    'language': pattern_info['language'],
                    'component_type': component_type
                }
        return None
    
    def _calculate_hash(self, file_path: str) -> Optional[str]:
        """Calculate SHA-256 hash of file content."""
        try:
            with open(file_path, 'rb') as f:
                content = f.read()
                return hashlib.sha256(content).hexdigest()[:16]
        except (IOError, OSError):
            return None
    
    def _extract_dependencies(self, file_path: str, language: str) -> List[str]:
        """Extract dependencies from file based on language."""
        dependencies = []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
                if language == 'python':
                    # Find import statements
                    import_patterns = [
                        r'^import\s+([a-zA-Z0-9_\.]+)',
                        r'^from\s+([a-zA-Z0-9_\.]+)\s+import',
                        r'^\s*import\s+([a-zA-Z0-9_\.]+)',
                        r'^\s*from\s+([a-zA-Z0-9_\.]+)\s+import'
                    ]
                    
                    for pattern in import_patterns:
                        matches = re.findall(pattern, content, re.MULTILINE)
                        for match in matches:
                            # Clean up the import
                            dep = match.split('.')[0]  # Take only top-level module
                            if dep not in dependencies and dep not in ['', ' ']:
                                dependencies.append(dep)
                
                elif language == 'config':
                    # For config files, look for references to other files
                    ref_patterns = [
                        r'"([a-zA-Z0-9_\-/]+\.(py|json|yaml|yml))"',
                        r"'([a-zA-Z0-9_\-/]+\.(py|json|yaml|yml))'",
                        r'path:\s*["\']([a-zA-Z0-9_\-/]+)["\']',
                        r'file:\s*["\']([a-zA-Z0-9_\-/]+)["\']'
                    ]
                    
                    for pattern in ref_patterns:
                        matches = re.findall(pattern, content)
                        for match in matches:
                            if isinstance(match, tuple):
                                dep = match[0]
                            else:
                                dep = match
                            if dep not in dependencies and dep not in ['', ' ']:
                                dependencies.append(dep)
        
        except (IOError, OSError, UnicodeDecodeError):
            pass
        
        return dependencies
    
    def scan_directory(self, root_path: str, max_depth: int = 5) -> Inventory:
        """
        Scan a directory and create inventory.
        
        Args:
            root_path: Root directory to scan
            max_depth: Maximum recursion depth
            
        Returns:
            Inventory object
        """
        logger.info(f"Starting scan of {root_path} (max depth: {max_depth})")
        
        root_path = os.path.abspath(root_path)
        components = []
        components_by_type = {}
        
        # Generate inventory ID
        inventory_id = f"inv_{hashlib.md5(root_path.encode()).hexdigest()[:8]}_{int(datetime.now().timestamp())}"
        
        for dirpath, dirnames, filenames in os.walk(root_path):
            # Calculate current depth
            rel_path = os.path.relpath(dirpath, root_path)
            depth = 0 if rel_path == '.' else len(rel_path.split(os.sep))
            
            if depth > max_depth:
                # Remove subdirectories from further walking
                dirnames[:] = []
                continue
            
            # Filter out excluded directories
            dirnames[:] = [d for d in dirnames if not self._should_exclude(os.path.join(dirpath, d))]
            
            for filename in filenames:
                file_path = os.path.join(dirpath, filename)
                rel_file_path = os.path.relpath(file_path, root_path)
                
                if self._should_exclude(file_path):
                    continue
                
                try:
                    # Get file stats
                    stat = os.stat(file_path)
                    size_bytes = stat.st_size
                    modified_time = datetime.fromtimestamp(stat.st_mtime).isoformat() + 'Z'
                    
                    # Classify component
                    classification = self._classify_component(rel_file_path)
                    
                    if classification:
                        language = classification['language']
                        component_type = classification['component_type']
                        
                        # Calculate file hash
                        file_hash = self._calculate_hash(file_path)
                        
                        # Extract dependencies
                        dependencies = self._extract_dependencies(file_path, language)
                        
                        # Create component
                        component = Component(
                            path=rel_file_path,
                            component_type=component_type,
                            size_bytes=size_bytes,
                            modified_time=modified_time,
                            language=language,
                            dependencies=dependencies,
                            metadata={
                                'full_path': file_path,
                                'depth': depth,
                                'filename': filename
                            },
                            classification=self._infer_classification(rel_file_path, component_type),
                            hash=file_hash
                        )
                        
                        components.append(component)
                        
                        # Update type counts
                        components_by_type[component_type] = components_by_type.get(component_type, 0) + 1
                        
                        logger.debug(f"Found {component_type}: {rel_file_path}")
                
                except (OSError, IOError) as e:
                    logger.warning(f"Could not process {file_path}: {e}")
        
        # Build dependency graph
        dependencies = self._build_dependency_graph(components)
        
        # Create inventory
        inventory = Inventory(
            inventory_id=inventory_id,
            timestamp=datetime.utcnow().isoformat() + 'Z',
            root_directories=[root_path],
            total_components=len(components),
            components_by_type=components_by_type,
            components=components,
            dependencies=dependencies,
            metadata={
                'scan_config': {
                    'max_depth': max_depth,
                    'exclude_patterns': self.EXCLUDE_PATTERNS
                },
                'stats': {
                    'files_scanned': len(components),
                    'unique_types': len(components_by_type),
                    'avg_dependencies': sum(len(c.dependencies) for c in components) / max(len(components), 1)
                }
            }
        )
        
        logger.info(f"Scan completed: {len(components)} components found across {len(components_by_type)} types")
        return inventory
    
    def _infer_classification(self, file_path: str, component_type: str) -> Optional[str]:
        """Infer higher-level classification based on path and type."""
        path_lower = file_path.lower()
        
        # SIMP-specific classifications
        if 'simp/' in path_lower:
            if 'agent' in path_lower or component_type == 'agent':
                return 'simp_agent'
            elif 'server' in path_lower or component_type == 'server':
                return 'simp_server'
            elif 'broker' in path_lower or component_type == 'broker':
                return 'simp_broker'
            elif 'compat' in path_lower:
                return 'simp_compat'
            elif 'mesh' in path_lower:
                return 'simp_mesh'
            elif 'orchestration' in path_lower:
                return 'simp_orchestration'
            elif 'financial' in path_lower:
                return 'simp_financial'
            elif 'test' in path_lower or component_type == 'test':
                return 'simp_test'
            else:
                return 'simp_core'
        
        # ProjectX classifications
        elif 'projectx' in path_lower:
            return 'projectx'
        
        # Stray Goose classifications
        elif 'stray_goose' in path_lower:
            return 'stray_goose'
        
        # Documentation
        elif component_type in ['readme', 'documentation']:
            return 'documentation'
        
        # Configuration
        elif component_type == 'config':
            return 'configuration'
        
        # Data
        elif component_type in ['dataset', 'log']:
            return 'data'
        
        return None
    
    def _build_dependency_graph(self, components: List[Component]) -> Dict[str, List[str]]:
        """Build dependency graph from components."""
        graph = {}
        
        for component in components:
            if component.dependencies:
                graph[component.path] = component.dependencies
        
        return graph
    
    def generate_inventory_report(self, inventory: Inventory, output_dir: str = ".") -> Dict[str, Any]:
        """Generate comprehensive inventory report."""
        report = {
            'summary': {
                'inventory_id': inventory.inventory_id,
                'timestamp': inventory.timestamp,
                'total_components': inventory.total_components,
                'unique_types': len(inventory.components_by_type),
                'root_directories': inventory.root_directories
            },
            'type_distribution': inventory.components_by_type,
            'largest_components': [],
            'recently_modified': [],
            'dependency_analysis': {
                'components_with_dependencies': sum(1 for c in inventory.components if c.dependencies),
                'total_dependencies': sum(len(c.dependencies) for c in inventory.components),
                'most_dependent_components': []
            },
            'classification_summary': {}
        }
        
        # Find largest components
        sorted_by_size = sorted(inventory.components, key=lambda c: c.size_bytes, reverse=True)[:10]
        report['largest_components'] = [
            {'path': c.path, 'size_bytes': c.size_bytes, 'type': c.component_type}
            for c in sorted_by_size
        ]
        
        # Find recently modified
        sorted_by_time = sorted(inventory.components, key=lambda c: c.modified_time, reverse=True)[:10]
        report['recently_modified'] = [
            {'path': c.path, 'modified_time': c.modified_time, 'type': c.component_type}
            for c in sorted_by_time
        ]
        
        # Find most dependent components
        sorted_by_deps = sorted(
            [c for c in inventory.components if c.dependencies],
            key=lambda c: len(c.dependencies),
            reverse=True
        )[:10]
        report['dependency_analysis']['most_dependent_components'] = [
            {'path': c.path, 'dependency_count': len(c.dependencies), 'dependencies': c.dependencies}
            for c in sorted_by_deps
        ]
        
        # Classification summary
        classifications = {}
        for component in inventory.components:
            if component.classification:
                classifications[component.classification] = classifications.get(component.classification, 0) + 1
        report['classification_summary'] = classifications
        
        # Save report
        report_path = os.path.join(output_dir, f"inventory_report_{inventory.inventory_id}.json")
        with open(report_path, 'w') as f:
            json.dump(report, f, indent=2, default=str)
        
        logger.info(f"Inventory report saved to {report_path}")
        return report


def main():
    """Command-line interface for inventory scanner."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Scan codebase and create inventory")
    parser.add_argument("directory", help="Directory to scan")
    parser.add_argument("--max-depth", type=int, default=5, help="Maximum recursion depth")
    parser.add_argument("--output", default=".", help="Output directory for inventory files")
    parser.add_argument("--generate-report", action="store_true", help="Generate detailed report")
    
    args = parser.parse_args()
    
    # Create output directory if it doesn't exist
    os.makedirs(args.output, exist_ok=True)
    
    # Scan directory
    scanner = InventoryScanner()
    inventory = scanner.scan_directory(args.directory, args.max_depth)
    
    # Save inventory
    inventory_path = os.path.join(args.output, f"inventory_{inventory.inventory_id}.json")
    inventory.save(inventory_path)
    
    print(f"✅ Inventory created: {inventory_path}")
    print(f"   Components: {inventory.total_components}")
    print(f"   Types: {len(inventory.components_by_type)}")
    
    # Generate report if requested
    if args.generate_report:
        report = scanner.generate_inventory_report(inventory, args.output)
        print(f"✅ Report generated with {len(report['type_distribution'])} component types")


if __name__ == "__main__":
    main()