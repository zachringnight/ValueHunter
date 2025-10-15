# Model Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     CFB MISMATCH MODEL WORKFLOW                         │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────┐
│   INPUT DATA        │
│  (data/external/)   │
└──────┬──────────────┘
       │
       ├─── defense_coverage_scheme 2.csv  (3,530 records)
       ├─── receiving_concept 2.csv        (2,072 records)
       └─── receiving_scheme 2.csv         (2,072 records)
       │
       ▼
┌─────────────────────┐
│  LOAD & VALIDATE    │
│  - Parse CSV files  │
│  - Validate schema  │
│  - Clean data       │
└──────┬──────────────┘
       │
       ▼
┌──────────────────────────────────────────────┐
│  AGGREGATE TO TEAM LEVEL                     │
│  - Group by team_name                        │
│  - Calculate weighted averages               │
│  - Weight by (player_count × games_tracked)  │
└──────┬───────────────────────────────────────┘
       │
       ▼
┌──────────────────────────────────────────────┐
│  COMPUTE FEATURE SCORES                      │
│  Using weights from configs/weights.yaml:    │
│                                              │
│  Defense (40%):                              │
│    • man_coverage_defense: 15%               │
│    • zone_coverage_defense: 15%              │
│    • man_qb_rating_against: 10%              │
│    • zone_qb_rating_against: 10%             │
│                                              │
│  Receiving Concepts (20%):                   │
│    • screen_efficiency: 10%                  │
│    • slot_efficiency: 10%                    │
│                                              │
│  Receiving Schemes (40%):                    │
│    • man_receiving_efficiency: 15%           │
│    • zone_receiving_efficiency: 15%          │
└──────┬───────────────────────────────────────┘
       │
       ▼
┌──────────────────────────────────────────────┐
│  CALCULATE MISMATCH SCORE                    │
│  - Normalize all features to 0-1 scale       │
│  - Apply weights                             │
│  - Sum to overall mismatch score             │
│  - Assign tier based on score:               │
│    • Elite (≥0.60)                           │
│    • Strong (0.40-0.59)                      │
│    • Average (0.20-0.39)                     │
│    • Below Average (0.10-0.19)               │
│    • Poor (<0.10)                            │
└──────┬───────────────────────────────────────┘
       │
       ▼
┌─────────────────────┐
│   OUTPUT FILES      │
│    (data/out/)      │
└─────────────────────┘
       │
       ├─── team_defense_coverage.csv   (136 teams, 136 KB)
       ├─── team_receiving_concept.csv  (136 teams, 130 KB)
       ├─── team_receiving_scheme.csv   (136 teams, 139 KB)
       └─── team_summary.csv            (136 teams,  49 KB)
              └─ Contains overall mismatch_score and mismatch_tier


┌─────────────────────────────────────────────────────────────────────────┐
│                         USAGE EXAMPLES                                  │
└─────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────┐
│  BASIC USAGE                                                         │
│  $ cfb-mismatch analyze                                              │
│                                                                      │
│  Output: Analyzes all teams and generates 4 CSV files               │
└──────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────┐
│  CUSTOM OUTPUT DIRECTORY                                             │
│  $ cfb-mismatch analyze --output-dir reports/week7/                  │
│                                                                      │
│  Output: Saves results to specified directory                       │
└──────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────┐
│  WITH CFBD INTEGRATION                                               │
│  $ export CFBD_API_KEY="your-key"                                    │
│  $ cfb-mismatch fetch-cfbd --season 2024 --season-type regular      │
│  $ cfb-mismatch analyze --season 2024                                │
│                                                                      │
│  Output: Includes win/loss records and point differentials          │
└──────────────────────────────────────────────────────────────────────┘


┌─────────────────────────────────────────────────────────────────────────┐
│                         SAMPLE OUTPUT                                   │
└─────────────────────────────────────────────────────────────────────────┘

Top 5 Teams by Overall Mismatch Score:
┌──────────────┬────────────────┬───────────────┐
│  Team Name   │ Mismatch Score │ Mismatch Tier │
├──────────────┼────────────────┼───────────────┤
│  INDIANA     │     0.705      │     Elite     │
│  ARIZONA     │     0.646      │     Elite     │
│  MO STATE    │     0.616      │     Elite     │
│  TEXAS       │     0.608      │     Elite     │
│  NOTRE DAME  │     0.599      │     Elite     │
└──────────────┴────────────────┴───────────────┘


┌─────────────────────────────────────────────────────────────────────────┐
│                      KEY STATISTICS                                     │
└─────────────────────────────────────────────────────────────────────────┘

Total Teams Analyzed:        136 teams
Total Player Records:        7,674 records
  - Defense:                 3,530 records
  - Receiving Concepts:      2,072 records
  - Receiving Schemes:       2,072 records

Output Files Generated:      4 CSV files (454 KB total)

Processing Time:             ~3-5 seconds

Elite Tier Teams:            5 teams (score ≥ 0.60)
Strong Tier Teams:           ~30 teams (score 0.40-0.59)
Average Tier Teams:          ~70 teams (score 0.20-0.39)
Below Average Tier:          ~25 teams (score 0.10-0.19)
Poor Tier Teams:             ~6 teams (score < 0.10)


┌─────────────────────────────────────────────────────────────────────────┐
│                   CONFIGURATION FILES                                   │
└─────────────────────────────────────────────────────────────────────────┘

configs/settings.yaml:
  - Enables/disables features
  - Specifies data file paths
  - Sets output directory

configs/weights.yaml:
  - Defines feature importance weights
  - All weights sum to 1.0
  - Customizable for different analyses


┌─────────────────────────────────────────────────────────────────────────┐
│                     ADDITIONAL RESOURCES                                │
└─────────────────────────────────────────────────────────────────────────┘

📖 QUICKSTART.md       - 3-step quick start guide
📖 HOW_TO_RUN.md       - Complete installation and usage guide
📖 EXAMPLE_RUN.md      - Detailed output explanation
📖 DEMO_OUTPUT.md      - Full demonstration walkthrough
📖 README.md           - Complete project documentation
📖 USAGE.md            - Additional usage examples
📖 FAQ.md              - Common questions and answers

🔧 demo_run.sh         - Automated demonstration script


┌─────────────────────────────────────────────────────────────────────────┐
│                         QUICK COMMANDS                                  │
└─────────────────────────────────────────────────────────────────────────┘

Install:               pip install -e .
Help:                  cfb-mismatch --help
Basic Run:             cfb-mismatch analyze
Demo Script:           ./demo_run.sh
View Results:          cat data/out/team_summary.csv
```
