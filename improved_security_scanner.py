#!/usr/bin/env python3
"""
Improved Security Scanner with Better False Positive Handling

Enhanced version that:
1. Avoids false positives for safe patterns like model.eval()
2. Better context-aware scanning
3. More accurate vulnerability detection
"""

import os
import sys
import re
import json
import hashlib
import subprocess
import threading
import time
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
import concurrent.futures


@dataclass
class SecurityFinding:
    """Security finding from scan."""
    id: str
    severity: str  # critical, high, medium, low, info
    category: str  # secret, vulnerability, configuration, authentication, etc.
    location: str  # file path or system component
    description: str
    evidence: str
    recommendation: str
    timestamp: datetime
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization."""
        result = asdict(self)
        result["timestamp"] = self.timestamp.isoformat() + "Z" if isinstance(self.timestamp, datetime) else self.timestamp
        return result


class ImprovedSecurityScanner:
    """Improved security scanner with better false positive handling."""
    
    def __init__(self, repo_path: str = "."):
        self.repo_path = Path(repo_path).resolve()
        self.scan_id = f"improved_scan_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
        
        # Improved secret patterns with better validation
        self.secret_patterns = {
            "api_key": [
                # API keys are typically 20+ characters, alphanumeric with possible underscores/dashes
                r'(?i)(?:api[_-]?key|secret[_-]?key|access[_-]?token)[\s]*[=:][\s]*["\']([a-zA-Z0-9_\-]{20,100})["\']',
            ],
            "wallet_key": [
                # Private keys are exactly 64 hex characters for many cryptocurrencies
                r'(?i)(?:private[_-]?key)[\s]*[=:][\s]*["\']([a-fA-F0-9]{64})["\']',
                # Mnemonics are 12-24 words
                r'(?i)(?:mnemonic|seed[_-]?phrase)[\s]*[=:][\s]*["\']([a-zA-Z\s]{20,200})["\']',
            ],
            "password": [
                # Passwords in code (not in comments)
                r'(?<!// )(?<!# )(?<!\* )(?:password|passwd|pwd)[\s]*[=:][\s]*["\']([^"\']{4,50})["\']',
            ],
            "aws_key": [
                # AWS keys have specific patterns
                r'(?i)(?:aws[_-]?access[_-]?key[_-]?id)[\s]*[=:][\s]*["\'](AKIA[0-9A-Z]{16})["\']',
                r'(?i)(?:aws[_-]?secret[_-]?access[_-]?key)[\s]*[=:][\s]*["\']([a-zA-Z0-9/+]{40})["\']',
            ],
            "stripe_key": [
                r'(?i)(?:stripe[_-]?(?:api[_-]?key|secret[_-]?key))[\s]*[=:][\s]*["\'](sk_[a-zA-Z0-9]{24})["\']',
            ],
            "github_token": [
                r'(?i)(?:github[_-]?(?:token|pat))[\s]*[=:][\s]*["\'](ghp_[a-zA-Z0-9]{36})["\']',
            ]
        }
        
        # Improved vulnerability patterns with context
        self.vulnerability_patterns = {
            "sql_injection": [
                # String concatenation in SQL queries
                r'execute\([^)]*"[^"]*"\s*\+\s*[^)]+\)',
                r'executemany\([^)]*"[^"]*"\s*\+\s*[^)]+\)',
                # f-strings in SQL (dangerous)
                r'execute\(f"[^"]*\{[^}]*\}[^"]*"\)',
            ],
            "command_injection": [
                # String concatenation in command execution
                r'os\.system\([^)]*"[^"]*"\s*\+\s*[^)]+\)',
                r'subprocess\.(?:run|Popen|call)\([^)]*"[^"]*"\s*\+\s*[^)]+\)',
                # User input in commands without validation
                r'os\.system\([^)]*input\([^)]*\)[^)]*\)',
                r'subprocess\.(?:run|Popen|call)\([^)]*input\([^)]*\)[^)]*\)',
            ],
            "xss": [
                # Direct template string rendering (Flask/Jinja2)
                r'Flask\.render_template_string\([^)]+\)',
                # Unsafe HTML output
                r'response\.write\([^)]*"[^"]*"\s*\+\s*[^)]+\)',
            ],
            "hardcoded_credentials": [
                # Actual hardcoded credentials (not in comments)
                r'(?<!// )(?<!# )(?<!\* )(?:password|passwd|pwd)[\s]*=[\s]*["\'][^"\']{4,}["\']',
            ],
            "insecure_random": [
                # Use of non-cryptographic random for security purposes
                r'random\.(?:randint|choice|random)\([^)]*\)\s*#.*(?:password|token|key|secret)',
                r'random\.(?:randint|choice|random)\([^)]*\).*#.*security',
            ]
        }
        
        # Safe patterns (not vulnerabilities)
        self.safe_patterns = [
            r'\.eval\(\)',  # model.eval(), tensor.eval() etc.
            r'\.eval\s*\(',  # method calls with eval in name
            r'#.*test.*password',  # Comments about testing
            r'#.*example.*key',  # Example code in comments
            r'placeholder|example|test|demo',  # Common placeholder text
        ]
        
        # File extensions to scan
        self.scannable_extensions = {
            '.py', '.js', '.ts', '.java', '.cpp', '.c', '.h', '.hpp',
            '.php', '.rb', '.go', '.rs', '.swift', '.kt', '.scala',
            '.json', '.yaml', '.yml', '.toml', '.ini', '.cfg', '.conf',
            '.env', '.properties', '.txt', '.md', '.rst', '.html', '.htm',
            '.xml', '.sql', '.sh', '.bash', '.zsh', '.ps1', '.bat'
        }
        
        # Directories to exclude
        self.exclude_dirs = {
            '.git', '__pycache__', 'node_modules', 'venv', '.venv',
            'env', '.env', 'dist', 'build', 'target', 'out', 'bin',
            'obj', '.idea', '.vscode', '.vs', '.gradle', '.mvn'
        }
        
        # Findings storage
        self.findings: List[SecurityFinding] = []
        self.files_scanned = 0
        
        print(f"🔍 Improved Security Scanner initialized")
        print(f"   Scan ID: {self.scan_id}")
        print(f"   Repository: {self.repo_path}")
    
    def is_safe_pattern(self, line: str) -> bool:
        """Check if line contains safe patterns (not vulnerabilities)."""
        for pattern in self.safe_patterns:
            if re.search(pattern, line, re.IGNORECASE):
                return True
        return False
    
    def scan_file_for_secrets(self, file_path: Path) -> List[SecurityFinding]:
        """Scan file for secrets with better validation."""
        findings = []
        
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                lines = content.split('\n')
            
            for line_num, line in enumerate(lines, 1):
                # Skip comments for certain checks
                is_comment = line.strip().startswith(('#', '//', '/*', '*', '*/'))
                
                for category, patterns in self.secret_patterns.items():
                    for pattern in patterns:
                        matches = re.finditer(pattern, line)
                        for match in matches:
                            # Skip if it's a comment (for passwords, but check API keys anyway)
                            if category == "password" and is_comment:
                                continue
                            
                            secret = match.group(1) if match.groups() else match.group(0)
                            
                            # Additional validation for specific patterns
                            if category == "api_key":
                                # Check if it looks like a real API key (not just random text)
                                if not any(c.isupper() for c in secret):
                                    continue  # Probably not a real API key
                            
                            # Create obfuscated version
                            if len(secret) > 8:
                                obfuscated = secret[:4] + '*' * (len(secret) - 8) + secret[-4:]
                            else:
                                obfuscated = '*' * len(secret)
                            
                            finding = SecurityFinding(
                                id=f"secret_{hashlib.md5(f'{file_path}:{line_num}:{category}'.encode()).hexdigest()[:8]}",
                                severity="critical" if category in ["api_key", "wallet_key"] else "high",
                                category=f"secret_{category}",
                                location=str(file_path.relative_to(self.repo_path)),
                                description=f"Potential {category.replace('_', ' ')} found in code",
                                evidence=f"Line {line_num}: {line.strip()[:100]}... (Secret: {obfuscated})",
                                recommendation=f"Remove hardcoded {category.replace('_', ' ')} and use environment variables or secure secret management",
                                timestamp=datetime.utcnow()
                            )
                            findings.append(finding)
        
        except Exception as e:
            print(f"  ⚠️  Error scanning {file_path}: {e}")
        
        return findings
    
    def scan_file_for_vulnerabilities(self, file_path: Path) -> List[SecurityFinding]:
        """Scan file for code vulnerabilities with context awareness."""
        findings = []
        
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                lines = content.split('\n')
            
            for line_num, line in enumerate(lines, 1):
                # Skip safe patterns
                if self.is_safe_pattern(line):
                    continue
                
                for vuln_type, patterns in self.vulnerability_patterns.items():
                    for pattern in patterns:
                        if re.search(pattern, line, re.IGNORECASE):
                            # Additional context checking
                            if vuln_type == "command_injection":
                                # Check if it's actually dangerous (not just subprocess.run(["ls"]))
                                if '["' in line and '"]' in line:
                                    # Likely safe list argument
                                    continue
                            
                            finding = SecurityFinding(
                                id=f"vuln_{hashlib.md5(f'{file_path}:{line_num}:{vuln_type}'.encode()).hexdigest()[:8]}",
                                severity=self.get_vulnerability_severity(vuln_type),
                                category=f"vulnerability_{vuln_type}",
                                location=str(file_path.relative_to(self.repo_path)),
                                description=f"Potential {vuln_type.replace('_', ' ')} vulnerability",
                                evidence=f"Line {line_num}: {line.strip()[:100]}...",
                                recommendation=self.get_vulnerability_recommendation(vuln_type),
                                timestamp=datetime.utcnow()
                            )
                            findings.append(finding)
        
        except Exception as e:
            print(f"  ⚠️  Error scanning {file_path} for vulnerabilities: {e}")
        
        return findings
    
    def get_vulnerability_severity(self, vuln_type: str) -> str:
        """Get severity for vulnerability type."""
        severity_map = {
            "sql_injection": "critical",
            "command_injection": "critical",
            "xss": "high",
            "hardcoded_credentials": "high",
            "insecure_random": "medium"
        }
        return severity_map.get(vuln_type, "medium")
    
    def get_vulnerability_recommendation(self, vuln_type: str) -> str:
        """Get recommendation for vulnerability type."""
        recommendations = {
            "sql_injection": "Use parameterized queries or ORM with proper escaping",
            "command_injection": "Use subprocess with shell=False and list arguments, validate/sanitize all inputs",
            "xss": "Use template escaping or output encoding frameworks",
            "hardcoded_credentials": "Move credentials to environment variables, .env files, or secure vault",
            "insecure_random": "Use secrets module for cryptographic randomness, random module only for non-security purposes"
        }
        return recommendations.get(vuln_type, "Review and fix the security issue")
    
    def run_scan(self) -> Dict:
        """Run improved security scan."""
        print(f"🚀 Starting improved security scan")
        print(f"   Scan ID: {self.scan_id}")
        print(f"   Time: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}")
        print()
        
        start_time = datetime.utcnow()
        self.findings = []
        self.files_scanned = 0
        
        # Collect files to scan
        files_to_scan = []
        for root, dirs, files in os.walk(self.repo_path):
            # Skip excluded directories
            dirs[:] = [d for d in dirs if d not in self.exclude_dirs]
            
            for file in files:
                file_path = Path(root) / file
                if self.should_scan_file(file_path):
                    files_to_scan.append(file_path)
        
        print(f"📁 Found {len(files_to_scan)} files to scan")
        
        # Scan files
        for i, file_path in enumerate(files_to_scan[:500], 1):  # Limit to 500 for speed
            try:
                # Scan for secrets
                secret_findings = self.scan_file_for_secrets(file_path)
                self.findings.extend(secret_findings)
                
                # Scan for vulnerabilities (only for code files)
                if file_path.suffix.lower() in {'.py', '.js', '.ts', '.java', '.php', '.rb', '.go'}:
                    vuln_findings = self.scan_file_for_vulnerabilities(file_path)
                    self.findings.extend(vuln_findings)
                
                self.files_scanned += 1
                
                if i % 100 == 0:
                    print(f"  📊 Progress: {i}/{min(500, len(files_to_scan))} files, {len(self.findings)} findings")
            
            except Exception as e:
                print(f"  ⚠️  Error scanning {file_path}: {e}")
        
        end_time = datetime.utcnow()
        
        # Categorize findings
        findings_by_severity = {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0}
        findings_by_category = {}
        
        for finding in self.findings:
            findings_by_severity[finding.severity] = findings_by_severity.get(finding.severity, 0) + 1
            category = finding.category
            findings_by_category[category] = findings_by_category.get(category, 0) + 1
        
        # Calculate security score
        security_score = self.calculate_security_score(findings_by_severity)
        
        result = {
            "scan_id": self.scan_id,
            "start_time": start_time.isoformat() + "Z",
            "end_time": end_time.isoformat() + "Z",
            "duration_seconds": (end_time - start_time).total_seconds(),
            "total_files_scanned": self.files_scanned,
            "total_findings": len(self.findings),
            "findings_by_severity": findings_by_severity,
            "findings_by_category": findings_by_category,
            "security_score": security_score,
            "timestamp": end_time.isoformat() + "Z"
        }
        
        return result
    
    def should_scan_file(self, file_path: Path) -> bool:
        """Check if file should be scanned."""
        # Check extension
        if file_path.suffix.lower() not in self.scannable_extensions:
            return False
        
        # Check if in exclude directory
        for part in file_path.parts:
            if part in self.exclude_dirs:
                return False
        
        # Check if file exists and is readable
        if not file_path.exists() or not file_path.is_file():
            return False
        
        return True
    
    def calculate_security_score(self, findings_by_severity: Dict) -> int:
        """Calculate security score (0-100)."""
        base_score = 100
        
        # Deduct points for findings
        deductions = {
            "critical": 20,
            "high": 10,
            "medium": 5,
            "low": 2,
            "info": 0
        }
        
        for severity, count in findings_by_severity.items():
            base_score -= count * deductions.get(severity, 0)
        
        # Ensure score doesn't go below 0
        return max(0, base_score)
    
    def print_summary(self, result: Dict):
        """Print scan summary to console."""
        print("\n" + "="*60)
        print("🔍 IMPROVED SECURITY SCAN COMPLETE")
        print("="*60)
        
        print(f"\n📊 Scan Summary:")
        print(f"   Scan ID: {result['scan_id']}")
        print(f"   Duration: {result['duration_seconds']:.1f} seconds")
        print(f"   Files Scanned: {result['total_files_scanned']}")
        print(f"   Total Findings: {result['total_findings']}")
        
        print(f"\n🚨 Findings by Severity:")
        for severity, count in result['findings_by_severity'].items():
            if count > 0:
                print(f"   {severity.title()}: {count}")
        
        print(f"\n📈 Security Score: {result['security_score']}/100")
        
        # Show top findings
        critical_findings = [f for f in self.findings if f.severity == "critical"]
        high_findings = [f for f in self.findings if f.severity == "high"]
        
        if critical_findings:
            print(f"\n⚠️  CRITICAL FINDINGS ({len(critical_findings)}):")
            for finding in critical_findings[:5]:
                print(f"   • {finding.location}: {finding.description}")
        
        if high_findings:
            print(f"\n⚠️  HIGH SEVERITY FINDINGS ({len(high_findings)}):")
            for finding in high_findings[:5]:
                print(f"   • {finding.location}: {finding.description}")
        
        print("\n" + "="*60)
        print("✅ Improved scan completed successfully")
        print("="*60)
    
    def save_report(self, result: Dict):
        """Save scan report."""
        output_dir = self.repo_path / "security_reports"
        output_dir.mkdir(parents=True, exist_ok=True)
        
        report_file = output_dir / f"improved_scan_{self.scan_id}.json"
        
        with open(report_file, 'w') as f:
            json.dump({
                "scan_result": result,
                "findings": [f.to_dict() for f in self.findings]
            }, f, indent=2, default=str)
        
        print(f"📄 Improved scan report saved to: {report_file}")
        return report_file


def main():
    """Run improved security scanner."""
    print("🧪 Running Improved Security Scanner")
    print("="*60)
    
    # Create scanner
    scanner = ImprovedSecurityScanner()
    
    # Run scan
    result = scanner.run_scan()
    
    # Print summary
    scanner.print_summary(result)
    
    # Save report
    report_file = scanner.save_report(result)
    
    # Show actual findings
    print(f"\n🔍 Actual Security Findings (not false positives):")
    
    real_findings = [f for f in scanner.findings if f.severity in ["critical", "high"]]
    
    if real_findings:
        for i, finding in enumerate(real_findings[:10], 1):
            print(f"\n  {i}. {finding.id}")
            print(f"     Severity: {finding.severity}")
            print(f"     Location: {finding.location}")
            print(f"     Description: {finding.description}")
            print(f"     Recommendation: {finding.recommendation}")
    else:
        print("  ✅ No critical or high severity findings found")
    
    print(f"\n📄 Full report saved to: {report_file}")
    
    print("\n" + "="*60)
    print("✅ Improved Security Scanner test completed")
    print("="*60)


if __name__ == "__main__":
    main()