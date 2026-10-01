from pathlib import Path

TEA_CODE_DIR = Path(__file__).resolve().parent
TEA_DIR = TEA_CODE_DIR.parent
PROJECT_ROOT = TEA_DIR.parent

EXCEL_DIR = TEA_DIR / "EXCEL"
TEA_ANALYSIS_DIR = TEA_CODE_DIR / "analysis_results"
MC_DIR = TEA_CODE_DIR / "MC"
SCENARIO_DIR = TEA_CODE_DIR / "scenario_results"


def ensure_output_dirs() -> None:
    for directory in (TEA_ANALYSIS_DIR, MC_DIR, SCENARIO_DIR):
        directory.mkdir(parents=True, exist_ok=True)
