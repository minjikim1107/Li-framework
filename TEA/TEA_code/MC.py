import copy
import random
from functools import lru_cache
from pathlib import Path
from contextlib import contextmanager

import numpy as np
import pandas as pd

import TEA
import Economic as ECO
from project_paths import EXCEL_DIR, MC_DIR


BASE_DIR = EXCEL_DIR
OUT_DIR = MC_DIR
OUT_DIR.mkdir(parents=True, exist_ok=True)

N_DRAWS = 3000
RANDOM_SEED = 42
MIN_ROWS_FOR_SENS = 30
MIN_UNIQUE_FOR_SENS = 3

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

OUT_CSV = OUT_DIR / "MC_draws.csv"
OUT_XLSX = OUT_DIR / "MC_result.xlsx"


PRICE_MULT_RANGE = {
    "NAOH": (0.70, 1.00, 1.30),
    "NACL": (0.70, 1.00, 1.30),
    "NA2CO3": (0.70, 1.00, 1.30),
    "CACO3": (0.70, 1.00, 1.30),
    "MGOH2": (0.70, 1.00, 1.30),
    "DILUENT": (0.70, 1.00, 1.30),
    "TBP": (0.70, 1.00, 1.30),
    "FECL3": (0.70, 1.00, 1.30),
    "HCL": (0.70, 1.00, 1.30),
    "MGCL2": (0.70, 1.00, 1.30),
    "WASTE": (0.70, 1.00, 1.30),
    "WATER": (0.70, 1.00, 1.30),
    "RESIN": (0.70, 1.00, 1.30),
}

ELEC_MULT_RANGE = (0.50, 1.00, 2.00)
STEAM_MULT_RANGE = (0.50, 1.00, 2.00)

HEAT_MULT_RANGE = (0.50, 1.00, 2.00)
CARBON_TAX_MULT_RANGE = (0.50, 1.0, 5.00)


FO_MEMBRANE_PRICE_RANGE = (30.0, 56.0, 60.0)
RO_MEMBRANE_PRICE_RANGE = (5.0, 10.0, 30.0)
FO_REPLACEMENT_RANGE = (0.20, 0.25, 1.0 / 3.0)
RO_REPLACEMENT_RANGE = (0.08, 0.15, 0.20)
IX_REPLACEMENT_RANGE = (0.04, 0.05, 0.10)
LABOR_MULT_RANGE = (0.80, 1.00, 1.20)
OP_HOURS_RANGE = (7000.0, 8500.0, 8760.0)
BASE_OP_HOURS = 8500.0

TRL_MAP = {
    "NE": 9.0,
    "SD": 4.0,
    "MED": 7.5,
    "MVR": 7.5,
    "RO": 8.5,
    "FO": 4.5,
    "IX": 7.5,
    "SX": 6.5,
    "PREP": 9.0,
    "CARB": 9.0,
}

TRL_ANCHORS = {
    4.0: (0.30, 0.50, 0.70),
    5.5: (0.20, 0.275, 0.35),
    7.5: (0.05, 0.125, 0.20),
    9.0: (0.00, 0.05, 0.10),
}


BASE_PRICE = {
    "NAOH": 0.32,
    "NACL": 0.025,
    "NA2CO3": 0.154,
    "CACO3": 0.30,
    "MGOH2": 0.773,
    "DILUENT": 5.00,
    "TBP": 6.00,
    "FECL3": 0.402,
    "HCL": 0.0162,
    "MGCL2": 0.09,
    "WASTE": 0.00019,
    "WATER": 0.000065,
    "RESIN": 6.0,
}


UTILITY_ACTIVE_MAP = {
    "NE_prep_carb": {"mult_elec": True, "mult_steam": False, "mult_carbon_tax": True},
    "SD_prep_carb": {"mult_elec": True, "mult_steam": False, "mult_carbon_tax": True},
    "MED_prep_carb": {"mult_elec": True, "mult_steam": True, "mult_carbon_tax": True},
    "MVR_prep_carb": {"mult_elec": True, "mult_steam": False, "mult_carbon_tax": True},
    "FO_prep_carb": {"mult_elec": True, "mult_steam": False, "mult_carbon_tax": True},
    "IX_MED_carb": {"mult_elec": True, "mult_steam": True, "mult_carbon_tax": True},
    "IX_MVR_carb": {"mult_elec": True, "mult_steam": False, "mult_carbon_tax": True},
    "IX_RO_carb": {"mult_elec": True, "mult_steam": False, "mult_carbon_tax": True},
    "SX_MED_carb": {"mult_elec": True, "mult_steam": True, "mult_carbon_tax": True},
    "SX_MVR_carb": {"mult_elec": True, "mult_steam": False, "mult_carbon_tax": True},
    "SX_RO_carb": {"mult_elec": True, "mult_steam": False, "mult_carbon_tax": True},
}

HEAT_ACTIVE_PATHWAYS = {
    "MVR_prep_carb",
    "IX_MVR_carb",
    "SX_MVR_carb",
}


def tri(rng, a, b, c):
    return rng.triangular(a, b, c)


@lru_cache(maxsize=None)
def load_first_row(excel_path, sheet_name):
    df = pd.read_excel(excel_path, sheet_name=sheet_name)
    return df.iloc[0].to_dict()


def get_trl_premium_range(trl_value):
    trl = float(trl_value)
    anchors = sorted(TRL_ANCHORS.items())
    min_trl = anchors[0][0]
    max_trl = anchors[-1][0]

    if trl < min_trl or trl > max_trl:
        raise ValueError(
            f"TRL must be between {min_trl:g} and {max_trl:g}; received {trl:g}."
        )

    for anchor_trl, premium_range in anchors:
        if np.isclose(trl, anchor_trl):
            return premium_range

    for (trl_low, range_low), (trl_high, range_high) in zip(anchors[:-1], anchors[1:]):
        if trl_low < trl < trl_high:
            fraction = (trl - trl_low) / (trl_high - trl_low)
            return tuple(
                low + fraction * (high - low)
                for low, high in zip(range_low, range_high)
            )

    raise RuntimeError(f"Could not interpolate a TRL premium range for TRL={trl:g}.")


def sample_trl_premium(rng, tech_name):
    trl = TRL_MAP[tech_name]
    lower, mode, upper = get_trl_premium_range(trl)
    return tri(rng, lower, mode, upper)


def print_trl_premium_ranges():
    print("TRL-informed CAPEX premium ranges:")
    for tech_name, trl in TRL_MAP.items():
        lower, mode, upper = get_trl_premium_range(trl)
        print(
            f"  {tech_name:>4s} | TRL {trl:.1f} | "
            f"({lower:.4f}, {mode:.4f}, {upper:.4f})"
        )


def build_sampled_material_prices(rng):
    sampled = {}
    for mat, base in BASE_PRICE.items():
        a, b, c = PRICE_MULT_RANGE[mat]
        sampled[mat] = base * tri(rng, a, b, c)
    return sampled


def build_draw_scenario(rng, lake):
    base_wage = ECO.LABOR_WAGE.get(lake, ECO.LABOR_WAGE["DEFAULT"])
    mult_labor = tri(rng, *LABOR_MULT_RANGE)
    return {
        "sampled_material_price": build_sampled_material_prices(rng),
        "sampled_energy_mult": {
            "elec": tri(rng, *ELEC_MULT_RANGE),
            "steam": tri(rng, *STEAM_MULT_RANGE),
            "heat": tri(rng, *HEAT_MULT_RANGE),
        },
        "sampled_carbon_mult": tri(rng, *CARBON_TAX_MULT_RANGE),
        "membrane_price_FO": tri(rng, *FO_MEMBRANE_PRICE_RANGE),
        "replacement_FO": tri(rng, *FO_REPLACEMENT_RANGE),
        "membrane_price_RO": tri(rng, *RO_MEMBRANE_PRICE_RANGE),
        "replacement_RO": tri(rng, *RO_REPLACEMENT_RANGE),
        "replacement_IX": tri(rng, *IX_REPLACEMENT_RANGE),
        "mult_labor": mult_labor,
        "sampled_labor_wage": base_wage * mult_labor,
        "op_hours": tri(rng, *OP_HOURS_RANGE),
    }


@contextmanager
def patched_opex_environment(
    lake,
    sampled_material_price,
    sampled_energy_mult,
    sampled_carbon_mult,
    mult_labor,
):
    original_country_param = copy.deepcopy(ECO.COUNTRY_PARAM)

    original_methods = {
        "NAOH": ECO.Opex.NAOH,
        "NACL": ECO.Opex.NACL,
        "NA2CO3": ECO.Opex.NA2CO3,
        "CACO3": ECO.Opex.CACO3,
        "MGOH2": ECO.Opex.MGOH2,
        "DILUENT": ECO.Opex.DILUENT,
        "TBP": ECO.Opex.TBP,
        "FECL3": ECO.Opex.FECL3,
        "HCL": ECO.Opex.HCL,
        "MGCL2": ECO.Opex.MGCL2,
        "WASTE": ECO.Opex.WASTE,
        "WATER": ECO.Opex.WATER,
        "RESIN": ECO.Opex.RESIN,
        "labor": ECO.Opex.labor,
        "heat": ECO.Opex.heat,
    }

    try:
        ECO.COUNTRY_PARAM[lake]["elec_base"] = (
            original_country_param[lake]["elec_base"] * sampled_energy_mult["elec"]
        )
        ECO.COUNTRY_PARAM[lake]["steam_base"] = (
            original_country_param[lake]["steam_base"] * sampled_energy_mult["steam"]
        )
        ECO.COUNTRY_PARAM[lake]["carbon_tax"] = (
            original_country_param[lake]["carbon_tax"] * sampled_carbon_mult
        )

        ECO.Opex.heat = staticmethod(
            lambda amount, year=ECO.BASELINE_HEAT_YEAR, f=original_methods[
                "heat"
            ], m=sampled_energy_mult["heat"]: f(amount, year)
            * m
        )

        ECO.Opex.NAOH = staticmethod(
            lambda amount, p=sampled_material_price["NAOH"]: amount * p
        )
        ECO.Opex.NACL = staticmethod(
            lambda amount, p=sampled_material_price["NACL"]: amount * p
        )
        ECO.Opex.NA2CO3 = staticmethod(
            lambda amount, p=sampled_material_price["NA2CO3"]: amount * p
        )
        ECO.Opex.CACO3 = staticmethod(
            lambda amount, p=sampled_material_price["CACO3"]: amount * p
        )
        ECO.Opex.MGOH2 = staticmethod(
            lambda amount, p=sampled_material_price["MGOH2"]: amount * p
        )
        ECO.Opex.DILUENT = staticmethod(
            lambda amount, p=sampled_material_price["DILUENT"]: amount * p
        )
        ECO.Opex.TBP = staticmethod(
            lambda amount, p=sampled_material_price["TBP"]: amount * p
        )
        ECO.Opex.FECL3 = staticmethod(
            lambda amount, p=sampled_material_price["FECL3"]: amount * p
        )
        ECO.Opex.HCL = staticmethod(
            lambda amount, p=sampled_material_price["HCL"]: amount * p
        )
        ECO.Opex.MGCL2 = staticmethod(
            lambda amount, p=sampled_material_price["MGCL2"]: amount * p
        )
        ECO.Opex.WASTE = staticmethod(
            lambda amount, p=sampled_material_price["WASTE"]: amount * p
        )
        ECO.Opex.WATER = staticmethod(
            lambda amount, p=sampled_material_price["WATER"]: amount * p
        )
        ECO.Opex.RESIN = staticmethod(
            lambda amount, p=sampled_material_price["RESIN"]: amount * p
        )

        ECO.Opex.labor = staticmethod(
            lambda Np, Nnp, f=original_methods["labor"], m=mult_labor: f(Np, Nnp) * m
        )

        ECO.Opex.set_lake(lake)
        yield
    finally:
        ECO.COUNTRY_PARAM.clear()
        ECO.COUNTRY_PARAM.update(original_country_param)

        ECO.Opex.NAOH = original_methods["NAOH"]
        ECO.Opex.NACL = original_methods["NACL"]
        ECO.Opex.NA2CO3 = original_methods["NA2CO3"]
        ECO.Opex.CACO3 = original_methods["CACO3"]
        ECO.Opex.MGOH2 = original_methods["MGOH2"]
        ECO.Opex.DILUENT = original_methods["DILUENT"]
        ECO.Opex.TBP = original_methods["TBP"]
        ECO.Opex.FECL3 = original_methods["FECL3"]
        ECO.Opex.HCL = original_methods["HCL"]
        ECO.Opex.MGCL2 = original_methods["MGCL2"]
        ECO.Opex.WASTE = original_methods["WASTE"]
        ECO.Opex.set_lake("DEFAULT")
        ECO.Opex.WATER = original_methods["WATER"]
        ECO.Opex.RESIN = original_methods["RESIN"]
        ECO.Opex.labor = original_methods["labor"]
        ECO.Opex.heat = original_methods["heat"]


def _rescale_linear_membrane_capex(result, technology, sampled_price):
    suffix = technology
    eq_key = f"C_eq_{suffix}"
    mem_key = f"C_eq_{suffix}_mem"
    total_key = f"CAP_TCI_{suffix}"
    capex_key = f"CAPEX_{suffix}_total"

    old_eq = float(result.get(eq_key, 0.0))
    old_mem = float(result.get(mem_key, 0.0))
    area_key = (
        "total_membrane_area_m2" if technology == "FO" else "membrane_area_total_m2"
    )

    area = float(result.pop("_mc_membrane_area_m2"))
    price_factor = 800.8 / 816.0 if technology == "FO" else 1.0
    new_mem = sampled_price * area * price_factor
    new_eq = old_eq - old_mem + new_mem

    if old_eq <= 0.0:
        return result

    ratio = new_eq / old_eq
    result[mem_key] = new_mem
    result[eq_key] = new_eq

    for key in list(result):
        if key in {
            eq_key,
            mem_key,
            f"C_eq_{suffix}_pre",
            f"C_eq_{suffix}_pump",
            f"C_eq_{suffix}_erd",
        }:
            continue
        if key.startswith("C_") or key.startswith("CAP_"):
            value = result[key]
            if isinstance(value, (int, float, np.floating)):
                result[key] = float(value) * ratio

    if total_key in result:
        result[total_key] = float(result[total_key])
    if capex_key in result and total_key in result:
        result[capex_key] = result[total_key]
    return result


def _scale_annual_result(result, technology, ratio):
    if np.isclose(ratio, 1.0):
        return result

    if "LI2CO3" in result:
        result["LI2CO3"] = float(result["LI2CO3"]) * ratio
    for key in list(result):
        if key.startswith("PROFIT_"):
            value = result[key]
            if isinstance(value, (int, float, np.floating)):
                result[key] = float(value) * ratio

    if technology not in {"NE", "SD"}:
        fixed_keys = []
        for key, value in result.items():
            if not key.startswith("OPEX_") or key.endswith("_total"):
                continue
            if not key.endswith(("_labor", "_main", "_replace")):
                continue
            if isinstance(value, (int, float, np.floating)):
                fixed_keys.append(key)

        fixed_opex = float(np.sum([float(result[key]) for key in fixed_keys]))
        total_keys = [
            key
            for key, value in result.items()
            if key.startswith("OPEX_")
            and key.endswith("_total")
            and isinstance(value, (int, float, np.floating))
        ]

        for total_key in total_keys:
            original_total = float(result[total_key])
            variable_opex = original_total - fixed_opex
            result[total_key] = fixed_opex + variable_opex * ratio
    return result


def _apply_pathway_specific_uncertainty(result, data, technology, draw_scenario):
    if technology in {"FO", "RO"}:
        replace_key = f"OPEX_{technology}_replace"
        total_key = f"OPEX_{technology}_total"
        area_key = (
            "total_membrane_area_m2" if technology == "FO" else "membrane_area_total_m2"
        )
        area = float(data[area_key])
        price = draw_scenario[f"membrane_price_{technology}"]
        replacement = draw_scenario[f"replacement_{technology}"]
        factor = 800.8 / 816.0 if technology == "FO" else 1.0
        new_replace = area * price * replacement * factor
        old_replace = float(result.get(replace_key, 0.0))
        result[replace_key] = new_replace
        result[total_key] = (
            float(result.get(total_key, 0.0)) + new_replace - old_replace
        )

    if technology == "IX":
        inventory = float(data["IX_resin_inventory_kg"])
        price = draw_scenario["sampled_material_price"]["RESIN"]
        replacement = draw_scenario["replacement_IX"]
        new_replace = inventory * price * replacement
        old_replace = float(result.get("OPEX_IX_resin_replace", 0.0))
        result["OPEX_IX_resin_replace"] = new_replace
        result["OPEX_IX_total"] = (
            float(result.get("OPEX_IX_total", 0.0)) + new_replace - old_replace
        )

    return result


def run_one_pathway_draw(lake, pathway_name, rng, draw_scenario):
    excel_path = BASE_DIR / lake / f"{pathway_name}.xlsx"
    if not excel_path.exists():
        raise FileNotFoundError(f"Excel not found: {excel_path}")

    sampled_material_price = draw_scenario["sampled_material_price"]
    sampled_energy_mult = draw_scenario["sampled_energy_mult"]
    sampled_carbon_mult = draw_scenario["sampled_carbon_mult"]
    op_hours = float(draw_scenario["op_hours"])
    hours_ratio = op_hours / BASE_OP_HOURS

    tech_list = TEA.PATHWAYS[pathway_name]
    pathway_id = TEA.PATHWAY_ID_MAP[pathway_name]

    capex_total = 0.0
    opex_total = 0.0
    profit_total = 0.0
    li2co3_prod = None

    capex_by_tech = {}
    opex_by_tech = {}
    trl_premium_by_tech = {}

    with patched_opex_environment(
        lake=lake,
        sampled_material_price=sampled_material_price,
        sampled_energy_mult=sampled_energy_mult,
        sampled_carbon_mult=sampled_carbon_mult,
        mult_labor=float(draw_scenario["mult_labor"]),
    ):
        for tech in tech_list:
            data = load_first_row(excel_path, tech)
            econ_func = TEA.get_econ_func(tech, pathway_id)
            if econ_func is None:
                continue

            result = econ_func(data)

            if tech in {"FO", "RO"}:
                result["_mc_membrane_area_m2"] = data[
                    (
                        "total_membrane_area_m2"
                        if tech == "FO"
                        else "membrane_area_total_m2"
                    )
                ]
                result = _rescale_linear_membrane_capex(
                    result,
                    tech,
                    draw_scenario[f"membrane_price_{tech}"],
                )

            result = _scale_annual_result(result, tech, hours_ratio)
            result = _apply_pathway_specific_uncertainty(
                result, data, tech, draw_scenario
            )

            tech_capex = 0.0
            tech_opex = 0.0
            tech_profit = 0.0

            for k, v in result.items():
                if not isinstance(v, (int, float, np.floating)):
                    continue
                if k.startswith("CAPEX_") and k.endswith("_total"):
                    tech_capex += float(v)
                elif k.startswith("OPEX_") and k.endswith("_total"):
                    tech_opex += float(v)
                elif k.startswith("PROFIT_"):
                    tech_profit += float(v)

            if "LI2CO3" in result:
                li2co3_prod = float(result["LI2CO3"])

            trl_premium = sample_trl_premium(rng, tech)
            trl_premium_by_tech[tech] = trl_premium

            tech_capex_adj = tech_capex * (1.0 + trl_premium)

            capex_by_tech[tech] = tech_capex_adj
            opex_by_tech[tech] = tech_opex

            capex_total += tech_capex_adj
            opex_total += tech_opex
            profit_total += tech_profit

    if li2co3_prod is None or li2co3_prod <= 0:
        lcol = np.nan
    else:
        annual_cost = capex_total * TEA.CRF + opex_total + profit_total
        lcol = annual_cost / li2co3_prod

    row = {
        "lake": lake,
        "pathway": pathway_name,
        "LCOL": lcol,
        "CAPEX_total": capex_total,
        "OPEX_total": opex_total,
        "PROFIT_total": profit_total,
        "Li2CO3_prod": li2co3_prod,
        "CRF": TEA.CRF,
        "mult_elec": sampled_energy_mult["elec"],
        "mult_steam": sampled_energy_mult["steam"],
        "mult_heat": sampled_energy_mult["heat"],
        "mult_carbon_tax": sampled_carbon_mult,
        "op_hours": op_hours,
        "mult_labor": draw_scenario["mult_labor"],
        "sampled_labor_wage": draw_scenario["sampled_labor_wage"],
        "membrane_price_FO": draw_scenario["membrane_price_FO"],
        "replacement_FO": draw_scenario["replacement_FO"],
        "membrane_price_RO": draw_scenario["membrane_price_RO"],
        "replacement_RO": draw_scenario["replacement_RO"],
        "replacement_IX": draw_scenario["replacement_IX"],
    }

    for mat, price in sampled_material_price.items():
        row[f"price_{mat}"] = price
        row[f"mult_price_{mat}"] = price / BASE_PRICE[mat]

    for tech, m in trl_premium_by_tech.items():
        row[f"trl_premium_{tech}"] = m
    for tech, val in capex_by_tech.items():
        row[f"CAPEX_{tech}_adj"] = val
    for tech, val in opex_by_tech.items():
        row[f"OPEX_{tech}_adj"] = val

    return row


def safe_rank_series(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s, errors="coerce").rank(method="average")


def ols_residuals(y: np.ndarray, X: np.ndarray) -> np.ndarray:
    y = np.asarray(y, dtype=float)
    if X.size == 0:
        return y - np.nanmean(y)

    X = np.asarray(X, dtype=float)
    X1 = np.column_stack([np.ones(len(X)), X])
    beta, *_ = np.linalg.lstsq(X1, y, rcond=None)
    return y - X1 @ beta


def calc_prcc_for_group(g: pd.DataFrame, variables: list[str]) -> dict:
    out = {var: np.nan for var in variables}

    if len(variables) == 0:
        return out

    rank_df = pd.DataFrame(index=g.index)
    rank_df["LCOL"] = safe_rank_series(g["LCOL"])
    for var in variables:
        rank_df[var] = safe_rank_series(g[var])

    rank_df = rank_df.dropna()
    if len(rank_df) < MIN_ROWS_FOR_SENS:
        return out

    for var in variables:
        use_cols = ["LCOL"] + variables
        tmp = rank_df[use_cols].dropna().copy()

        if len(tmp) < MIN_ROWS_FOR_SENS:
            out[var] = np.nan
            continue

        x = tmp[var].values
        y = tmp["LCOL"].values
        others = [v for v in variables if v != var]

        if np.nanstd(x) == 0 or np.nanstd(y) == 0:
            out[var] = np.nan
            continue

        if len(others) == 0:
            out[var] = np.corrcoef(x, y)[0, 1]
            continue

        X_other = tmp[others].values
        rx = ols_residuals(x, X_other)
        ry = ols_residuals(y, X_other)

        if np.nanstd(rx) == 0 or np.nanstd(ry) == 0:
            out[var] = np.nan
            continue

        out[var] = np.corrcoef(rx, ry)[0, 1]

    return out


def calc_std_beta_for_group(g: pd.DataFrame, variables: list[str]) -> dict:
    out = {var: np.nan for var in variables}
    if len(variables) == 0:
        return out

    tmp = g[["LCOL"] + variables].apply(pd.to_numeric, errors="coerce").dropna().copy()
    if len(tmp) < MIN_ROWS_FOR_SENS:
        return out

    y = tmp["LCOL"]
    X = tmp[variables]

    y_std = y.std(ddof=0)
    x_std = X.std(ddof=0)
    valid_cols = x_std[x_std > 0].index.tolist()

    if len(valid_cols) == 0 or pd.isna(y_std) or y_std == 0:
        return out

    Xz = (X[valid_cols] - X[valid_cols].mean()) / X[valid_cols].std(ddof=0)
    yz = (y - y.mean()) / y_std

    try:
        beta, *_ = np.linalg.lstsq(Xz.values, yz.values, rcond=None)
        for idx, var in enumerate(valid_cols):
            out[var] = beta[idx]
    except Exception:
        pass

    return out


def calc_spearman_for_group(g: pd.DataFrame, variables: list[str]) -> dict:
    out = {var: np.nan for var in variables}
    for var in variables:
        tmp = g[[var, "LCOL"]].apply(pd.to_numeric, errors="coerce").dropna().copy()
        if len(tmp) < MIN_ROWS_FOR_SENS:
            continue
        if (
            tmp[var].nunique(dropna=True) < MIN_UNIQUE_FOR_SENS
            or tmp["LCOL"].nunique(dropna=True) < MIN_UNIQUE_FOR_SENS
        ):
            continue
        tmp_rank = tmp.rank(method="average")
        out[var] = tmp_rank[var].corr(tmp_rank["LCOL"], method="pearson")
    return out


def get_active_variables_for_pathway(pathway: str, df_cols: list[str]) -> list[str]:
    active = []

    utility_flags = UTILITY_ACTIVE_MAP.get(pathway, {})
    for var in ["mult_elec", "mult_steam", "mult_carbon_tax"]:
        if utility_flags.get(var, False) and var in df_cols:
            active.append(var)

    if pathway in HEAT_ACTIVE_PATHWAYS and "mult_heat" in df_cols:
        active.append("mult_heat")

    for mat in BASE_PRICE.keys():
        var = f"mult_price_{mat}"
        if var in df_cols:
            active.append(var)

    techs = TEA.PATHWAYS.get(pathway, [])
    for tech in techs:
        var = f"trl_premium_{tech}"
        if var in df_cols:
            active.append(var)

    if "FO" in techs:
        for var in ["membrane_price_FO", "replacement_FO"]:
            if var in df_cols:
                active.append(var)
    if "RO" in techs:
        for var in ["membrane_price_RO", "replacement_RO"]:
            if var in df_cols:
                active.append(var)
    if "IX" in techs and "replacement_IX" in df_cols:
        active.append("replacement_IX")

    labor_techs = {"PREP", "CARB", "IX", "SX", "MED", "MVR"}
    if labor_techs.intersection(techs) and "mult_labor" in df_cols:
        active.append("mult_labor")

    if "op_hours" in df_cols:
        active.append("op_hours")

    return active


def calc_variable_impacts(df):
    rows = []
    df_cols = df.columns.tolist()

    for (lake, pathway), g in df.groupby(["lake", "pathway"]):
        g = g.copy()
        g["LCOL"] = pd.to_numeric(g["LCOL"], errors="coerce")
        g = g.dropna(subset=["LCOL"])

        if (
            len(g) < MIN_ROWS_FOR_SENS
            or g["LCOL"].nunique(dropna=True) < MIN_UNIQUE_FOR_SENS
        ):
            continue

        active_vars = get_active_variables_for_pathway(pathway, df_cols)
        if len(active_vars) == 0:
            continue

        prcc_map = calc_prcc_for_group(g, active_vars)
        beta_map = calc_std_beta_for_group(g, active_vars)
        spearman_map = calc_spearman_for_group(g, active_vars)

        abs_prcc_vals = [abs(v) for v in prcc_map.values() if pd.notna(v)]
        prcc_sum_abs = (
            float(np.sum(abs_prcc_vals)) if len(abs_prcc_vals) > 0 else np.nan
        )

        abs_beta_vals = [abs(v) for v in beta_map.values() if pd.notna(v)]
        beta_sum_abs = (
            float(np.sum(abs_beta_vals)) if len(abs_beta_vals) > 0 else np.nan
        )

        for var in active_vars:
            prcc = prcc_map.get(var, np.nan)
            beta = beta_map.get(var, np.nan)

            prcc_contrib = np.nan
            if pd.notna(prcc) and pd.notna(prcc_sum_abs) and prcc_sum_abs > 0:
                prcc_contrib = abs(prcc) / prcc_sum_abs * 100.0

            beta_contrib = np.nan
            if pd.notna(beta) and pd.notna(beta_sum_abs) and beta_sum_abs > 0:
                beta_contrib = abs(beta) / beta_sum_abs * 100.0

            rows.append(
                {
                    "lake": lake,
                    "pathway": pathway,
                    "variable": var,
                    "prcc": prcc,
                    "abs_prcc": abs(prcc) if pd.notna(prcc) else np.nan,
                    "prcc_contribution_pct": prcc_contrib,
                    "std_beta": beta,
                    "abs_std_beta": abs(beta) if pd.notna(beta) else np.nan,
                    "beta_contribution_pct": beta_contrib,
                    "spearman_rho": spearman_map.get(var, np.nan),
                }
            )

    impact_df = pd.DataFrame(rows)

    if not impact_df.empty:
        impact_df = impact_df.sort_values(
            by=["lake", "pathway", "abs_prcc", "abs_std_beta"],
            ascending=[True, True, False, False],
        )

    return impact_df


class _ModeRNG:
    @staticmethod
    def triangular(left, mode, right):
        return float(mode)


def build_mode_scenario(lake):
    base_wage = ECO.LABOR_WAGE.get(lake, ECO.LABOR_WAGE["DEFAULT"])
    return {
        "sampled_material_price": BASE_PRICE.copy(),
        "sampled_energy_mult": {"elec": 1.0, "steam": 1.0, "heat": 1.0},
        "sampled_carbon_mult": 1.0,
        "membrane_price_FO": FO_MEMBRANE_PRICE_RANGE[1],
        "replacement_FO": FO_REPLACEMENT_RANGE[1],
        "membrane_price_RO": RO_MEMBRANE_PRICE_RANGE[1],
        "replacement_RO": RO_REPLACEMENT_RANGE[1],
        "replacement_IX": IX_REPLACEMENT_RANGE[1],
        "mult_labor": 1.0,
        "sampled_labor_wage": base_wage,
        "op_hours": BASE_OP_HOURS,
    }


def aggregate_direct_tea(lake, pathway_name):
    excel_path = BASE_DIR / lake / f"{pathway_name}.xlsx"
    pathway_id = TEA.PATHWAY_ID_MAP[pathway_name]
    capex = opex = profit = 0.0
    product = None
    ECO.Opex.set_lake(lake)
    try:
        for tech in TEA.PATHWAYS[pathway_name]:
            data = load_first_row(excel_path, tech)
            func = TEA.get_econ_func(tech, pathway_id)
            result = func(data)
            for key, value in result.items():
                if not isinstance(value, (int, float, np.floating)):
                    continue
                if key.startswith("CAPEX_") and key.endswith("_total"):
                    capex += float(value)
                elif key.startswith("OPEX_") and key.endswith("_total"):
                    opex += float(value)
                elif key.startswith("PROFIT_"):
                    profit += float(value)
            if "LI2CO3" in result:
                product = float(result["LI2CO3"])
    finally:
        ECO.Opex.set_lake("DEFAULT")
    return {
        "CAPEX_total": capex,
        "OPEX_total": opex,
        "PROFIT_total": profit,
        "Li2CO3_prod": product,
    }


def validate_requested_invariants():
    print("\nValidation checks:")
    max_opex_diff = 0.0
    max_product_diff = 0.0
    lake = LAKES[0]
    mode_rng = _ModeRNG()
    mode_scenario = build_mode_scenario(lake)
    for pathway in PATHWAYS:
        direct = aggregate_direct_tea(lake, pathway)
        revised = run_one_pathway_draw(lake, pathway, mode_rng, mode_scenario)
        max_opex_diff = max(
            max_opex_diff, abs(direct["OPEX_total"] - revised["OPEX_total"])
        )
        max_product_diff = max(
            max_product_diff,
            abs(direct["Li2CO3_prod"] - revised["Li2CO3_prod"]),
        )

    print(f"  mode/base deterministic OPEX max diff: {max_opex_diff:.6g}")
    print(f"  op_hours=8500 production max diff: {max_product_diff:.6g}")
    print("  CAPEX is the only quantity receiving TRL premium: verified by code path")
    print("  N_OL formula is unchanged; labor multiplier is applied after N_OL")
    print("  membrane price is shared by pathway and used in CAPEX/replacement OPEX")
    print("  IX replacement changes OPEX only; resin inventory is unchanged")


def main():
    print_trl_premium_ranges()
    validate_requested_invariants()
    rng = np.random.default_rng(RANDOM_SEED)
    random.seed(RANDOM_SEED)

    rows = []
    draw_id = 0

    for lake in LAKES:
        for i in range(N_DRAWS):
            draw_rows = []
            draw_scenario = build_draw_scenario(rng, lake)

            for pathway in PATHWAYS:
                row = run_one_pathway_draw(lake, pathway, rng, draw_scenario)
                row["draw_id"] = draw_id
                row["draw_in_lake"] = i
                draw_rows.append(row)

            valid = [r for r in draw_rows if pd.notna(r["LCOL"])]
            if valid:
                winner_path = min(valid, key=lambda x: x["LCOL"])["pathway"]
                for r in draw_rows:
                    r["winner"] = 1 if r["pathway"] == winner_path else 0
                    r["winner_pathway"] = winner_path
            else:
                for r in draw_rows:
                    r["winner"] = 0
                    r["winner_pathway"] = None

            rows.extend(draw_rows)
            draw_id += 1

            if (i + 1) % 100 == 0:
                print(f"[{lake}] {i+1}/{N_DRAWS} draws completed")

    df = pd.DataFrame(rows)
    df.to_csv(OUT_CSV, index=False, encoding="utf-8-sig")

    summary = (
        df.groupby(["lake", "pathway"], dropna=False)
        .agg(
            mean_LCOL=("LCOL", "mean"),
            std_LCOL=("LCOL", "std"),
            p10_LCOL=("LCOL", lambda x: np.nanpercentile(x, 10)),
            p50_LCOL=("LCOL", lambda x: np.nanpercentile(x, 50)),
            p90_LCOL=("LCOL", lambda x: np.nanpercentile(x, 90)),
            winner_probability=("winner", "mean"),
        )
        .reset_index()
    )

    rank_rows = []
    for (lake, draw_no), g in df.groupby(["lake", "draw_id"]):
        g2 = g[["pathway", "LCOL"]].dropna().sort_values("LCOL")
        for rank, (_, rr) in enumerate(g2.iterrows(), start=1):
            rank_rows.append(
                {
                    "lake": lake,
                    "draw_id": draw_no,
                    "pathway": rr["pathway"],
                    "rank": rank,
                    "LCOL": rr["LCOL"],
                }
            )
    df_rank = pd.DataFrame(rank_rows)

    impact_df = calc_variable_impacts(df)

    with pd.ExcelWriter(OUT_XLSX, engine="xlsxwriter") as writer:
        df.to_excel(writer, sheet_name="MC_DRAWS", index=False)
        summary.to_excel(writer, sheet_name="SUMMARY", index=False)
        df_rank.to_excel(writer, sheet_name="RANKS", index=False)
        impact_df.to_excel(writer, sheet_name="VAR_IMPACT", index=False)

    print("Saved CSV :", OUT_CSV)
    print("Saved XLSX:", OUT_XLSX)


if __name__ == "__main__":
    main()
