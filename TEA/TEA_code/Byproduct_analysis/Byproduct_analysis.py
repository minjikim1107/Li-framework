from __future__ import annotations

from pathlib import Path
import sys

import numpy as np
import pandas as pd

ANALYSIS_DIR = Path(__file__).resolve().parent
TEA_CODE_DIR = ANALYSIS_DIR.parent
BASELINE_XLSX = TEA_CODE_DIR / "TEA_result.xlsx"
TEA_DETAIL_DIR = TEA_CODE_DIR / "analysis_results"
OUTPUT_DIR = ANALYSIS_DIR
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


CONSERVATIVE_CREDIT_FACTOR = 0.50

LAKES = ["Atacama", "Zabuye", "Uyuni", "GSL"]
PATHWAYS = [
    "NE_prep_carb",
    "SD_prep_carb",
    "MED_prep_carb",
    "MVR_prep_carb",
    "FO_prep_carb",
    "IX_MED_carb",
    "IX_MVR_carb",
    "IX_RO_carb",
    "SX_MED_carb",
    "SX_MVR_carb",
    "SX_RO_carb",
]
PATHWAY_LABELS = {p: f"P{i}" for i, p in enumerate(PATHWAYS, start=1)}
PATHWAY_NAMES = {
    "NE_prep_carb": "NE-PREP-CARB",
    "SD_prep_carb": "SD-PREP-CARB",
    "MED_prep_carb": "MED-PREP-CARB",
    "MVR_prep_carb": "MVR-PREP-CARB",
    "FO_prep_carb": "FO-PREP-CARB",
    "IX_MED_carb": "IX-MED-CARB",
    "IX_MVR_carb": "IX-MVR-CARB",
    "IX_RO_carb": "IX-RO-CARB",
    "SX_MED_carb": "SX-MED-CARB",
    "SX_MVR_carb": "SX-MVR-CARB",
    "SX_RO_carb": "SX-RO-CARB",
}

SCENARIOS = {
    "baseline": {
        "freshwater_factor": 1.0,
        "byproduct_factor": 1.0,
        "description": "100% of freshwater and by-product credits",
    },
    "conservative": {
        "freshwater_factor": CONSERVATIVE_CREDIT_FACTOR,
        "byproduct_factor": CONSERVATIVE_CREDIT_FACTOR,
        "description": (
            f"{CONSERVATIVE_CREDIT_FACTOR:.0%} of freshwater and by-product credits"
        ),
    },
    "no-credit": {
        "freshwater_factor": 0.0,
        "byproduct_factor": 0.0,
        "description": "No freshwater or by-product credits",
    },
}

SCENARIO_ORDER = list(SCENARIOS)


def _number(value, default=0.0) -> float:
    value = pd.to_numeric(value, errors="coerce")
    return default if pd.isna(value) else float(value)


def _profit_columns(detail: pd.DataFrame) -> tuple[list[str], list[str]]:
    all_profit = [str(c) for c in detail.columns if str(c).startswith("PROFIT_")]
    freshwater = [c for c in all_profit if "freshwater" in c.lower()]
    byproduct = [c for c in all_profit if c not in freshwater]
    return freshwater, byproduct


def _read_credit_breakdown(lake: str, pathway: str) -> dict:
    path = TEA_DETAIL_DIR / lake / f"{pathway}_econ.xlsx"
    if not path.exists():
        raise FileNotFoundError(f"Missing TEA detail workbook: {path}")

    detail = pd.read_excel(path, sheet_name="DETAIL")
    freshwater_cols, byproduct_cols = _profit_columns(detail)

    def sum_columns(columns: list[str]) -> float:
        if not columns:
            return 0.0
        return float(detail[columns].apply(pd.to_numeric, errors="coerce").sum().sum())

    freshwater_credit = sum_columns(freshwater_cols)
    byproduct_credit = sum_columns(byproduct_cols)
    detail_profit_total = sum_columns(freshwater_cols + byproduct_cols)

    return {
        "freshwater_credit": freshwater_credit,
        "byproduct_credit": byproduct_credit,
        "detail_profit_total": detail_profit_total,
        "freshwater_columns": "; ".join(freshwater_cols),
        "byproduct_columns": "; ".join(byproduct_cols),
    }


def load_base_data() -> tuple[pd.DataFrame, pd.DataFrame]:
    if not BASELINE_XLSX.exists():
        raise FileNotFoundError(f"Missing baseline TEA workbook: {BASELINE_XLSX}")

    summary = pd.read_excel(BASELINE_XLSX, sheet_name="SUMMARY_ALL")
    summary = summary[summary["lake"].isin(LAKES)].copy()
    summary = summary[summary["pathway"].isin(PATHWAYS)].copy()

    rows = []
    for _, row in summary.iterrows():
        lake = str(row["lake"])
        pathway = str(row["pathway"])
        credit = _read_credit_breakdown(lake, pathway)

        reported_profit = _number(row["PROFIT_total"])
        captured_profit = credit["detail_profit_total"]
        credit["uncaptured_profit"] = reported_profit - captured_profit

        rows.append(
            {
                "lake": lake,
                "pathway": pathway,
                "CAPEX_total": _number(row["CAPEX_total"]),
                "OPEX_total": _number(row["OPEX_total"]),
                "PROFIT_total": reported_profit,
                "Li2CO3_prod": _number(row["Li2CO3_prod"]),
                "CRF": _number(row["CRF"]),
                "LCOL_baseline_reported": _number(row["LCOL"]),
                "freshwater_credit": credit["freshwater_credit"],
                "byproduct_credit": credit["byproduct_credit"],
                "uncaptured_profit": credit["uncaptured_profit"],
                "freshwater_columns": credit["freshwater_columns"],
                "byproduct_columns": credit["byproduct_columns"],
            }
        )

    base = pd.DataFrame(rows)
    if base.empty:
        raise ValueError("No matching lake/pathway rows found in TEA_result.xlsx")

    base["noncredit_profit"] = (
        base["PROFIT_total"] - base["freshwater_credit"] - base["byproduct_credit"]
    )
    return base, summary


def calculate_scenarios(base: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows = []
    for _, row in base.iterrows():
        for scenario, settings in SCENARIOS.items():
            profit = (
                row["noncredit_profit"]
                + settings["freshwater_factor"] * row["freshwater_credit"]
                + settings["byproduct_factor"] * row["byproduct_credit"]
            )
            annual_cost = row["CAPEX_total"] * row["CRF"] + row["OPEX_total"] + profit
            lcol = annual_cost / row["Li2CO3_prod"] if row["Li2CO3_prod"] else np.nan
            rows.append(
                {
                    "lake": row["lake"],
                    "pathway": row["pathway"],
                    "pathway_id": PATHWAY_LABELS[row["pathway"]],
                    "pathway_name": PATHWAY_NAMES[row["pathway"]],
                    "scenario": scenario,
                    "freshwater_credit_factor": settings["freshwater_factor"],
                    "byproduct_credit_factor": settings["byproduct_factor"],
                    "freshwater_credit": row["freshwater_credit"],
                    "byproduct_credit": row["byproduct_credit"],
                    "noncredit_profit": row["noncredit_profit"],
                    "PROFIT_total_scenario": profit,
                    "annual_cost_scenario": annual_cost,
                    "LCOL": lcol,
                    "LCOL_baseline_reported": row["LCOL_baseline_reported"],
                    "baseline_reconstruction_error": (
                        lcol - row["LCOL_baseline_reported"]
                        if scenario == "baseline"
                        else np.nan
                    ),
                }
            )

    result = pd.DataFrame(rows)
    result["rank"] = (
        result.groupby(["lake", "scenario"])["LCOL"]
        .rank(method="min", ascending=True)
        .astype(int)
    )

    baseline_rank = result[result["scenario"] == "baseline"][
        ["lake", "pathway", "rank", "LCOL"]
    ].rename(columns={"rank": "baseline_rank", "LCOL": "LCOL_baseline_reconstructed"})
    result = result.merge(baseline_rank, on=["lake", "pathway"], how="left")
    result["rank_change_vs_baseline"] = result["rank"] - result["baseline_rank"]
    result["is_winner"] = result["rank"] == 1

    ranking = result[
        [
            "lake",
            "scenario",
            "pathway_id",
            "pathway",
            "pathway_name",
            "LCOL",
            "rank",
            "baseline_rank",
            "rank_change_vs_baseline",
            "is_winner",
        ]
    ].copy()
    return result, ranking


def write_outputs(
    result: pd.DataFrame, ranking: pd.DataFrame, base: pd.DataFrame
) -> None:
    output_xlsx = OUTPUT_DIR / "Byproduct_credit_robustness.xlsx"
    output_csv = OUTPUT_DIR / "Byproduct_credit_robustness.csv"

    definitions = pd.DataFrame(
        [
            ["baseline", 1.0, 1.0, SCENARIOS["baseline"]["description"]],
            [
                "conservative",
                CONSERVATIVE_CREDIT_FACTOR,
                CONSERVATIVE_CREDIT_FACTOR,
                SCENARIOS["conservative"]["description"],
            ],
            ["no-credit", 0.0, 0.0, SCENARIOS["no-credit"]["description"]],
        ],
        columns=[
            "scenario",
            "freshwater_credit_factor",
            "byproduct_credit_factor",
            "description",
        ],
    )

    with pd.ExcelWriter(output_xlsx, engine="xlsxwriter") as writer:
        result.to_excel(writer, sheet_name="Scenario_LCOL", index=False)
        ranking.to_excel(writer, sheet_name="Ranking_changes", index=False)
        base.to_excel(writer, sheet_name="Credit_breakdown", index=False)
        definitions.to_excel(writer, sheet_name="Scenario_definitions", index=False)
    result.to_csv(output_csv, index=False, encoding="utf-8-sig")

    print(f"Workbook written: {output_xlsx}")
    print(f"CSV written: {output_csv}")


def main() -> None:
    base, _summary = load_base_data()
    result, ranking = calculate_scenarios(base)
    write_outputs(result, ranking, base)

    max_error = (
        result.loc[result["scenario"] == "baseline", "baseline_reconstruction_error"]
        .abs()
        .max()
    )
    winner_table = ranking[ranking["is_winner"]][
        ["lake", "scenario", "pathway_id", "pathway_name"]
    ].sort_values(["lake", "scenario"])
    print(f"Baseline LCOL reconstruction max absolute error: {max_error:.3e}")
    print("Scenario winners:")
    print(winner_table.to_string(index=False))


if __name__ == "__main__":
    main()
