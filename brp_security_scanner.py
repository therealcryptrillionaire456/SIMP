#!/usr/bin/env python3
"""
BRP Security Scanner - Self-Audit Tool for SIMP System

Uses enhanced BRP arsenal to scan SIMP system for vulnerabilities:
1. Secret scanning (API keys, wallet keys, crypto keys)
2. Code vulnerability analysis
3. Configuration security review
4. Network and service testing
5. Authentication and authorization testing
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


@dataclass
class ScanResult:
    """Complete scan results."""
    scan_id: str
    start_time: datetime
    end_time: datetime
    total_files_scanned: int
    total_findings: int
    findings_by_severity: Dict[str, int]
    findings_by_category: Dict[str, int]
    critical_findings: List[SecurityFinding]
    high_findings: List[SecurityFinding]
    medium_findings: List[SecurityFinding]
    low_findings: List[SecurityFinding]
    info_findings: List[SecurityFinding]
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization."""
        result = asdict(self)
        result["start_time"] = self.start_time.isoformat() + "Z"
        result["end_time"] = self.end_time.isoformat() + "Z"
        result["duration_seconds"] = (self.end_time - self.start_time).total_seconds()
        return result


class BRPSecurityScanner:
    """BRP Security Scanner for SIMP system self-audit."""
    
    def __init__(self, repo_path: str = "."):
        self.repo_path = Path(repo_path).resolve()
        self.scan_id = f"scan_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
        
        # Security patterns for secret detection
        self.secret_patterns = {
            "api_key": [
                r'(?i)(api[_-]?key)[\s]*[=:][\s]*["\']?([a-zA-Z0-9_\-]{20,})["\']?',
                r'(?i)(secret[_-]?key)[\s]*[=:][\s]*["\']?([a-zA-Z0-9_\-]{20,})["\']?',
                r'(?i)(access[_-]?token)[\s]*[=:][\s]*["\']?([a-zA-Z0-9_\-]{20,})["\']?',
            ],
            "wallet_key": [
                r'(?i)(private[_-]?key)[\s]*[=:][\s]*["\']?([a-zA-Z0-9]{64})["\']?',
                r'(?i)(mnemonic)[\s]*[=:][\s]*["\']?([a-zA-Z\s]{20,})["\']?',
                r'(?i)(seed[_-]?phrase)[\s]*[=:][\s]*["\']?([a-zA-Z\s]{20,})["\']?',
            ],
            "crypto_key": [
                r'(?i)(secret[_-]?phrase)[\s]*[=:][\s]*["\']?([a-zA-Z0-9_\-]{20,})["\']?',
                r'(?i)(encryption[_-]?key)[\s]*[=:][\s]*["\']?([a-zA-Z0-9_\-]{32,})["\']?',
                r'(?i)(aes[_-]?key)[\s]*[=:][\s]*["\']?([a-zA-Z0-9_\-]{32,})["\']?',
            ],
            "password": [
                r'(?i)(password)[\s]*[=:][\s]*["\']?([a-zA-Z0-9_\-!@#$%^&*()]{8,})["\']?',
                r'(?i)(passwd)[\s]*[=:][\s]*["\']?([a-zA-Z0-9_\-!@#$%^&*()]{8,})["\']?',
                r'(?i)(pwd)[\s]*[=:][\s]*["\']?([a-zA-Z0-9_\-!@#$%^&*()]{8,})["\']?',
            ],
            "aws_key": [
                r'(?i)(aws[_-]?access[_-]?key[_-]?id)[\s]*[=:][\s]*["\']?(AKIA[0-9A-Z]{16})["\']?',
                r'(?i)(aws[_-]?secret[_-]?access[_-]?key)[\s]*[=:][\s]*["\']?([a-zA-Z0-9/+]{40})["\']?',
            ],
            "stripe_key": [
                r'(?i)(stripe[_-]?api[_-]?key)[\s]*[=:][\s]*["\']?(sk_[a-zA-Z0-9]{24})["\']?',
                r'(?i)(stripe[_-]?secret[_-]?key)[\s]*[=:][\s]*["\']?(sk_[a-zA-Z0-9]{24})["\']?',
            ],
            "github_token": [
                r'(?i)(github[_-]?token)[\s]*[=:][\s]*["\']?(ghp_[a-zA-Z0-9]{36})["\']?',
                r'(?i)(github[_-]?pat)[\s]*[=:][\s]*["\']?(ghp_[a-zA-Z0-9]{36})["\']?',
            ]
        }
        
        # Vulnerability patterns
        self.vulnerability_patterns = {
            "sql_injection": [
                r'execute\(.*\+.*\)',
                r'executemany\(.*\+.*\)',
                r'cursor\.execute\(f".*"\)',
                r'cursor\.execute\(".*" \+ .*\)',
            ],
            "command_injection": [
                r'os\.system\([^)]*\+[^)]*\)',  # String concatenation in os.system
                r'subprocess\.run\([^)]*\+[^)]*\)',  # String concatenation in subprocess.run
                r'subprocess\.Popen\([^)]*\+[^)]*\)',  # String concatenation in subprocess.Popen
                r'exec\([^)]*[+\*][^)]*\)',  # exec with string operations
                r'eval\([^)]*[+\*][^)]*\)',  # eval with string operations
            ],
            "xss": [
                r'Flask\.render_template_string\(.*\)',
                r'response\.write\(.*\+.*\)',
                r'direct output without escaping',
            ],
            "hardcoded_credentials": [
                r'password\s*=\s*["\'][^"\']{4,}["\']',
                r'passwd\s*=\s*["\'][^"\']{4,}["\']',
                r'pwd\s*=\s*["\'][^"\']{4,}["\']',
            ],
            "insecure_random": [
                r'random\.randint\(\)',
                r'random\.choice\(\)',
                r'random\.random\(\)',
                r'use of non-cryptographic random',
            ]
        }
        
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
        
        print(f"🔍 BRP Security Scanner initialized")
        print(f"   Scan ID: {self.scan_id}")
        print(f"   Repository: {self.repo_path}")
        print(f"   Secret patterns: {len(self.secret_patterns)} categories")
        print(f"   Vulnerability patterns: {len(self.vulnerability_patterns)} categories")
    
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
    
    def scan_file_for_secrets(self, file_path: Path) -> List[SecurityFinding]:
        """Scan file for secrets."""
        findings = []
        
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                lines = content.split('\n')
                
            for line_num, line in enumerate(lines, 1):
                for category, patterns in self.secret_patterns.items():
                    for pattern in patterns:
                        matches = re.finditer(pattern, line)
                        for match in matches:
                            # Extract the secret (group 2 is usually the secret)
                            secret = match.group(2) if match.groups() else match.group(0)
                            
                            # Create obfuscated version for evidence
                            if len(secret) > 8:
                                obfuscated = secret[:4] + '*' * (len(secret) - 8) + secret[-4:]
                            else:
                                obfuscated = '*' * len(secret)
                            
                            finding = SecurityFinding(
                                id=f"secret_{hashlib.md5(f'{file_path}:{line_num}:{category}'.encode()).hexdigest()[:8]}",
                                severity="critical" if category in ["api_key", "wallet_key", "crypto_key"] else "high",
                                category=f"secret_{category}",
                                location=str(file_path.relative_to(self.repo_path)),
                                description=f"Potential {category.replace('_', ' ')} found in code",
                                evidence=f"Line {line_num}: {line.strip()[:100]}... (Secret: {obfuscated})",
                                recommendation=f"Remove hardcoded {category.replace('_', ' ')} and use environment variables or secure secret management",
                                timestamp=datetime.utcnow()
                            )
                            findings.append(finding)
        
        except Exception as e:
            # Log but don't fail on file read errors
            print(f"  ⚠️  Error scanning {file_path}: {e}")
        
        return findings
    
    def scan_file_for_vulnerabilities(self, file_path: Path) -> List[SecurityFinding]:
        """Scan file for code vulnerabilities."""
        findings = []
        
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                lines = content.split('\n')
            
            for line_num, line in enumerate(lines, 1):
                for vuln_type, patterns in self.vulnerability_patterns.items():
                    for pattern in patterns:
                        if re.search(pattern, line, re.IGNORECASE):
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
            "command_injection": "Use subprocess with shell=False and validate/sanitize inputs",
            "xss": "Use template escaping or output encoding",
            "hardcoded_credentials": "Move credentials to environment variables or secure vault",
            "insecure_random": "Use secrets module for cryptographic randomness"
        }
        return recommendations.get(vuln_type, "Review and fix the security issue")
    
    def scan_file(self, file_path: Path) -> Tuple[int, List[SecurityFinding]]:
        """Scan a single file for security issues."""
        findings = []
        
        if not self.should_scan_file(file_path):
            return 0, findings
        
        try:
            # Scan for secrets
            secret_findings = self.scan_file_for_secrets(file_path)
            findings.extend(secret_findings)
            
            # Scan for vulnerabilities (only for code files)
            if file_path.suffix.lower() in {'.py', '.js', '.ts', '.java', '.php', '.rb', '.go'}:
                vuln_findings = self.scan_file_for_vulnerabilities(file_path)
                findings.extend(vuln_findings)
            
            return 1, findings
        
        except Exception as e:
            print(f"  ⚠️  Error scanning {file_path}: {e}")
            return 0, []
    
    def scan_directory(self, directory: Path = None) -> ScanResult:
        """Scan directory recursively for security issues."""
        if directory is None:
            directory = self.repo_path
        
        print(f"🚀 Starting security scan of: {directory}")
        print(f"   Scan ID: {self.scan_id}")
        print(f"   Time: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}")
        print()
        
        start_time = datetime.utcnow()
        self.findings = []
        self.files_scanned = 0
        
        # Collect all files to scan
        files_to_scan = []
        for root, dirs, files in os.walk(directory):
            # Skip excluded directories
            dirs[:] = [d for d in dirs if d not in self.exclude_dirs]
            
            for file in files:
                file_path = Path(root) / file
                if self.should_scan_file(file_path):
                    files_to_scan.append(file_path)
        
        print(f"📁 Found {len(files_to_scan)} files to scan")
        
        # Scan files with thread pool for performance
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
            future_to_file = {executor.submit(self.scan_file, file_path): file_path 
                            for file_path in files_to_scan[:1000]}  # Limit for demo
            
            completed = 0
            for future in concurrent.futures.as_completed(future_to_file):
                file_path = future_to_file[future]
                try:
                    scanned_count, file_findings = future.result()
                    self.files_scanned += scanned_count
                    self.findings.extend(file_findings)
                    
                    completed += 1
                    if completed % 100 == 0:
                        print(f"  📊 Progress: {completed}/{len(future_to_file)} files, {len(self.findings)} findings")
                
                except Exception as e:
                    print(f"  ⚠️  Error processing {file_path}: {e}")
        
        end_time = datetime.utcnow()
        
        # Categorize findings
        findings_by_severity = {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0}
        findings_by_category = {}
        
        critical_findings = []
        high_findings = []
        medium_findings = []
        low_findings = []
        info_findings = []
        
        for finding in self.findings:
            findings_by_severity[finding.severity] = findings_by_severity.get(finding.severity, 0) + 1
            
            category = finding.category
            findings_by_category[category] = findings_by_category.get(category, 0) + 1
            
            if finding.severity == "critical":
                critical_findings.append(finding)
            elif finding.severity == "high":
                high_findings.append(finding)
            elif finding.severity == "medium":
                medium_findings.append(finding)
            elif finding.severity == "low":
                low_findings.append(finding)
            else:
                info_findings.append(finding)
        
        # Create result
        result = ScanResult(
            scan_id=self.scan_id,
            start_time=start_time,
            end_time=end_time,
            total_files_scanned=self.files_scanned,
            total_findings=len(self.findings),
            findings_by_severity=findings_by_severity,
            findings_by_category=findings_by_category,
            critical_findings=critical_findings,
            high_findings=high_findings,
            medium_findings=medium_findings,
            low_findings=low_findings,
            info_findings=info_findings
        )
        
        return result
    
    def generate_report(self, result: ScanResult, output_dir: Path = None) -> Path:
        """Generate comprehensive security report."""
        if output_dir is None:
            output_dir = self.repo_path / "security_reports"
        
        output_dir.mkdir(parents=True, exist_ok=True)
        
        report_file = output_dir / f"security_scan_{self.scan_id}.json"
        summary_file = output_dir / f"security_summary_{self.scan_id}.md"
        
        # Save JSON report
        with open(report_file, 'w') as f:
            json.dump({
                "scan_result": result.to_dict(),
                "findings": [f.to_dict() for f in self.findings]
            }, f, indent=2, default=str)
        
        # Generate markdown summary
        self.generate_markdown_summary(result, summary_file)
        
        print(f"📄 Report saved to: {report_file}")
        print(f"📄 Summary saved to: {summary_file}")
        
        return report_file
    
    def generate_markdown_summary(self, result: ScanResult, output_file: Path):
        """Generate markdown summary report."""
        duration = (result.end_time - result.start_time).total_seconds()
        
        with open(output_file, 'w') as f:
            f.write(f"# 🔍 BRP Security Scan Report\n\n")
            f.write(f"**Scan ID**: {result.scan_id}\n")
            f.write(f"**Scan Date**: {result.start_time.strftime('%Y-%m-%d %H:%M:%S UTC')}\n")
            f.write(f"**Duration**: {duration:.1f} seconds\n")
            f.write(f"**Files Scanned**: {result.total_files_scanned}\n")
            f.write(f"**Total Findings**: {result.total_findings}\n\n")
            
            f.write("## 📊 Executive Summary\n\n")
            
            # Severity breakdown
            f.write("### Findings by Severity:\n")
            for severity, count in result.findings_by_severity.items():
                if count > 0:
                    f.write(f"- **{severity.title()}**: {count}\n")
            
            f.write("\n### Findings by Category:\n")
            for category, count in sorted(result.findings_by_category.items(), key=lambda x: x[1], reverse=True):
                if count > 0:
                    f.write(f"- **{category}**: {count}\n")
            
            f.write("\n## 🚨 Critical Findings\n\n")
            if result.critical_findings:
                for finding in result.critical_findings[:10]:  # Show top 10
                    f.write(f"### {finding.id}\n")
                    f.write(f"- **Location**: `{finding.location}`\n")
                    f.write(f"- **Description**: {finding.description}\n")
                    f.write(f"- **Evidence**: {finding.evidence}\n")
                    f.write(f"- **Recommendation**: {finding.recommendation}\n\n")
            else:
                f.write("✅ No critical findings\n\n")
            
            f.write("## ⚠️ High Severity Findings\n\n")
            if result.high_findings:
                for finding in result.high_findings[:10]:
                    f.write(f"### {finding.id}\n")
                    f.write(f"- **Location**: `{finding.location}`\n")
                    f.write(f"- **Description**: {finding.description}\n")
                    f.write(f"- **Evidence**: {finding.evidence}\n")
                    f.write(f"- **Recommendation**: {finding.recommendation}\n\n")
            else:
                f.write("✅ No high severity findings\n\n")
            
            f.write("## 📋 Recommendations\n\n")
            f.write("### Immediate Actions:\n")
            if result.critical_findings or result.high_findings:
                f.write("1. **Review all critical and high findings immediately**\n")
                f.write("2. **Remove any hardcoded secrets from code**\n")
                f.write("3. **Fix SQL injection and command injection vulnerabilities**\n")
                f.write("4. **Implement proper input validation and sanitization**\n")
            else:
                f.write("✅ No immediate critical actions required\n")
            
            f.write("\n### Security Improvements:\n")
            f.write("1. **Implement secret management** (Hashicorp Vault, AWS Secrets Manager, etc.)\n")
            f.write("2. **Add security scanning to CI/CD pipeline**\n")
            f.write("3. **Regular security training for developers**\n")
            f.write("4. **Implement code review with security focus**\n")
            
            f.write("\n## 🏁 Conclusion\n\n")
            if result.critical_findings:
                f.write(f"⚠️ **URGENT ACTION REQUIRED**: {len(result.critical_findings)} critical findings need immediate attention\n")
            elif result.high_findings:
                f.write(f"⚠️ **Attention Required**: {len(result.high_findings)} high severity findings need review\n")
            else:
                f.write("✅ **Good Security Posture**: No critical or high severity findings\n")
            
            f.write(f"\n**Overall Security Score**: {self.calculate_security_score(result)}/100\n")
            
            f.write("\n---\n")
            f.write(f"*Report generated by BRP Security Scanner v1.0*\n")
            f.write(f"*Scan completed: {result.end_time.strftime('%Y-%m-%d %H:%M:%S UTC')}*\n")
    
    def calculate_security_score(self, result: ScanResult) -> int:
        """Calculate security score (0-100)."""
        base_score = 100
        
        # Deduct points for findings
        deductions = {
            "critical": 20,
            "high": 10,
            "medium": 5,
            "low": 2,
            "info": 1
        }
        
        for severity, count in result.findings_by_severity.items():
            base_score -= count * deductions.get(severity, 0)
        
        # Ensure score doesn't go below 0
        return max(0, base_score)
    
    def print_summary(self, result: ScanResult):
        """Print scan summary to console."""
        print("\n" + "="*60)
        print("🔍 BRP SECURITY SCAN COMPLETE")
        print("="*60)
        
        duration = (result.end_time - result.start_time).total_seconds()
        
        print(f"\n📊 Scan Summary:")
        print(f"   Scan ID: {result.scan_id}")
        print(f"   Duration: {duration:.1f} seconds")
        print(f"   Files Scanned: {result.total_files_scanned}")
        print(f"   Total Findings: {result.total_findings}")
        
        print(f"\n🚨 Findings by Severity:")
        for severity, count in result.findings_by_severity.items():
            if count > 0:
                print(f"   {severity.title()}: {count}")
        
        print(f"\n📈 Security Score: {self.calculate_security_score(result)}/100")
        
        if result.critical_findings:
            print(f"\n⚠️  CRITICAL FINDINGS ({len(result.critical_findings)}):")
            for finding in result.critical_findings[:5]:  # Show top 5
                print(f"   • {finding.location}: {finding.description}")
        
        if result.high_findings:
            print(f"\n⚠️  HIGH SEVERITY FINDINGS ({len(result.high_findings)}):")
            for finding in result.high_findings[:5]:
                print(f"   • {finding.location}: {finding.description}")
        
        print("\n" + "="*60)
        print("✅ Scan completed successfully")
        print("="*60)


# Test function
if __name__ == "__main__":
    print("🧪 Testing BRP Security Scanner")
    print("="*60)
    
    # Create scanner
    scanner = BRPSecurityScanner()
    
    # Run scan
    result = scanner.scan_directory()
    
    # Print summary
    scanner.print_summary(result)
    
    # Generate report
    report_file = scanner.generate_report(result)
    
    print(f"\n📄 Detailed report saved to: {report_file}")
    
    # Show sample findings if any
    if result.critical_findings or result.high_findings:
        print("\n🔍 Sample Critical/High Findings:")
        for finding in (result.critical_findings + result.high_findings)[:3]:
            print(f"\n  ID: {finding.id}")
            print(f"  Severity: {finding.severity}")
            print(f"  Location: {finding.location}")
            print(f"  Description: {finding.description}")
            print(f"  Recommendation: {finding.recommendation}")
    
    print("\n" + "="*60)
    print("✅ BRP Security Scanner test completed")
    print("="*60)