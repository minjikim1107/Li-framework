from pathlib import Path
from typing import Dict, Iterable, List, Tuple

import pandas as pd

TEA_CODE_DIR = Path(__file__).resolve().parents[1]
OUTPUT_DIR = Path(__file__).resolve().parent
ANALYSIS_RESULTS_DIR = TEA_CODE_DIR / "analysis_results"
BASELINE_XLSX = TEA_CODE_DIR / "TEA_result.xlsx"
OUTPUT_XLSX = OUTPUT_DIR / "capacity_analysis.xlsx"
OUTPUT_CSV = OUTPUT_DIR / "capacity_analysis.csv"

BASELINE_NOMINAL_CAPACITY_TPY = 19_683.59

CAPACITY_CASES: Tuple[Tuple[str, float, float], ...] = (
    ("10 kt/y nominal", 10_000.0, 10_000.0 / BASELINE_NOMINAL_CAPACITY_TPY),
    ("~20 kt/y nominal (baseline)", BASELINE_NOMINAL_CAPACITY_TPY, 1.0),
    ("40 kt/y nominal", 40_000.0, 40_000.0 / BASELINE_NOMINAL_CAPACITY_TPY),
)


PATHWAY_TECHS: Dict[str, Tuple[str, ...]] = {
    "NE_prep_carb": ("NE", "PREP", "CARB"),
    "SD_prep_carb": ("SD", "PREP", "CARB"),
    "MED_prep_carb": ("MED", "PREP", "CARB"),
    "MVR_prep_carb": ("MVR", "PREP", "CARB"),
    "FO_prep_carb": ("FO", "PREP", "CARB"),
    "IX_MED_carb": ("IX", "MED", "CARB"),
    "IX_MVR_carb": ("IX", "MVR", "CARB"),
    "IX_RO_carb": ("IX", "RO", "CARB"),
    "SX_MED_carb": ("SX", "MED", "CARB"),
    "SX_MVR_carb": ("SX", "MVR", "CARB"),
    "SX_RO_carb": ("SX", "RO", "CARB"),
}

MODULE_CAPEX_EXPONENT: Dict[str, float] = {
    "NE": 0.80,
    "SD": 0.90,
    "MED": 0.85,
    "MVR": 0.85,
    "FO": 0.96,
    "RO": 0.865,
    "IX": 1.00,
    "SX": 0.60,
    "PREP": 0.60,
    "CARB": 0.60,
}


MAINTENANCE_RATE = 2.75 / 100.0


def _as_float(value, default: float = 0.0) -> float:
    if pd.isna(value):
        return default
    return float(value)


def _read_detail(lake: str, pathway: str) -> pd.DataFrame:
    path = ANALYSIS_RESULTS_DIR / lake / f"{pathway}_econ.xlsx"
    if not path.exists():
        raise FileNotFoundError(f"TEA detail file not found: {path}")
    return pd.read_excel(path, sheet_name="DETAIL")


def _detail_row(detail: pd.DataFrame, tech: str) -> pd.Series:
    rows = detail.loc[detail["TECH"].astype(str).str.upper() == tech.upper()]
    if rows.empty:
        raise ValueError(f"Technology '{tech}' not found in TEA DETAIL output")
    return rows.iloc[0]


def _component_sum(row: pd.Series, predicate) -> float:
    total = 0.0
    for key, value in row.items():
        if predicate(str(key)):
            total += _as_float(value)
    return total


def _module_base_values(
    summary_row: pd.Series, detail: pd.DataFrame, tech: str
) -> Dict[str, float]:
    row = _detail_row(detail, tech)
    capex_base = _as_float(summary_row.get(f"CAPEX_{tech}", 0.0))
    opex_base = _as_float(summary_row.get(f"OPEX_{tech}", 0.0))
    profit_base = _as_float(summary_row.get(f"PROFIT_{tech}", 0.0))

    labor_base = _component_sum(
        row,
        lambda key: key.startswith("OPEX_") and key.endswith("_labor"),
    )
    maintenance_base = _component_sum(
        row,
        lambda key: key.startswith("OPEX_") and key.endswith("_main"),
    )

    if tech in {"NE", "SD"}:
        variable_base = opex_base
        opex_method = "linear composite module OPEX (existing NE/SD structure)"
    else:
        variable_base = opex_base - labor_base - maintenance_base
        opex_method = "variable OPEX linear + fixed current labor + scaled maintenance"

    return {
        "capex_base": capex_base,
        "opex_base": opex_base,
        "variable_base": variable_base,
        "labor_base": labor_base,
        "maintenance_base": maintenance_base,
        "profit_base": profit_base,
        "opex_method": opex_method,
    }


def build_capacity_analysis(summary: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
    required = {
        "lake",
        "pathway",
        "CAPEX_total",
        "OPEX_total",
        "PROFIT_total",
        "Li2CO3_prod",
        "CRF",
    }
    missing = sorted(required.difference(summary.columns))
    if missing:
        raise ValueError("TEA summary is missing columns: " + ", ".join(missing))

    summary_rows: List[Dict[str, object]] = []
    module_rows: List[Dict[str, object]] = []

    for _, base in summary.iterrows():
        lake = str(base["lake"])
        pathway = str(base["pathway"])
        techs = PATHWAY_TECHS.get(pathway)
        if techs is None:
            raise ValueError(
                f"Pathway is not registered in Capacity_analysis.py: {pathway}"
            )

        detail = _read_detail(lake, pathway)
        modules = {tech: _module_base_values(base, detail, tech) for tech in techs}

        for case_label, nominal_capacity_tpy, sf in CAPACITY_CASES:
            capex_total = 0.0
            opex_total = 0.0
            profit_total = 0.0

            for tech in techs:
                values = modules[tech]
                exponent = MODULE_CAPEX_EXPONENT[tech]
                capex_scaled = values["capex_base"] * sf**exponent

                if tech in {"NE", "SD"}:
                    labor_scaled = 0.0
                    maintenance_scaled = 0.0
                    opex_scaled = values["variable_base"] * sf
                else:
                    labor_scaled = values["labor_base"]

                    maintenance_scaled = (
                        values["maintenance_base"] * sf**exponent
                        if values["maintenance_base"] > 0.0
                        else 0.0
                    )
                    opex_scaled = (
                        values["variable_base"] * sf + labor_scaled + maintenance_scaled
                    )

                profit_scaled = values["profit_base"] * sf
                capex_total += capex_scaled
                opex_total += opex_scaled
                profit_total += profit_scaled

                module_rows.append(
                    {
                        "capacity_case": case_label,
                        "nominal_input_capacity_tpy": nominal_capacity_tpy,
                        "SF_input": sf,
                        "lake": lake,
                        "pathway": pathway,
                        "technology": tech,
                        "CAPEX_exponent": exponent,
                        "CAPEX_base": values["capex_base"],
                        "CAPEX_scaled": capex_scaled,
                        "OPEX_base": values["opex_base"],
                        "OPEX_variable_base": values["variable_base"],
                        "labor_base": values["labor_base"],
                        "labor_scaled": labor_scaled,
                        "maintenance_base": values["maintenance_base"],
                        "maintenance_scaled": maintenance_scaled,
                        "OPEX_scaled": opex_scaled,
                        "PROFIT_base": values["profit_base"],
                        "PROFIT_scaled": profit_scaled,
                        "OPEX_scaling_method": values["opex_method"],
                    }
                )

            actual_li2co3_tpy = _as_float(base["Li2CO3_prod"]) / 1000.0 * sf
            annual_cost = (
                capex_total * _as_float(base["CRF"]) + opex_total + profit_total
            )
            lcol = (
                annual_cost / (actual_li2co3_tpy * 1000.0)
                if actual_li2co3_tpy
                else None
            )

            summary_rows.append(
                {
                    "capacity_case": case_label,
                    "nominal_input_capacity_tpy": nominal_capacity_tpy,
                    "SF_input": sf,
                    "lake": lake,
                    "pathway": pathway,
                    "actual_Li2CO3_tpy": actual_li2co3_tpy,
                    "actual_yield_vs_nominal": (
                        actual_li2co3_tpy / nominal_capacity_tpy
                        if nominal_capacity_tpy
                        else None
                    ),
                    "CAPEX_total": capex_total,
                    "OPEX_total": opex_total,
                    "PROFIT_total": profit_total,
                    "Li2CO3_prod_kg_y": actual_li2co3_tpy * 1000.0,
                    "CRF": _as_float(base["CRF"]),
                    "LCOL": lcol,
                    "baseline_CAPEX_total": _as_float(base["CAPEX_total"]),
                    "baseline_OPEX_total": _as_float(base["OPEX_total"]),
                    "baseline_PROFIT_total": _as_float(base["PROFIT_total"]),
                    "baseline_Li2CO3_prod_kg_y": _as_float(base["Li2CO3_prod"]),
                    "baseline_LCOL": _as_float(base["LCOL"]),
                }
            )

    return pd.DataFrame(summary_rows), pd.DataFrame(module_rows)


def _baseline_check(capacity_summary: pd.DataFrame) -> pd.DataFrame:
    base = capacity_summary.loc[
        capacity_summary["capacity_case"] == "~20 kt/y nominal (baseline)"
    ].copy()
    base["delta_CAPEX"] = base["CAPEX_total"] - base["baseline_CAPEX_total"]
    base["delta_OPEX"] = base["OPEX_total"] - base["baseline_OPEX_total"]
    base["delta_PROFIT"] = base["PROFIT_total"] - base["baseline_PROFIT_total"]
    base["delta_Li2CO3"] = base["Li2CO3_prod_kg_y"] - base["baseline_Li2CO3_prod_kg_y"]
    base["delta_LCOL"] = base["LCOL"] - base["baseline_LCOL"]
    return base[
        [
            "lake",
            "pathway",
            "delta_CAPEX",
            "delta_OPEX",
            "delta_PROFIT",
            "delta_Li2CO3",
            "delta_LCOL",
        ]
    ]


def main() -> None:
    if not BASELINE_XLSX.exists():
        raise FileNotFoundError(f"Baseline TEA workbook not found: {BASELINE_XLSX}")

    summary = pd.read_excel(BASELINE_XLSX, sheet_name="SUMMARY_ALL")
    capacity_summary, module_detail = build_capacity_analysis(summary)
    baseline_check = _baseline_check(capacity_summary)

    assumptions = pd.DataFrame(
        {
            "item": [
                "capacity_definition",
                "baseline_nominal_capacity_tpy",
                "SF_10",
                "SF_base",
                "SF_40",
                "CAPEX_rule",
                "OPEX_variable_rule",
                "labor_rule",
                "maintenance_rule",
                "loss_rule",
                "source_baseline",
            ],
            "value": [
                "nominal Li2CO3-equivalent input/design capacity",
                BASELINE_NOMINAL_CAPACITY_TPY,
                CAPACITY_CASES[0][2],
                CAPACITY_CASES[1][2],
                CAPACITY_CASES[2][2],
                "module CAPEX_base * SF_input ** MODULE_CAPEX_EXPONENT[module]",
                "linear with SF_input",
                "unchanged current Np/Nnp staffing; no capacity scaling",
                f"original *_main * module CAPEX scale factor where original *_main exists; otherwise unchanged at zero (base rate={MAINTENANCE_RATE:.4f})",
                "actual pathway Li2CO3 output = baseline output * SF_input",
                str(BASELINE_XLSX),
            ],
        }
    )
    exponents = pd.DataFrame(
        list(MODULE_CAPEX_EXPONENT.items()),
        columns=["technology", "CAPEX_exponent"],
    )
    assumptions = pd.concat(
        [
            assumptions,
            pd.DataFrame(
                {
                    "item": ["module_CAPEX_exponents"],
                    "value": [str(MODULE_CAPEX_EXPONENT)],
                }
            ),
        ],
        ignore_index=True,
    )

    with pd.ExcelWriter(OUTPUT_XLSX, engine="xlsxwriter") as writer:
        capacity_summary.to_excel(writer, sheet_name="CAPACITY_SUMMARY", index=False)
        module_detail.to_excel(writer, sheet_name="MODULE_DETAIL", index=False)
        baseline_check.to_excel(writer, sheet_name="BASELINE_CHECK", index=False)
        assumptions.to_excel(writer, sheet_name="ASSUMPTIONS", index=False)
        exponents.to_excel(writer, sheet_name="CAPEX_EXPONENTS", index=False)

    capacity_summary.to_csv(OUTPUT_CSV, index=False, encoding="utf-8-sig")

    numeric_check = baseline_check.select_dtypes(include="number")
    max_base_error = numeric_check.abs().max().max()
    print(f"Capacity analysis written: {OUTPUT_XLSX}")
    print(f"Capacity analysis CSV written: {OUTPUT_CSV}")
    print(f"Rows: {len(capacity_summary)} summary, {len(module_detail)} module detail")
    print(f"Maximum baseline reconstruction error: {max_base_error:.6g}")


if __name__ == "__main__":
    main()
