#!/bin/bash

# Demo script to run the CFB Mismatch Model
# This script demonstrates the basic usage of the model

echo "=================================================="
echo "CFB Mismatch Model - Demo Run"
echo "=================================================="
echo ""
echo "This script will:"
echo "  1. Verify installation"
echo "  2. Run the model analysis"
echo "  3. Display results"
echo ""
echo "=================================================="
echo ""

# Check if cfb-mismatch is installed
echo "Step 1: Verifying installation..."
if ! command -v cfb-mismatch &> /dev/null; then
    echo "❌ cfb-mismatch command not found. Installing..."
    pip install -e . || {
        echo "❌ Installation failed. Please run 'pip install -e .' manually"
        exit 1
    }
else
    echo "✅ cfb-mismatch is installed"
fi
echo ""

# Show help
echo "Step 2: Available commands..."
cfb-mismatch --help
echo ""
echo "=================================================="
echo ""

# Run the analysis
echo "Step 3: Running analysis..."
echo ""
cfb-mismatch analyze
echo ""
echo "=================================================="
echo ""

# Display output files
echo "Step 4: Generated files..."
echo ""
ls -lh data/out/
echo ""
echo "=================================================="
echo ""

# Show sample data from summary
echo "Step 5: Sample results from team_summary.csv..."
echo ""
echo "First 10 teams:"
head -11 data/out/team_summary.csv | column -t -s,
echo ""
echo "=================================================="
echo ""

echo "✅ Demo complete!"
echo ""
echo "Output files are located in: data/out/"
echo "  - team_defense_coverage.csv"
echo "  - team_receiving_concept.csv"
echo "  - team_receiving_scheme.csv"
echo "  - team_summary.csv"
echo ""
echo "For more information, see HOW_TO_RUN.md"
echo "=================================================="
