from __future__ import annotations

from typing import Dict

YEARS = (2020, 2030, 2040, 2050)

REGION_TO_LAKE = {
    "USA_GSL": "GSL",
    "Chile_Atacama": "Atacama",
    "Bolivia_Uyuni": "Uyuni",
    "China_Zabuye": "Zabuye",
}
LAKE_TO_REGION = {lake: region for region, lake in REGION_TO_LAKE.items()}


HEAT_PRICE_USD_PER_MJ: Dict[str, Dict[int, float]] = {
    "USA_GSL": {2020: 0.00608, 2030: 0.00886, 2040: 0.01106, 2050: 0.01331},
    "Chile_Atacama": {2020: 0.00939, 2030: 0.01364, 2040: 0.01706, 2050: 0.02044},
    "Bolivia_Uyuni": {2020: 0.00939, 2030: 0.01364, 2040: 0.01706, 2050: 0.02044},
    "China_Zabuye": {2020: 0.00703, 2030: 0.01022, 2040: 0.01281, 2050: 0.01533},
}


def get_heat_price(region_or_lake: str, year: int) -> float:
    region = LAKE_TO_REGION.get(region_or_lake, region_or_lake)
    if region not in HEAT_PRICE_USD_PER_MJ:
        valid = ", ".join(sorted((*HEAT_PRICE_USD_PER_MJ, *LAKE_TO_REGION)))
        raise KeyError(f"Unknown region/lake {region_or_lake!r}. Valid keys: {valid}")
    if year not in YEARS:
        raise KeyError(f"Unsupported year {year}. Valid years: {YEARS}")
    return HEAT_PRICE_USD_PER_MJ[region][year]


def validate_heat_price_mapping() -> None:
    for region, values in HEAT_PRICE_USD_PER_MJ.items():
        if set(values) != set(YEARS):
            raise ValueError(f"Incomplete heat-price years for {region}: {values}")
        if any(value < 0 for value in values.values()):
            raise ValueError(f"Negative heat price found for {region}: {values}")


if __name__ == "__main__":
    validate_heat_price_mapping()
    print("External heat-price mapping (USD/MJ-heat)")
    for region, lake in REGION_TO_LAKE.items():
        values = ", ".join(
            f"{year}: {get_heat_price(region, year):.4f}" for year in YEARS
        )
        print(f"{region} ({lake}) | {values}")
