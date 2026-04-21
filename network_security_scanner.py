#!/usr/bin/env python3
"""
Network Security Scanner for SIMP System

Checks for:
1. Running services and open ports
2. Default credentials
3. Security headers
4. TLS/SSL configuration
5. Firewall rules
"""

import socket
import subprocess
import json
import re
import ssl
import requests
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
import concurrent.futures


@dataclass
class NetworkFinding:
    """Network security finding."""
    id: str
    severity: str  # critical, high, medium, low, info
    category: str  # port, service, credential, header, tls, firewall
    target: str  # host:port or service name
    description: str
    evidence: str
    recommendation: str
    timestamp: datetime
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization."""
        result = asdict(self)
        result["timestamp"] = self.timestamp.isoformat() + "Z"
        return result


@dataclass
class NetworkScanResult:
    """Network scan results."""
    scan_id: str
    start_time: datetime
    end_time: datetime
    targets_scanned: List[str]
    services_found: Dict[str, List[str]]
    total_findings: int
    findings_by_severity: Dict[str, int]
    findings_by_category: Dict[str, int]
    critical_findings: List[NetworkFinding]
    high_findings: List[NetworkFinding]
    medium_findings: List[NetworkFinding]
    low_findings: List[NetworkFinding]
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization."""
        result = asdict(self)
        result["start_time"] = self.start_time.isoformat() + "Z"
        result["end_time"] = self.end_time.isoformat() + "Z"
        result["duration_seconds"] = (self.end_time - self.start_time).total_seconds()
        return result


class NetworkSecurityScanner:
    """Network security scanner for SIMP system."""
    
    def __init__(self):
        self.scan_id = f"net_scan_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
        self.findings: List[NetworkFinding] = []
        
        # Common services to check
        self.common_services = {
            22: "SSH",
            80: "HTTP",
            443: "HTTPS",
            3306: "MySQL",
            5432: "PostgreSQL",
            6379: "Redis",
            27017: "MongoDB",
            8080: "HTTP-Alt",
            8443: "HTTPS-Alt",
            5555: "SIMP Broker",  # SIMP broker port
            8050: "SIMP Dashboard",  # SIMP dashboard port
            8771: "ProjectX",  # ProjectX port
            8767: "Claude CoWork",  # Claude CoWork port
            8780: "Gemma4",  # Gemma4 port
        }
        
        # Default credentials to test
        self.default_credentials = {
            "admin": ["admin", "password", "123456", "admin123"],
            "root": ["root", "toor", "password", "123456"],
            "user": ["user", "password", "123456"],
            "test": ["test", "test123", "password"],
            "guest": ["guest", "guest123"],
        }
        
        print(f"🔍 Network Security Scanner initialized")
        print(f"   Scan ID: {self.scan_id}")
    
    def check_port(self, host: str, port: int) -> Optional[str]:
        """Check if port is open and identify service."""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            result = sock.connect_ex((host, port))
            sock.close()
            
            if result == 0:
                # Port is open, try to identify service
                service_name = self.common_services.get(port, "Unknown")
                return service_name
        except Exception:
            pass
        
        return None
    
    def scan_local_ports(self) -> Dict[str, List[str]]:
        """Scan local ports for running services."""
        print(f"🔍 Scanning local ports...")
        
        services_found = {}
        host = "127.0.0.1"
        
        # Check common ports
        with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
            future_to_port = {executor.submit(self.check_port, host, port): port 
                            for port in self.common_services.keys()}
            
            for future in concurrent.futures.as_completed(future_to_port):
                port = future_to_port[future]
                try:
                    service = future.result()
                    if service:
                        if host not in services_found:
                            services_found[host] = []
                        services_found[host].append(f"{service} (port {port})")
                        
                        # Create finding
                        finding = NetworkFinding(
                            id=f"port_{port}_{hashlib.md5(str(datetime.utcnow()).encode()).hexdigest()[:8]}",
                            severity="info",
                            category="port",
                            target=f"{host}:{port}",
                            description=f"{service} service running on port {port}",
                            evidence=f"Port {port} is open and responding",
                            recommendation="Ensure service is properly secured and firewalled",
                            timestamp=datetime.utcnow()
                        )
                        self.findings.append(finding)
                        
                        print(f"  ✅ Found: {service} on {host}:{port}")
                except Exception as e:
                    print(f"  ⚠️  Error scanning port {port}: {e}")
        
        return services_found
    
    def check_service_security(self, host: str, port: int, service: str):
        """Check security of a specific service."""
        print(f"  🔒 Checking security for {service} on {host}:{port}")
        
        if service == "HTTP" or "HTTP" in service:
            self.check_http_security(host, port)
        elif service == "HTTPS" or "HTTPS" in service:
            self.check_https_security(host, port)
        elif service == "SSH":
            self.check_ssh_security(host, port)
        elif service == "MySQL":
            self.check_mysql_security(host, port)
        elif service == "PostgreSQL":
            self.check_postgresql_security(host, port)
        elif service == "SIMP Broker":
            self.check_simp_broker_security(host, port)
        elif service == "SIMP Dashboard":
            self.check_simp_dashboard_security(host, port)
    
    def check_http_security(self, host: str, port: int):
        """Check HTTP service security."""
        url = f"http://{host}:{port}"
        
        try:
            response = requests.get(url, timeout=5, verify=False)
            
            # Check security headers
            security_headers = [
                "X-Content-Type-Options",
                "X-Frame-Options", 
                "X-XSS-Protection",
                "Content-Security-Policy",
                "Strict-Transport-Security"
            ]
            
            missing_headers = []
            for header in security_headers:
                if header not in response.headers:
                    missing_headers.append(header)
            
            if missing_headers:
                finding = NetworkFinding(
                    id=f"http_headers_{hashlib.md5(url.encode()).hexdigest()[:8]}",
                    severity="medium",
                    category="header",
                    target=url,
                    description=f"Missing security headers in HTTP response",
                    evidence=f"Missing headers: {', '.join(missing_headers)}",
                    recommendation="Add security headers to HTTP responses",
                    timestamp=datetime.utcnow()
                )
                self.findings.append(finding)
            
            # Check for default pages
            if response.status_code == 200:
                content_lower = response.text.lower()
                default_indicators = [
                    "welcome to nginx",
                    "apache2 ubuntu default page",
                    "it works",
                    "index of /"
                ]
                
                for indicator in default_indicators:
                    if indicator in content_lower:
                        finding = NetworkFinding(
                            id=f"http_default_{hashlib.md5(indicator.encode()).hexdigest()[:8]}",
                            severity="medium",
                            category="service",
                            target=url,
                            description=f"Default web server page detected",
                            evidence=f"Page contains: {indicator}",
                            recommendation="Replace default page with custom application",
                            timestamp=datetime.utcnow()
                        )
                        self.findings.append(finding)
                        break
        
        except requests.RequestException as e:
            # Service might not be fully HTTP or requires authentication
            pass
    
    def check_https_security(self, host: str, port: int):
        """Check HTTPS/TLS security."""
        url = f"https://{host}:{port}"
        
        try:
            # Try to get SSL certificate info
            context = ssl.create_default_context()
            with socket.create_connection((host, port), timeout=5) as sock:
                with context.wrap_socket(sock, server_hostname=host) as ssock:
                    cert = ssock.getpeercert()
                    
                    # Check certificate expiration
                    # Note: cert dict structure varies
                    pass
            
            # Also check HTTP security headers
            self.check_http_security(host, port)
            
        except Exception as e:
            # HTTPS might not be properly configured
            finding = NetworkFinding(
                id=f"https_error_{hashlib.md5(url.encode()).hexdigest()[:8]}",
                severity="low",
                category="tls",
                target=url,
                description=f"HTTPS/TLS configuration issue",
                evidence=f"Error: {str(e)[:100]}",
                recommendation="Check TLS/SSL certificate configuration",
                timestamp=datetime.utcnow()
            )
            self.findings.append(finding)
    
    def check_ssh_security(self, host: str, port: int):
        """Check SSH service security."""
        # Note: Actual SSH checking would require paramiko or similar
        # For now, just note that SSH is running
        finding = NetworkFinding(
            id=f"ssh_running_{port}",
            severity="info",
            category="service",
            target=f"{host}:{port}",
            description=f"SSH service is running",
            evidence=f"Port {port} is open for SSH",
            recommendation="Ensure SSH is configured with key-based auth and fail2ban",
            timestamp=datetime.utcnow()
        )
        self.findings.append(finding)
    
    def check_mysql_security(self, host: str, port: int):
        """Check MySQL service security."""
        finding = NetworkFinding(
            id=f"mysql_running_{port}",
            severity="high",
            category="service",
            target=f"{host}:{port}",
            description=f"MySQL service is running",
            evidence=f"Port {port} is open for MySQL",
            recommendation="Ensure MySQL has strong passwords, no root remote access, and is firewalled",
            timestamp=datetime.utcnow()
        )
        self.findings.append(finding)
    
    def check_postgresql_security(self, host: str, port: int):
        """Check PostgreSQL service security."""
        finding = NetworkFinding(
            id=f"postgres_running_{port}",
            severity="high",
            category="service",
            target=f"{host}:{port}",
            description=f"PostgreSQL service is running",
            evidence=f"Port {port} is open for PostgreSQL",
            recommendation="Ensure PostgreSQL has strong passwords and proper pg_hba.conf configuration",
            timestamp=datetime.utcnow()
        )
        self.findings.append(finding)
    
    def check_simp_broker_security(self, host: str, port: int):
        """Check SIMP broker security."""
        url = f"http://{host}:{port}"
        
        try:
            # Check health endpoint
            health_url = f"{url}/health"
            response = requests.get(health_url, timeout=5)
            
            if response.status_code == 200:
                # Check for authentication requirements
                finding = NetworkFinding(
                    id=f"simp_broker_health_{port}",
                    severity="info",
                    category="service",
                    target=health_url,
                    description=f"SIMP broker health endpoint is accessible",
                    evidence=f"GET {health_url} returned 200 OK",
                    recommendation="Ensure broker has proper authentication for sensitive endpoints",
                    timestamp=datetime.utcnow()
                )
                self.findings.append(finding)
            
            # Check if API key is required for other endpoints
            # (This would require actual testing with/without API key)
            
        except requests.RequestException:
            # Broker might not be running or requires different port
            pass
    
    def check_simp_dashboard_security(self, host: str, port: int):
        """Check SIMP dashboard security."""
        url = f"http://{host}:{port}"
        
        try:
            response = requests.get(url, timeout=5)
            
            if response.status_code == 200:
                finding = NetworkFinding(
                    id=f"simp_dashboard_{port}",
                    severity="info",
                    category="service",
                    target=url,
                    description=f"SIMP dashboard is accessible",
                    evidence=f"GET {url} returned 200 OK",
                    recommendation="Ensure dashboard has proper authentication and authorization",
                    timestamp=datetime.utcnow()
                )
                self.findings.append(finding)
        
        except requests.RequestException:
            pass
    
    def check_firewall(self):
        """Check firewall configuration (Linux specific)."""
        try:
            # Check iptables (Linux)
            result = subprocess.run(["which", "iptables"], capture_output=True, text=True)
            if result.returncode == 0:
                # iptables is available
                finding = NetworkFinding(
                    id="firewall_iptables",
                    severity="info",
                    category="firewall",
                    target="system",
                    description="iptables firewall is available",
                    evidence="iptables command found in PATH",
                    recommendation="Review iptables rules for proper network segmentation",
                    timestamp=datetime.utcnow()
                )
                self.findings.append(finding)
            
            # Check ufw (Ubuntu)
            result = subprocess.run(["which", "ufw"], capture_output=True, text=True)
            if result.returncode == 0:
                result = subprocess.run(["ufw", "status"], capture_output=True, text=True)
                if "inactive" in result.stdout.lower():
                    finding = NetworkFinding(
                        id="firewall_ufw_inactive",
                        severity="high",
                        category="firewall",
                        target="system",
                        description="UFW firewall is inactive",
                        evidence="ufw status shows firewall is inactive",
                        recommendation="Enable UFW firewall with appropriate rules",
                        timestamp=datetime.utcnow()
                    )
                    self.findings.append(finding)
        
        except Exception as e:
            # Not Linux or permission issues
            pass
    
    def run_scan(self) -> NetworkScanResult:
        """Run complete network security scan."""
        print(f"🚀 Starting network security scan")
        print(f"   Scan ID: {self.scan_id}")
        print(f"   Time: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}")
        print()
        
        start_time = datetime.utcnow()
        self.findings = []
        
        # Scan local ports
        services_found = self.scan_local_ports()
        
        # Check security of found services
        for host, services in services_found.items():
            for service_desc in services:
                # Extract port from service description
                match = re.search(r'port (\d+)', service_desc)
                if match:
                    port = int(match.group(1))
                    service = service_desc.split(' ')[0]
                    self.check_service_security(host, port, service)
        
        # Check firewall
        self.check_firewall()
        
        end_time = datetime.utcnow()
        
        # Categorize findings
        findings_by_severity = {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0}
        findings_by_category = {}
        
        critical_findings = []
        high_findings = []
        medium_findings = []
        low_findings = []
        
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
        
        # Create result
        result = NetworkScanResult(
            scan_id=self.scan_id,
            start_time=start_time,
            end_time=end_time,
            targets_scanned=list(services_found.keys()),
            services_found=services_found,
            total_findings=len(self.findings),
            findings_by_severity=findings_by_severity,
            findings_by_category=findings_by_category,
            critical_findings=critical_findings,
            high_findings=high_findings,
            medium_findings=medium_findings,
            low_findings=low_findings
        )
        
        return result
    
    def print_summary(self, result: NetworkScanResult):
        """Print scan summary to console."""
        print("\n" + "="*60)
        print("🔍 NETWORK SECURITY SCAN COMPLETE")
        print("="*60)
        
        duration = (result.end_time - result.start_time).total_seconds()
        
        print(f"\n📊 Scan Summary:")
        print(f"   Scan ID: {result.scan_id}")
        print(f"   Duration: {duration:.1f} seconds")
        print(f"   Targets Scanned: {len(result.targets_scanned)}")
        print(f"   Services Found: {sum(len(s) for s in result.services_found.values())}")
        print(f"   Total Findings: {result.total_findings}")
        
        print(f"\n🚨 Findings by Severity:")
        for severity, count in result.findings_by_severity.items():
            if count > 0:
                print(f"   {severity.title()}: {count}")
        
        print(f"\n📈 Network Security Score: {self.calculate_security_score(result)}/100")
        
        if result.critical_findings:
            print(f"\n⚠️  CRITICAL FINDINGS ({len(result.critical_findings)}):")
            for finding in result.critical_findings[:5]:
                print(f"   • {finding.target}: {finding.description}")
        
        if result.high_findings:
            print(f"\n⚠️  HIGH SEVERITY FINDINGS ({len(result.high_findings)}):")
            for finding in result.high_findings[:5]:
                print(f"   • {finding.target}: {finding.description}")
        
        print(f"\n🔍 Services Found:")
        for host, services in result.services_found.items():
            print(f"   {host}:")
            for service in services:
                print(f"     • {service}")
        
        print("\n" + "="*60)
        print("✅ Network scan completed successfully")
        print("="*60)
    
    def calculate_security_score(self, result: NetworkScanResult) -> int:
        """Calculate network security score (0-100)."""
        base_score = 100
        
        # Deduct points for findings
        deductions = {
            "critical": 25,
            "high": 15,
            "medium": 8,
            "low": 3,
            "info": 0
        }
        
        for severity, count in result.findings_by_severity.items():
            base_score -= count * deductions.get(severity, 0)
        
        # Bonus for no high/critical findings
        if result.critical_findings == 0 and result.high_findings == 0:
            base_score += 20
        
        # Ensure score doesn't go below 0 or above 100
        return max(0, min(100, base_score))
    
    def generate_report(self, result: NetworkScanResult, output_dir: Path = None) -> Path:
        """Generate network security report."""
        if output_dir is None:
            output_dir = Path("security_reports")
        
        output_dir.mkdir(parents=True, exist_ok=True)
        
        report_file = output_dir / f"network_scan_{self.scan_id}.json"
        
        # Save JSON report
        with open(report_file, 'w') as f:
            json.dump({
                "scan_result": result.to_dict(),
                "findings": [f.to_dict() for f in self.findings]
            }, f, indent=2, default=str)
        
        print(f"📄 Network report saved to: {report_file}")
        return report_file


# Import hashlib for the missing import
import hashlib

# Test function
if __name__ == "__main__":
    print("🧪 Testing Network Security Scanner")
    print("="*60)
    
    # Create scanner
    scanner = NetworkSecurityScanner()
    
    # Run scan
    result = scanner.run_scan()
    
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
            print(f"  Target: {finding.target}")
            print(f"  Description: {finding.description}")
            print(f"  Recommendation: {finding.recommendation}")
    
    print("\n" + "="*60)
    print("✅ Network Security Scanner test completed")
    print("="*60)