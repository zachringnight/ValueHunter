from setuptools import setup, find_packages

setup(
    name="valuehunter",
    version="1.1.0",
    author="ValueHunter",
    description="NBA player props pricing engine — statistical modeling, Monte Carlo simulation, and edge detection",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    url="https://github.com/zachringnight/ValueHunter",
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Topic :: Scientific/Engineering :: Information Analysis",
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
