from pathlib import Path
import sys

import pandas as pd

TEA_CODE_DIR = Path(__file__).resolve().parents[1]
if str(TEA_CODE_DIR) not in sys.path:
    sys.path.insert(0, str(TEA_CODE_DIR))

from Economic import LABOR_WAGE
from project_paths import TEA_ANALYSIS_DIR

OLD_WAGE = 52_700.0

LAKES = ("Atacama", "Uyuni", "Zabuye", "GSL")


def _summary_path() -> Path:
    lakes_tag = "_".join(LAKES)
    return Path(TEA_ANALYSIS_DIR) / f"econ_summary_{lakes_tag}_pathways.xlsx"


def build_comparison(summary: pd.DataFrame) -> pd.DataFrame:
    required = {
        "lake",
        "pathway",
        "CAPEX_total",
        "OPEX_total",
        "OPEX_labor_total",
        "PROFIT_total",
        "Li2CO3_prod",
        "CRF",
        "LCOL",
    }
    missing = sorted(required.difference(summary.columns))
    if missing:
        raise ValueError(
            "TEA summary is missing labor audit columns: " + ", ".join(missing)
        )

    rows = []
    for _, row in summary.iterrows():
        lake = str(row["lake"])
        new_wage = float(LABOR_WAGE.get(lake, LABOR_WAGE["DEFAULT"]))
        labor_new = float(row["OPEX_labor_total"] or 0.0)
        labor_old = labor_new * OLD_WAGE / new_wage

        opex_new = float(row["OPEX_total"])
        opex_old = opex_new - labor_new + labor_old

        production = float(row["Li2CO3_prod"])
        annual_cost_old = (
            float(row["CAPEX_total"]) * float(row["CRF"])
            + opex_old
            + float(row["PROFIT_total"])
        )
        lcol_old = annual_cost_old / production if production else None
        lcol_new = float(row["LCOL"]) if pd.notna(row["LCOL"]) else None

        rows.append(
            {
                "lake": lake,
                "pathway": row["pathway"],
                "old_labor_wage": OLD_WAGE,
                "new_labor_wage": new_wage,
                "labor_cost_old": labor_old,
                "labor_cost_new": labor_new,
                "labor_cost_delta": labor_new - labor_old,
                "OPEX_old": opex_old,
                "OPEX_new": opex_new,
                "OPEX_delta": opex_new - opex_old,
                "LCOL_old": lcol_old,
                "LCOL_new": lcol_new,
                "LCOL_delta": (
                    lcol_new - lcol_old
                    if lcol_new is not None and lcol_old is not None
                    else None
                ),
            }
        )

    return pd.DataFrame(rows)


def main() -> None:
    source = _summary_path()
    if not source.exists():
        raise FileNotFoundError(f"TEA summary not found: {source}. Run TEA.py first.")

    summary = pd.read_excel(source, sheet_name="SUMMARY_ALL")
    comparison = build_comparison(summary)

    output_dir = Path(__file__).resolve().parent
    output_dir.mkdir(parents=True, exist_ok=True)
    output_xlsx = output_dir / "labor_cost_comparison.xlsx"
    output_csv = output_dir / "labor_cost_comparison.csv"

    with pd.ExcelWriter(output_xlsx, engine="xlsxwriter") as writer:
        comparison.to_excel(writer, sheet_name="LABOR_COMPARISON", index=False)
        summary.to_excel(writer, sheet_name="SUMMARY_CURRENT", index=False)
    comparison.to_csv(output_csv, index=False, encoding="utf-8-sig")

    print(f"Labor comparison written: {output_xlsx}")
    print(f"Labor comparison CSV written: {output_csv}")


if __name__ == "__main__":
    main()
