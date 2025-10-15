#!/bin/bash

# Simple script to run the CFB Mismatch Model
# Usage: ./run_model.sh

echo "============================================================"
echo "CFB Mismatch Model - Quick Run"
echo "============================================================"
echo ""
echo "Running model analysis..."
echo ""

# Run the analyze command
if cfb-mismatch analyze; then
    echo ""
    echo "============================================================"
    echo "✓ Model run complete!"
    echo "============================================================"
    echo ""
    echo "Output files are in: data/out/"
    echo "  - team_summary.csv (main results)"
    echo "  - team_defense_coverage.csv"
    echo "  - team_receiving_concept.csv"
    echo "  - team_receiving_scheme.csv"
    echo ""
    exit 0
else
    echo ""
    echo "============================================================"
    echo "✗ Error running model"
    echo "============================================================"
    echo ""
    echo "Make sure you have installed the package:"
    echo "  pip install -e ."
    echo ""
    exit 1
fi
