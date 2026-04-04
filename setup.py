#!/usr/bin/env python3
"""
Setup configuration for SIMP Protocol

Install with: pip install -e .
Or: pip install .
"""

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="simp-protocol",
    version="0.1.0",
    author="Kasey Marcelle",
    author_email="automationkasey@gmail.com",
    description="Standardized Inter-agent Message Protocol - Communication framework for AI agents",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/therealcryptrillionaire456/simp",
    project_urls={
        "Bug Tracker": "https://github.com/therealcryptrillionaire456/simp/issues",
        "Documentation": "https://github.com/therealcryptrillionaire456/simp#documentation",
        "Source Code": "https://github.com/therealcryptrillionaire456/simp",
    },
    packages=find_packages(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Intended Audience :: Science/Research",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.14",
        "Topic :: Software Development :: Libraries",
        "Topic :: Software Development :: Libraries :: Application Frameworks",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
    ],
    python_requires=">=3.9",
    install_requires=[
        "flask>=3.1.0",
        "requests>=2.33.0",
        "cryptography>=46.0.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "black>=23.0.0",
            "flake8>=6.0.0",
            "mypy>=1.0.0",
            "autopep8>=2.0.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "simp-server=simp.server.http_server:main",
        ],
    },
    include_package_data=True,
    zip_safe=False,
)
