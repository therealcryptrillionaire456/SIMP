#!/usr/bin/env python3
"""
Port Manager for SIMP Ecosystem
Shows all ports in use and helps manage port assignments
"""

import socket
import sys
from typing import Dict, List, Tuple
from dataclasses import dataclass
from datetime import datetime

@dataclass
class PortInfo:
    port: int
    process_name: str
    pid: int
    protocol: str = "TCP"
    status: str = "LISTEN"

def scan_ports(start: int = 8000, end: int = 9000) -> List[PortInfo]:
    """Scan for open ports in range"""
    open_ports = []
    
    for port in range(start, end + 1):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(0.1)
        result = sock.connect_ex(('127.0.0.1', port))
        sock.close()
        
        if result == 0:
            # Try to get process info (macOS specific)
            import subprocess
            try:
                # Use lsof to get process info
                cmd = f"lsof -i :{port} -sTCP:LISTEN"
                output = subprocess.check_output(cmd, shell=True, text=True).strip()
                lines = output.split('\n')
                if len(lines) > 1:
                    # Parse lsof output
                    parts = lines[1].split()
                    if len(parts) >= 2:
                        process_name = parts[0]
                        pid = int(parts[1])
                        open_ports.append(PortInfo(port, process_name, pid))
            except:
                # Fallback if lsof fails
                open_ports.append(PortInfo(port, "Unknown", 0))
    
    return open_ports

def get_simp_ports() -> Dict[str, List[PortInfo]]:
    """Get ports used by SIMP ecosystem"""
    all_ports = scan_ports(5000, 9000)
    
    simp_ports = []
    other_ports = []
    
    simp_keywords = ['python', 'uvicorn', 'fastapi', 'simp', 'gate', 'quantum', 'dashboard', 'broker']
    
    for port_info in all_ports:
        process_lower = port_info.process_name.lower()
        if any(keyword in process_lower for keyword in simp_keywords):
            simp_ports.append(port_info)
        else:
            other_ports.append(port_info)
    
    return {
        'simp_ports': sorted(simp_ports, key=lambda x: x.port),
        'other_ports': sorted(other_ports, key=lambda x: x.port)
    }

def print_port_table(ports: List[PortInfo], title: str):
    """Print a formatted table of ports"""
    print(f"\n{'='*60}")
    print(f"📡 {title}")
    print(f"{'='*60}")
    print(f"{'Port':<8} {'Process':<20} {'PID':<8} {'Status':<10}")
    print(f"{'-'*8} {'-'*20} {'-'*8} {'-'*10}")
    
    for port_info in ports:
        print(f"{port_info.port:<8} {port_info.process_name:<20} {port_info.pid:<8} {port_info.status:<10}")
    
    print(f"{'='*60}")

def find_conflicts() -> List[Tuple[int, List[PortInfo]]]:
    """Find port conflicts (multiple processes on same port)"""
    all_ports = scan_ports(5000, 9000)
    
    # Group by port
    port_groups = {}
    for port_info in all_ports:
        if port_info.port not in port_groups:
            port_groups[port_info.port] = []
        port_groups[port_info.port].append(port_info)
    
    # Find ports with multiple processes
    conflicts = [(port, infos) for port, infos in port_groups.items() if len(infos) > 1]
    return conflicts

def main():
    """Main function"""
    print("🚀 SIMP Port Management System")
    print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Get all ports
    ports = get_simp_ports()
    
    # Print SIMP ports
    if ports['simp_ports']:
        print_port_table(ports['simp_ports'], "SIMP Ecosystem Ports")
        print(f"\n✅ Found {len(ports['simp_ports'])} SIMP-related ports")
    else:
        print("⚠️  No SIMP ports found")
    
    # Print other ports (optional)
    if len(sys.argv) > 1 and sys.argv[1] == "--all":
        if ports['other_ports']:
            print_port_table(ports['other_ports'], "Other Ports in Range")
    
    # Check for conflicts
    conflicts = find_conflicts()
    if conflicts:
        print(f"\n❌ PORT CONFLICTS DETECTED:")
        for port, processes in conflicts:
            print(f"\n  Port {port} has {len(processes)} processes:")
            for proc in processes:
                print(f"    • {proc.process_name} (PID: {proc.pid})")
    else:
        print(f"\n✅ No port conflicts detected")
    
    # Show available ports
    print(f"\n🔍 Available Ports (8000-8100):")
    available = []
    for port in range(8000, 8101):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(0.1)
        result = sock.connect_ex(('127.0.0.1', port))
        sock.close()
        if result != 0:
            available.append(port)
    
    if available:
        print(f"   First 10 available: {', '.join(map(str, available[:10]))}")
        if len(available) > 10:
            print(f"   ... and {len(available) - 10} more")
    else:
        print("   No available ports in range")
    
    print(f"\n💡 Usage Tips:")
    print(f"   1. Use tools/port_utils.py to find free ports")
    print(f"   2. All agents now use dynamic port allocation")
    print(f"   3. Run this script with --all to see all ports")
    print(f"   4. Check ./start_agents_with_port_routing.sh for startup")

if __name__ == "__main__":
    main()