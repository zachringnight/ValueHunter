# QUICK START GUIDE

## Run the Model in 3 Simple Steps

### Step 1: Install
```bash
git clone https://github.com/zachringnight/ValueHunter.git
cd ValueHunter
pip install -e .
```

### Step 2: Run
```bash
# Choose one of these methods:

# Method 1: Simple Python script
python run_model.py

# Method 2: Simple bash script
./run_model.sh

# Method 3: CLI command
cfb-mismatch analyze
```

### Step 3: View Results
```bash
ls data/out/
cat data/out/team_summary.csv
```

## What You Get

The model analyzes **136 college football teams** across multiple dimensions:
- **Defense**: Man and zone coverage grades, QB rating allowed
- **Receiving**: Efficiency by concept (screen, slot) and scheme (man/zone)
- **Overall**: Combined mismatch score and tier classification

## Output Files

| File | Description | Size |
|------|-------------|------|
| `team_summary.csv` | Overall mismatch scores and tiers | 49 KB |
| `team_defense_coverage.csv` | Defensive coverage statistics | 136 KB |
| `team_receiving_concept.csv` | Receiving concept metrics | 130 KB |
| `team_receiving_scheme.csv` | Receiving scheme statistics | 139 KB |

## Sample Output

```
--- Top 5 Teams by Overall Mismatch Score ---
 team_name  mismatch_score mismatch_tier
   INDIANA        0.705147         Elite
   ARIZONA        0.645588         Elite
  MO STATE        0.616176         Elite
     TEXAS        0.608088         Elite
NOTRE DAME        0.599265         Elite
```

## Try the Demo

Run one of the included scripts to see everything in action:
```bash
# Option 1: Comprehensive demo
./demo_run.sh

# Option 2: Quick run scripts
python run_model.py
# or
./run_model.sh
```

## Next Steps

- **Detailed Guide**: See [HOW_TO_RUN.md](HOW_TO_RUN.md) for comprehensive instructions
- **Example Run**: See [EXAMPLE_RUN.md](EXAMPLE_RUN.md) for detailed output explanation
- **Full Documentation**: See [README.md](README.md) for complete project overview

## Need Help?

```bash
# Show all available commands
cfb-mismatch --help

# Show options for analyze command
cfb-mismatch analyze --help

# Show options for fetching CFBD data
cfb-mismatch fetch-cfbd --help
```

## Advanced Usage

### Custom Output Location
```bash
cfb-mismatch analyze --output-dir my_reports/
```

### Integration with CFBD API
```bash
export CFBD_API_KEY="your-key"
cfb-mismatch fetch-cfbd --season 2024 --season-type regular
cfb-mismatch analyze --season 2024
```

---

**That's it!** You can now run the CFB Mismatch Model and analyze college football team statistics.
