#!/usr/bin/env python3
"""
JSONL File Rotation Tool for SIMP System

This tool manages rotation of large JSONL files to prevent disk space issues
and maintain system performance. It provides automatic rotation based on size
and age thresholds.

Usage:
    python3 tools/jsonl_rotator.py --check
    python3 tools/jsonl_rotator.py --rotate --max-size 100
    python3 tools/jsonl_rotator.py --rotate --max-age 30
    python3 tools/jsonl_rotator.py --rotate --max-size 50 --max-age 7
    python3 tools/jsonl_rotator.py --status
"""

import json
import gzip
import shutil
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any
import argparse
import sys
import os
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@dataclass
class FileStats:
    """Statistics for a JSONL file"""
    path: Path
    size_bytes: int
    line_count: int
    last_modified: datetime
    compressed_size: Optional[int] = None
    compressed_path: Optional[Path] = None

class JSONLRotator:
    """Manages rotation of JSONL files"""
    
    def __init__(self, data_dir: str = "data", archive_dir: str = "data/archive"):
        self.data_dir = Path(data_dir)
        self.archive_dir = Path(archive_dir)
        self.archive_dir.mkdir(parents=True, exist_ok=True)
        
        # Files to monitor and their rotation thresholds
        self.file_configs = {
            "task_ledger.jsonl": {
                "max_size_mb": 100,  # Rotate when > 100MB
                "max_age_days": 30,  # Rotate when > 30 days old
                "compress": True,
                "keep_recent": 5,    # Keep 5 most recent versions
                "keep_compressed": 10  # Keep 10 compressed versions
            },
            "agent_registry.jsonl": {
                "max_size_mb": 10,   # Rotate when > 10MB
                "max_age_days": 90,  # Rotate when > 90 days old
                "compress": True,
                "keep_recent": 3,
                "keep_compressed": 5
            },
            "orchestration_plans.jsonl": {
                "max_size_mb": 50,   # Rotate when > 50MB
                "max_age_days": 60,  # Rotate when > 60 days old
                "compress": True,
                "keep_recent": 3,
                "keep_compressed": 5
            },
            "orchestration_log.jsonl": {
                "max_size_mb": 50,   # Rotate when > 50MB
                "max_age_days": 30,  # Rotate when > 30 days old
                "compress": True,
                "keep_recent": 3,
                "keep_compressed": 5
            },
            "financial_ops_proposals.jsonl": {
                "max_size_mb": 25,   # Rotate when > 25MB
                "max_age_days": 45,  # Rotate when > 45 days old
                "compress": True,
                "keep_recent": 3,
                "keep_compressed": 5
            }
        }
    
    def get_file_stats(self, file_path: Path) -> Optional[FileStats]:
        """Get statistics for a JSONL file"""
        if not file_path.exists():
            return None
            
        stat = file_path.stat()
        last_modified = datetime.fromtimestamp(stat.st_mtime)
        line_count = 0
        
        try:
            with open(file_path, 'r') as f:
                line_count = sum(1 for _ in f)
        except Exception as e:
            logger.warning(f"Error reading {file_path}: {e}")
        
        # Check for compressed version
        compressed_path = file_path.with_suffix('.jsonl.gz')
        compressed_size = None
        if compressed_path.exists():
            compressed_size = compressed_path.stat().st_size
        
        return FileStats(
            path=file_path,
            size_bytes=stat.st_size,
            line_count=line_count,
            last_modified=last_modified,
            compressed_size=compressed_size,
            compressed_path=compressed_path
        )
    
    def should_rotate(self, file_path: Path, config: Dict[str, Any]) -> bool:
        """Check if a file should be rotated based on size and age"""
        stats = self.get_file_stats(file_path)
        if not stats:
            return False
        
        # Check size threshold
        max_size_bytes = config["max_size_mb"] * 1024 * 1024
        if stats.size_bytes > max_size_bytes:
            logger.info(f"File {file_path} exceeds size threshold: {stats.size_bytes / (1024*1024):.2f}MB > {config['max_size_mb']}MB")
            return True
        
        # Check age threshold
        max_age = datetime.now() - timedelta(days=config["max_age_days"])
        if stats.last_modified < max_age:
            logger.info(f"File {file_path} exceeds age threshold: {stats.last_modified} > {max_age}")
            return True
        
        return False
    
    def rotate_file(self, file_path: Path, config: Dict[str, Any]) -> bool:
        """Rotate a single file"""
        try:
            stats = self.get_file_stats(file_path)
            if not stats:
                return False
            
            # Create timestamped filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            base_name = file_path.stem
            rotated_name = f"{base_name}_{timestamp}.jsonl"
            rotated_path = self.archive_dir / rotated_name
            
            # Move file to archive
            logger.info(f"Rotating {file_path} to {rotated_path}")
            shutil.move(str(file_path), str(rotated_path))
            
            # Compress if enabled
            if config["compress"]:
                compressed_path = rotated_path.with_suffix('.jsonl.gz')
                logger.info(f"Compressing {rotated_path} to {compressed_path}")
                with open(rotated_path, 'rb') as f_in:
                    with gzip.open(compressed_path, 'wb') as f_out:
                        shutil.copyfileobj(f_in, f_out)
                
                # Remove original compressed file
                rotated_path.unlink()
                
                # Clean up old compressed files
                self._cleanup_old_versions(file_path.stem, config, compressed=True)
            else:
                # Clean up old uncompressed files
                self._cleanup_old_versions(file_path.stem, config, compressed=False)
            
            logger.info(f"Successfully rotated {file_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error rotating {file_path}: {e}")
            return False
    
    def _cleanup_old_versions(self, base_name: str, config: Dict[str, Any], compressed: bool = False):
        """Clean up old versions of a file"""
        suffix = '.jsonl.gz' if compressed else '.jsonl'
        pattern = f"{base_name}_*{suffix}"
        
        # Find all matching files
        files = list(self.archive_dir.glob(pattern))
        files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
        
        # Remove old files
        keep_count = config["keep_compressed"] if compressed else config["keep_recent"]
        for old_file in files[keep_count:]:
            try:
                old_file.unlink()
                logger.info(f"Removed old version: {old_file}")
            except Exception as e:
                logger.warning(f"Error removing {old_file}: {e}")
    
    def check_all_files(self) -> Dict[str, Any]:
        """Check all files and return rotation status"""
        status = {
            "timestamp": datetime.now().isoformat(),
            "files": {},
            "needs_rotation": []
        }
        
        for filename, config in self.file_configs.items():
            file_path = self.data_dir / filename
            stats = self.get_file_stats(file_path)
            
            if not stats:
                status["files"][filename] = {
                    "exists": False,
                    "should_rotate": False
                }
                continue
            
            should_rotate = self.should_rotate(file_path, config)
            
            status["files"][filename] = {
                "exists": True,
                "size_bytes": stats.size_bytes,
                "size_mb": stats.size_bytes / (1024 * 1024),
                "line_count": stats.line_count,
                "last_modified": stats.last_modified.isoformat(),
                "compressed_exists": stats.compressed_path is not None,
                "compressed_size": stats.compressed_size,
                "should_rotate": should_rotate
            }
            
            if should_rotate:
                status["needs_rotation"].append(filename)
        
        return status
    
    def rotate_all_files(self) -> Dict[str, Any]:
        """Rotate all files that need rotation"""
        results = {
            "timestamp": datetime.now().isoformat(),
            "rotated": [],
            "failed": [],
            "skipped": []
        }
        
        status = self.check_all_files()
        
        for filename in status["needs_rotation"]:
            file_path = self.data_dir / filename
            config = self.file_configs[filename]
            
            if self.rotate_file(file_path, config):
                results["rotated"].append(filename)
            else:
                results["failed"].append(filename)
        
        # Files that don't need rotation
        for filename, file_info in status["files"].items():
            if file_info["exists"] and not file_info["should_rotate"]:
                results["skipped"].append(filename)
        
        return results

def main():
    parser = argparse.ArgumentParser(description="JSONL File Rotation Tool")
    parser.add_argument("--check", action="store_true", help="Check which files need rotation")
    parser.add_argument("--rotate", action="store_true", help="Rotate files that need rotation")
    parser.add_argument("--status", action="store_true", help="Show current file status")
    parser.add_argument("--max-size", type=float, help="Override max size in MB")
    parser.add_argument("--max-age", type=int, help="Override max age in days")
    parser.add_argument("--data-dir", default="data", help="Data directory path")
    parser.add_argument("--archive-dir", default="data/archive", help="Archive directory path")
    
    args = parser.parse_args()
    
    rotator = JSONLRotator(args.data_dir, args.archive_dir)
    
    if args.check:
        status = rotator.check_all_files()
        print("JSONL File Rotation Status")
        print("=" * 50)
        print(f"Timestamp: {status['timestamp']}")
        print()
        
        for filename, file_info in status["files"].items():
            if file_info["exists"]:
                size_mb = file_info["size_mb"]
                print(f"{filename:30} | {size_mb:8.2f} MB | {file_info['line_count']:8,d} lines | "
                      f"{'ROTATE' if file_info['should_rotate'] else 'OK'}")
            else:
                print(f"{filename:30} | File does not exist")
        
        if status["needs_rotation"]:
            print(f"\nFiles needing rotation: {len(status['needs_rotation'])}")
            for filename in status["needs_rotation"]:
                print(f"  - {filename}")
        else:
            print("\nNo files need rotation")
    
    elif args.rotate:
        results = rotator.rotate_all_files()
        print("JSONL File Rotation Results")
        print("=" * 50)
        print(f"Timestamp: {results['timestamp']}")
        print()
        print(f"Rotated: {len(results['rotated'])}")
        for filename in results["rotated"]:
            print(f"  ✓ {filename}")
        
        print(f"Failed: {len(results['failed'])}")
        for filename in results["failed"]:
            print(f"  ✗ {filename}")
        
        print(f"Skipped: {len(results['skipped'])}")
        for filename in results["skipped"]:
            print(f"  - {filename}")
    
    elif args.status:
        status = rotator.check_all_files()
        print("JSONL File Status")
        print("=" * 50)
        print(f"Timestamp: {status['timestamp']}")
        print()
        
        for filename, file_info in status["files"].items():
            if file_info["exists"]:
                size_mb = file_info["size_mb"]
                compressed_mb = file_info["compressed_size"] / (1024 * 1024) if file_info["compressed_size"] else 0
                print(f"{filename:30} | {size_mb:8.2f} MB | {file_info['line_count']:8,d} lines | "
                      f"{'COMPRESSED' if file_info['compressed_exists'] else 'UNCOMPRESSED'}")
                if file_info["compressed_exists"]:
                    print(f"{'':30} | {compressed_mb:8.2f} MB (compressed)")
                if file_info["should_rotate"]:
                    print(f"{'':30} | ⚠️  NEEDS ROTATION")
            else:
                print(f"{filename:30} | File does not exist")
    
    else:
        parser.print_help()

if __name__ == "__main__":
    main()