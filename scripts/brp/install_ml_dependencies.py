#!/usr/bin/env python3
"""
Install ML Dependencies for Bill Russell Protocol
Phase 1: Complete setup for defending against Anthropic, Meta, OpenAI threats
"""

import subprocess
import sys
import os
from pathlib import Path
import logging
from datetime import datetime

# Setup logging
log_dir = Path("logs")
log_dir.mkdir(exist_ok=True)
log_file = log_dir / f"dependency_install_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler()
    ]
)
log = logging.getLogger(__name__)

def run_command(cmd, description):
    """Run a shell command with logging."""
    log.info(f"Starting: {description}")
    log.info(f"Command: {cmd}")
    
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            check=True
        )
        log.info(f"✓ Success: {description}")
        if result.stdout:
            log.debug(f"Output: {result.stdout[:500]}...")
        return True
    except subprocess.CalledProcessError as e:
        log.error(f"✗ Failed: {description}")
        log.error(f"Error: {e.stderr}")
        return False
    except Exception as e:
        log.error(f"✗ Error: {description} - {str(e)}")
        return False

def check_python_version():
    """Check Python version requirements."""
    log.info("Checking Python version...")
    version = sys.version_info
    if version.major == 3 and version.minor >= 8:
        log.info(f"✓ Python {version.major}.{version.minor}.{version.micro} meets requirements")
        return True
    else:
        log.error(f"✗ Python {version.major}.{version.minor}.{version.micro} - Need Python 3.8+")
        return False

def check_gpu_availability():
    """Check if GPU is available for ML training."""
    log.info("Checking GPU availability...")
    try:
        import torch
        if torch.cuda.is_available():
            gpu_name = torch.cuda.get_device_name(0)
            gpu_memory = torch.cuda.get_device_properties(0).total_memory / 1e9
            log.info(f"✓ GPU available: {gpu_name} ({gpu_memory:.1f} GB)")
            return True
        else:
            log.warning("⚠ No GPU available - will use CPU (training will be slower)")
            return False
    except ImportError:
        log.warning("⚠ PyTorch not installed - cannot check GPU")
        return False

def install_core_dependencies():
    """Install core ML and data science dependencies."""
    dependencies = [
        # Data processing
        ("pandas", "pandas>=2.0.0"),
        ("scikit-learn", "scikit-learn>=1.3.0"),
        ("numpy", "numpy>=1.24.0"),
        ("pyyaml", "pyyaml>=6.0"),
        
        # Web/Networking
        ("requests", "requests>=2.31.0"),
        ("urllib3", "urllib3>=2.0.0"),
        
        # Utilities
        ("psutil", "psutil>=5.9.0"),
        ("tqdm", "tqdm>=4.65.0"),
        ("python-dotenv", "python-dotenv>=1.0.0"),
    ]
    
    log.info("Installing core dependencies...")
    success_count = 0
    
    for package_name, package_spec in dependencies:
        cmd = f"{sys.executable} -m pip install --quiet {package_spec}"
        if run_command(cmd, f"Install {package_name}"):
            success_count += 1
    
    log.info(f"Core dependencies: {success_count}/{len(dependencies)} installed")
    return success_count == len(dependencies)

def install_ml_dependencies():
    """Install ML-specific dependencies."""
    ml_dependencies = [
        # PyTorch (with CUDA if available)
        ("torch", "torch torchvision torchaudio"),
        
        # Hugging Face Transformers
        ("transformers", "transformers>=4.35.0"),
        
        # Datasets
        ("datasets", "datasets>=2.14.0"),
        
        # Accelerate for distributed training
        ("accelerate", "accelerate>=0.24.0"),
        
        # Bitsandbytes for 4-bit quantization
        ("bitsandbytes", "bitsandbytes>=0.41.0"),
        
        # PEFT for parameter-efficient fine-tuning
        ("peft", "peft>=0.7.0"),
        
        # Sentence transformers for embeddings
        ("sentence-transformers", "sentence-transformers>=2.2.0"),
    ]
    
    log.info("Installing ML dependencies...")
    success_count = 0
    
    # First check if we should install CUDA version of PyTorch
    try:
        import torch
        if torch.cuda.is_available():
            log.info("GPU detected - will install PyTorch with CUDA support")
            # Use appropriate PyTorch install command for CUDA
            ml_dependencies[0] = ("torch", "torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118")
    except:
        pass
    
    for package_name, package_spec in ml_dependencies:
        cmd = f"{sys.executable} -m pip install --quiet {package_spec}"
        if run_command(cmd, f"Install {package_name}"):
            success_count += 1
    
    log.info(f"ML dependencies: {success_count}/{len(ml_dependencies)} installed")
    return success_count == len(ml_dependencies)

def install_telegram_dependencies():
    """Install Telegram bot dependencies."""
    telegram_deps = [
        ("python-telegram-bot", "python-telegram-bot>=20.0"),
        ("aiohttp", "aiohttp>=3.9.0"),
    ]
    
    log.info("Installing Telegram dependencies...")
    success_count = 0
    
    for package_name, package_spec in telegram_deps:
        cmd = f"{sys.executable} -m pip install --quiet {package_spec}"
        if run_command(cmd, f"Install {package_name}"):
            success_count += 1
    
    log.info(f"Telegram dependencies: {success_count}/{len(telegram_deps)} installed")
    return success_count == len(telegram_deps)

def verify_installations():
    """Verify all installations are working."""
    log.info("Verifying installations...")
    
    packages_to_verify = [
        "torch",
        "transformers",
        "datasets",
        "pandas",
        "numpy",
        "sklearn",
        "yaml",
        "requests",
        "psutil",
        "tqdm",
        "dotenv",
        "accelerate",
        "peft",
        "sentence_transformers",
        "telegram",
    ]
    
    success_count = 0
    for package in packages_to_verify:
        try:
            if package == "sklearn":
                __import__("sklearn")
            elif package == "yaml":
                __import__("yaml")
            elif package == "telegram":
                __import__("telegram")
            else:
                __import__(package)
            log.info(f"✓ {package} imports successfully")
            success_count += 1
        except ImportError as e:
            log.warning(f"⚠ {package} import failed: {e}")
    
    log.info(f"Verification: {success_count}/{len(packages_to_verify)} packages working")
    return success_count >= len(packages_to_verify) * 0.8  # 80% threshold

def create_requirements_file():
    """Create requirements.txt file for reproducibility."""
    log.info("Creating requirements.txt file...")
    
    requirements = """# Bill Russell Protocol - Production Dependencies
# Generated: {timestamp}

# Core dependencies
pandas>=2.0.0
numpy>=1.24.0
scikit-learn>=1.3.0
pyyaml>=6.0
requests>=2.31.0
urllib3>=2.0.0
psutil>=5.9.0
tqdm>=4.65.0
python-dotenv>=1.0.0

# ML dependencies
torch>=2.0.0
transformers>=4.35.0
datasets>=2.14.0
accelerate>=0.24.0
bitsandbytes>=0.41.0
peft>=0.7.0
sentence-transformers>=2.2.0

# Telegram integration
python-telegram-bot>=20.0
aiohttp>=3.9.0

# Development
pytest>=7.4.0
black>=23.0.0
flake8>=6.0.0
""".format(timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    
    with open("requirements.txt", "w") as f:
        f.write(requirements)
    
    log.info("✓ Created requirements.txt")
    return True

def main():
    """Main installation process."""
    log.info("=" * 60)
    log.info("BILL RUSSELL PROTOCOL - ML DEPENDENCIES INSTALLATION")
    log.info("=" * 60)
    log.info("Phase 1: Installing dependencies for production deployment")
    log.info("Defending against: Anthropic, Meta, OpenAI, Enterprise threats")
    log.info("=" * 60)
    
    # Check prerequisites
    if not check_python_version():
        log.error("Python version check failed")
        return False
    
    check_gpu_availability()
    
    # Install dependencies
    log.info("\n" + "=" * 60)
    log.info("INSTALLATION PROCESS")
    log.info("=" * 60)
    
    steps = [
        ("Core Dependencies", install_core_dependencies),
        ("ML Dependencies", install_ml_dependencies),
        ("Telegram Dependencies", install_telegram_dependencies),
        ("Verification", verify_installations),
        ("Requirements File", create_requirements_file),
    ]
    
    success_count = 0
    for step_name, step_func in steps:
        log.info(f"\nStep: {step_name}")
        log.info("-" * 40)
        if step_func():
            success_count += 1
            log.info(f"✓ {step_name} completed")
        else:
            log.error(f"✗ {step_name} failed")
    
    # Summary
    log.info("\n" + "=" * 60)
    log.info("INSTALLATION SUMMARY")
    log.info("=" * 60)
    log.info(f"Steps completed: {success_count}/{len(steps)}")
    
    if success_count == len(steps):
        log.info("✅ ALL DEPENDENCIES INSTALLED SUCCESSFULLY")
        log.info("Phase 1 complete - Ready for dataset acquisition")
    else:
        log.warning(f"⚠ {len(steps) - success_count} steps had issues")
        log.info("Some dependencies may need manual installation")
    
    log.info(f"\nLog file: {log_file}")
    log.info("=" * 60)
    
    return success_count == len(steps)

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)