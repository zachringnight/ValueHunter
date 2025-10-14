"""Setup script for CFB Mismatch Model package."""
from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="cfb-mismatch",
    version="0.1.0",
    author="ValueHunter Contributors",
    description="College Football Mismatch Model - computes weekly position-group mismatch scores",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/zachringnight/ValueHunter",
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
    python_requires=">=3.9",
    install_requires=[
        "requests>=2.28.0",
        "pandas>=1.5.0",
        "pyyaml>=6.0",
        "cfbd>=4.5.0",
    ],
    entry_points={
        "console_scripts": [
            "cfb-mismatch=cfb_mismatch.cli:main",
        ],
    },
)
