from __future__ import annotations

import os
from dataclasses import dataclass
from contextlib import contextmanager
from typing import Dict, List, Optional, Tuple, Any

import pandas as pd
import numpy as np

import TEA
import Economic as ECO
from Economic import Opex
from heat_price_mapping import (
    ELECTRIC_HEATER_EFFICIENCY,
    heat_price_from_electricity_price,
    heater_electricity_kwh,
)
from project_paths import EXCEL_DIR, SCENARIO_DIR

BASE_DIR = str(EXCEL_DIR)
OUT_DIR = str(SCENARIO_DIR)
os.makedirs(OUT_DIR, exist_ok=True)

DISCOUNT_RATE = 0.07
PLANT_LIFE = 20
CRF = (
    DISCOUNT_RATE
    * (1 + DISCOUNT_RATE) ** PLANT_LIFE
    / ((1 + DISCOUNT_RATE) ** PLANT_LIFE - 1)
)
YEARS = [2020, 2030, 2040, 2050]

COUNTRY_TO_LAKE = {
    "USA": "GSL",
    "Chile": "Atacama",
    "Bolivia": "Uyuni",
    "China": "Zabuye",
}
LAKE_TO_COUNTRY = {v: k for k, v in COUNTRY_TO_LAKE.items()}


GRID_GROWTH = {
    2020: 11 / 11,
    2030: 16 / 11,
    2040: 20 / 11,
    2050: 24 / 11,
}
SOLAR_MULT = {
    2020: 1.0,
    2030: ((0.08 + 0.02) / 2) / 0.085,
    2040: ((((0.08 + 0.02) / 2) + ((0.05 + 0.01) / 2)) / 2) / 0.085,
    2050: ((0.05 + 0.01) / 2) / 0.085,
}

WIND_MULT = {
    2020: 1.0,
    2030: ((0.03 + 0.05) / 2) / 0.06,
    2040: ((((0.03 + 0.05) / 2) + ((0.02 + 0.03) / 2)) / 2) / 0.06,
    2050: ((0.02 + 0.03) / 2) / 0.06,
}


CARBON_MULT_EAST_ASIA = {
    2020: 1.0,
    2030: 23 / 10,
    2040: 42 / 10,
    2050: 70 / 10,
}

CARBON_MULT_LAC = {
    2020: 1.0,
    2030: 23 / 10,
    2040: 42 / 10,
    2050: 70 / 10,
}

BOLIVIA_CARBON_TAX = {
    2020: 0.0,
    2030: 5.0,
    2040: 10.0,
    2050: 23.0,
}

CARBON_MULT_WORLD = {
    2020: 1.0,
    2030: ((23 + 38) / 2) / ((10 + 24) / 2),
    2040: ((50 + 60) / 2) / ((10 + 24) / 2),
    2050: 75 / ((10 + 24) / 2),
}


def scale_grid(lake: str, year: int) -> float:
    return ECO.COUNTRY_PARAM[lake]["elec_base"] * GRID_GROWTH[year]


def scale_carbon(lake: str, year: int, mult_map: dict) -> float:
    return ECO.COUNTRY_PARAM[lake]["carbon_tax"] * mult_map[year]


def scale_steam(lake: str, year: int) -> float:
    return ECO.COUNTRY_PARAM[lake]["steam_base"] * GRID_GROWTH[year]


ENERGY_PRICE_DB: Dict[str, Dict[int, Dict[str, Any]]] = {
    "GSL": {
        2020: {
            "electricity": {
                "grid": scale_grid("GSL", 2020),
                "onshore_wind": 0.035,
                "solar_pv": 0.050,
            },
            "steam": {"base": scale_steam("GSL", 2020)},
            "carbon_tax": scale_carbon("GSL", 2020, CARBON_MULT_WORLD),
            "elec_ef": ECO.COUNTRY_PARAM["GSL"]["elec_ef"],
            "steam_ef": ECO.COUNTRY_PARAM["GSL"]["steam_ef"],
        },
        2030: {
            "electricity": {
                "grid": scale_grid("GSL", 2030),
                "onshore_wind": 0.035,
                "solar_pv": 0.030,
            },
            "steam": {"base": scale_steam("GSL", 2030)},
            "carbon_tax": scale_carbon("GSL", 2030, CARBON_MULT_WORLD),
            "elec_ef": ECO.COUNTRY_PARAM["GSL"]["elec_ef"],
            "steam_ef": ECO.COUNTRY_PARAM["GSL"]["steam_ef"],
        },
        2040: {
            "electricity": {
                "grid": scale_grid("GSL", 2040),
                "onshore_wind": (0.035 + 0.030) / 2,
                "solar_pv": (0.030 + 0.020) / 2,
            },
            "steam": {"base": scale_steam("GSL", 2040)},
            "carbon_tax": scale_carbon("GSL", 2040, CARBON_MULT_WORLD),
            "elec_ef": ECO.COUNTRY_PARAM["GSL"]["elec_ef"],
            "steam_ef": ECO.COUNTRY_PARAM["GSL"]["steam_ef"],
        },
        2050: {
            "electricity": {
                "grid": scale_grid("GSL", 2050),
                "onshore_wind": 0.030,
                "solar_pv": 0.020,
            },
            "steam": {"base": scale_steam("GSL", 2050)},
            "carbon_tax": scale_carbon("GSL", 2050, CARBON_MULT_WORLD),
            "elec_ef": ECO.COUNTRY_PARAM["GSL"]["elec_ef"],
            "steam_ef": ECO.COUNTRY_PARAM["GSL"]["steam_ef"],
        },
    },
    "Atacama": {
        2020: {
            "electricity": {
                "grid": scale_grid("Atacama", 2020),
                "onshore_wind": 0.060,
                "solar_pv": 0.110,
            },
            "steam": {"base": scale_steam("Atacama", 2020)},
            "carbon_tax": scale_carbon("Atacama", 2020, CARBON_MULT_LAC),
            "elec_ef": ECO.COUNTRY_PARAM["Atacama"]["elec_ef"],
            "steam_ef": ECO.COUNTRY_PARAM["Atacama"]["steam_ef"],
        },
        2030: {
            "electricity": {
                "grid": scale_grid("Atacama", 2030),
                "onshore_wind": 0.060 * WIND_MULT[2030],
                "solar_pv": 0.110 * SOLAR_MULT[2030],
            },
            "steam": {"base": scale_steam("Atacama", 2030)},
            "carbon_tax": scale_carbon("Atacama", 2030, CARBON_MULT_LAC),
            "elec_ef": ECO.COUNTRY_PARAM["Atacama"]["elec_ef"],
            "steam_ef": ECO.COUNTRY_PARAM["Atacama"]["steam_ef"],
        },
        2040: {
            "electricity": {
                "grid": scale_grid("Atacama", 2040),
                "onshore_wind": 0.060 * WIND_MULT[2040],
                "solar_pv": 0.110 * SOLAR_MULT[2040],
            },
            "steam": {"base": scale_steam("Atacama", 2040)},
            "carbon_tax": scale_carbon("Atacama", 2040, CARBON_MULT_LAC),
            "elec_ef": ECO.COUNTRY_PARAM["Atacama"]["elec_ef"],
            "steam_ef": ECO.COUNTRY_PARAM["Atacama"]["steam_ef"],
        },
        2050: {
            "electricity": {
                "grid": scale_grid("Atacama", 2050),
                "onshore_wind": 0.060 * WIND_MULT[2050],
                "solar_pv": 0.110 * SOLAR_MULT[2050],
            },
            "steam": {"base": scale_steam("Atacama", 2050)},
            "carbon_tax": scale_carbon("Atacama", 2050, CARBON_MULT_LAC),
            "elec_ef": ECO.COUNTRY_PARAM["Atacama"]["elec_ef"],
            "steam_ef": ECO.COUNTRY_PARAM["Atacama"]["steam_ef"],
        },
    },
    "Uyuni": {
        2020: {
            "electricity": {
                "grid": scale_grid("Uyuni", 2020),
                "onshore_wind": 0.060,
                "solar_pv": 0.110,
            },
            "steam": {"base": scale_steam("Uyuni", 2020)},
            "carbon_tax": BOLIVIA_CARBON_TAX[2020],
            "elec_ef": ECO.COUNTRY_PARAM["Uyuni"]["elec_ef"],
            "steam_ef": ECO.COUNTRY_PARAM["Uyuni"]["steam_ef"],
        },
        2030: {
            "electricity": {
                "grid": scale_grid("Uyuni", 2030),
                "onshore_wind": 0.060 * WIND_MULT[2030],
                "solar_pv": 0.110 * SOLAR_MULT[2030],
            },
            "steam": {"base": scale_steam("Uyuni", 2030)},
            "carbon_tax": BOLIVIA_CARBON_TAX[2030],
            "elec_ef": ECO.COUNTRY_PARAM["Uyuni"]["elec_ef"],
            "steam_ef": ECO.COUNTRY_PARAM["Uyuni"]["steam_ef"],
        },
        2040: {
            "electricity": {
                "grid": scale_grid("Uyuni", 2040),
                "onshore_wind": 0.060 * WIND_MULT[2040],
                "solar_pv": 0.110 * SOLAR_MULT[2040],
            },
            "steam": {"base": scale_steam("Uyuni", 2040)},
            "carbon_tax": BOLIVIA_CARBON_TAX[2040],
            "elec_ef": ECO.COUNTRY_PARAM["Uyuni"]["elec_ef"],
            "steam_ef": ECO.COUNTRY_PARAM["Uyuni"]["steam_ef"],
        },
        2050: {
            "electricity": {
                "grid": scale_grid("Uyuni", 2050),
                "onshore_wind": 0.060 * WIND_MULT[2050],
                "solar_pv": 0.110 * SOLAR_MULT[2050],
            },
            "steam": {"base": scale_steam("Uyuni", 2050)},
            "carbon_tax": BOLIVIA_CARBON_TAX[2050],
            "elec_ef": ECO.COUNTRY_PARAM["Uyuni"]["elec_ef"],
            "steam_ef": ECO.COUNTRY_PARAM["Uyuni"]["steam_ef"],
        },
    },
    "Zabuye": {
        2020: {
            "electricity": {
                "grid": scale_grid("Zabuye", 2020),
                "onshore_wind": 0.045,
                "solar_pv": 0.040,
            },
            "steam": {"base": scale_steam("Zabuye", 2020)},
            "carbon_tax": scale_carbon("Zabuye", 2020, CARBON_MULT_EAST_ASIA),
            "elec_ef": ECO.COUNTRY_PARAM["Zabuye"]["elec_ef"],
            "steam_ef": ECO.COUNTRY_PARAM["Zabuye"]["steam_ef"],
        },
        2030: {
            "electricity": {
                "grid": scale_grid("Zabuye", 2030),
                "onshore_wind": 0.040,
                "solar_pv": 0.025,
            },
            "steam": {"base": scale_steam("Zabuye", 2030)},
            "carbon_tax": scale_carbon("Zabuye", 2030, CARBON_MULT_EAST_ASIA),
            "elec_ef": ECO.COUNTRY_PARAM["Zabuye"]["elec_ef"],
            "steam_ef": ECO.COUNTRY_PARAM["Zabuye"]["steam_ef"],
        },
        2040: {
            "electricity": {
                "grid": scale_grid("Zabuye", 2040),
                "onshore_wind": (0.040 + 0.040) / 2,
                "solar_pv": (0.025 + 0.015) / 2,
            },
            "steam": {"base": scale_steam("Zabuye", 2040)},
            "carbon_tax": scale_carbon("Zabuye", 2040, CARBON_MULT_EAST_ASIA),
            "elec_ef": ECO.COUNTRY_PARAM["Zabuye"]["elec_ef"],
            "steam_ef": ECO.COUNTRY_PARAM["Zabuye"]["steam_ef"],
        },
        2050: {
            "electricity": {
                "grid": scale_grid("Zabuye", 2050),
                "onshore_wind": 0.040,
                "solar_pv": 0.015,
            },
            "steam": {"base": scale_steam("Zabuye", 2050)},
            "carbon_tax": scale_carbon("Zabuye", 2050, CARBON_MULT_EAST_ASIA),
            "elec_ef": ECO.COUNTRY_PARAM["Zabuye"]["elec_ef"],
            "steam_ef": ECO.COUNTRY_PARAM["Zabuye"]["steam_ef"],
        },
    },
}


ELECTRICITY_MIX_SCENARIOS: Dict[str, Dict[str, float]] = {
    "G100": {"grid": 1.0, "onshore_wind": 0.0, "solar_pv": 0.0},
    "W100": {"grid": 0.0, "onshore_wind": 1.0, "solar_pv": 0.0},
    "S100": {"grid": 0.0, "onshore_wind": 0.0, "solar_pv": 1.0},
    "MIX_80_10_10": {"grid": 0.8, "onshore_wind": 0.1, "solar_pv": 0.1},
    "MIX_60_20_20": {"grid": 0.6, "onshore_wind": 0.2, "solar_pv": 0.2},
    "MIX_50_25_25": {"grid": 0.5, "onshore_wind": 0.25, "solar_pv": 0.25},
    "MIX_40_30_30": {"grid": 0.4, "onshore_wind": 0.3, "solar_pv": 0.3},
    "MIX_20_40_40": {"grid": 0.2, "onshore_wind": 0.4, "solar_pv": 0.4},
    "MIX_00_50_50": {"grid": 0.0, "onshore_wind": 0.5, "solar_pv": 0.5},
}

TECH_TRL_DB: Dict[str, Dict[int, float]] = {
    "NE": {2020: 9.0, 2030: 9.0, 2040: 9.0, 2050: 9.0},
    "SD": {2020: 4.0, 2030: 6.0, 2040: 7.0, 2050: 8.0},
    "MED": {2020: 7.5, 2030: 8.0, 2040: 8.5, 2050: 9.0},
    "MVR": {2020: 7.5, 2030: 8.0, 2040: 8.5, 2050: 9.0},
    "RO": {2020: 8.5, 2030: 8.7, 2040: 8.9, 2050: 9.0},
    "FO": {2020: 4.5, 2030: 5.0, 2040: 6.5, 2050: 8.0},
    "IX": {2020: 7.5, 2030: 7.5, 2040: 8.0, 2050: 8.5},
    "SX": {2020: 6.5, 2030: 7.0, 2040: 8.0, 2050: 8.5},
    "PREP": {2020: 9.0, 2030: 9.0, 2040: 9.0, 2050: 9.0},
    "CARB": {2020: 9.0, 2030: 9.0, 2040: 9.0, 2050: 9.0},
}

TRL_APPLY_TO_CAPEX = True
TRL_APPLY_TO_OPEX = False

TRL_ANCHORS = {
    4.0: (0.30, 0.50, 0.70),
    5.5: (0.20, 0.275, 0.35),
    7.5: (0.05, 0.125, 0.20),
    9.0: (0.00, 0.05, 0.10),
}


@dataclass
class ScenarioSpec:
    lake: str
    year: int
    elec_mix_name: str
    pathway_name: str
    steam_case: str = "base"


def safe_value(x: Any, default: float = 0.0) -> float:
    if x is None:
        return default
    try:
        if pd.isna(x):
            return default
    except Exception:
        pass
    return float(x)


def validate_mix(mix: Dict[str, float], tol: float = 1e-9) -> None:
    s = sum(mix.values())
    if abs(s - 1.0) > tol:
        raise ValueError(f"Electricity mix sum must be 1.0, got {s}")


def blended_electricity_price(lake: str, year: int, mix_name: str) -> float:
    price_info = ENERGY_PRICE_DB[lake][year]["electricity"]
    mix = ELECTRICITY_MIX_SCENARIOS[mix_name]
    validate_mix(mix)
    return sum(mix[src] * price_info[src] for src in mix)


def blended_electricity_ef(lake: str, year: int, mix_name: str) -> float:
    db = ENERGY_PRICE_DB[lake][year]
    mix = ELECTRICITY_MIX_SCENARIOS[mix_name]
    validate_mix(mix)
    grid_ef = safe_value(db.get("elec_ef"), 0.0)
    return mix.get("grid", 0.0) * grid_ef


def get_energy_context(
    lake: str, year: int, mix_name: str, steam_case: str = "base"
) -> Dict[str, float]:
    db = ENERGY_PRICE_DB[lake][year]
    elec_price = blended_electricity_price(lake, year, mix_name)
    elec_ef = blended_electricity_ef(lake, year, mix_name)
    steam_price = safe_value(db["steam"].get(steam_case), 0.0)
    heat_price = heat_price_from_electricity_price(elec_price)

    return {
        "elec_price": elec_price,
        "steam_price": steam_price,
        "heat_price": heat_price,
        "electric_heater_efficiency": ELECTRIC_HEATER_EFFICIENCY,
        "carbon_tax": safe_value(db.get("carbon_tax"), 0.0),
        "elec_ef": elec_ef,
        "steam_ef": safe_value(db.get("steam_ef"), 0.0),
    }


def get_trl_premium_range(trl_value: float) -> Tuple[float, float, float]:
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


def interpolate_premium_from_trl(trl: float) -> float:
    return get_trl_premium_range(trl)[1]


def tech_trl_multiplier(tech_name: str, year: int) -> Tuple[float, float, float]:
    if tech_name not in TECH_TRL_DB or year not in TECH_TRL_DB[tech_name]:
        raise KeyError(f"Missing TRL trajectory for {tech_name} in {year}.")
    trl = float(TECH_TRL_DB[tech_name][year])
    gap = max(0.0, 9.0 - trl)
    premium = interpolate_premium_from_trl(trl)
    mult = 1.0 + premium
    return trl, gap, mult


def print_trl_premium_ranges() -> None:
    print("TRL-informed CAPEX premium ranges (future scenario modes):")
    for tech_name, trajectory in TECH_TRL_DB.items():
        for year, trl in trajectory.items():
            lower, mode, upper = get_trl_premium_range(trl)
            print(
                f"  {tech_name:>4s} | {year} | TRL {trl:.1f} | "
                f"({lower:.4f}, {mode:.4f}, {upper:.4f})"
            )


@contextmanager
def patched_opex_for_scenario(energy_ctx: Dict[str, float]):
    orig_elec = Opex.elec
    orig_steam = Opex.steam
    orig_heat = Opex.heat
    orig_cfe = Opex.carbon_from_elec
    orig_cfs = Opex.carbon_from_steam
    orig_cfh = Opex.carbon_from_heat

    elec_price = energy_ctx["elec_price"]
    steam_price = energy_ctx["steam_price"]
    elec_price = energy_ctx["elec_price"]
    carbon_tax = energy_ctx["carbon_tax"]
    elec_ef = energy_ctx["elec_ef"]
    steam_ef = energy_ctx["steam_ef"]

    def _elec(elec_use_kwh: float) -> float:
        return safe_value(elec_use_kwh) * elec_price

    def _steam(steam_use_kg: float) -> float:
        return safe_value(steam_use_kg) * steam_price

    def _heat(heat_use_mj: float) -> float:
        return heater_electricity_kwh(safe_value(heat_use_mj)) * elec_price

    def _carbon_from_elec(elec_use_kwh: float) -> float:
        co2_ton = safe_value(elec_use_kwh) * (elec_ef / 1000.0)
        return co2_ton * carbon_tax

    def _carbon_from_steam(steam_use_kwh: float) -> float:
        co2_ton = safe_value(steam_use_kwh) * (steam_ef / 1000.0)
        return co2_ton * carbon_tax

    def _carbon_from_heat(heat_use_mj: float) -> float:
        co2_ton = safe_value(heat_use_mj) * ECO.HEAT_CO2_FACTOR_T_PER_MJ
        return co2_ton * carbon_tax

    Opex.elec = staticmethod(_elec)
    Opex.steam = staticmethod(_steam)
    Opex.heat = staticmethod(_heat)
    Opex.carbon_from_elec = staticmethod(_carbon_from_elec)
    Opex.carbon_from_steam = staticmethod(_carbon_from_steam)
    Opex.carbon_from_heat = staticmethod(_carbon_from_heat)

    try:
        yield
    finally:
        Opex.elec = orig_elec
        Opex.steam = orig_steam
        Opex.heat = orig_heat
        Opex.carbon_from_elec = orig_cfe
        Opex.carbon_from_steam = orig_cfs
        Opex.carbon_from_heat = orig_cfh


def run_econ_for_pathway_scenario(spec: ScenarioSpec) -> Optional[Dict[str, Any]]:
    excel_path = os.path.join(BASE_DIR, spec.lake, f"{spec.pathway_name}.xlsx")
    if not os.path.exists(excel_path):
        print(f"!! Excel not found: {excel_path}")
        return None

    if spec.pathway_name not in TEA.PATHWAYS:
        print(f"!! Unknown pathway: {spec.pathway_name}")
        return None

    energy_ctx = get_energy_context(
        spec.lake, spec.year, spec.elec_mix_name, spec.steam_case
    )
    tech_list = TEA.PATHWAYS[spec.pathway_name]
    pathway_id = TEA.PATHWAY_ID_MAP[spec.pathway_name]

    capex_total = 0.0
    opex_total = 0.0
    profit_total = 0.0
    li2co3_prod = None

    capex_total_raw = 0.0
    opex_total_raw = 0.0
    tech_trl_dict: Dict[str, float] = {}
    tech_trl_gap_dict: Dict[str, float] = {}
    tech_trl_mult_dict: Dict[str, float] = {}
    tech_capex_raw_dict: Dict[str, float] = {}
    tech_capex_adj_dict: Dict[str, float] = {}
    tech_opex_raw_dict: Dict[str, float] = {}
    tech_opex_adj_dict: Dict[str, float] = {}

    Opex.set_lake(spec.lake)

    with patched_opex_for_scenario(energy_ctx):
        for tech in tech_list:
            try:
                df = pd.read_excel(excel_path, sheet_name=tech)
                data = df.iloc[0].to_dict()
            except Exception as e:
                print(f"   !! Failed to read sheet '{tech}' -> skip ({e})")
                continue

            econ_func = TEA.get_econ_func(tech, pathway_id)
            if econ_func is None:
                print(f"   !! No economic function for tech: {tech}")
                continue

            result = econ_func(data)

            tech_capex = 0.0
            tech_opex = 0.0
            tech_profit = 0.0

            for k, v in result.items():
                if k.startswith("CAPEX_") and k.endswith("_total"):
                    tech_capex += float(v)
                elif k.startswith("OPEX_") and k.endswith("_total"):
                    tech_opex += float(v)
                elif k.startswith("PROFIT_"):
                    tech_profit += float(v)

            tech_trl, tech_trl_gap, tech_trl_mult = tech_trl_multiplier(tech, spec.year)

            tech_capex_raw_dict[tech] = tech_capex
            tech_opex_raw_dict[tech] = tech_opex
            tech_trl_dict[tech] = tech_trl
            tech_trl_gap_dict[tech] = tech_trl_gap
            tech_trl_mult_dict[tech] = tech_trl_mult

            tech_capex_adj = (
                tech_capex * tech_trl_mult if TRL_APPLY_TO_CAPEX else tech_capex
            )
            tech_opex_adj = (
                tech_opex * tech_trl_mult if TRL_APPLY_TO_OPEX else tech_opex
            )

            tech_capex_adj_dict[tech] = tech_capex_adj
            tech_opex_adj_dict[tech] = tech_opex_adj

            capex_total_raw += tech_capex
            opex_total_raw += tech_opex
            capex_total += tech_capex_adj
            opex_total += tech_opex_adj
            profit_total += tech_profit

            if "LI2CO3" in result and safe_value(result["LI2CO3"]) > 0:
                li2co3_prod = safe_value(result["LI2CO3"])

    annual_cost = None
    lcol = None
    if li2co3_prod not in (None, 0):
        annual_cost = capex_total * CRF + opex_total + profit_total
        lcol = annual_cost / li2co3_prod

    mix = ELECTRICITY_MIX_SCENARIOS[spec.elec_mix_name]
    elec_src = ENERGY_PRICE_DB[spec.lake][spec.year]["electricity"]

    summary_row: Dict[str, Any] = {
        "country": LAKE_TO_COUNTRY.get(spec.lake, spec.lake),
        "lake": spec.lake,
        "year": spec.year,
        "pathway": spec.pathway_name,
        "elec_mix_name": spec.elec_mix_name,
        "grid_share": mix["grid"],
        "wind_share": mix["onshore_wind"],
        "solar_share": mix["solar_pv"],
        "price_grid": elec_src["grid"],
        "price_onshore_wind": elec_src["onshore_wind"],
        "price_solar_pv": elec_src["solar_pv"],
        "elec_price_blended": energy_ctx["elec_price"],
        "steam_case": spec.steam_case,
        "steam_price": energy_ctx["steam_price"],
        "heat_price_usd_per_mj": energy_ctx["heat_price"],
        "electric_heater_efficiency": energy_ctx["electric_heater_efficiency"],
        "carbon_tax": energy_ctx["carbon_tax"],
        "elec_ef": energy_ctx["elec_ef"],
        "steam_ef": energy_ctx["steam_ef"],
        "trl_basis": "tech-level",
        "CRF": CRF,
        "LI2CO3_prod": li2co3_prod,
        "CAPEX_total_raw": capex_total_raw,
        "OPEX_total_raw": opex_total_raw,
        "PROFIT_total": profit_total,
        "CAPEX_total_adj": capex_total,
        "OPEX_total_adj": opex_total,
        "annual_cost": annual_cost,
        "LCOL": lcol,
    }

    for tech in tech_list:
        summary_row[f"TRL_{tech}"] = tech_trl_dict.get(tech)
        summary_row[f"TRL_gap_{tech}"] = tech_trl_gap_dict.get(tech)
        summary_row[f"TRL_multiplier_{tech}"] = tech_trl_mult_dict.get(tech)
        summary_row[f"CAPEX_{tech}_raw"] = tech_capex_raw_dict.get(tech)
        summary_row[f"CAPEX_{tech}_adj"] = tech_capex_adj_dict.get(tech)
        summary_row[f"OPEX_{tech}_raw"] = tech_opex_raw_dict.get(tech)
        summary_row[f"OPEX_{tech}_adj"] = tech_opex_adj_dict.get(tech)
    return summary_row


def country_sheet_name_from_lake(lake: str) -> str:
    country = LAKE_TO_COUNTRY.get(lake, lake)
    return country[:31]


OUTPUT_COLUMNS = [
    "country",
    "lake",
    "year",
    "pathway",
    "elec_mix_name",
    "grid_share",
    "wind_share",
    "solar_share",
    "price_grid",
    "price_onshore_wind",
    "price_solar_pv",
    "elec_price_blended",
    "steam_case",
    "steam_price",
    "heat_price_usd_per_mj",
    "electric_heater_efficiency",
    "carbon_tax",
    "elec_ef",
    "steam_ef",
    "trl_basis",
    "CRF",
    "LI2CO3_prod",
    "CAPEX_total_raw",
    "OPEX_total_raw",
    "PROFIT_total",
    "CAPEX_total_adj",
    "OPEX_total_adj",
    "annual_cost",
    "LCOL",
]


def run_scenario_batch_to_country_workbook(
    pathways: Optional[List[str]] = None,
    lakes: Optional[List[str]] = None,
    years: Optional[List[int]] = None,
    elec_mix_names: Optional[List[str]] = None,
    steam_case: str = "base",
    out_tag: str = "scenario_country_sheets",
) -> pd.DataFrame:
    if pathways is None:
        pathways = list(TEA.PATHWAYS.keys())
    if lakes is None:
        lakes = list(COUNTRY_TO_LAKE.values())
    if years is None:
        years = YEARS
    if elec_mix_names is None:
        elec_mix_names = list(ELECTRICITY_MIX_SCENARIOS.keys())

    all_rows: List[Dict[str, Any]] = []

    for lake in lakes:
        for year in years:
            for mix_name in elec_mix_names:
                for pathway_name in pathways:
                    spec = ScenarioSpec(
                        lake=lake,
                        year=year,
                        elec_mix_name=mix_name,
                        pathway_name=pathway_name,
                        steam_case=steam_case,
                    )
                    row = run_econ_for_pathway_scenario(spec)
                    if row is not None:
                        all_rows.append(row)

    df = pd.DataFrame(all_rows)
    if df.empty:
        raise RuntimeError(
            "No scenario results were generated. Check excel paths and pathway names."
        )

    ordered_cols = OUTPUT_COLUMNS + [c for c in df.columns if c not in OUTPUT_COLUMNS]
    df = df[ordered_cols]
    df = df.sort_values(["country", "year", "elec_mix_name", "pathway"]).reset_index(
        drop=True
    )

    workbook_path = os.path.join(OUT_DIR, f"{out_tag}.xlsx")
    csv_path = os.path.join(OUT_DIR, f"{out_tag}.csv")

    with pd.ExcelWriter(workbook_path, engine="xlsxwriter") as writer:
        for lake in lakes:
            sub = df[df["lake"] == lake].copy()
            if sub.empty:
                continue
            sheet_name = country_sheet_name_from_lake(lake)
            sub.to_excel(writer, sheet_name=sheet_name, index=False)

        df.to_excel(writer, sheet_name="All", index=False)

    df.to_csv(csv_path, index=False, encoding="utf-8-sig")

    print(f"Saved workbook -> {workbook_path}")
    print(f"Saved csv      -> {csv_path}")
    return df


if __name__ == "__main__":
    print_trl_premium_ranges()
    selected_pathways = [
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

    selected_mixes = [
        "G100",
        "W100",
        "S100",
        "MIX_80_10_10",
        "MIX_60_20_20",
        "MIX_50_25_25",
        "MIX_40_30_30",
        "MIX_20_40_40",
        "MIX_00_50_50",
    ]

    run_scenario_batch_to_country_workbook(
        pathways=selected_pathways,
        lakes=["Atacama", "Uyuni", "Zabuye", "GSL"],
        years=[2020, 2030, 2040, 2050],
        elec_mix_names=selected_mixes,
        steam_case="base",
        out_tag="tea_energy_mix_trl_country_sheets",
    )
