#!/usr/bin/env python3
"""
OpenShell integration module for BRP.
Provides command execution and system interaction capabilities.
"""

import sys
import os
from pathlib import Path
from typing import Dict, Any, List, Optional
import json
import logging
import subprocess
import shlex
import threading
import queue
import time

# Add OpenShell repository to path for potential imports
openshell_path = Path(__file__).parent.parent.parent / "repos" / "OpenShell"
if openshell_path.exists():
    sys.path.insert(0, str(openshell_path))

from .base_module import OffensiveModule

logger = logging.getLogger(__name__)

class OpenShellModule(OffensiveModule):
    """OpenShell integration module for command execution."""
    
    def __init__(self):
        super().__init__("openshell", "OpenShell")
        self.repo_path = openshell_path
        self.command_history = []
        self.active_processes = {}
        self.command_queue = queue.Queue()
        self.sandbox_mode = True  # Default to safe mode
        self.allowed_commands = self._load_allowed_commands()
        self.dangerous_patterns = self._load_dangerous_patterns()
        
        # Start command processor thread
        self.processor_thread = threading.Thread(target=self._command_processor)
        self.processor_thread.daemon = True
        self.processor_thread.start()
    
    def _load_allowed_commands(self) -> List[str]:
        """Load list of allowed commands for sandbox mode."""
        return [
            'ls', 'pwd', 'whoami', 'date', 'echo', 'cat', 'head', 'tail',
            'grep', 'find', 'ps', 'top', 'df', 'du', 'free', 'uname',
            'hostname', 'env', 'which', 'whereis', 'file', 'stat',
            'wc', 'sort', 'uniq', 'cut', 'tr', 'sed', 'awk'
        ]
    
    def _load_dangerous_patterns(self) -> List[Dict[str, Any]]:
        """Load dangerous command patterns."""
        return [
            {
                'pattern': r'rm\s+-rf',
                'description': 'Recursive force delete',
                'danger_level': 'critical'
            },
            {
                'pattern': r':\(\)\{:\|:\&\};:',
                'description': 'Fork bomb',
                'danger_level': 'critical'
            },
            {
                'pattern': r'mkfs|dd\s+if=/dev/',
                'description': 'Disk destruction',
                'danger_level': 'critical'
            },
            {
                'pattern': r'chmod\s+[0-7]{3,4}\s+.*',
                'description': 'Permission modification',
                'danger_level': 'high'
            },
            {
                'pattern': r'>/dev/sd[a-z]',
                'description': 'Direct disk writing',
                'danger_level': 'critical'
            },
            {
                'pattern': r'wget\s+.*\|\s*sh',
                'description': 'Pipe to shell from download',
                'danger_level': 'high'
            },
            {
                'pattern': r'curl\s+.*\|\s*sh',
                'description': 'Pipe to shell from curl',
                'danger_level': 'high'
            },
            {
                'pattern': r'nc\s+-l\s+-p\s+\d+',
                'description': 'Network listener',
                'danger_level': 'medium'
            },
            {
                'pattern': r'ssh\s+-R\s+\d+:',
                'description': 'Reverse SSH tunnel',
                'danger_level': 'medium'
            },
            {
                'pattern': r'python\s+-c\s+.*import\s+os.*',
                'description': 'Python OS commands',
                'danger_level': 'medium'
            }
        ]
    
    def initialize(self) -> bool:
        """Initialize OpenShell module."""
        try:
            # Check if OpenShell repository exists
            if not self.repo_path.exists():
                logger.warning(f"OpenShell repository not found at {self.repo_path}")
                self.available = False
                return False
            
            # Initialize capabilities
            self.capabilities = [
                {
                    'name': 'command_execution',
                    'description': 'Execute shell commands with safety controls',
                    'operations': ['execute_command', 'run_script', 'background_task']
                },
                {
                    'name': 'system_interaction',
                    'description': 'Interact with system resources and processes',
                    'operations': ['manage_process', 'monitor_resources', 'system_info']
                },
                {
                    'name': 'file_operations',
                    'description': 'Safe file operations and manipulation',
                    'operations': ['read_file', 'write_file', 'file_operations']
                },
                {
                    'name': 'network_operations',
                    'description': 'Network connectivity and testing',
                    'operations': ['test_connectivity', 'port_scan', 'network_info']
                },
                {
                    'name': 'security_controls',
                    'description': 'Security and safety controls for operations',
                    'operations': ['set_sandbox', 'check_safety', 'audit_commands']
                }
            ]
            
            self.available = True
            self.initialized = True
            
            logger.info(f"OpenShell module initialized with {len(self.capabilities)} capabilities")
            logger.info(f"Sandbox mode: {self.sandbox_mode}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize OpenShell module: {e}")
            self.available = False
            return False
    
    def check_availability(self) -> bool:
        """Check if OpenShell module is available."""
        return self.repo_path.exists() and any(self.repo_path.iterdir())
    
    def get_capabilities(self) -> List[Dict[str, Any]]:
        """Get OpenShell module capabilities."""
        return self.capabilities
    
    def execute(self, operation: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Execute OpenShell operation."""
        if not self.initialized:
            return {'error': 'OpenShell module not initialized'}
        
        operation_handlers = {
            'execute_command': self._execute_command,
            'run_script': self._run_script,
            'background_task': self._background_task,
            'manage_process': self._manage_process,
            'monitor_resources': self._monitor_resources,
            'system_info': self._system_info,
            'read_file': self._read_file,
            'write_file': self._write_file,
            'file_operations': self._file_operations,
            'test_connectivity': self._test_connectivity,
            'port_scan': self._port_scan,
            'network_info': self._network_info,
            'set_sandbox': self._set_sandbox_mode,
            'check_safety': self._check_command_safety,
            'audit_commands': self._audit_command_history
        }
        
        handler = operation_handlers.get(operation)
        if not handler:
            return {'error': f'Unknown operation: {operation}'}
        
        try:
            return handler(parameters)
        except Exception as e:
            logger.error(f"Error executing OpenShell operation {operation}: {e}")
            return {'error': str(e)}
    
    # ===== Offensive Module Methods =====
    
    def scan(self, target: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Scan target using command-line tools."""
        scan_type = parameters.get('scan_type', 'basic')
        
        # Build scan command based on type
        if scan_type == 'basic':
            command = f"ping -c 4 {target}"
        elif scan_type == 'port_scan':
            command = f"nc -zv {target} 22 80 443 2>&1"
        elif scan_type == 'service_scan':
            command = f"nmap -sV {target}"
        else:
            return {'error': f'Unknown scan type: {scan_type}'}
        
        # Execute scan command
        result = self._execute_safe_command(command)
        
        return {
            'scan_type': scan_type,
            'target': target,
            'command': command,
            'result': result,
            'success': result.get('success', False)
        }
    
    def exploit(self, vulnerability: Dict[str, Any]) -> Dict[str, Any]:
        """Execute exploit command."""
        exploit_command = vulnerability.get('command', '')
        
        if not exploit_command:
            return {'error': 'No exploit command provided'}
        
        # Check if command is safe to execute
        safety_check = self._check_command_safety({'command': exploit_command})
        if not safety_check.get('safe', False):
            return {
                'error': 'Exploit command failed safety check',
                'safety_issues': safety_check.get('issues', []),
                'recommendation': 'Review command or disable sandbox mode'
            }
        
        # Execute exploit command
        result = self._execute_command({'command': exploit_command})
        
        return {
            'exploit_executed': True,
            'command': exploit_command,
            'result': result,
            'vulnerability': vulnerability.get('name', 'unknown')
        }
    
    def execute_attack(self, attack_plan: Dict[str, Any]) -> Dict[str, Any]:
        """Execute attack plan using command execution."""
        attack_type = attack_plan.get('attack_type', 'command_injection')
        commands = attack_plan.get('commands', [])
        
        if not commands:
            return {'error': 'No commands in attack plan'}
        
        results = []
        for cmd in commands:
            # Check command safety
            safety_check = self._check_command_safety({'command': cmd})
            if safety_check.get('safe', False):
                result = self._execute_command({'command': cmd})
                results.append({
                    'command': cmd,
                    'result': result,
                    'success': result.get('success', False)
                })
            else:
                results.append({
                    'command': cmd,
                    'result': {'error': 'Command failed safety check'},
                    'success': False,
                    'safety_issues': safety_check.get('issues', [])
                })
        
        return {
            'attack_executed': True,
            'attack_type': attack_type,
            'commands_executed': len([r for r in results if r['success']]),
            'commands_failed': len([r for r in results if not r['success']]),
            'results': results
        }
    
    # ===== Core OpenShell Methods =====
    
    def _command_processor(self):
        """Process commands from queue."""
        while True:
            try:
                task = self.command_queue.get(timeout=1)
                self._process_command_task(task)
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"Error in command processor: {e}")
    
    def _process_command_task(self, task: Dict):
        """Process a command task."""
        command = task.get('command', '')
        callback = task.get('callback')
        
        try:
            result = self._execute_raw_command(command)
            if callback:
                callback(result)
        except Exception as e:
            logger.error(f"Error processing command {command}: {e}")
    
    def _execute_command(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a shell command."""
        command = parameters.get('command', '')
        timeout = parameters.get('timeout', 30)
        background = parameters.get('background', False)
        
        if not command:
            return {'error': 'No command provided'}
        
        # Check command safety
        safety_check = self._check_command_safety({'command': command})
        if self.sandbox_mode and not safety_check.get('safe', False):
            return {
                'error': 'Command failed safety check in sandbox mode',
                'command': command,
                'safety_issues': safety_check.get('issues', []),
                'sandbox_mode': self.sandbox_mode
            }
        
        # Execute command
        if background:
            # Queue for background execution
            task_id = len(self.command_history) + 1
            self.command_queue.put({
                'command': command,
                'task_id': task_id,
                'timestamp': time.time()
            })
            
            return {
                'task_id': task_id,
                'status': 'queued',
                'command': command,
                'message': 'Command queued for background execution'
            }
        else:
            # Execute immediately
            return self._execute_raw_command(command, timeout)
    
    def _execute_raw_command(self, command: str, timeout: int = 30) -> Dict[str, Any]:
        """Execute raw shell command."""
        try:
            # Parse command
            args = shlex.split(command)
            
            # Execute with timeout
            process = subprocess.run(
                args,
                capture_output=True,
                text=True,
                timeout=timeout,
                shell=False
            )
            
            # Record in history
            history_entry = {
                'timestamp': time.time(),
                'command': command,
                'returncode': process.returncode,
                'success': process.returncode == 0
            }
            self.command_history.append(history_entry)
            
            return {
                'success': process.returncode == 0,
                'returncode': process.returncode,
                'stdout': process.stdout,
                'stderr': process.stderr,
                'command': command,
                'execution_time': time.time() - history_entry['timestamp']
            }
            
        except subprocess.TimeoutExpired:
            return {
                'success': False,
                'error': f'Command timed out after {timeout} seconds',
                'command': command
            }
        except FileNotFoundError:
            return {
                'success': False,
                'error': f'Command not found: {command.split()[0]}',
                'command': command
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'command': command
            }
    
    def _execute_safe_command(self, command: str) -> Dict[str, Any]:
        """Execute command with additional safety checks."""
        # Always check safety
        safety_check = self._check_command_safety({'command': command})
        
        if not safety_check.get('safe', False):
            return {
                'success': False,
                'error': 'Command failed safety check',
                'safety_issues': safety_check.get('issues', []),
                'command': command
            }
        
        return self._execute_raw_command(command)
    
    def _run_script(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Run a shell script."""
        script_content = parameters.get('script', '')
        script_args = parameters.get('args', '')
        
        if not script_content:
            return {'error': 'No script content provided'}
        
        # Create temporary script file
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.sh', delete=False) as f:
            f.write('#!/bin/bash\n')
            f.write(script_content)
            script_path = f.name
        
        try:
            # Make executable
            os.chmod(script_path, 0o755)
            
            # Build command
            command = f"{script_path} {script_args}".strip()
            
            # Execute
            result = self._execute_command({'command': command})
            
            # Clean up
            os.unlink(script_path)
            
            return {
                'script_executed': True,
                'result': result,
                'script_size': len(script_content)
            }
            
        except Exception as e:
            # Clean up on error
            if os.path.exists(script_path):
                os.unlink(script_path)
            return {'error': f'Script execution failed: {e}'}
    
    def _background_task(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Start a background task."""
        command = parameters.get('command', '')
        task_name = parameters.get('name', f'task_{len(self.active_processes) + 1}')
        
        if not command:
            return {'error': 'No command provided'}
        
        # Check safety
        safety_check = self._check_command_safety({'command': command})
        if self.sandbox_mode and not safety_check.get('safe', False):
            return {
                'error': 'Command failed safety check',
                'safety_issues': safety_check.get('issues', [])
            }
        
        try:
            # Start process
            process = subprocess.Popen(
                shlex.split(command),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            # Store process info
            self.active_processes[task_name] = {
                'process': process,
                'command': command,
                'start_time': time.time(),
                'pid': process.pid
            }
            
            return {
                'task_started': True,
                'task_name': task_name,
                'pid': process.pid,
                'command': command,
                'message': f'Background task {task_name} started with PID {process.pid}'
            }
            
        except Exception as e:
            return {'error': f'Failed to start background task: {e}'}
    
    def _manage_process(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Manage running processes."""
        action = parameters.get('action', 'list')
        task_name = parameters.get('task_name', '')
        
        if action == 'list':
            # List all active processes
            processes = []
            for name, info in self.active_processes.items():
                processes.append({
                    'name': name,
                    'pid': info['pid'],
                    'command': info['command'],
                    'running': info['process'].poll() is None,
                    'start_time': info['start_time']
                })
            
            return {
                'active_processes': len(self.active_processes),
                'processes': processes
            }
        
        elif action == 'stop':
            # Stop a specific process
            if task_name not in self.active_processes:
                return {'error': f'Task {task_name} not found'}
            
            process_info = self.active_processes[task_name]
            process = process_info['process']
            
            try:
                process.terminate()
                process.wait(timeout=5)
                del self.active_processes[task_name]
                
                return {
                    'task_stopped': True,
                    'task_name': task_name,
                    'pid': process_info['pid']
                }
            except:
                try:
                    process.kill()
                    del self.active_processes[task_name]
                    return {
                        'task_killed': True,
                        'task_name': task_name,
                        'pid': process_info['pid']
                    }
                except Exception as e:
                    return {'error': f'Failed to stop task: {e}'}
        
        elif action == 'status':
            # Check status of a process
            if task_name not in self.active_processes:
                return {'error': f'Task {task_name} not found'}
            
            process_info = self.active_processes[task_name]
            process = process_info['process']
            return_code = process.poll()
            
            return {
                'task_name': task_name,
                'pid': process_info['pid'],
                'running': return_code is None,
                'return_code': return_code,
                'command': process_info['command'],
                'uptime': time.time() - process_info['start_time']
            }
        
        else:
            return {'error': f'Unknown action: {action}'}
    
    def _monitor_resources(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Monitor system resources."""
        monitor_type = parameters.get('type', 'system')
        
        if monitor_type == 'system':
            # Get system resource usage
            commands = {
                'memory': 'free -h',
                'disk': 'df -h',
                'cpu': 'top -bn1 | grep "Cpu(s)"',
                'processes': 'ps aux --sort=-%cpu | head -10'
            }
            
            results = {}
            for resource, command in commands.items():
                result = self._execute_safe_command(command)
                results[resource] = result
            
            return {
                'resource_monitoring': True,
                'results': results,
                'timestamp': time.time()
            }
        
        elif monitor_type == 'process':
            # Monitor specific process
            pid = parameters.get('pid', '')
            if not pid:
                return {'error': 'PID required for process monitoring'}
            
            command = f"ps -p {pid} -o pid,ppid,user,%cpu,%mem,cmd"
            result = self._execute_safe_command(command)
            
            return {
                'process_monitoring': True,
                'pid': pid,
                'result': result
            }
        
        else:
            return {'error': f'Unknown monitor type: {monitor_type}'}
    
    def _system_info(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Get system information."""
        info_commands = {
            'hostname': 'hostname',
            'os': 'uname -a',
            'kernel': 'cat /proc/version',
            'cpu': 'lscpu | grep "Model name"',
            'memory': 'cat /proc/meminfo | grep MemTotal',
            'disk': 'lsblk',
            'network': 'ip addr show',
            'users': 'who',
            'uptime': 'uptime'
        }
        
        info = {}
        for key, command in info_commands.items():
            result = self._execute_safe_command(command)
            if result.get('success'):
                info[key] = result.get('stdout', '').strip()
            else:
                info[key] = f"Error: {result.get('error', 'unknown')}"
        
        return {
            'system_info': True,
            'info': info,
            'timestamp': time.time()
        }
    
    def _read_file(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Read file contents."""
        file_path = parameters.get('path', '')
        lines = parameters.get('lines', 0)  # 0 means all lines
        
        if not file_path:
            return {'error': 'No file path provided'}
        
        # Safety check - prevent reading sensitive files
        sensitive_paths = ['/etc/passwd', '/etc/shadow', '/root/', '/proc/']
        if any(file_path.startswith(path) for path in sensitive_paths) and self.sandbox_mode:
            return {'error': 'Access to sensitive file blocked in sandbox mode'}
        
        # Build command
        if lines > 0:
            command = f"head -n {lines} {shlex.quote(file_path)}"
        else:
            command = f"cat {shlex.quote(file_path)}"
        
        result = self._execute_safe_command(command)
        
        return {
            'file_read': True,
            'path': file_path,
            'result': result,
            'lines_requested': lines if lines > 0 else 'all'
        }
    
    def _write_file(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Write to file."""
        file_path = parameters.get('path', '')
        content = parameters.get('content', '')
        append = parameters.get('append', False)
        
        if not file_path or content is None:
            return {'error': 'File path and content required'}
        
        # Safety check
        if self.sandbox_mode and file_path.startswith('/'):
            return {'error': 'Writing to root paths blocked in sandbox mode'}
        
        # Use temp file and mv for safety
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
            f.write(content)
            temp_path = f.name
        
        try:
            # Build command
            if append:
                command = f"cat {shlex.quote(temp_path)} >> {shlex.quote(file_path)}"
            else:
                command = f"mv {shlex.quote(temp_path)} {shlex.quote(file_path)}"
            
            result = self._execute_safe_command(command)
            
            return {
                'file_written': True,
                'path': file_path,
                'append': append,
                'result': result,
                'content_length': len(content)
            }
            
        except Exception as e:
            # Clean up temp file
            if os.path.exists(temp_path):
                os.unlink(temp_path)
            return {'error': f'File write failed: {e}'}
    
    def _file_operations(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Perform file operations."""
        operation = parameters.get('operation', '')
        path = parameters.get('path', '')
        
        if not operation or not path:
            return {'error': 'Operation and path required'}
        
        # Safety check for dangerous operations
        if operation in ['delete', 'move', 'chmod'] and self.sandbox_mode:
            return {'error': f'{operation} operation blocked in sandbox mode'}
        
        if operation == 'list':
            command = f"ls -la {shlex.quote(path)}"
        elif operation == 'stat':
            command = f"stat {shlex.quote(path)}"
        elif operation == 'find':
            pattern = parameters.get('pattern', '*')
            command = f"find {shlex.quote(path)} -name {shlex.quote(pattern)}"
        elif operation == 'grep':
            pattern = parameters.get('pattern', '')
            if not pattern:
                return {'error': 'Pattern required for grep'}
            command = f"grep -r {shlex.quote(pattern)} {shlex.quote(path)}"
        else:
            return {'error': f'Unknown file operation: {operation}'}
        
        result = self._execute_safe_command(command)
        
        return {
            'file_operation': operation,
            'path': path,
            'result': result
        }
    
    def _test_connectivity(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Test network connectivity."""
        target = parameters.get('target', '')
        port = parameters.get('port', 0)
        
        if not target:
            return {'error': 'Target required'}
        
        if port > 0:
            # Test specific port
            command = f"nc -zv {shlex.quote(target)} {port} 2>&1"
        else:
            # Ping test
            command = f"ping -c 4 {shlex.quote(target)} 2>&1"
        
        result = self._execute_safe_command(command)
        
        return {
            'connectivity_test': True,
            'target': target,
            'port': port if port > 0 else 'ping',
            'result': result,
            'reachable': 'succeeded' in result.get('stdout', '') or 'bytes from' in result.get('stdout', '')
        }
    
    def _port_scan(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Simple port scan."""
        target = parameters.get('target', '')
        ports = parameters.get('ports', '22,80,443,8080')
        
        if not target:
            return {'error': 'Target required'}
        
        # Simple port scan using netcat
        open_ports = []
        for port in ports.split(','):
            port = port.strip()
            if port.isdigit():
                result = self._test_connectivity({'target': target, 'port': int(port)})
                if result.get('reachable', False):
                    open_ports.append(port)
        
        return {
            'port_scan': True,
            'target': target,
            'ports_scanned': ports,
            'open_ports': open_ports,
            'open_count': len(open_ports)
        }
    
    def _network_info(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Get network information."""
        commands = {
            'interfaces': 'ip addr show',
            'routing': 'ip route show',
            'dns': 'cat /etc/resolv.conf',
            'connections': 'netstat -tuln',
            'firewall': 'iptables -L -n 2>/dev/null || echo "iptables not available"'
        }
        
        info = {}
        for key, command in commands.items():
            result = self._execute_safe_command(command)
            if result.get('success'):
                info[key] = result.get('stdout', '').strip()
        
        return {
            'network_info': True,
            'info': info,
            'timestamp': time.time()
        }
    
    def _set_sandbox_mode(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Set sandbox mode."""
        enabled = parameters.get('enabled', True)
        
        self.sandbox_mode = enabled
        
        return {
            'sandbox_mode_updated': True,
            'enabled': self.sandbox_mode,
            'message': f'Sandbox mode {"enabled" if enabled else "disabled"}'
        }
    
    def _check_command_safety(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Check if command is safe to execute."""
        command = parameters.get('command', '')
        
        if not command:
            return {'error': 'No command provided'}
        
        issues = []
        
        # Check for dangerous patterns
        for pattern_info in self.dangerous_patterns:
            if re.search(pattern_info['pattern'], command, re.IGNORECASE):
                issues.append({
                    'pattern': pattern_info['pattern'],
                    'description': pattern_info['description'],
                    'danger_level': pattern_info['danger_level']
                })
        
        # Check if command is in allowed list (for sandbox mode)
        if self.sandbox_mode:
            first_word = command.split()[0] if command.split() else ''
            if first_word not in self.allowed_commands:
                issues.append({
                    'pattern': 'not_in_allowed_list',
                    'description': f'Command "{first_word}" not in allowed list for sandbox mode',
                    'danger_level': 'medium'
                })
        
        return {
            'safe': len(issues) == 0,
            'issues': issues,
            'command': command,
            'sandbox_mode': self.sandbox_mode
        }
    
    def _audit_command_history(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Audit command history."""
        limit = parameters.get('limit', 50)
        
        recent_history = self.command_history[-limit:] if self.command_history else []
        
        # Analyze history for patterns
        analysis = {
            'total_commands': len(self.command_history),
            'successful_commands': len([h for h in self.command_history if h.get('success', False)]),
            'failed_commands': len([h for h in self.command_history if not h.get('success', False)]),
            'recent_commands': recent_history,
            'common_patterns': self._analyze_command_patterns(recent_history)
        }
        
        return {
            'audit_completed': True,
            'analysis': analysis,
            'timestamp': time.time()
        }
    
    def _analyze_command_patterns(self, history: List[Dict]) -> Dict[str, Any]:
        """Analyze patterns in command history."""
        if not history:
            return {}
        
        commands = [h.get('command', '') for h in history]
        
        # Count command frequencies
        from collections import Counter
        command_counter = Counter()
        for cmd in commands:
            first_word = cmd.split()[0] if cmd.split() else ''
            if first_word:
                command_counter[first_word] += 1
        
        # Find most common commands
        most_common = command_counter.most_common(5)
        
        # Check for suspicious patterns
        suspicious = []
        for cmd in commands:
            safety_check = self._check_command_safety({'command': cmd})
            if safety_check.get('issues'):
                suspicious.append({
                    'command': cmd,
                    'issues': safety_check.get('issues', [])
                })
        
        return {
            'most_common_commands': most_common,
            'suspicious_commands': suspicious,
            'unique_commands': len(command_counter),
            'total_executions': len(commands)
        }