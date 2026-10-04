from __future__ import annotations

import math
from typing import Dict

YEARS = (2020, 2030, 2040, 2050)
MJ_PER_KWH = 3.6
ELECTRIC_HEATER_EFFICIENCY = 0.99

REGION_TO_LAKE = {
    "USA_GSL": "GSL",
    "Chile_Atacama": "Atacama",
    "Bolivia_Uyuni": "Uyuni",
    "China_Zabuye": "Zabuye",
}
LAKE_TO_REGION = {lake: region for region, lake in REGION_TO_LAKE.items()}

ELECTRICITY_PRICE_USD_PER_KWH: Dict[str, Dict[int, float]] = {
    "USA_GSL": {2020: 0.0832, 2030: 0.1210, 2040: 0.1513, 2050: 0.1815},
    "Chile_Atacama": {2020: 0.2100, 2030: 0.3055, 2040: 0.3818, 2050: 0.4582},
    "Bolivia_Uyuni": {2020: 0.1224, 2030: 0.1780, 2040: 0.2225, 2050: 0.2671},
    "China_Zabuye": {2020: 0.0800, 2030: 0.1164, 2040: 0.1455, 2050: 0.1745},
}


def get_electricity_price(region_or_lake: str, year: int) -> float:
    region = LAKE_TO_REGION.get(region_or_lake, region_or_lake)
    if region not in ELECTRICITY_PRICE_USD_PER_KWH:
        valid = ", ".join(sorted((*ELECTRICITY_PRICE_USD_PER_KWH, *LAKE_TO_REGION)))
        raise KeyError(f"Unknown region/lake {region_or_lake!r}. Valid keys: {valid}")
    if year not in YEARS:
        raise KeyError(f"Unsupported year {year}. Valid years: {YEARS}")
    return ELECTRICITY_PRICE_USD_PER_KWH[region][year]


def heat_price_from_electricity_price(electricity_price_usd_per_kwh: float) -> float:
    price = float(electricity_price_usd_per_kwh)
    if not math.isfinite(price) or price < 0:
        raise ValueError(f"Electricity price must be finite and non-negative: {price}")
    return price / (MJ_PER_KWH * ELECTRIC_HEATER_EFFICIENCY)


def heater_electricity_kwh(external_heat_mj: float) -> float:
    heat_mj = float(external_heat_mj)
    if not math.isfinite(heat_mj) or heat_mj < 0:
        raise ValueError(f"External heat duty must be finite and non-negative: {heat_mj}")
    return heat_mj / (MJ_PER_KWH * ELECTRIC_HEATER_EFFICIENCY)


def get_heat_price(region_or_lake: str, year: int) -> float:
    return heat_price_from_electricity_price(get_electricity_price(region_or_lake, year))


def validate_heat_price_mapping() -> None:
    for region, values in ELECTRICITY_PRICE_USD_PER_KWH.items():
        if set(values) != set(YEARS):
            raise ValueError(f"Incomplete electricity-price years for {region}: {values}")
        if any(value < 0 for value in values.values()):
            raise ValueError(f"Negative electricity price found for {region}: {values}")


if __name__ == "__main__":
    validate_heat_price_mapping()
    print("Electric-heater heat prices (USD/MJ_th), efficiency=0.99")
    for region, lake in REGION_TO_LAKE.items():
        values = ", ".join(f"{year}: {get_heat_price(region, year):.5f}" for year in YEARS)
        print(f"{region} ({lake}) | {values}")
