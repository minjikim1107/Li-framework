from pathlib import Path
import numpy as np
import pandas as pd
import MC
import TEA

OUTPUT_DIR = Path(__file__).resolve().parent / "sensitivity_results"
SUPPLE_XLSX = OUTPUT_DIR / "Sensitivity_full.xlsx"
FULL_CSV = OUTPUT_DIR / "Sensitivity_full_results.csv"
MAIN_CSV = OUTPUT_DIR / "Sensitivity_main_results.csv"
LAKE_ORDER = list(MC.LAKES)
PATHWAY_ORDER = list(MC.PATHWAYS)
PATHWAY_TECH_MAP = {pathway: set(TEA.PATHWAYS[pathway]) for pathway in PATHWAY_ORDER}
MAIN_VARIABLES = [
    "trl_related_capex",
    "mult_elec",
    "mult_steam",
    "mult_heat",
    "mult_carbon_tax",
    "mult_price_NAOH",
    "mult_price_NA2CO3",
    "mult_price_HCL",
    "mult_price_MGCL2",
    "mult_price_MGOH2",
    "mult_price_WATER",
    "op_hours",
    "replacement_FO",
    "replacement_RO",
    "replacement_IX",
]
MATERIALS_FOR_PREP_CARB = {"NAOH", "NA2CO3", "MGOH2", "CACO3", "WASTE"}
MATERIALS_FOR_IX_PATHWAY = {"NAOH", "NA2CO3", "MGOH2", "WASTE", "HCL", "WATER", "RESIN"}
MATERIALS_FOR_SX_PATHWAY = {
    "NAOH",
    "NA2CO3",
    "WASTE",
    "NACL",
    "HCL",
    "MGCL2",
    "MGOH2",
    "TBP",
    "DILUENT",
    "FECL3",
}


def all_uncertainty_variables():
    variables = ["mult_elec", "mult_steam", "mult_heat", "mult_carbon_tax"]

    variables.extend(f"mult_price_{mat}" for mat in MC.BASE_PRICE)
    variables.extend(
        [
            "membrane_price_FO",
            "replacement_FO",
            "membrane_price_RO",
            "replacement_RO",
            "replacement_IX",
            "mult_labor",
            "op_hours",
        ]
    )
    variables.extend(f"trl_premium_{tech}" for tech in MC.TRL_MAP)
    return variables


def pathway_materials(pathway):
    techs = set(PATHWAY_TECH_MAP[pathway])
    if "PREP" in techs:
        materials = set(MATERIALS_FOR_PREP_CARB)
    elif "IX" in techs:
        materials = set(MATERIALS_FOR_IX_PATHWAY)
    elif "SX" in techs:
        materials = set(MATERIALS_FOR_SX_PATHWAY)
    else:
        materials = set()

    if "FO" in techs:
        materials.add("NACL")
    return materials


def pathway_uses_freshwater(lake, pathway):
    excel_path = MC.BASE_DIR / lake / f"{pathway}.xlsx"
    for tech in TEA.PATHWAYS[pathway]:
        data = MC.load_first_row(excel_path, tech)
        for key in (
            "MED_freshwater",
            "MVR_freshwater",
            "freshwater_kg_s",
            "IX_wash_water_kg_y",
            "freshwater_SD_kg_year",
        ):
            try:
                if float(data.get(key, 0.0)) > 0.0:
                    return True
            except (TypeError, ValueError):
                continue
    return False


def variable_is_active(lake, pathway, variable):
    techs = set(TEA.PATHWAYS[pathway])

    if variable == "mult_carbon_tax":
        baseline_tax = float(MC.ECO.COUNTRY_PARAM[lake]["carbon_tax"])
        return not np.isclose(baseline_tax, 0.0)
    if variable in {"mult_elec", "op_hours", "mult_labor"}:
        return True
    if variable == "mult_steam":
        return "MED" in techs
    if variable == "mult_heat":
        return "MVR" in techs
    if variable == "mult_price_WATER":
        return pathway_uses_freshwater(lake, pathway)
    if variable.startswith("mult_price_"):
        material = variable.replace("mult_price_", "")
        return material in pathway_materials(pathway)
    if variable.startswith("trl_premium_"):
        return variable.replace("trl_premium_", "") in techs
    if variable == "membrane_price_FO":
        return "FO" in techs
    if variable == "replacement_FO":
        return "FO" in techs
    if variable == "membrane_price_RO":
        return "RO" in techs
    if variable == "replacement_RO":
        return "RO" in techs
    if variable == "replacement_IX":
        return "IX" in techs
    return False


def delta_lcol_for_group(group, variable):
    if variable not in group.columns:
        return np.nan
    x = pd.to_numeric(group[variable], errors="coerce")
    y = pd.to_numeric(group["LCOL"], errors="coerce")
    valid = x.notna() & y.notna()
    x = x[valid]
    y = y[valid]
    if len(x) < 10 or x.nunique(dropna=True) < 2:
        return np.nan
    q10, q90 = x.quantile([0.10, 0.90])
    return float(y[x >= q90].mean() - y[x <= q10].mean())


def build_delta_table(mc_draws, variables):
    rows = []
    for (lake, pathway), group in mc_draws.groupby(["lake", "pathway"]):
        for variable in variables:
            rows.append(
                {
                    "lake": lake,
                    "pathway": pathway,
                    "variable": variable,
                    "Delta_LCOL": delta_lcol_for_group(group, variable),
                }
            )
    return pd.DataFrame(rows)


def _trl_components(group, pathway):
    numerator = pd.Series(0.0, index=group.index)
    denominator = pd.Series(0.0, index=group.index)
    for tech in TEA.PATHWAYS[pathway]:
        premium_col = f"trl_premium_{tech}"
        capex_col = f"CAPEX_{tech}_adj"
        if premium_col not in group.columns or capex_col not in group.columns:
            continue
        premium = pd.to_numeric(group[premium_col], errors="coerce")
        adjusted = pd.to_numeric(group[capex_col], errors="coerce")
        base_capex = adjusted / (1.0 + premium)
        numerator = numerator + base_capex * premium
        denominator = denominator + base_capex
    return numerator, denominator


def build_trl_controlled_delta_table(mc_draws):
    rows = []
    for (lake, pathway), group in mc_draws.groupby(["lake", "pathway"]):
        production = pd.to_numeric(group["Li2CO3_prod"], errors="coerce")
        crf = pd.to_numeric(group["CRF"], errors="coerce")
        for tech in TEA.PATHWAYS[pathway]:
            premium_col = f"trl_premium_{tech}"
            capex_col = f"CAPEX_{tech}_adj"
            if premium_col not in group.columns or capex_col not in group.columns:
                continue
            premium = pd.to_numeric(group[premium_col], errors="coerce")
            adjusted = pd.to_numeric(group[capex_col], errors="coerce")
            base_capex = adjusted / (1.0 + premium)
            valid = premium.notna() & base_capex.notna() & production.gt(0)
            q10, q90 = premium[valid].quantile([0.10, 0.90])
            paired_delta = (base_capex * (q90 - q10) * crf / production).where(valid)
            rows.append(
                {
                    "lake": lake,
                    "pathway": pathway,
                    "variable": f"trl_premium_{tech}",
                    "Delta_LCOL": float(paired_delta.mean()),
                }
            )
    return pd.DataFrame(rows)


def build_trl_related_delta_table(mc_draws):
    rows = []
    for (lake, pathway), group in mc_draws.groupby(["lake", "pathway"]):
        numerator, denominator = _trl_components(group, pathway)
        uplift = numerator / denominator.replace(0.0, np.nan)
        production = pd.to_numeric(group["Li2CO3_prod"], errors="coerce")
        crf = pd.to_numeric(group["CRF"], errors="coerce")
        valid = uplift.notna() & production.gt(0)
        q10, q90 = uplift[valid].quantile([0.10, 0.90])
        paired_delta = (denominator * (q90 - q10) * crf / production).where(valid)
        rows.append(
            {
                "lake": lake,
                "pathway": pathway,
                "variable": "trl_related_capex",
                "Delta_LCOL": float(paired_delta.mean()),
            }
        )
    return pd.DataFrame(rows)


def build_full_results(mc_draws, impacts):
    variables = all_uncertainty_variables()
    delta = build_delta_table(mc_draws, variables)
    delta_lookup = delta.set_index(["lake", "pathway", "variable"])
    trl_delta = build_trl_controlled_delta_table(mc_draws)
    trl_lookup = trl_delta.set_index(["lake", "pathway", "variable"])
    impact_lookup = impacts.set_index(["lake", "pathway", "variable"])

    rows = []
    for lake in LAKE_ORDER:
        for pathway in PATHWAY_ORDER:
            for variable in variables:
                active = variable_is_active(lake, pathway, variable)
                key = (lake, pathway, variable)
                if key in impact_lookup.index and active:
                    impact = impact_lookup.loc[key]
                    prcc = impact.get("prcc", np.nan)
                    rho = impact.get("spearman_rho", np.nan)
                    beta = impact.get("std_beta", np.nan)
                else:
                    prcc = rho = beta = np.nan

                if key in trl_lookup.index and active:
                    d_lcol = trl_lookup.loc[key, "Delta_LCOL"]
                    delta_method = "paired_counterfactual_TRL"
                else:
                    d_lcol = (
                        delta_lookup.loc[key, "Delta_LCOL"]
                        if key in delta_lookup.index and active
                        else np.nan
                    )
                    delta_method = "decile_contrast"
                rows.append(
                    {
                        "lake": lake,
                        "pathway": pathway,
                        "variable": variable,
                        "Delta_LCOL": d_lcol,
                        "PRCC": prcc,
                        "Spearman_rho": rho,
                        "std_beta": beta,
                        "Delta_method": delta_method if active else "inactive",
                        "variable_group": variable_group(variable),
                        "active": bool(active),
                        "main_selected": variable in MAIN_VARIABLES,
                    }
                )

    return pd.DataFrame(rows)


def variable_group(variable):
    if variable.startswith("trl_premium_"):
        return "TRL"
    if variable in {"mult_elec", "mult_steam", "mult_heat", "mult_carbon_tax"}:
        return "Energy & Carbon"
    if variable.startswith("mult_price_"):
        return "Material price"
    return "Operations & replacement"


def build_main_results(mc_draws, full_results):
    selected = full_results[full_results["main_selected"]].copy()
    selected["sensitivity"] = selected["Delta_LCOL"]

    trl = build_trl_related_delta_table(mc_draws)
    trl["sensitivity"] = trl["Delta_LCOL"]
    trl["Delta_LCOL"] = trl["sensitivity"]
    trl["PRCC"] = np.nan
    trl["Spearman_rho"] = np.nan
    trl["std_beta"] = np.nan
    trl["variable_group"] = "TRL"
    trl["active"] = True
    trl["main_selected"] = True

    columns = [
        "lake",
        "pathway",
        "variable",
        "Delta_LCOL",
        "sensitivity",
        "PRCC",
        "Spearman_rho",
        "std_beta",
        "variable_group",
        "active",
        "main_selected",
    ]
    return pd.concat([selected[columns], trl[columns]], ignore_index=True)


def write_supplementary_excel(full_results):
    from openpyxl import load_workbook
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

    variable_labels = {
        "mult_elec": "Electricity price",
        "mult_steam": "Steam price",
        "mult_heat": "Heat price",
        "mult_carbon_tax": "Carbon tax",
        "mult_price_NAOH": "NaOH price",
        "mult_price_NACL": "NaCl price",
        "mult_price_NA2CO3": "Na₂CO₃ price",
        "mult_price_CACO3": "CaCO₃ price",
        "mult_price_MGOH2": "Mg(OH)₂ credit",
        "mult_price_DILUENT": "Diluent price",
        "mult_price_TBP": "TBP price",
        "mult_price_FECL3": "FeCl₃ price",
        "mult_price_HCL": "HCl price",
        "mult_price_MGCL2": "MgCl₂ price",
        "mult_price_WASTE": "Waste-treatment price",
        "mult_price_WATER": "Freshwater cost/credit",
        "mult_price_RESIN": "IX sorbent unit cost",
        "membrane_price_FO": "FO membrane unit cost",
        "replacement_FO": "FO membrane replacement",
        "membrane_price_RO": "RO membrane unit cost",
        "replacement_RO": "RO membrane replacement",
        "replacement_IX": "IX sorbent replacement",
        "mult_labor": "Labor cost",
        "op_hours": "Operating hours",
        "trl_premium_NE": "NE TRL-related CAPEX",
        "trl_premium_SD": "SD TRL-related CAPEX",
        "trl_premium_MED": "MED TRL-related CAPEX",
        "trl_premium_MVR": "MVR TRL-related CAPEX",
        "trl_premium_FO": "FO TRL-related CAPEX",
        "trl_premium_RO": "RO TRL-related CAPEX",
        "trl_premium_IX": "IX TRL-related CAPEX",
        "trl_premium_SX": "SX TRL-related CAPEX",
        "trl_premium_PREP": "PREP TRL-related CAPEX",
        "trl_premium_CARB": "CARB TRL-related CAPEX",
    }
    variables = all_uncertainty_variables()
    pathway_labels = {pathway: f"P{i}" for i, pathway in enumerate(PATHWAY_ORDER, 1)}

    expected_rows = len(LAKE_ORDER) * len(PATHWAY_ORDER) * len(variables)
    if len(full_results) != expected_rows:
        raise AssertionError(
            f"Full sensitivity row count mismatch: {len(full_results)} != {expected_rows}"
        )

    with pd.ExcelWriter(SUPPLE_XLSX, engine="openpyxl") as writer:
        for lake in LAKE_ORDER:
            lake_results = full_results[full_results["lake"] == lake].copy()
            value_lookup = lake_results.set_index(["variable", "pathway"])["Delta_LCOL"]
            active_lookup = lake_results.set_index(["variable", "pathway"])["active"]

            rows = []
            for variable in variables:
                row = {"Variable": variable_labels.get(variable, variable)}
                for pathway in PATHWAY_ORDER:
                    key = (variable, pathway)
                    active = bool(active_lookup.get(key, False))
                    value = value_lookup.get(key, np.nan)
                    row[pathway_labels[pathway]] = (
                        float(value) if active and pd.notna(value) else "-"
                    )
                rows.append(row)

            display = pd.DataFrame(rows, columns=["Variable", *pathway_labels.values()])
            display.to_excel(writer, sheet_name=lake, index=False, startrow=3)

    workbook = load_workbook(SUPPLE_XLSX)
    header_fill = PatternFill("solid", fgColor="E7E6E6")
    group_fills = {
        "Energy & Carbon": PatternFill("solid", fgColor="FFF2CC"),
        "Material price": PatternFill("solid", fgColor="FCE4D6"),
        "Operations & replacement": PatternFill("solid", fgColor="E4DFEC"),
        "TRL": PatternFill("solid", fgColor="DDEBF7"),
    }
    medium_black = Side(style="medium", color="000000")
    thin_gray = Side(style="thin", color="D9D9D9")

    for lake in LAKE_ORDER:
        worksheet = workbook[lake]
        worksheet.merge_cells("A1:L1")
        worksheet["A1"] = (
            f"Supplementary Table: Full pathway-level sensitivity results for Lake {lake}."
        )
        worksheet["A1"].font = Font(name="Arial", size=11, bold=True)
        worksheet["A1"].alignment = Alignment(horizontal="left", vertical="center")

        worksheet.merge_cells("A2:L2")
        worksheet["A2"] = (
            "Values are signed ΔLCOL (USD kg⁻¹ Li₂CO₃), calculated as mean LCOL "
            "for the upper-decile input samples minus that for the lower-decile input samples. "
            "Inactive or non-applicable pathway-variable combinations are shown as '-'."
        )
        worksheet["A2"].font = Font(name="Arial", size=10)
        worksheet["A2"].alignment = Alignment(
            horizontal="left", vertical="top", wrap_text=True
        )
        worksheet.row_dimensions[2].height = 34

        for cell in worksheet[4]:
            cell.font = Font(name="Arial", size=10, bold=True)
            cell.fill = header_fill
            cell.alignment = Alignment(horizontal="center", vertical="center")
            cell.border = Border(top=medium_black, bottom=medium_black)

        for row_number, variable in enumerate(variables, start=5):
            group = variable_group(variable)
            label_cell = worksheet.cell(row=row_number, column=1)
            label_cell.fill = group_fills[group]
            label_cell.font = Font(name="Arial", size=10)
            label_cell.alignment = Alignment(horizontal="left", vertical="center")
            label_cell.border = Border(bottom=thin_gray)

            for column in range(2, 13):
                cell = worksheet.cell(row=row_number, column=column)
                cell.font = Font(name="Arial", size=10)
                cell.alignment = Alignment(horizontal="center", vertical="center")
                cell.border = Border(bottom=thin_gray)
                if isinstance(cell.value, (int, float)):
                    cell.number_format = "0.0000;-0.0000"

        worksheet.column_dimensions["A"].width = 31
        for column_letter in "BCDEFGHIJKL":
            worksheet.column_dimensions[column_letter].width = 12
        worksheet.freeze_panes = "B5"
        worksheet.auto_filter.ref = f"A4:L{worksheet.max_row}"
        worksheet.sheet_view.showGridLines = False
        worksheet.page_setup.orientation = "landscape"
        worksheet.page_setup.fitToWidth = 1
        worksheet.page_setup.fitToHeight = 0
        worksheet.sheet_properties.pageSetUpPr.fitToPage = True
        worksheet.print_title_rows = "1:4"
        worksheet.print_area = f"A1:L{worksheet.max_row}"

    workbook.save(SUPPLE_XLSX)


def main():
    if not MC.OUT_CSV.exists():
        MC.main()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    mc_draws = pd.read_csv(MC.OUT_CSV)
    impacts = MC.calc_variable_impacts(mc_draws).copy()
    full_results = build_full_results(mc_draws, impacts)
    main_results = build_main_results(mc_draws, full_results)
    expected = len(LAKE_ORDER) * len(PATHWAY_ORDER) * len(all_uncertainty_variables())
    if len(full_results) != expected:
        raise AssertionError(
            f"Full sensitivity row count mismatch: {len(full_results)} != {expected}"
        )
    full_results.to_csv(FULL_CSV, index=False, encoding="utf-8-sig")
    main_results.to_csv(MAIN_CSV, index=False, encoding="utf-8-sig")
    write_supplementary_excel(full_results)
    print(f"Saved: {FULL_CSV}")
    print(f"Saved: {MAIN_CSV}")
    print(f"Saved: {SUPPLE_XLSX}")
    print(f"Rows: {len(full_results)}; active: {int(full_results['active'].sum())}")


if __name__ == "__main__":
    main()
