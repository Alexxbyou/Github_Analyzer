# GitHub Account Repository Analyzer

Analyzes all repositories under a GitHub account and produces a structured dataset summarizing activity, contribution volume, repository size, and technology stack for each repository.

## Analysis Steps
1. Setup & API Connection Test
2. Retrieve Raw Repository List
3. Identify All Contributors Across Repos (to identify local git user if relevant)
4. Retrieve Contribution Data Per Repo
5. Analysis, Build DataFrame & Export CSV

## Setup

1. Create a conda environment and install dependencies:

```bash
conda create -n gha_env python=3.11 -y
conda activate gha_env
pip install -r requirements.txt
```

2. Create a `.env` file in the project root (see `.env.example`):

```
GH_TOKEN=your_github_personal_access_token
```

The token needs the `repo` scope to access private repositories.

## How to Run

### Notebook (interactive)

Open `Notebook/Github_Analyzer.ipynb` with the `gha_env` kernel and run cells top to bottom.

### CLI Script

```bash
# Basic run (uses cache from previous runs)
python Script/github_analyzer.py

# Ignore cache and re-fetch all repos
python Script/github_analyzer.py --no-cache

# Anonymize repo names in output
python Script/github_analyzer.py --anonymize

# Flag specific repos to exclude from line count totals
python Script/github_analyzer.py --exclude repo-name-1 repo-name-2

# Custom output directory
python Script/github_analyzer.py --output-dir ./MyOutput
```

Output is saved to `Output/github_analysis.csv`.

## Folder Structure

```
Github_Analyzer/
├── Doc/
│   └── github_repo_analysis_requirements.md   # Requirements and design decisions
├── Notebook/
│   └── Github_Analyzer.ipynb                  # Interactive notebook (Phase 1)
├── Script/
│   └── github_analyzer.py                     # CLI tool (Phase 2)
├── Output/                                    # Generated output (git-ignored)
│   ├── cache/                                 # Per-repo JSON cache
│   ├── github_analysis.csv                    # Final dataset
│   └── top_languages.png                      # Language distribution chart
├── .env                                       # GitHub token (git-ignored)
├── .env.example                               # Template for .env
├── requirements.txt                           # Python dependencies
└── README.md
```
