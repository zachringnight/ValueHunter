from setuptools import setup, find_packages

setup(
    name="nba-props",
    version="1.1.0",
    author="Value Hunter",
    description="NBA 3PM Props Engine - pregame player props pricing system",
    url="https://github.com/zachringnight/ValueHunter",
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Libraries",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
    python_requires=">=3.9",
    install_requires=[
        "pandas>=1.5.0",
        "pyyaml>=6.0",
        "requests>=2.28.0",
        "numpy>=1.24.0",
        "scipy>=1.10.0",
        "scikit-learn>=1.3.0",
        "fastapi>=0.100.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.0",
        ],
    },
)
