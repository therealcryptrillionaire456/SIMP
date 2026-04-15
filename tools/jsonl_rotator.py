#!/usr/bin/env python3
"""
JSONL File Rotator for SIMP System

Manages rotation of large JSONL files to prevent unbounded growth.
Supports rotation based on size, age, or line count.

Usage:
    python3 tools/jsonl_rotator.py --check [--dry-run]
    python3 tools/jsonl_rotator.py --rotate agent_registry.jsonl [--max-size 100MB]
    python3 tools/jsonl_rotator.py --cleanup --keep-days 30
"""

import json
import gzip
import shutil
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import argparse
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


@dataclass
class RotationPolicy:
    """Policy for when to rotate a JSONL file"""
    max_size_mb: float = 100.0  # Rotate when file exceeds this size
    max_lines: int = 100000     # Rotate when file exceeds this many lines
    max_age_days: int = 30      # Rotate when file is older than this
    compress_old: bool = True   # Compress rotated files
    keep_compressed_days: int = 90  # Keep compressed files for this many days
    backup_count: int = 5       # Number of rotated files to keep
    
    @property
    def max_size_bytes(self) -> int:
        return int(self.max_size_mb * 1024 * 1024)


@dataclass
class FileStats:
    """Statistics for a JSONL file"""
    path: Path
    size_bytes: int
    line_count: int
    modified_time: datetime
    age_days: float
    needs_rotation: bool = False
    rotation_reason: Optional[str] = None
    
    @classmethod
    def from_path(cls, path: Path, policy: RotationPolicy) -> 'FileStats':
        """Create FileStats from file path"""
        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")
        
        stat = path.stat()
        size_bytes = stat.st_size
        line_count = 0
        
        # Count lines efficiently
        try:
            with open(path, 'r', encoding='utf-8') as f:
                line_count = sum(1 for _ in f)
        except:
            # If we can't read as text, try binary and count newlines
            with open(path, 'rb') as f:
                line_count = sum(1 for _ in f)
        
        modified_time = datetime.fromtimestamp(stat.st_mtime)
        age_days = (datetime.now() - modified_time).total_seconds() / 86400
        
        # Check if rotation is needed
        needs_rotation = False
        rotation_reason = None
        
        if size_bytes > policy.max_size_bytes:
            needs_rotation = True
            rotation_reason = f"Size ({size_bytes / (1024*1024):.1f}MB) > {policy.max_size_mb}MB"
        elif line_count > policy.max_lines:
            needs_rotation = True
            rotation_reason = f"Lines ({line_count:,}) > {policy.max_lines:,}"
        elif age_days > policy.max_age_days:
            needs_rotation = True
            rotation_reason = f"Age ({age_days:.1f} days) > {policy.max_age_days} days"
        
        return cls(
            path=path,
            size_bytes=size_bytes,
            line_count=line_count,
            modified_time=modified_time,
            age_days=age_days,
            needs_rotation=needs_rotation,
            rotation_reason=rotation_reason
        )
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization"""
        return {
            "path": str(self.path),
            "size_bytes": self.size_bytes,
            "size_mb": self.size_bytes / (1024 * 1024),
            "line_count": self.line_count,
            "modified_time": self.modified_time.isoformat(),
            "age_days": self.age_days,
            "needs_rotation": self.needs_rotation,
            "rotation_reason": self.rotation_reason
        }


class JSONLRotator:
    """Rotate JSONL files based on policies"""
    
    def __init__(self, data_dir: str = "data", policy: Optional[RotationPolicy] = None):
        self.data_dir = Path(data_dir)
        self.policy = policy or RotationPolicy()
        self.rotated_files: List[Path] = []
        
        # Default files to monitor
        self.default_files = [
            "agent_registry.jsonl",
            "task_ledger.jsonl", 
            "orchestration_plans.jsonl",
            "orchestration_log.jsonl",
            "financial_ops_proposals.jsonl",
            "security_audit.jsonl",
            "rollback_log.jsonl"
        ]
    
    def check_all_files(self) -> Dict[str, FileStats]:
        """Check all JSONL files against rotation policy"""
        stats = {}
        
        for filename in self.default_files:
            file_path = self.data_dir / filename
            if file_path.exists():
                try:
                    stats[filename] = FileStats.from_path(file_path, self.policy)
                except Exception as e:
                    print(f"Error checking {filename}: {e}")
        
        # Also check any other .jsonl files in data directory
        for file_path in self.data_dir.glob("*.jsonl"):
            if file_path.name not in stats:
                try:
                    stats[file_path.name] = FileStats.from_path(file_path, self.policy)
                except Exception as e:
                    print(f"Error checking {file_path.name}: {e}")
        
        return stats
    
    def rotate_file(self, file_path: Path, dry_run: bool = False) -> Optional[Path]:
        """Rotate a single file"""
        if not file_path.exists():
            print(f"File does not exist: {file_path}")
            return None
        
        # Generate rotation timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        rotated_name = f"{file_path.stem}.{timestamp}{file_path.suffix}"
        rotated_path = file_path.parent / rotated_name
        
        # Generate compressed name if compression is enabled
        if self.policy.compress_old:
            compressed_path = rotated_path.with_suffix(rotated_path.suffix + ".gz")
        else:
            compressed_path = None
        
        print(f"Rotating {file_path.name}:")
        print(f"  Original: {file_path}")
        print(f"  Rotated:  {rotated_path}")
        if compressed_path:
            print(f"  Compressed: {compressed_path}")
        
        if dry_run:
            print("  DRY RUN - No files changed")
            return rotated_path
        
        try:
            # 1. Rename current file to rotated name
            file_path.rename(rotated_path)
            print(f"  ✓ Renamed to {rotated_path.name}")
            
            # 2. Create new empty file
            file_path.touch()
            print(f"  ✓ Created new empty file")
            
            # 3. Compress if enabled
            if self.policy.compress_old and compressed_path:
                self._compress_file(rotated_path, compressed_path)
                print(f"  ✓ Compressed to {compressed_path.name}")
                
                # Remove uncompressed rotated file
                rotated_path.unlink()
                rotated_path = compressed_path
            
            self.rotated_files.append(rotated_path)
            return rotated_path
            
        except Exception as e:
            print(f"  ✗ Error during rotation: {e}")
            # Try to restore original state
            if rotated_path.exists() and not file_path.exists():
                try:
                    rotated_path.rename(file_path)
                    print("  ✓ Restored original file")
                except:
                    print("  ✗ Could not restore original file")
            return None
    
    def _compress_file(self, source: Path, dest: Path):
        """Compress a file using gzip"""
        with open(source, 'rb') as f_in:
            with gzip.open(dest, 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)
    
    def rotate_all_needed(self, dry_run: bool = False) -> Dict[str, Optional[Path]]:
        """Rotate all files that need rotation"""
        stats = self.check_all_files()
        results = {}
        
        files_to_rotate = [(name, stat) for name, stat in stats.items() if stat.needs_rotation]
        
        if not files_to_rotate:
            print("No files need rotation")
            return results
        
        print(f"Found {len(files_to_rotate)} file(s) needing rotation:")
        for name, stat in files_to_rotate:
            print(f"  {name}: {stat.rotation_reason}")
        
        print()
        
        for name, stat in files_to_rotate:
            print(f"\nRotating {name}...")
            rotated_path = self.rotate_file(stat.path, dry_run)
            results[name] = rotated_path
        
        return results
    
    def cleanup_old_files(self, keep_days: Optional[int] = None, dry_run: bool = False):
        """Clean up old rotated files"""
        if keep_days is None:
            keep_days = self.policy.keep_compressed_days
        
        cutoff_date = datetime.now() - timedelta(days=keep_days)
        deleted_files = []
        kept_files = []
        
        # Look for rotated files (with timestamps in name)
        pattern = "*.[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]_[0-9][0-9][0-9][0-9][0-9][0-9]*"
        
        for file_path in self.data_dir.glob(pattern):
            # Try to extract timestamp from filename
            timestamp_str = None
            for part in file_path.stem.split('.'):
                if len(part) == 15 and part[8] == '_':  # YYYYMMDD_HHMMSS
                    timestamp_str = part
                    break
            
            if not timestamp_str:
                continue
            
            try:
                file_date = datetime.strptime(timestamp_str, "%Y%m%d_%H%M%S")
            except ValueError:
                # Not a valid timestamp, skip
                continue
            
            if file_date < cutoff_date:
                deleted_files.append((file_path, file_date))
            else:
                kept_files.append((file_path, file_date))
        
        print(f"Found {len(deleted_files)} old file(s) to delete (older than {keep_days} days):")
        for file_path, file_date in deleted_files:
            age_days = (datetime.now() - file_date).days
            print(f"  {file_path.name} ({age_days} days old)")
        
        print(f"\nKeeping {len(kept_files)} file(s):")
        for file_path, file_date in kept_files:
            age_days = (datetime.now() - file_date).days
            print(f"  {file_path.name} ({age_days} days old)")
        
        if dry_run:
            print("\nDRY RUN - No files deleted")
            return
        
        # Delete old files
        deleted_count = 0
        for file_path, file_date in deleted_files:
            try:
                file_path.unlink()
                deleted_count += 1
                print(f"✓ Deleted {file_path.name}")
            except Exception as e:
                print(f"✗ Error deleting {file_path.name}: {e}")
        
        print(f"\nDeleted {deleted_count} file(s)")
    
    def enforce_backup_count(self, backup_count: Optional[int] = None, dry_run: bool = False):
        """Enforce maximum number of backup files per type"""
        if backup_count is None:
            backup_count = self.policy.backup_count
        
        # Group files by base name
        files_by_base = {}
        
        # Look for files with timestamps
        for file_path in self.data_dir.glob("*.*.jsonl*"):
            # Extract base name (without timestamp and compression suffix)
            parts = file_path.stem.split('.')
            if len(parts) >= 2:
                base_name = parts[0]
                if base_name not in files_by_base:
                    files_by_base[base_name] = []
                
                # Try to extract timestamp
                timestamp = None
                for part in parts[1:]:
                    if len(part) == 15 and part[8] == '_':  # YYYYMMDD_HHMMSS
                        try:
                            timestamp = datetime.strptime(part, "%Y%m%d_%H%M%S")
                            break
                        except ValueError:
                            continue
                
                if timestamp:
                    files_by_base[base_name].append((file_path, timestamp))
        
        deleted_count = 0
        
        for base_name, files in files_by_base.items():
            # Sort by timestamp (oldest first)
            files.sort(key=lambda x: x[1])
            
            # Keep only the newest backup_count files
            files_to_delete = files[:-backup_count] if len(files) > backup_count else []
            
            if files_to_delete:
                print(f"\n{base_name}: Keeping {backup_count} newest, deleting {len(files_to_delete)} old:")
                
                for file_path, timestamp in files_to_delete:
                    age_days = (datetime.now() - timestamp).days
                    print(f"  Delete: {file_path.name} ({age_days} days old)")
                    
                    if not dry_run:
                        try:
                            file_path.unlink()
                            deleted_count += 1
                        except Exception as e:
                            print(f"    Error: {e}")
        
        if dry_run:
            print(f"\nDRY RUN - Would delete {deleted_count} file(s)")
        else:
            print(f"\nDeleted {deleted_count} file(s)")
    
    def generate_report(self, output_file: Optional[Path] = None) -> Dict:
        """Generate a rotation report"""
        stats = self.check_all_files()
        
        report = {
            "timestamp": datetime.now().isoformat(),
            "policy": {
                "max_size_mb": self.policy.max_size_mb,
                "max_lines": self.policy.max_lines,
                "max_age_days": self.policy.max_age_days,
                "compress_old": self.policy.compress_old,
                "keep_compressed_days": self.policy.keep_compressed_days,
                "backup_count": self.policy.backup_count
            },
            "files": {name: stat.to_dict() for name, stat in stats.items()},
            "summary": {
                "total_files": len(stats),
                "files_needing_rotation": sum(1 for stat in stats.values() if stat.needs_rotation),
                "total_size_mb": sum(stat.size_bytes for stat in stats.values()) / (1024 * 1024),
                "total_lines": sum(stat.line_count for stat in stats.values())
            }
        }
        
        if output_file:
            with open(output_file, 'w') as f:
                json.dump(report, f, indent=2)
            print(f"Report saved to: {output_file}")
        
        return report


def main():
    parser = argparse.ArgumentParser(description="JSONL File Rotator for SIMP System")
    parser.add_argument("--check", action="store_true", help="Check files against rotation policy")
    parser.add_argument("--rotate", type=str, help="Rotate specific file (e.g., agent_registry.jsonl)")
    parser.add_argument("--rotate-all", action="store_true", help="Rotate all files needing rotation")
    parser.add_argument("--cleanup", action="store_true", help="Clean up old rotated files")
    parser.add_argument("--enforce-backups", action="store_true", help="Enforce maximum backup count")
    
    # Policy options
    parser.add_argument("--max-size", type=float, default=100.0, help="Maximum file size in MB (default: 100)")
    parser.add_argument("--max-lines", type=int, default=100000, help="Maximum lines per file (default: 100000)")
    parser.add_argument("--max-age", type=int, default=30, help="Maximum age in days (default: 30)")
    parser.add_argument("--keep-days", type=int, default=90, help="Keep rotated files for N days (default: 90)")
    parser.add_argument("--backup-count", type=int, default=5, help="Number of backups to keep (default: 5)")
    parser.add_argument("--no-compress", action="store_true", help="Don't compress rotated files")
    
    # General options
    parser.add_argument("--data-dir", type=str, default="data", help="Data directory path")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done without making changes")
    parser.add_argument("--report", type=str, help="Generate report file")
    
    args = parser.parse_args()
    
    data_dir = Path(args.data_dir)
    if not data_dir.exists():
        print(f"Error: Data directory does not exist: {data_dir}")
        sys.exit(1)
    
    # Create rotation policy
    policy = RotationPolicy(
        max_size_mb=args.max_size,
        max_lines=args.max_lines,
        max_age_days=args.max_age,
        compress_old=not args.no_compress,
        keep_compressed_days=args.keep_days,
        backup_count=args.backup_count
    )
    
    rotator = JSONLRotator(data_dir, policy)
    
    if args.dry_run:
        print("DRY RUN MODE - No changes will be made\n")
    
    # Generate report if requested
    if args.report:
        report_path = Path(args.report)
        rotator.generate_report(report_path)
        print()
    
    # Execute requested actions
    if args.check:
        print("Checking files against rotation policy:")
        print(f"  Max size:   {policy.max_size_mb} MB")
        print(f"  Max lines:  {policy.max_lines:,}")
        print(f"  Max age:    {policy.max_age_days} days")
        print()
        
        stats = rotator.check_all_files()
        
        if not stats:
            print("No JSONL files found")
            return
        
        print(f"{'File':30} {'Size (MB)':>10} {'Lines':>10} {'Age (days)':>10} {'Rotation':>10}")
        print("-" * 80)
        
        for name, stat in stats.items():
            size_mb = stat.size_bytes / (1024 * 1024)
            rotation = "✓" if stat.needs_rotation else "-"
            print(f"{name:30} {size_mb:10.1f} {stat.line_count:10,} {stat.age_days:10.1f} {rotation:>10}")
        
        print()
        needs_rotation = sum(1 for stat in stats.values() if stat.needs_rotation)
        total_size_mb = sum(stat.size_bytes for stat in stats.values()) / (1024 * 1024)
        
        print(f"Summary: {len(stats)} files, {needs_rotation} need rotation, total size: {total_size_mb:.1f} MB")
        
        # Show reasons for files needing rotation
        if needs_rotation > 0:
            print("\nFiles needing rotation:")
            for name, stat in stats.items():
                if stat.needs_rotation:
                    print(f"  {name}: {stat.rotation_reason}")
    
    elif args.rotate:
        file_path = data_dir / args.rotate
        if not file_path.exists():
            print(f"Error: File not found: {file_path}")
            sys.exit(1)
        
        rotator.rotate_file(file_path, args.dry_run)
    
    elif args.rotate_all:
        results = rotator.rotate_all_needed(args.dry_run)
        
        if results:
            print(f"\nRotation complete: {len(results)} file(s) rotated")
        else:
            print("No files needed rotation")
    
    elif args.cleanup:
        rotator.cleanup_old_files(args.keep_days, args.dry_run)
    
    elif args.enforce_backups:
        rotator.enforce_backup_count(args.backup_count, args.dry_run)
    
    else:
        # Default action: show status
        print("JSONL File Rotator for SIMP System")
        print("=" * 60)
        print(f"Data directory: {data_dir}")
        print()
        
        stats = rotator.check_all_files()
        
        if not stats:
            print("No JSONL files found")
            return
        
        # Show summary
        total_size_mb = sum(stat.size_bytes for stat in stats.values()) / (1024 * 1024)
        total_lines = sum(stat.line_count for stat in stats.values())
        needs_rotation = sum(1 for stat in stats.values() if stat.needs_rotation)
        
        print(f"Found {len(stats)} JSONL file(s):")
        print(f"  Total size:  {total_size_mb:.1f} MB")
        print(f"  Total lines: {total_lines:,}")
        print(f"  Need rotation: {needs_rotation} file(s)")
        print()
        
        # Show largest files
        print("Largest files:")
        sorted_stats = sorted(stats.items(), key=lambda x: x[1].size_bytes, reverse=True)
        for name, stat in sorted_stats[:5]:
            size_mb = stat.size_bytes / (1024 * 1024)
            print(f"  {name:30} {size_mb:8.1f} MB ({stat.line_count:,} lines)")
        
        print()
        print("Use --check for detailed status, --rotate-all to rotate files needing rotation")
        print("Use --help for all options")


if __name__ == "__main__":
    main()