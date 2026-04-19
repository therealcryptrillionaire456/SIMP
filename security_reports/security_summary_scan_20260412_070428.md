# 🔍 BRP Security Scan Report

**Scan ID**: scan_20260412_070428
**Scan Date**: 2026-04-12 07:04:28 UTC
**Duration**: 5.4 seconds
**Files Scanned**: 1000
**Total Findings**: 49

## 📊 Executive Summary

### Findings by Severity:
- **Critical**: 30
- **High**: 16
- **Medium**: 3

### Findings by Category:
- **secret_api_key**: 16
- **vulnerability_command_injection**: 14
- **secret_password**: 14
- **vulnerability_insecure_random**: 3
- **vulnerability_xss**: 1
- **vulnerability_hardcoded_credentials**: 1

## 🚨 Critical Findings

### vuln_808fc74b
- **Location**: `fine_tune_secbert_simplified.py`
- **Description**: Potential command injection vulnerability
- **Evidence**: Line 262: model.eval()...
- **Recommendation**: Use subprocess with shell=False and validate/sanitize inputs

### vuln_e0724ad2
- **Location**: `fine_tune_secbert.py`
- **Description**: Potential command injection vulnerability
- **Evidence**: Line 384: self.model.eval()...
- **Recommendation**: Use subprocess with shell=False and validate/sanitize inputs

### vuln_3a947bc5
- **Location**: `fine_tune_secbert.py`
- **Description**: Potential command injection vulnerability
- **Evidence**: Line 577: model.eval()...
- **Recommendation**: Use subprocess with shell=False and validate/sanitize inputs

### vuln_5ec0de42
- **Location**: `tools/scrapling_query_app/mythos_reconstruction.py`
- **Description**: Potential command injection vulnerability
- **Evidence**: Line 170: self.eval()...
- **Recommendation**: Use subprocess with shell=False and validate/sanitize inputs

### vuln_34ee0a59
- **Location**: `bill_russel_ml_pipeline/training_pipeline.py`
- **Description**: Potential command injection vulnerability
- **Evidence**: Line 366: model.eval()...
- **Recommendation**: Use subprocess with shell=False and validate/sanitize inputs

### vuln_615c42e7
- **Location**: `bill_russel_ml_pipeline/training_pipeline.py`
- **Description**: Potential command injection vulnerability
- **Evidence**: Line 389: model.eval()...
- **Recommendation**: Use subprocess with shell=False and validate/sanitize inputs

### vuln_cdb08425
- **Location**: `mythos_implementation/src/modeling_mythos.py`
- **Description**: Potential command injection vulnerability
- **Evidence**: Line 616: self.eval()...
- **Recommendation**: Use subprocess with shell=False and validate/sanitize inputs

### vuln_21f50d97
- **Location**: `mythos_implementation/src/training.py`
- **Description**: Potential command injection vulnerability
- **Evidence**: Line 240: self.model.eval()...
- **Recommendation**: Use subprocess with shell=False and validate/sanitize inputs

### vuln_00a0f5ed
- **Location**: `mythos_implementation/src/training.py`
- **Description**: Potential command injection vulnerability
- **Evidence**: Line 444: self.model.eval()...
- **Recommendation**: Use subprocess with shell=False and validate/sanitize inputs

### vuln_c866481c
- **Location**: `tests/test_sprint40_deerflow_upgrades.py`
- **Description**: Potential command injection vulnerability
- **Evidence**: Line 389: "python3 -c \"exec('import os; os.system(\\\"ls\\\")\")",...
- **Recommendation**: Use subprocess with shell=False and validate/sanitize inputs

## ⚠️ High Severity Findings

### secret_83658b42
- **Location**: `fix_security_issues.py`
- **Description**: Potential password found in code
- **Evidence**: Line 85: password = password_match.group(1)... (Secret: pass******atch)
- **Recommendation**: Remove hardcoded password and use environment variables or secure secret management

### vuln_55d8e154
- **Location**: `brp_security_scanner.py`
- **Description**: Potential xss vulnerability
- **Evidence**: Line 133: r'direct output without escaping',...
- **Recommendation**: Use template escaping or output encoding

### secret_f5da0334
- **Location**: `tools/onboarding_pack_generator.py`
- **Description**: Potential password found in code
- **Evidence**: Line 388: "solution": "Add repo root to PYTHONPATH: `export PYTHONPATH=$PWD:$PYTHONPATH`",... (Secret: $PYT***PATH)
- **Recommendation**: Remove hardcoded password and use environment variables or secure secret management

### secret_b646d637
- **Location**: `keep-the-change/backend/docker-compose.yml`
- **Description**: Potential password found in code
- **Evidence**: Line 13: POSTGRES_PASSWORD: ktcpassword... (Secret: ktcp***word)
- **Recommendation**: Remove hardcoded password and use environment variables or secure secret management

### secret_d8a14780
- **Location**: `keep-the-change/backend/docker-compose.yml`
- **Description**: Potential password found in code
- **Evidence**: Line 126: PGADMIN_DEFAULT_PASSWORD: admin123... (Secret: ********)
- **Recommendation**: Remove hardcoded password and use environment variables or secure secret management

### secret_2669b7b0
- **Location**: `keep-the-change/backend/app/schemas/user.py`
- **Description**: Potential password found in code
- **Evidence**: Line 38: password: Optional[str] = Field(None, min_length=8)... (Secret: ********)
- **Recommendation**: Remove hardcoded password and use environment variables or secure secret management

### secret_74b0147d
- **Location**: `brp_enhancement/repos/CAI/examples/continue_mode_security_audit.py`
- **Description**: Potential password found in code
- **Evidence**: Line 59: DB_PASSWORD = "admin123"... (Secret: ********)
- **Recommendation**: Remove hardcoded password and use environment variables or secure secret management

### vuln_0149fd27
- **Location**: `brp_enhancement/repos/CAI/examples/continue_mode_security_audit.py`
- **Description**: Potential hardcoded credentials vulnerability
- **Evidence**: Line 59: DB_PASSWORD = "admin123"...
- **Recommendation**: Move credentials to environment variables or secure vault

### secret_561d7fe9
- **Location**: `brp_enhancement/repos/CAI/src/cai/tools/network/capture_traffic.py`
- **Description**: Potential password found in code
- **Evidence**: Line 39: client.connect(ip, port=port, username=username, password=password, timeout=timeout)... (Secret: ********)
- **Recommendation**: Remove hardcoded password and use environment variables or secure secret management

### secret_44d3e14a
- **Location**: `brp_enhancement/repos/CAI/benchmarks/utils/seceval_dataset/questions.json`
- **Description**: Potential password found in code
- **Evidence**: Line 11995: "A: function saveUserData($username, $password) { $encryptedPassword = encryptPassword($password); $... (Secret: encr******************ord))
- **Recommendation**: Remove hardcoded password and use environment variables or secure secret management

## 📋 Recommendations

### Immediate Actions:
1. **Review all critical and high findings immediately**
2. **Remove any hardcoded secrets from code**
3. **Fix SQL injection and command injection vulnerabilities**
4. **Implement proper input validation and sanitization**

### Security Improvements:
1. **Implement secret management** (Hashicorp Vault, AWS Secrets Manager, etc.)
2. **Add security scanning to CI/CD pipeline**
3. **Regular security training for developers**
4. **Implement code review with security focus**

## 🏁 Conclusion

⚠️ **URGENT ACTION REQUIRED**: 30 critical findings need immediate attention

**Overall Security Score**: 0/100

---
*Report generated by BRP Security Scanner v1.0*
*Scan completed: 2026-04-12 07:04:33 UTC*
