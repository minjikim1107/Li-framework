import os
import pandas as pd
from project_paths import (
    EXCEL_DIR,
    TEA_CODE_DIR as _TEA_CODE_DIR,
    TEA_ANALYSIS_DIR,
    ensure_output_dirs,
)
from collections import defaultdict
from Economic import *

BASE_DIR = str(EXCEL_DIR)
TEA_CODE_DIR = str(_TEA_CODE_DIR)
ANALYSIS_DIR = str(TEA_ANALYSIS_DIR)
SALT_LAKES = ["GSL", "Atacama", "Uyuni", "Zabuye"]

r = 0.07
n = 20
CRF = r * (1 + r) ** n / ((1 + r) ** n - 1)


def run_econ_for_pathway(lake, pathway_name):
    print(f"\n=== 경제성 평가 시작: {lake} | {pathway_name} ===")
    Opex.set_lake(lake)
    excel_path = os.path.join(BASE_DIR, lake, f"{pathway_name}.xlsx")

    if not os.path.exists(excel_path):
        print(f"!! 파일 없음: {excel_path}")
        return

    tech_list = PATHWAYS[pathway_name]

    capex_total = 0.0
    opex_total = 0.0
    profit_total = 0.0
    li2co3_prod = None
    detail_rows = []

    capex_by_tech = defaultdict(float)
    opex_by_tech = defaultdict(float)
    profit_by_tech = defaultdict(float)

    for tech in tech_list:
        print(f" → 기술 처리: {tech}")

        try:
            df = pd.read_excel(excel_path, sheet_name=tech)
            data = df.iloc[0].to_dict()
        except Exception as e:
            print(f"   !! 시트 '{tech}' 읽기 실패 → skip ({e})")
            continue

        pathway_id = PATHWAY_ID_MAP[pathway_name]

        econ_func = get_econ_func(tech, pathway_id)

        if econ_func is None:
            print(f"   !! 경제성 함수 없음: {tech}")
            continue

        result = econ_func(data)

        for k, v in result.items():
            if k.startswith("CAPEX_") and k.endswith("_total"):
                capex_total += v
                capex_by_tech[tech] += v

            if k.startswith("OPEX_") and k.endswith("_total"):
                opex_total += v
                opex_by_tech[tech] += v
            if k.startswith("PROFIT_"):
                profit_total += v
                profit_by_tech[tech] += v

        if "LI2CO3" in result:
            li2co3_prod = float(result["LI2CO3"])

        row = {"TECH": tech}
        row.update(result)
        detail_rows.append(row)

    if li2co3_prod is None or li2co3_prod == 0:
        print(f"   !! Li2CO3 생산량(LI2CO3)이 없거나 0 → LCOL 계산 불가")
        lcol = None
    else:
        annual_cost = capex_total * CRF + opex_total + profit_total
        lcol = annual_cost / li2co3_prod

    print(f"   CAPEX_total  = {capex_total:,.0f} $")
    print(f"   OPEX_total   = {opex_total:,.0f} $/yr")
    print(f"   PROFIT_total = {profit_total:,.0f} $/yr")
    if li2co3_prod is not None:
        print(f"   Li2CO3_prod  = {li2co3_prod:,.2f} kg/yr")
    if lcol is not None:
        print(f"   LCOL         = {lcol:,.4f} $/kg Li2CO3")

    df_detail = pd.DataFrame(detail_rows)
    labor_cost = sum(
        float(value)
        for row in detail_rows
        for key, value in row.items()
        if key.startswith("OPEX_") and key.endswith("_labor")
    )
    summary_row = {
        "lake": lake,
        "pathway": pathway_name,
        "CAPEX_total": capex_total,
        "OPEX_total": opex_total,
        "OPEX_labor_total": labor_cost,
        "LABOR_WAGE": LABOR_WAGE.get(lake, LABOR_WAGE["DEFAULT"]),
        "PROFIT_total": profit_total,
        "Li2CO3_prod": li2co3_prod,
        "CRF": CRF,
        "LCOL": lcol,
    }

    for tech in tech_list:
        summary_row[f"CAPEX_{tech}"] = capex_by_tech.get(tech, 0.0)
        summary_row[f"OPEX_{tech}"] = opex_by_tech.get(tech, 0.0)
        summary_row[f"PROFIT_{tech}"] = profit_by_tech.get(tech, 0.0)

    df_summary = pd.DataFrame([summary_row])

    lake_analysis_dir = os.path.join(ANALYSIS_DIR, lake)
    os.makedirs(lake_analysis_dir, exist_ok=True)
    out_file = os.path.join(lake_analysis_dir, f"{pathway_name}_econ.xlsx")

    with pd.ExcelWriter(out_file, engine="xlsxwriter") as w:
        df_summary.to_excel(w, sheet_name="SUMMARY", index=False)
        df_detail.to_excel(w, sheet_name="DETAIL", index=False)

    print(f"=== 저장 완료 → {out_file}")
    return summary_row


def run_econ(pathways, lakes=None):
    if isinstance(pathways, str):
        pathways = [pathways]

    if lakes is None:
        lakes = SALT_LAKES
    elif isinstance(lakes, str):
        lakes = [lakes]

    for lk in lakes:
        if lk not in SALT_LAKES:
            print(f"잘못된 lake 이름: {lk}")
            print("가능한 lake:", SALT_LAKES)
            return

    for pw in pathways:
        if pw not in PATHWAYS:
            print(f"잘못된 pathway 이름: {pw}")
            print("가능한 pathway:", list(PATHWAYS.keys()))
            return

    all_summary_rows = []

    for lake in lakes:
        for pw in pathways:
            summary_row = run_econ_for_pathway(lake, pw)
            if summary_row is not None:
                all_summary_rows.append(summary_row)

    if all_summary_rows:
        df_all = pd.DataFrame(all_summary_rows)

        lakes_tag = "_".join(lakes)
        os.makedirs(ANALYSIS_DIR, exist_ok=True)
        out_all = os.path.join(ANALYSIS_DIR, f"econ_summary_{lakes_tag}_pathways.xlsx")

        df_all.to_excel(out_all, sheet_name="SUMMARY_ALL", index=False)
        canonical_out = os.path.join(TEA_CODE_DIR, "TEA_result.xlsx")
        df_all.to_excel(canonical_out, sheet_name="SUMMARY_ALL", index=False)
        print(f"\n### 전체 SUMMARY 저장 완료 → {out_all}")


def MED(data: dict) -> dict:
    CAPEX_MAP = {
        "PUMP": ("MED_PUMP", Capex.PUMP),
        "HX": ("MED_HX", Capex.HX),
        "HEATER1": ("MED_HEATER1", Capex.HEAT),
        "HEATER2": ("MED_HEATER2", Capex.HEAT),
        "HEATER3": ("MED_HEATER3", Capex.HEAT),
        "EVAP1": ("MED_EVAP1", Capex.VESSEL),
        "EVAP2": ("MED_EVAP2", Capex.VESSEL),
        "EVAP3": ("MED_EVAP3", Capex.VESSEL),
        "FD1": ("MED_FD1", Capex.VESSEL),
        "FD2": ("MED_FD2", Capex.VESSEL),
        "FD3": ("MED_FD3", Capex.VESSEL),
        "COOL": ("MED_COOL", Capex.HEAT),
    }

    ELEC_MAP = {
        "PUMP": "MED_elec_PUMP",
        "HX": "MED_elec_HX",
    }

    results = {}
    C_BM_sum = 0.0
    C_BM_O_sum = 0.0

    def _capex_from_cbm(C_BM_i, C_BM_i_O):
        return (1.18 * C_BM_i + 0.5 * C_BM_i_O) * 800.8 / 397

    for equip, (col_name, capex_func) in CAPEX_MAP.items():
        val = data[col_name]
        C_BM_i, C_BM_i_O = capex_func(val)
        CAPEX_i = _capex_from_cbm(C_BM_i, C_BM_i_O)
        results[f"CAPEX_{equip}"] = CAPEX_i
        C_BM_sum += C_BM_i
        C_BM_O_sum += C_BM_i_O

    CAPEX_MED_total = _capex_from_cbm(C_BM_sum, C_BM_O_sum)
    results["CAPEX_MED_total"] = CAPEX_MED_total

    OPEX_MED_total = 0.0
    OPEX_MED_carbon = 0.0

    for equip, elec_col in ELEC_MAP.items():
        elec_use = data[elec_col]
        OPEX_i = Opex.elec(elec_use)
        results[f"OPEX_{equip}"] = OPEX_i
        OPEX_MED_total += OPEX_i

        C_i = Opex.carbon_from_elec(elec_use)
        results[f"OPEX_{equip}_carbon"] = C_i
        OPEX_MED_carbon += C_i

    freshwater = data["MED_freshwater"]
    O_freshwater = Opex.WATER(freshwater)
    results["PROFIT_freshwater"] = -O_freshwater

    OPEX_cooling = Opex.cooling(data["MED_cooling"])
    results["OPEX_MED_cooling"] = OPEX_cooling
    OPEX_MED_total += OPEX_cooling

    OPEX_steam = Opex.steam(data["MED_steam"])
    results["OPEX_MED_steam"] = OPEX_steam
    OPEX_MED_total += OPEX_steam

    OPEX_MED_carbon += Opex.carbon_from_steam(data["MED_steam"])

    OPEX_labor = Opex.labor(0, 12)
    results["OPEX_MED_labor"] = OPEX_labor
    OPEX_MED_total += OPEX_labor

    OPEX_MED_main = Opex.maintenence(CAPEX_MED_total)
    results["OPEX_MED_main"] = OPEX_MED_main
    OPEX_MED_total += OPEX_MED_main

    OPEX_MED_total += OPEX_MED_carbon
    results["OPEX_MED_carbon"] = OPEX_MED_carbon

    results["OPEX_MED_total"] = OPEX_MED_total
    return results


def MVR(data: dict) -> dict:
    CAPEX_MAP = {
        "EVAP": ("MVR_EVAP1", Capex.VESSEL),
        "COOL": ("MVR_COOL", Capex.HEAT),
        "COMP": ("MVR_COMP", Capex.COMP),
        "HEATER": ("MVR_HEATER1", Capex.HEAT),
    }

    ELEC_MAP = {
        "COMP": "MVR_elec_COMP",
    }

    results = {}
    C_BM_sum = 0.0
    C_BM_O_sum = 0.0

    def _capex_from_cbm(C_BM_i, C_BM_i_O):
        return (1.18 * C_BM_i + 0.5 * C_BM_i_O) * 800.8 / 397

    for equip, (col_name, capex_func) in CAPEX_MAP.items():
        val = data[col_name]
        C_BM_i, C_BM_i_O = capex_func(val)
        CAPEX_i = _capex_from_cbm(C_BM_i, C_BM_i_O)
        results[f"CAPEX_{equip}"] = CAPEX_i
        C_BM_sum += C_BM_i
        C_BM_O_sum += C_BM_i_O

    CAPEX_MVR_total = _capex_from_cbm(C_BM_sum, C_BM_O_sum)
    results["CAPEX_MVR_total"] = CAPEX_MVR_total

    OPEX_MVR_total = 0.0
    OPEX_MVR_carbon = 0.0

    for equip, elec_col in ELEC_MAP.items():
        elec_use = data[elec_col]
        OPEX_i = Opex.elec(elec_use)
        results[f"OPEX_{equip}"] = OPEX_i
        OPEX_MVR_total += OPEX_i

        C_i = Opex.carbon_from_elec(elec_use)
        results[f"OPEX_{equip}_carbon"] = C_i
        OPEX_MVR_carbon += C_i

    freshwater = data["MVR_freshwater"]
    O_freshwater = Opex.WATER(freshwater)
    results["PROFIT_freshwater"] = -O_freshwater

    OPEX_cooling = Opex.cooling(data["MVR_cooling"])
    results["OPEX_MVR_cooling"] = OPEX_cooling
    OPEX_MVR_total += OPEX_cooling

    heat_use = float(data.get("MVR_heat", 0.0))
    OPEX_heat = Opex.heat(heat_use)
    results["OPEX_MVR_heat"] = OPEX_heat
    OPEX_MVR_total += OPEX_heat

    OPEX_heat_carbon = Opex.carbon_from_heat(heat_use)
    results["OPEX_MVR_heat_carbon"] = OPEX_heat_carbon
    OPEX_MVR_carbon += OPEX_heat_carbon

    OPEX_labor = Opex.labor(0, 4)
    results["OPEX_MVR_labor"] = OPEX_labor
    OPEX_MVR_total += OPEX_labor

    OPEX_MVR_main = Opex.maintenence(CAPEX_MVR_total)
    results["OPEX_MVR_main"] = OPEX_MVR_main
    OPEX_MVR_total += OPEX_MVR_main

    OPEX_MVR_total += OPEX_MVR_carbon
    results["OPEX_MVR_carbon"] = OPEX_MVR_carbon

    results["OPEX_MVR_total"] = OPEX_MVR_total
    return results


def FO(data: dict) -> dict:
    area_m2 = float(data["total_membrane_area_m2"])
    Q_feed_in_L_hr = float(data["Q_feed_in_L_hr"])
    rho_in = float(data["rho_in_kg_m3"])
    NaCl = float(data["NaCl_kg_year"])
    rho_out = float(data["rho_out_kg_m3"])
    feed_in_L_hr = float(data["Q_feed_in_L_hr"])
    net_power_kW = float(data["FO_net_power_kW"])
    dp_pump = float(data["FO_dp_feed_bar_total"])

    flow_kg_s = Q_feed_in_L_hr * rho_in / (1000.0 * 3600.0)

    cap_dict = Capex.FO(flow_kg_s, rho_out, area_m2, feed_in_L_hr, dp_pump)
    CAPEX_FO_total = float(cap_dict.get("CAP_TCI_FO", 0.0))

    op_dict = Opex.FO(Q_feed_in_L_hr, net_power_kW, NaCl, rho_in, area_m2)
    OPEX_FO_total = float(op_dict.get("OPEX_FO_total", 0.0))

    result = {}
    result.update(cap_dict)
    result.update(op_dict)

    result["CAPEX_FO_total"] = CAPEX_FO_total
    result["OPEX_FO_total"] = OPEX_FO_total

    return result


def RO(data: dict) -> dict:
    Q_feed_m3_s = float(data["Q_feed_m3_s"])
    Q_pump_in_m3_s = float(data["Q_HP_pump_in_m3_s"])
    Q_erd_in_m3_s = float(data["Q_ERD_in_m3_s"])
    area_m2 = float(data["membrane_area_total_m2"])
    dp_pump = float(data["RO_dP_module_bar_used"])
    net_power_kW = float(data["RO_net_power_kW"])
    freshwater_kg_s = float(data["freshwater_kg_s"])

    cap_dict = Capex.RO(Q_feed_m3_s, Q_pump_in_m3_s, Q_erd_in_m3_s, area_m2, dp_pump)
    CAPEX_RO_total = float(cap_dict.get("CAP_TCI_RO", 0.0))

    op_dict = Opex.RO(net_power_kW, area_m2, freshwater_kg_s)
    OPEX_RO_total = float(op_dict.get("OPEX_RO_total", 0.0))

    result = {}
    result.update(cap_dict)
    result.update(op_dict)

    result["CAPEX_RO_total"] = CAPEX_RO_total
    result["OPEX_RO_total"] = OPEX_RO_total

    return result


def NE(data: dict) -> dict:
    flow_L_hr = float(data["Flow_in_L_hr"])
    area_km2 = float(data["Area_pond_km2"])

    cap_dict = Capex.NE(flow_L_hr, area_km2)

    CAPEX_NE_total = float(cap_dict.get("CAPEX_NE", 0.0))

    op_dict = Opex.NE(area_km2)
    elec_cost = float(op_dict.get("OPEX_NE_elec", 0.0))
    steam_cost = float(op_dict.get("OPEX_NE_steam_fuel", 0.0))
    material_cost = float(op_dict.get("OPEX_NE_material", 0.0))

    p = Opex._get_param()
    elec_base = float(p["elec_base"]) if p["elec_base"] > 0 else 0.0
    if elec_base > 0:
        elec_use_kwh = elec_cost / elec_base
    else:
        elec_use_kwh = 0.0

    carbon_elec = Opex.carbon_from_elec(elec_use_kwh)

    if steam_cost > 0:
        steam_use_kwh = steam_cost / p["steam_cost"]
    else:
        steam_use_kwh = 0.0
    carbon_steam = Opex.carbon_from_steam(steam_use_kwh)

    carbon_total = carbon_elec + carbon_steam

    OPEX_NE = float(op_dict.get("OPEX_NE", 0.0))
    OPEX_NE_total = OPEX_NE + carbon_total
    result = {}

    result.update(cap_dict)
    result.update(op_dict)

    result["OPEX_NE_carbon"] = carbon_total
    result["CAPEX_NE_total"] = CAPEX_NE_total
    result["OPEX_NE_total"] = OPEX_NE_total

    return result


def SD(data: dict) -> dict:
    flow_L_hr = float(data["Flow_in_L_hr"])
    area_km2 = float(data["Area_pond_km2"])
    SD_rate = float(data.get("SD_rate", 0.0))
    freshwater_SD_kg_year = float(data.get("freshwater_SD_kg_year", 0.0))

    cap_dict = Capex.SD(flow_L_hr, area_km2, SD_rate)
    CAPEX_SD_total = float(cap_dict.get("CAPEX_SD", 0.0))

    op_dict = Opex.SD(area_km2, freshwater_SD_kg_year)

    elec_cost = float(op_dict.get("OPEX_SD_elec", 0.0))
    gas_cost = float(op_dict.get("OPEX_SD_gas_fuel", 0.0))
    material_cost = float(op_dict.get("OPEX_SD_material", 0.0))
    freshwater_profit = float(op_dict.get("PROFIT_SD_freshwater", 0.0))

    p = Opex._get_param()
    elec_base = float(p["elec_base"]) if p["elec_base"] > 0 else 0.0
    if elec_base > 0:
        elec_use_kwh = elec_cost / elec_base
    else:
        elec_use_kwh = 0.0
    carbon_elec = Opex.carbon_from_elec(elec_use_kwh)

    carbon_total = carbon_elec

    OPEX_SD = float(op_dict.get("OPEX_SD", 0.0))
    OPEX_SD_total = OPEX_SD + carbon_total

    result = {}

    result.update(cap_dict)
    result.update(op_dict)

    result["OPEX_SD_carbon"] = carbon_total
    result["CAPEX_SD_total"] = CAPEX_SD_total
    result["OPEX_SD_total"] = OPEX_SD_total

    return result


def SX(data: dict) -> dict:
    OP_TIME = 8500.0

    CAPEX_MAP = {
        "EXT": ("SX_EXT_V", Capex.MIXSETTLER, False),
        "WASH": ("SX_WASH_V", Capex.MIXSETTLER, False),
        "STRIP1": ("SX_STRIP1_V", Capex.MIXSETTLER, False),
        "STRIP2": ("SX_STRIP2_V", Capex.MIXSETTLER, False),
        "REGEN": ("SX_REGEN_V", Capex.MIXSETTLER, False),
        "PUMP_EXT": ("SX_elec_EXT", Capex.PUMP, True),
        "PUMP_WASH": ("SX_elec_WASH", Capex.PUMP, True),
        "PUMP_STRIP1": ("SX_elec_STRIP1", Capex.PUMP, True),
        "PUMP_STRIP2": ("SX_elec_STRIP2", Capex.PUMP, True),
        "PUMP_REGEN": ("SX_elec_REGEN", Capex.PUMP, True),
    }

    ELEC_MAP = {
        "EXT": "SX_elec_EXT",
        "WASH": "SX_elec_WASH",
        "STRIP1": "SX_elec_STRIP1",
        "STRIP2": "SX_elec_STRIP2",
        "REGEN": "SX_elec_REGEN",
    }

    results = {}
    C_BM_sum = 0.0
    C_BM_O_sum = 0.0

    def _cap(C, O):
        return (1.18 * C + 0.5 * O) * 800.8 / 397

    for equip, (col, func, divide_by_op_time) in CAPEX_MAP.items():
        val = abs(float(data.get(col, 0.0)))

        if divide_by_op_time:
            val /= OP_TIME

        C, O = func(val)
        results[f"CAPEX_{equip}"] = _cap(C, O)
        C_BM_sum += C
        C_BM_O_sum += O

    CAPEX_SX_equip = _cap(C_BM_sum, C_BM_O_sum)
    results["CAPEX_SX_equip"] = CAPEX_SX_equip

    tau_hr = (30 / 60.0) * 5

    TBP_init_kg = abs(float(data.get("SX_TBP", 0.0))) * tau_hr
    DILUENT_init_kg = abs(float(data.get("SX_DILUENT", 0.0))) * tau_hr
    FECL3_init_kg = abs(float(data.get("SX_FECL3", 0.0))) * tau_hr

    CAPEX_init = (
        Opex.TBP(TBP_init_kg)
        + Opex.DILUENT(DILUENT_init_kg)
        + Opex.FECL3(FECL3_init_kg)
    )
    results["CAPEX_SX_init_chem"] = CAPEX_init

    CAPEX_SX_total = CAPEX_SX_equip + CAPEX_init
    results["CAPEX_SX_total"] = CAPEX_SX_total

    OPEX_elec = 0.0
    OPEX_carbon = 0.0
    OPEX_reagent = 0.0

    for equip, elec_col in ELEC_MAP.items():
        elec_use = abs(float(data.get(elec_col, 0.0)))

        O_i = Opex.elec(elec_use)
        results[f"OPEX_{equip}"] = O_i
        OPEX_elec += O_i

        C_i = Opex.carbon_from_elec(elec_use)
        results[f"OPEX_{equip}_carbon"] = C_i
        OPEX_carbon += C_i

    results["OPEX_SX_elec"] = OPEX_elec
    results["OPEX_SX_carbon"] = OPEX_carbon

    reagents = [
        ("Wash_HCl", Opex.HCL),
        ("Wash_MgCl2", Opex.MGCL2),
        ("Strip1_HCl", Opex.HCL),
        ("Strip1_NaCl", Opex.NACL),
        ("Strip2_HCl", Opex.HCL),
        ("Strip2_NaCl", Opex.NACL),
        ("Regen_MgCl2", Opex.MGCL2),
        ("Regen_Mg(OH)2", Opex.MGOH2),
    ]

    for key, f in reagents:
        amt = abs(float(data.get(key, 0.0)))
        cost = f(amt)
        results[f"OPEX_{key}"] = cost
        OPEX_reagent += cost

    results["OPEX_SX_reagent"] = OPEX_reagent

    OPEX_waste = Opex.WASTE(abs(float(data.get("SX_WASTE", 0.0))))
    results["OPEX_SX_WASTE"] = OPEX_waste

    OPEX_labor = Opex.labor(0, 5)
    results["OPEX_SX_labor"] = OPEX_labor

    OPEX_main = Opex.maintenence(CAPEX_SX_equip)
    results["OPEX_SX_main"] = OPEX_main

    OPEX_total = (
        OPEX_elec + OPEX_carbon + OPEX_reagent + OPEX_waste + OPEX_labor + OPEX_main
    )
    results["OPEX_SX_total"] = OPEX_total

    return results


def IX(data: dict) -> dict:
    results = {}

    Di_m = float(data["IX_unit_bed_diameter_m"])
    L_m = float(data["IX_unit_bed_height_m"])
    n_ads = int(data["IX_n_ads_bed"])
    n_regen = int(data["IX_n_regen_bed"])

    cap_ads = Capex.IX(
        Di_m=Di_m,
        L_m=L_m,
        n_col=n_ads,
        operating_pressure_psig=5.0,
        design_temp_F=120.0,
        material="carbon_steel",
        vertical=True,
    )

    cap_reg = Capex.IX(
        Di_m=Di_m,
        L_m=L_m,
        n_col=n_regen,
        operating_pressure_psig=5.0,
        design_temp_F=120.0,
        material="carbon_steel",
        vertical=True,
    )

    CAPEX_IX_ads_columns = float(cap_ads["CP_total_targetCE"])
    CAPEX_IX_regen_columns = float(cap_reg["CP_total_targetCE"])
    CAPEX_IX_columns = CAPEX_IX_ads_columns + CAPEX_IX_regen_columns

    results["CAPEX_IX_ads_columns"] = CAPEX_IX_ads_columns
    results["CAPEX_IX_regen_columns"] = CAPEX_IX_regen_columns
    results["CAPEX_IX_columns"] = CAPEX_IX_columns

    pump_kw = float(data["IX_feed_pump_power_kW"])
    C_pump, O_pump = Capex.PUMP(max(pump_kw, 0.1))
    CAPEX_IX_feedpump = (1.18 * C_pump + 0.5 * O_pump) * 800.8 / 397

    results["CAPEX_IX_feedpump"] = CAPEX_IX_feedpump

    resin_inventory_kg = float(data["IX_resin_inventory_kg"])
    CAPEX_IX_resin_init = Opex.RESIN(resin_inventory_kg)

    results["CAPEX_IX_resin_init"] = CAPEX_IX_resin_init

    CAPEX_IX_total = CAPEX_IX_columns + CAPEX_IX_feedpump + CAPEX_IX_resin_init
    results["CAPEX_IX_total"] = CAPEX_IX_total

    OPEX_total = 0.0
    OPEX_carbon = 0.0

    elec_kwh_y = float(data["IX_elec_feedpump_kWh_y"])
    O_elec = Opex.elec(elec_kwh_y)
    C_elec = Opex.carbon_from_elec(elec_kwh_y)

    results["OPEX_IX_elec"] = O_elec
    results["OPEX_IX_elec_carbon"] = C_elec
    OPEX_total += O_elec
    OPEX_carbon += C_elec

    hcl_kg_y = float(data["IX_HCl_eq_kg_y"])
    O_hcl = Opex.HCL(hcl_kg_y)
    results["OPEX_IX_HCl"] = O_hcl
    OPEX_total += O_hcl

    wash_kg_y = float(data["IX_wash_water_kg_y"])
    O_wash = Opex.WATER(wash_kg_y)
    results["OPEX_IX_wash_water"] = O_wash
    OPEX_total += O_wash

    resin_replace_kg_y = resin_inventory_kg * 0.05
    results["OPEX_IX_resin_replace"] = Opex.RESIN(resin_replace_kg_y)
    OPEX_total += results["OPEX_IX_resin_replace"]

    O_labor = Opex.labor(0, 6)
    results["OPEX_IX_labor"] = O_labor
    OPEX_total += O_labor

    O_main = Opex.maintenence(CAPEX_IX_columns + CAPEX_IX_feedpump)
    results["OPEX_IX_main"] = O_main
    OPEX_total += O_main

    results["OPEX_IX_carbon"] = OPEX_carbon
    OPEX_total += OPEX_carbon

    results["OPEX_IX_total"] = OPEX_total

    results["IX_product_Li_kg_y"] = float(data.get("IX_product_Li_kg_y", 0.0))
    results["IX_total_Li_recovery_pct"] = float(
        data.get("IX_total_Li_recovery_pct", 0.0)
    )

    return results


def PREP(data: dict) -> dict:
    CAPEX_MAP = {
        "MGCSTR": ("PREP_MGCSTR", Capex.CSTR),
        "CACSTR": ("PREP_CACSTR", Capex.CSTR),
        "MGFILT": (["PREP_MGFILT_V", "PREP_MGFILT_M"], Capex.FILT),
        "CAFILT": (["PREP_CAFILT_V", "PREP_CAFILT_M"], Capex.FILT),
    }

    ELEC_MAP = {
        "MGFILT": "PREP_elec_MGFILT",
        "CAFILT": "PREP_elec_CAFILT",
        "MGCSTR": "PREP_elec_MGCSTR",
        "CACSTR": "PREP_elec_CACSTR",
    }

    results = {}
    C_BM_sum = C_BM_O_sum = 0.0

    def _cap(C, O):
        return (1.18 * C + 0.5 * O) * 800.8 / 397

    for eq, (cols, func) in CAPEX_MAP.items():
        if isinstance(cols, str):
            cols = [cols]
        vals = [data[c] for c in cols]
        C, O = func(*vals)
        results[f"CAPEX_{eq}"] = _cap(C, O)
        C_BM_sum += C
        C_BM_O_sum += O

    CAPEX_PREP_total = _cap(C_BM_sum, C_BM_O_sum)
    results["CAPEX_PREP_total"] = CAPEX_PREP_total

    OPEX_total = 0.0
    OPEX_PREP_carbon = 0.0

    for equip, elec_col in ELEC_MAP.items():
        elec_use = data[elec_col]
        OPEX_i = Opex.elec(elec_use)
        results[f"OPEX_{equip}"] = OPEX_i
        OPEX_total += OPEX_i

        C_i = Opex.carbon_from_elec(elec_use)
        results[f"OPEX_{equip}_carbon"] = C_i
        OPEX_PREP_carbon += C_i

    NA2CO3 = data["NA2CO3_1"]
    O_NA2CO3 = Opex.NA2CO3(NA2CO3)
    results["OPEX_NA2CO3_PREP"] = O_NA2CO3
    OPEX_total += O_NA2CO3

    NAOH = data["NAOH"]
    O_NAOH = Opex.NAOH(NAOH)
    results["OPEX_NAOH"] = O_NAOH
    OPEX_total += O_NAOH

    MGOH2 = data["MGOH2"]
    O_MGOH2 = Opex.MGOH2(MGOH2)
    results["PROFIT_MGOH2"] = -O_MGOH2

    CACO3 = data["CACO3"]
    O_CACO3 = Opex.CACO3(CACO3)
    results["PROFIT_CACO3"] = -O_CACO3

    OPEX_PREP_labor = Opex.labor(2, 2)
    results["OPEX_PREP_labor"] = OPEX_PREP_labor
    OPEX_total += OPEX_PREP_labor

    OPEX_PREP_main = Opex.maintenence(CAPEX_PREP_total)
    results["OPEX_PREP_main"] = OPEX_PREP_main
    OPEX_total += OPEX_PREP_main

    OPEX_total += OPEX_PREP_carbon
    results["OPEX_PREP_carbon"] = OPEX_PREP_carbon

    results["OPEX_PREP_total"] = OPEX_total
    return results


def CARB(data: dict) -> dict:
    CAPEX_MAP = {
        "LICSTR": ("CARB_LICSTR", Capex.CSTR),
        "LIFILT": (["CARB_LIFILT_V", "CARB_LIFILT_M"], Capex.FILT),
    }

    ELEC_MAP = {
        "LICSTR": "CARB_elec_LICSTR",
        "LIFILT": "CARB_elec_LIFILT",
    }

    results = {}
    C_BM_sum = C_BM_O_sum = 0.0

    def _cap(C, O):
        return (1.18 * C + 0.5 * O) * 800.8 / 397

    for eq, (cols, func) in CAPEX_MAP.items():
        if isinstance(cols, str):
            cols = [cols]
        vals = [data[c] for c in cols]
        C, O = func(*vals)
        results[f"CAPEX_{eq}"] = _cap(C, O)
        C_BM_sum += C
        C_BM_O_sum += O

    CAPEX_CARB_total = _cap(C_BM_sum, C_BM_O_sum)
    results["CAPEX_CARB_total"] = CAPEX_CARB_total

    OPEX_total = 0.0
    OPEX_CARB_carbon = 0.0

    for equip, elec_col in ELEC_MAP.items():
        elec_use = data[elec_col]
        OPEX_i = Opex.elec(elec_use)
        results[f"OPEX_{equip}"] = OPEX_i
        OPEX_total += OPEX_i

        C_i = Opex.carbon_from_elec(elec_use)
        results[f"OPEX_{equip}_carbon"] = C_i
        OPEX_CARB_carbon += C_i

    NA2CO3 = data["NA2CO3_2"]
    O_NA2CO3 = Opex.NA2CO3(NA2CO3)
    results["OPEX_CARB_NA2CO3"] = O_NA2CO3
    OPEX_total += O_NA2CO3

    results["LI2CO3"] = data["LI2CO3"]

    OPEX_CARB_Waste = Opex.WASTE(data["WASTE"])
    results["OPEX_CARB_NACL"] = OPEX_CARB_Waste
    OPEX_total += OPEX_CARB_Waste

    OPEX_CARB_labor = Opex.labor(1, 1)
    results["OPEX_CARB_labor"] = OPEX_CARB_labor
    OPEX_total += OPEX_CARB_labor

    OPEX_CARB_main = Opex.maintenence(CAPEX_CARB_total)
    results["OPEX_CARB_main"] = OPEX_CARB_main
    OPEX_total += OPEX_CARB_main

    OPEX_total += OPEX_CARB_carbon
    results["OPEX_CARB_carbon"] = OPEX_CARB_carbon

    results["OPEX_CARB_total"] = OPEX_total
    return results


def SX_CARB(data: dict) -> dict:
    CAPEX_MAP = {
        "LICSTR": ("CARB_LICSTR", Capex.CSTR),
        "LIFILT": (["CARB_LIFILT_V", "CARB_LIFILT_M"], Capex.FILT),
        "WASTEFILT": (["CARB_WASTEFILT_V", "CARB_WASTEFILT_M"], Capex.FILT),
    }

    ELEC_MAP = {
        "LICSTR": "CARB_elec_LICSTR",
        "LIFILT": "CARB_elec_LIFILT",
        "WASTEFILT": "CARB_elec_WASTEFILT",
    }

    results = {}
    C_BM_sum = C_BM_O_sum = 0.0

    def _cap(C, O):
        return (1.18 * C + 0.5 * O) * 800.8 / 397

    for eq, (cols, func) in CAPEX_MAP.items():
        if isinstance(cols, str):
            cols = [cols]
        vals = [data[c] for c in cols]
        C, O = func(*vals)
        results[f"CAPEX_{eq}"] = _cap(C, O)
        C_BM_sum += C
        C_BM_O_sum += O

    CAPEX_CARB_total = _cap(C_BM_sum, C_BM_O_sum)
    results["CAPEX_CARB_total"] = CAPEX_CARB_total

    OPEX_total = 0.0
    OPEX_CARB_carbon = 0.0

    for equip, elec_col in ELEC_MAP.items():
        elec_use = data[elec_col]
        OPEX_i = Opex.elec(elec_use)
        results[f"OPEX_{equip}"] = OPEX_i
        OPEX_total += OPEX_i

        C_i = Opex.carbon_from_elec(elec_use)
        results[f"OPEX_{equip}_carbon"] = C_i
        OPEX_CARB_carbon += C_i

    NA2CO3 = data["NA2CO3_2"]
    O_NA2CO3 = Opex.NA2CO3(NA2CO3)
    results["OPEX_NA2CO3_CARB"] = O_NA2CO3
    OPEX_total += O_NA2CO3

    NAOH = data["NAOH"]
    O_NAOH = Opex.NAOH(NAOH)
    results["OPEX_NAOH_CARB"] = O_NAOH
    OPEX_total += O_NAOH

    results["LI2CO3"] = data["LI2CO3"]

    NACL = data["REC_NACL"]
    O_NACL = Opex.NACL(NACL)
    results["PROFIT_NACL"] = -O_NACL

    OPEX_CARB_Waste = Opex.WASTE(data["WASTE"])
    results["OPEX_CARB_Waste"] = OPEX_CARB_Waste
    OPEX_total += OPEX_CARB_Waste

    OPEX_CARB_labor = Opex.labor(1, 1)
    results["OPEX_CARB_labor"] = OPEX_CARB_labor
    OPEX_total += OPEX_CARB_labor

    OPEX_CARB_main = Opex.maintenence(CAPEX_CARB_total)
    results["OPEX_CARB_main"] = OPEX_CARB_main
    OPEX_total += OPEX_CARB_main

    OPEX_total += OPEX_CARB_carbon
    results["OPEX_CARB_carbon"] = OPEX_CARB_carbon

    results["OPEX_CARB_total"] = OPEX_total
    return results


def IX_CARB(data: dict) -> dict:
    CAPEX_MAP = {
        "LICSTR": ("CARB_LICSTR", Capex.CSTR),
        "LIFILT": (["CARB_LIFILT_V", "CARB_LIFILT_M"], Capex.FILT),
        "WASTEFILT": (["CARB_WASTEFILT_V", "CARB_WASTEFILT_M"], Capex.FILT),
    }

    ELEC_MAP = {
        "LICSTR": "CARB_elec_LICSTR",
        "LIFILT": "CARB_elec_LIFILT",
        "WASTEFILT": "CARB_elec_WASTEFILT",
    }

    results = {}
    C_BM_sum = C_BM_O_sum = 0.0

    def _cap(C, O):
        return (1.18 * C + 0.5 * O) * 800.8 / 397

    for eq, (cols, func) in CAPEX_MAP.items():
        if isinstance(cols, str):
            cols = [cols]
        vals = [data[c] for c in cols]
        C, O = func(*vals)
        results[f"CAPEX_{eq}"] = _cap(C, O)
        C_BM_sum += C
        C_BM_O_sum += O

    CAPEX_CARB_total = _cap(C_BM_sum, C_BM_O_sum)
    results["CAPEX_CARB_total"] = CAPEX_CARB_total

    OPEX_total = 0.0
    OPEX_CARB_carbon = 0.0

    for equip, elec_col in ELEC_MAP.items():
        elec_use = data[elec_col]
        OPEX_i = Opex.elec(elec_use)
        results[f"OPEX_{equip}"] = OPEX_i
        OPEX_total += OPEX_i

        C_i = Opex.carbon_from_elec(elec_use)
        results[f"OPEX_{equip}_carbon"] = C_i
        OPEX_CARB_carbon += C_i

    NA2CO3 = data["NA2CO3_2"]
    O_NA2CO3 = Opex.NA2CO3(NA2CO3)
    results["OPEX_NA2CO3_CARB"] = O_NA2CO3
    OPEX_total += O_NA2CO3

    NAOH = data["NAOH"]
    O_NAOH = Opex.NAOH(NAOH)
    results["OPEX_NAOH_CARB"] = O_NAOH
    OPEX_total += O_NAOH

    results["LI2CO3"] = data["LI2CO3"]

    MGOH2 = data["REC_NACL"]
    O_MGOH2 = Opex.MGOH2(MGOH2)
    results["PROFIT_MGOH2"] = -O_MGOH2

    OPEX_CARB_Waste = Opex.WASTE(data["WASTE"])
    results["OPEX_CARB_Waste"] = OPEX_CARB_Waste
    OPEX_total += OPEX_CARB_Waste

    OPEX_CARB_labor = Opex.labor(1, 1)
    results["OPEX_CARB_labor"] = OPEX_CARB_labor
    OPEX_total += OPEX_CARB_labor

    OPEX_CARB_main = Opex.maintenence(CAPEX_CARB_total)
    results["OPEX_CARB_main"] = OPEX_CARB_main
    OPEX_total += OPEX_CARB_main

    OPEX_total += OPEX_CARB_carbon
    results["OPEX_CARB_carbon"] = OPEX_CARB_carbon

    results["OPEX_CARB_total"] = OPEX_total
    return results


PATHWAYS = {
    "NE_prep_carb": ["NE", "PREP", "CARB"],
    "SD_prep_carb": ["SD", "PREP", "CARB"],
    "MED_prep_carb": ["MED", "PREP", "CARB"],
    "MVR_prep_carb": ["MVR", "PREP", "CARB"],
    "FO_prep_carb": ["FO", "PREP", "CARB"],
    "IX_MED_carb": ["IX", "MED", "CARB"],
    "IX_MVR_carb": ["IX", "MVR", "CARB"],
    "IX_RO_carb": ["IX", "RO", "CARB"],
    "SX_MED_carb": ["SX", "MED", "CARB"],
    "SX_MVR_carb": ["SX", "MVR", "CARB"],
    "SX_RO_carb": ["SX", "RO", "CARB"],
}


PATHWAY_ID_MAP = {name: idx + 1 for idx, name in enumerate(PATHWAYS.keys())}


def get_econ_func(tech: str, pathway_id: int):
    if tech == "CARB":
        if 6 <= pathway_id <= 8:
            return IX_CARB

        if 9 <= pathway_id <= 11:
            return SX_CARB

        return CARB

    return TECH_FUNC.get(tech)


TECH_FUNC = {
    "MED": MED,
    "MVR": MVR,
    "FO": FO,
    "SD": SD,
    "NE": NE,
    "PREP": PREP,
    "CARB": CARB,
    "IX": IX,
    "SX": SX,
    "RO": RO,
}


if __name__ == "__main__":
    ensure_output_dirs()

    pathway = [
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
    run_econ(pathway, lakes=["Atacama", "Uyuni", "Zabuye", "GSL"])
