# Examples

This directory contains example scripts and sample data files to help you get started with the CFB Mismatch Model.

## Files

### Scripts

- **basic_usage.py** - Demonstrates basic usage patterns including:
  - Loading configurations
  - Computing mismatches for a single week
  - Batch processing multiple weeks

### Sample Data

Sample CSV files showing the expected format for external data sources:

- **sample_pff_ol_dl.csv** - Example PFF offensive/defensive line data
- **sample_pff_def_front_cov.csv** - Example PFF defensive front and coverage data
- **sample_pff_run_concepts.csv** - Example PFF run concept data
- **sample_fp_receiver_splits.csv** - Example FantasyPoints receiver data

## Running Examples

### Basic Usage

```bash
# Make sure the package is installed
pip install -e .

# Set your API key
export CFBD_API_KEY=your_api_key_here

# Run the basic usage example
python examples/basic_usage.py
```

### Using Sample Data

To test with the sample PFF and FantasyPoints data:

1. Copy sample files to the data directory:
   ```bash
   cp examples/sample_*.csv data/external/
   ```

2. Update `configs/settings.yaml`:
   ```yaml
   use_pff: true
   use_fantasypoints: true
   ```

3. Run the model:
   ```bash
   cfb-mismatch week --year 2024 --week 1
   ```

## Creating Your Own Data Files

### PFF Data Format

The sample files show the expected column names and data types. Your actual PFF exports should match these formats:

- **pff_ol_dl.csv**: Win rates for offensive and defensive lines
- **pff_def_front_cov.csv**: Defensive front and coverage frequencies
- **pff_run_concepts.csv**: Run concept usage and efficiency

### FantasyPoints Data Format

- **fp_receiver_splits.csv**: Receiver performance vs man/zone coverage

See the sample files for exact column names and data ranges.

## Output

When you run the examples with a valid API key, output files will be created in:
- `examples/output/` - For single week runs
- `examples/output/weekN/` - For batch processing

Output includes:
- `cfb_unit_mismatches_week<N>.csv` - Complete mismatch data
- `top_run_mismatches.csv` - Top run game mismatches
- `top_pass_mismatches.csv` - Top passing game mismatches
- `top_passpro_mismatches.csv` - Top pass protection mismatches
