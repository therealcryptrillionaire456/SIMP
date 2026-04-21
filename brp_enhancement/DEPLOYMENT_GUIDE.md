# Enhanced BRP Deployment Guide

## Overview
The Enhanced Bill Russell Protocol (BRP) is a cybersecurity framework that integrates 5 specialized repositories to create a defensive specialist with offensive scoring capabilities.

## Quick Start

### 1. Start BRP Framework
```bash
./start_brp.sh [mode]
```
Modes: defensive (default), offensive, hybrid, intelligence

### 2. Run as Service
```bash
python3 brp_service.py [mode]
```

### 3. Python API Usage
```python
from integration.brp_enhanced_framework import BRPEnhancedFramework

# Initialize
brp = BRPEnhancedFramework(mode='defensive')

# Process events
result = brp.process_event({
    'type': 'security_alert',
    'data': {'threat_level': 'high', 'source': 'firewall'}
})

# Switch modes
brp.switch_mode('hybrid')

# Get system status
status = brp.get_system_status()
```

## Modules

### 1. CAI (Cybersecurity AI)
- **Type**: Defensive
- **Capabilities**: AI security evaluation, prompt injection defense
- **Use**: AI system security assessment

### 2. hexstrike-ai
- **Type**: Hybrid  
- **Capabilities**: Binary analysis, malware detection, exploit development
- **Use**: Binary security analysis and manipulation

### 3. pentagi
- **Type**: Offensive
- **Capabilities**: Penetration testing, vulnerability assessment
- **Use**: Authorized security testing

### 4. OpenShell
- **Type**: Hybrid
- **Capabilities**: Command execution, system administration
- **Use**: System management and security operations

### 5. strix
- **Type**: Hybrid
- **Capabilities**: Monitoring, threat detection, security analytics
- **Use**: Continuous security monitoring

## Operation Modes

### Defensive Mode (Default)
- Primary focus: Threat detection and prevention
- All defensive capabilities active
- Offensive capabilities disabled or restricted

### Offensive Mode
- Primary focus: Security testing and exploit development
- All offensive capabilities active
- Requires explicit authorization
- Defensive monitoring continues

### Hybrid Mode
- Balanced defensive and offensive operations
- Real-time threat response with countermeasures
- Requires high authorization level

### Intelligence Mode
- Focus: Information gathering and analysis
- Knowledge graph construction
- Threat intelligence correlation

## Security Considerations

1. **Authorization**: Offensive capabilities require explicit authorization
2. **Audit Logging**: All operations are logged to SQLite database
3. **Safety Controls**: Command validation, sandbox mode available
4. **Rate Limiting**: Event processing rate limits enforced

## Monitoring

### Logs
- Framework logs: `logs/brp_framework.log`
- Deployment logs: `logs/deployment_*.log`
- Test results: `logs/*_results.json`

### Database
- SQLite database: `data/brp_operations.db`
- Contains: Events, responses, threat intelligence

## Troubleshooting

### Common Issues

1. **Module import errors**: Ensure Python path includes BRP directory
2. **Database errors**: Check file permissions on `data/` directory
3. **Missing dependencies**: All modules use standard Python libraries

### Testing
```bash
# Run basic tests
python3 tests/test_framework_basic.py

# Run stress tests  
python3 tests/stress_test.py

# Run integration tests
python3 tests/test_integration_complete.py
```

## Support
For issues or questions, check:
- Framework documentation in `docs/`
- Module documentation in `integration/modules/`
- Test examples in `tests/`
