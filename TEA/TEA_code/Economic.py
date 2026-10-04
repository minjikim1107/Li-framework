import numpy as np
import copy
import math
from heat_price_mapping import heater_electricity_kwh

HEAT_CO2_FACTOR_T_PER_MJ = 0.0000623
BASELINE_HEAT_YEAR = 2020


LABOR_WAGE = {
    "DEFAULT": 52700.0,
    "GSL": 54620.0,
    "Atacama": 16429.0,
    "Uyuni": 3972.0,
    "Zabuye": 12562.0,
}

COUNTRY_PARAM = {
    "DEFAULT": {
        "elec_base": 0.13,
        "steam_base": 0.13 * 0.001163 * 830 * 1.6,
        "carbon_tax": 0.0,
        "elec_ef": 0.475,
        "steam_ef": 0.22,
    },
    "GSL": {
        "elec_base": 0.0832,
        "steam_base": 0.013,
        "carbon_tax": 23.0,
        "elec_ef": 0.475,
        "steam_ef": 0.22,
    },
    "Atacama": {
        "elec_base": 0.21,
        "steam_base": 0.02,
        "carbon_tax": 5,
        "elec_ef": 0.475,
        "steam_ef": 0.22,
    },
    "Uyuni": {
        "elec_base": 0.1224,
        "steam_base": 0.02,
        "carbon_tax": 0.0,
        "elec_ef": 0.475,
        "steam_ef": 0.22,
    },
    "Zabuye": {
        "elec_base": 0.08,
        "steam_base": 0.015,
        "carbon_tax": 12,
        "elec_ef": 0.475,
        "steam_ef": 0.22,
    },
}

_CURRENT_LAKE = "DEFAULT"


class Capex:
    def CSTR(V):
        K = [4.1052, 0.5320, -0.0005]

        if 0.1 <= V <= 35:
            logCpO = K[0] + K[1] * np.log10(V) + K[2] * np.log10(V) ** 2
            CpO_reactor = 10**logCpO
        elif V > 35:
            V_ref = 35
            logCpO_ref = K[0] + K[1] * np.log10(V_ref) + K[2] * np.log10(V_ref) ** 2
            CpO_ref = 10 ** (logCpO_ref)
            CpO_reactor = CpO_ref * (V / V_ref) ** 0.6
        else:
            V_ref = 0.1
            logCpO_ref = K[0] + K[1] * np.log10(V_ref) + K[2] * np.log10(V_ref) ** 2
            CpO_ref = 10 ** (logCpO_ref)
            CpO_reactor = CpO_ref * (V / V_ref) ** 0.6

        FBM = 4.0
        C_BM_CSTR = CpO_reactor * FBM
        return C_BM_CSTR, C_BM_CSTR

    def FILT(V_input, M_output):
        alpha = 200
        pressure_difference = 35
        psi = 0.3
        viscosity = 0.0347
        Nr = 30 * 60
        w = M_output / V_input
        Constant = np.sqrt(2 * psi * Nr * pressure_difference / (alpha * w * viscosity))
        Filter_Area_Oxide = V_input / Constant

        C = [4.8123, 0.2858, 0.0420]

        logCpO_ref = C[0] + C[1] * np.log10(0.9) + C[2] * np.log10(0.9) ** 2
        CpO_ref = 10**logCpO_ref
        CpO_FILT = CpO_ref * (Filter_Area_Oxide / 0.9) ** 0.62

        FBM = 1.65
        C_BM_FILT = CpO_FILT * FBM
        return C_BM_FILT, C_BM_FILT

    def HX(A):
        K = [4.3247, -0.3030, 0.1634]

        if 10 <= A <= 1000:
            logCpO = K[0] + K[1] * np.log10(A) + K[2] * np.log10(A) ** 2
            CpO_reactor = 10**logCpO
        elif A > 1000:
            A_ref = 1000
            logCpO_ref = K[0] + K[1] * np.log10(A_ref) + K[2] * np.log10(A_ref) ** 2
            CpO_ref = 10 ** (logCpO_ref)
            CpO_reactor = CpO_ref * (A / A_ref) ** 0.6
        else:
            A_ref = 10
            logCpO_ref = K[0] + K[1] * np.log10(A_ref) + K[2] * np.log10(A_ref) ** 2
            CpO_ref = 10 ** (logCpO_ref)
            CpO_reactor = CpO_ref * (A / A_ref) ** 0.6

        FP = 1
        FM = 1.39
        C_BM_HX = CpO_reactor * (1.63 + 1.66 * FM * FP)
        return C_BM_HX, C_BM_HX

    def PUMP(P):
        K = [3.8696, 0.3161, 0.1220]

        if 0.1 <= P <= 200:
            logCpO = K[0] + K[1] * np.log10(P) + K[2] * np.log10(P) ** 2
            CpO_block = 10**logCpO
        elif P > 200:
            P_ref = 35
            logCpO_ref = K[0] + K[1] * np.log10(P_ref) + K[2] * np.log10(P_ref) ** 2
            CpO_ref = 10 ** (logCpO_ref)
            CpO_block = CpO_ref * (P / P_ref) ** 0.6
        else:
            P_ref = 0.1
            logCpO_ref = K[0] + K[1] * np.log10(P_ref) + K[2] * np.log10(P_ref) ** 2
            CpO_ref = 10 ** (logCpO_ref)
            CpO_block = CpO_ref * (P / P_ref) ** 0.6

        FM = 1
        FP = 1
        C_BM_block = CpO_block * (1.89 + 1.35 * FM * FP)
        return C_BM_block, C_BM_block

    def HEAT(H):
        K = [2.0829, -0.9074, -0.0243]

        if 650 <= H <= 10750:
            logCpO = K[0] + K[1] * np.log10(H) + K[2] * np.log10(H) ** 2
            CpO_block = 10**logCpO
        elif H > 10750:
            H_ref = 10750
            logCpO_ref = K[0] + K[1] * np.log10(H_ref) + K[2] * np.log10(H_ref) ** 2
            CpO_ref = 10 ** (logCpO_ref)
            CpO_block = CpO_ref * (H / H_ref) ** 0.6
        else:
            H_ref = 650
            logCpO_ref = K[0] + K[1] * np.log10(H_ref) + K[2] * np.log10(H_ref) ** 2
            CpO_ref = 10 ** (logCpO_ref)
            CpO_block = CpO_ref * (H / H_ref) ** 0.6

        FM = 2.1
        FP = 1
        FT = 1
        C_BM_block = CpO_block * (FT * FP * FM)
        return C_BM_block, C_BM_block

    def COMP(P):
        K = [2.2897, 1.3604, -0.1027]

        if 450 <= P <= 3000:
            logCpO = K[0] + K[1] * np.log10(P) + K[2] * np.log10(P) ** 2
            CpO_block = 10**logCpO
        elif P > 3000:
            P_ref = 3000
            logCpO_ref = K[0] + K[1] * np.log10(P_ref) + K[2] * np.log10(P_ref) ** 2
            CpO_ref = 10 ** (logCpO_ref)
            CpO_block = CpO_ref * (P / P_ref) ** 0.6
        else:
            P_ref = 450
            logCpO_ref = K[0] + K[1] * np.log10(P_ref) + K[2] * np.log10(P_ref) ** 2
            CpO_ref = 10 ** (logCpO_ref)
            CpO_block = CpO_ref * (P / P_ref) ** 0.6

        FBM = 2.7
        C_BM_block = CpO_block * FBM
        return C_BM_block, C_BM_block

    def VESSEL(V):
        K = [3.5565, 0.3776, 0.0905]

        if 0.1 <= V <= 628:
            logCpO = K[0] + K[1] * np.log10(V) + K[2] * np.log10(V) ** 2
            CpO_block = 10**logCpO
        elif V > 628:
            V_ref = 628
            logCpO_ref = K[0] + K[1] * np.log10(V_ref) + K[2] * np.log10(V_ref) ** 2
            CpO_ref = 10 ** (logCpO_ref)
            CpO_block = CpO_ref * (V / V_ref) ** 0.6
        else:
            V_ref = 0.1
            logCpO_ref = K[0] + K[1] * np.log10(V_ref) + K[2] * np.log10(V_ref) ** 2
            CpO_ref = 10 ** (logCpO_ref)
            CpO_block = CpO_ref * (V / V_ref) ** 0.6

        FM = 1
        FP = 1
        C_BM_block = CpO_block * (1.49 + 1.52 * FM * FP)
        return C_BM_block, C_BM_block

    def MIXSETTLER(V):
        K = [4.7116, -0.5521, 0.0004]

        if 0.04 <= V <= 60:
            logCpO = K[0] + K[1] * np.log10(V) + K[2] * np.log10(V) ** 2
            CpO_block = 10**logCpO
        elif V > 60:
            V_ref = 60
            logCpO_ref = K[0] + K[1] * np.log10(V_ref) + K[2] * np.log10(V_ref) ** 2
            CpO_ref = 10 ** (logCpO_ref)
            CpO_block = CpO_ref * (V / V_ref) ** 0.6
        else:
            V_ref = 0.04
            logCpO_ref = K[0] + K[1] * np.log10(V_ref) + K[2] * np.log10(V_ref) ** 2
            CpO_ref = 10 ** (logCpO_ref)
            CpO_block = CpO_ref * (V / V_ref) ** 0.6

        FBM = 4.0
        C_BM_block = CpO_block * FBM
        return C_BM_block, C_BM_block

    @staticmethod
    def NE(flow_L_h: float, area_pond_km2: float) -> dict:
        int_rate_real = 0.07
        t_year = 20

        C_wells_ref = 19509202
        C_pond_ref = 170178239
        C_plant_ref = 160160000
        C_onsite_ref = 34668379
        C_offsite_ref = 54441218
        C_direct_ref = C_wells_ref + C_pond_ref + C_onsite_ref + C_offsite_ref
        C_indirect_ref = 48773004
        C_contingency_ref = 73159506

        CAPEX_ref = C_indirect_ref + C_contingency_ref + C_direct_ref

        area_pond_km2_ref = 11.4

        area_factor = area_pond_km2 / area_pond_km2_ref

        CAPEX_NE = CAPEX_ref * (area_factor) ** 0.8

        return {
            "CAPEX_NE": CAPEX_NE,
        }

    @staticmethod
    def SD(flow_L_h: float, area_pond_km2: float, SD_rate: float) -> dict:
        int_rate_real = 0.07
        t_year = 20

        area_km2 = max(0.0, area_pond_km2)

        C_wells_ref = 19509202
        C_pond_ref = 170178239
        C_plant_ref = 160160000
        C_onsite_ref = 34668379
        C_offsite_ref = 54441218
        C_direct_ref = C_wells_ref + C_pond_ref + C_onsite_ref + C_offsite_ref
        C_indirect_ref = 48773004
        C_contingency_ref = 73159506

        CAPEX_ref = C_indirect_ref + C_contingency_ref + C_direct_ref

        area_pond_km2_ref = 11.4

        area_factor = area_pond_km2 / area_pond_km2_ref

        CAPEX_SD_ev = area_km2 * 0.5 * 23.74 * 1000000
        CAPEX_SD = CAPEX_ref * (area_factor) ** 0.6 + CAPEX_SD_ev

        return {
            "CAPEX_SD": CAPEX_SD,
            "CAPEX_SD_ev": CAPEX_SD_ev,
        }

    @staticmethod
    def FO(
        flow_kg_s: float,
        rho_out_kg_m3: float,
        membrane_area_m2: float,
        feed_in_L_hr: float,
        dp_pump: float,
    ) -> dict:
        C_ref_mem = 56
        C_eq_mem = C_ref_mem * membrane_area_m2 * 800.8 / 816.0

        C_eq_pre = (
            0.1 * 996.0 * ((feed_in_L_hr * 0.001 * 8500 / 365) ** 0.8) * 800.8 / 797.9
        )

        C_eq_pump = (
            81 * (flow_kg_s * 3600 / rho_out_kg_m3 * dp_pump) ** 0.96 * 800.8 / 797.9
        )

        C_eq = C_eq_pre + C_eq_mem + C_eq_pump

        int_rate_real = 0.07
        t = 20

        C_install = C_eq * 0.10
        C_instru = C_eq * 0.025
        C_Piping = C_eq * 0.01
        C_elec = C_eq * 0.0
        C_build = C_eq * 0.0
        C_yard = C_eq * 0.0
        C_serv = C_eq * 0.10
        C_land = C_eq * 0.01

        C_direct = (
            C_eq
            + C_install
            + C_instru
            + C_Piping
            + C_elec
            + C_build
            + C_yard
            + C_serv
            + C_land
        )

        C_indirect = C_eq * 0.05
        C_contractor = C_eq * 0.03
        C_contingency = C_eq * 0.06

        CAP_FCI = C_direct + C_indirect + C_contractor + C_contingency
        CAP_SUC = CAP_FCI * 0.2
        CAP_WCI = CAP_FCI * 0.2

        CAP_TCI = CAP_FCI + CAP_SUC + CAP_WCI

        ann_factor = (int_rate_real * (1 + int_rate_real) ** t) / (
            (1 + int_rate_real) ** t - 1
        )
        CAP_EAC = CAP_TCI * ann_factor

        return {
            "C_eq_FO": C_eq,
            "C_eq_FO_pre": C_eq_pre,
            "C_eq_FO_mem": C_eq_mem,
            "C_eq_FO_pump": C_eq_pump,
            "C_install_FO": C_install,
            "C_instru_FO": C_instru,
            "C_Piping_FO": C_Piping,
            "C_elec_FO": C_elec,
            "C_build_FO": C_build,
            "C_yard_FO": C_yard,
            "C_serv_FO": C_serv,
            "C_land_FO": C_land,
            "C_direct_FO": C_direct,
            "C_indirect_FO": C_indirect,
            "CAP_FCI_FO": CAP_FCI,
            "CAP_SUC_FO": CAP_SUC,
            "CAP_WCI_FO": CAP_WCI,
            "CAP_TCI_FO": CAP_TCI,
            "CAP_EAC_FO": CAP_EAC,
        }

    @staticmethod
    def RO(
        Q_feed_m3_s: float,
        Q_pump_in_m3_s: float,
        Q_erd_in_m3_s: float,
        membrane_area_m2: float,
        dp_pump: float,
    ) -> dict:
        C_ref_mem = 10
        C_eq_mem = C_ref_mem * membrane_area_m2
        delta_P = dp_pump

        C_eq_pre = (
            0.1 * 996.0 * ((Q_feed_m3_s * 3600 * 8500 / 365) ** 0.8) * 800.8 / 797.9
        )

        C_eq_erd = 3134.7 * Q_erd_in_m3_s * 3600 * 800.8 / 708.8

        C_eq_pump = 81 * (Q_pump_in_m3_s * 3600 * delta_P) ** 0.96 * 800.8 / 797.9

        C_eq = C_eq_pre + C_eq_mem + C_eq_pump + C_eq_erd

        int_rate_real = 0.07
        t = 20

        C_install = C_eq * 0.10
        C_instru = C_eq * 0.025
        C_Piping = C_eq * 0.01
        C_elec = C_eq * 0.0
        C_build = C_eq * 0.0
        C_yard = C_eq * 0.0
        C_serv = C_eq * 0.10
        C_land = C_eq * 0.01

        C_direct = (
            C_eq
            + C_install
            + C_instru
            + C_Piping
            + C_elec
            + C_build
            + C_yard
            + C_serv
            + C_land
        )

        C_indirect = C_eq * 0.05
        C_contractor = C_eq * 0.03
        C_contingency = C_eq * 0.06

        CAP_FCI = C_direct + C_indirect + C_contractor + C_contingency
        CAP_SUC = CAP_FCI * 0.2
        CAP_WCI = CAP_FCI * 0.2

        CAP_TCI = CAP_FCI + CAP_SUC + CAP_WCI

        ann_factor = (int_rate_real * (1 + int_rate_real) ** t) / (
            (1 + int_rate_real) ** t - 1
        )
        CAP_EAC = CAP_TCI * ann_factor

        return {
            "C_eq_RO": C_eq,
            "C_eq_RO_pre": C_eq_pre,
            "C_eq_RO_mem": C_eq_mem,
            "C_eq_RO_pump": C_eq_pump,
            "C_eq_RO_erd": C_eq_pump,
            "C_install_RO": C_install,
            "C_instru_RO": C_instru,
            "C_Piping_RO": C_Piping,
            "C_elec_RO": C_elec,
            "C_build_RO": C_build,
            "C_yard_RO": C_yard,
            "C_serv_RO": C_serv,
            "C_land_RO": C_land,
            "C_direct_RO": C_direct,
            "C_indirect_RO": C_indirect,
            "CAP_FCI_RO": CAP_FCI,
            "CAP_SUC_RO": CAP_SUC,
            "CAP_WCI_RO": CAP_WCI,
            "CAP_TCI_RO": CAP_TCI,
            "CAP_EAC_RO": CAP_EAC,
        }

    @staticmethod
    def IX(
        Di_m: float,
        L_m: float,
        n_col: int = 1,
        operating_pressure_psig: float = 5.0,
        design_temp_F: float = 200.0,
        material: str = "carbon_steel",
        vertical: bool = True,
        weld_efficiency: float = 0.85,
        corrosion_allowance_in: float = 0.125,
        CE_target: float = 800.8,
        CE_base: float = 567.0,
    ) -> dict:
        def _ix_material_factor(material: str = "carbon_steel") -> float:
            material_map = {
                "carbon_steel": 1.0,
                "low_alloy_steel": 1.2,
                "ss304": 1.7,
                "ss316": 2.1,
                "carpenter_20cb3": 3.2,
                "nickel_200": 5.4,
                "monel_400": 3.6,
                "inconel_600": 3.9,
                "incoloy_825": 3.7,
                "titanium": 7.7,
            }
            if material not in material_map:
                raise ValueError(f"Unknown material: {material}")
            return material_map[material]

        def _ix_allowable_stress_psi(
            material: str = "carbon_steel", design_temp_F: float = 200.0
        ) -> float:
            if material == "low_alloy_steel":
                if design_temp_F <= 750:
                    return 15000.0
                elif design_temp_F <= 800:
                    return 14750.0
                elif design_temp_F <= 850:
                    return 14200.0
                else:
                    return 13100.0
            else:
                return 13750.0

        def _ix_design_pressure_psig(Po_psig: float) -> float:
            if Po_psig <= 10.0:
                return 10.0
            elif Po_psig <= 1000.0:
                x = math.log(Po_psig)
                return math.exp(0.60608 + 0.91615 * x + 0.0015655 * x * x)
            else:
                return 1.1 * Po_psig

        def _ix_min_wall_thickness_in(Di_ft: float) -> float:
            if Di_ft <= 4:
                return 0.25
            elif Di_ft <= 6:
                return 5.0 / 16.0
            elif Di_ft <= 8:
                return 3.0 / 8.0
            elif Di_ft <= 10:
                return 7.0 / 16.0
            elif Di_ft <= 12:
                return 0.50
            else:
                return 0.50

        def _ix_round_plate_thickness_in(t_in: float) -> float:
            if t_in <= 0.5:
                step = 1.0 / 16.0
            elif t_in <= 2.0:
                step = 1.0 / 8.0
            elif t_in <= 3.0:
                step = 1.0 / 4.0
            else:
                step = 1.0 / 4.0
            return math.ceil(t_in / step) * step

        if Di_m <= 0 or L_m <= 0 or n_col <= 0:
            return {
                "Di_m": Di_m,
                "L_m": L_m,
                "n_col": n_col,
                "t_shell_in": 0.0,
                "W_lb_each": 0.0,
                "CV_each_baseCE": 0.0,
                "CPL_each_baseCE": 0.0,
                "CP_each_targetCE": 0.0,
                "CP_total_targetCE": 0.0,
            }

        Di_in = Di_m * 39.3701
        L_in = L_m * 39.3701
        Di_ft = Di_m * 3.28084
        L_ft = L_m * 3.28084

        Pd = _ix_design_pressure_psig(operating_pressure_psig)
        S = _ix_allowable_stress_psi(material, design_temp_F)
        FM = _ix_material_factor(material)

        denom = 2.0 * S * weld_efficiency - 1.2 * Pd
        if denom <= 0:
            raise ValueError("Invalid thickness calculation: denominator <= 0")

        tp_in = Pd * Di_in / denom
        t_min_in = _ix_min_wall_thickness_in(Di_ft)
        t_no_corr_in = max(tp_in, t_min_in)
        t_req_in = t_no_corr_in + corrosion_allowance_in
        t_shell_in = _ix_round_plate_thickness_in(t_req_in)

        rho_lb_in3 = 0.284
        W_lb_each = (
            math.pi
            * (Di_in + t_shell_in)
            * (L_in + 0.8 * Di_in)
            * t_shell_in
            * rho_lb_in3
        )

        lnW = math.log(max(W_lb_each, 1.0))

        if vertical:
            CV_each = math.exp(7.1390 + 0.18255 * lnW + 0.02297 * lnW**2)
            CPL_each = 410.0 * (Di_ft**0.73960) * (L_ft**0.70684)
        else:
            CV_each = math.exp(5.6336 + 0.4599 * lnW + 0.00582 * lnW**2)
            CPL_each = 2275.0 * (Di_ft**0.2094)

        CP_each_target = (CE_target / CE_base) * (FM * CV_each + CPL_each)
        CP_total_target = CP_each_target * n_col

        return {
            "Di_m": Di_m,
            "L_m": L_m,
            "n_col": n_col,
            "Pd_psig": Pd,
            "S_psi": S,
            "FM": FM,
            "t_pressure_only_in": tp_in,
            "t_min_in": t_min_in,
            "t_req_in": t_req_in,
            "t_shell_in": t_shell_in,
            "W_lb_each": W_lb_each,
            "CV_each_baseCE": CV_each,
            "CPL_each_baseCE": CPL_each,
            "CP_each_targetCE": CP_each_target,
            "CP_total_targetCE": CP_total_target,
        }


class Opex:
    @staticmethod
    def set_lake(lake_name: str):
        global _CURRENT_LAKE
        if lake_name in COUNTRY_PARAM:
            _CURRENT_LAKE = lake_name
        else:
            print(f"[WARN] Unknown lake '{lake_name}', fallback to 'DEFAULT'")
            _CURRENT_LAKE = "DEFAULT"

    @staticmethod
    def _get_param():
        return COUNTRY_PARAM.get(_CURRENT_LAKE, COUNTRY_PARAM["DEFAULT"])

    @staticmethod
    def elec(elec_use_kwh: float) -> float:
        p = Opex._get_param()
        return elec_use_kwh * p["elec_base"]

    @staticmethod
    def steam(steam_use_kg: float) -> float:
        p = Opex._get_param()
        return steam_use_kg * p["steam_base"]

    @staticmethod
    def heat(heat_use_mj: float, year: int = BASELINE_HEAT_YEAR) -> float:
        p = Opex._get_param()
        heater_use_kwh = heater_electricity_kwh(heat_use_mj)
        return heater_use_kwh * p["elec_base"]

    @staticmethod
    def cooling(cooling_use_m3: float) -> float:
        cooling_cost = 0.0343
        return cooling_use_m3 * cooling_cost

    @staticmethod
    def NAOH(amount_kg: float) -> float:
        cost_NAOH = 0.32
        return amount_kg * cost_NAOH

    @staticmethod
    def NACL(amount_kg: float) -> float:
        cost_NACL = 0.025
        return amount_kg * cost_NACL

    @staticmethod
    def NA2CO3(amount_kg: float) -> float:
        cost_NA2CO3 = 0.154
        return amount_kg * cost_NA2CO3

    @staticmethod
    def CACO3(amount_kg: float) -> float:
        cost_CACO3 = 0.3
        return amount_kg * cost_CACO3

    @staticmethod
    def MGOH2(amount_kg: float) -> float:
        cost_MGOH2 = 0.773
        return amount_kg * cost_MGOH2

    @staticmethod
    def DILUENT(amount_kg: float) -> float:
        cost_DILUENT = 5
        return amount_kg * cost_DILUENT

    @staticmethod
    def TBP(amount_kg: float) -> float:
        cost_TBP = 6
        return amount_kg * cost_TBP

    @staticmethod
    def FECL3(amount_kg: float) -> float:
        cost_FECL3 = 0.402
        return amount_kg * cost_FECL3

    @staticmethod
    def HCL(amount_kg: float) -> float:
        cost_HCL = 0.0162
        return amount_kg * cost_HCL

    @staticmethod
    def MGCL2(amount_kg: float) -> float:
        cost_MGCL2 = 0.09
        return amount_kg * cost_MGCL2

    @staticmethod
    def WATER(amount_kg: float) -> float:
        cost_freshwater = 0.000065
        return amount_kg * cost_freshwater

    @staticmethod
    def WASTE(amount_kg: float) -> float:
        cost_wastewater = 0.00019
        return amount_kg * cost_wastewater

    @staticmethod
    def RESIN(amount_kg: float) -> float:
        unit_cost = 6.0
        return amount_kg * unit_cost

    @staticmethod
    def labor(Np: int, Nnp: int) -> float:
        N_OL = 4.5 * (6.29 + 31.7 * Np + 0.23 * Nnp) ** 0.5
        C_labor = LABOR_WAGE.get(_CURRENT_LAKE, LABOR_WAGE["DEFAULT"])
        return C_labor * N_OL

    @staticmethod
    def maintenence(total_capex: float) -> float:
        return total_capex * 2.75 / 100.0

    @staticmethod
    def transport(m_nh3_kg: float, d_km: float) -> float:
        cost = 5e-6 * d_km + 0.015
        return m_nh3_kg * cost

    @staticmethod
    def carbon_from_elec(elec_use_kwh: float) -> float:
        p = Opex._get_param()

        co2_ton = elec_use_kwh * (p["elec_ef"] / 1000.0)
        return co2_ton * p["carbon_tax"]

    @staticmethod
    def carbon_from_steam(steam_use_kwh: float) -> float:
        p = Opex._get_param()
        co2_ton = steam_use_kwh * (p["steam_ef"] / 1000.0)
        return co2_ton * p["carbon_tax"]

    @staticmethod
    def carbon_from_heat(heat_use_mj: float) -> float:
        p = Opex._get_param()
        co2_ton = float(heat_use_mj) * HEAT_CO2_FACTOR_T_PER_MJ
        return co2_ton * p["carbon_tax"]

    @staticmethod
    def NE(area_pond_km2: float) -> dict:
        p = Opex._get_param()
        price_elec = p["elec_base"]

        C_main_ref = 5250000
        C_energy_ref = 6885358
        C_labor_ref = 4150000
        C_supply_ref = 10625000
        C_GA_ref = 2145000

        area_pond_km2_ref = 11.4

        area_factor = area_pond_km2 / area_pond_km2_ref

        OPEX_elec = C_energy_ref / 0.13 * price_elec * area_factor

        OPEX_other = (C_labor_ref + C_main_ref + C_GA_ref + C_supply_ref) * area_factor
        OPEX_NE = OPEX_other + OPEX_elec

        material_cost = 0.0

        return {
            "OPEX_NE": OPEX_NE,
            "OPEX_NE_elec": OPEX_elec,
            "OPEX_other": OPEX_other,
        }

    @staticmethod
    def SD(area_pond_km2: float, freshwater_SD_kg_year: float) -> dict:
        p = Opex._get_param()
        price_elec = p["elec_base"]

        C_main_ref = 5250000
        C_energy_ref = 6885358
        C_labor_ref = 4150000
        C_supply_ref = 10625000
        C_GA_ref = 2145000

        area_pond_km2_ref = 11.4

        area_factor = area_pond_km2 / area_pond_km2_ref

        OPEX_elec = C_energy_ref / 0.13 * price_elec * area_factor

        OPEX_other = (C_labor_ref + C_main_ref + C_GA_ref + C_supply_ref) * area_factor

        OPEX_SD_ev = area_pond_km2 * 0.5 * 0.2 * 23.74 * 1000000
        OPEX_SD = OPEX_other + OPEX_elec + OPEX_SD_ev

        freshwater_profit = 0.0
        if freshwater_SD_kg_year > 0.0:
            freshwater_cost = Opex.WATER(freshwater_SD_kg_year)
            freshwater_profit = -freshwater_cost

        return {
            "OPEX_SD": OPEX_SD,
            "OPEX_SD_elec": OPEX_elec,
            "OPEX_SD_material": OPEX_SD_ev,
            "OPEX_SD_other": OPEX_other,
            "PROFIT_SD_freshwater": freshwater_profit,
        }

    @staticmethod
    def FO(
        flow_L_hr: float,
        net_power_kW: float,
        NaCl: float,
        rho_in: float,
        membrane_area_m2: float,
        op_time_hour: int = 8500,
    ) -> dict:
        p = Opex._get_param()
        price_elec = p["elec_base"]

        flow_m3_hr = flow_L_hr / rho_in

        elec_use_kwh = net_power_kW * op_time_hour

        C_mem_elec = elec_use_kwh * price_elec

        C_mem_replace = membrane_area_m2 * 56.0 * 0.25 * 800.8 / 816.0

        C_NaCl = Opex.NACL(NaCl)

        C_carbon = Opex.carbon_from_elec(elec_use_kwh)

        OPEX_FO_total = C_mem_elec + C_mem_replace + C_carbon + C_NaCl

        return {
            "OPEX_FO_elec": C_mem_elec,
            "OPEX_FO_replace": C_mem_replace,
            "OPEX_FO_carbon": C_carbon,
            "OPEX_FO_NaCl": C_NaCl,
            "OPEX_FO_total": OPEX_FO_total,
        }

    @staticmethod
    def RO(
        net_power_kW: float,
        membrane_area_m2: float,
        freshwater_kg_s: float,
        op_time_hour: int = 8500,
    ) -> dict:
        p = Opex._get_param()
        price_elec = p["elec_base"]

        elec_use_kwh = net_power_kW * op_time_hour

        C_mem_elec = elec_use_kwh * price_elec

        C_mem_replace = membrane_area_m2 * 10.0 * 0.15

        C_carbon = Opex.carbon_from_elec(elec_use_kwh)

        if freshwater_kg_s > 0.0:
            freshwater_cost = Opex.WATER(freshwater_kg_s * 3600 * 8500)
            freshwater_profit = -freshwater_cost

        OPEX_RO_total = C_mem_elec + C_mem_replace + C_carbon

        return {
            "OPEX_RO_elec": C_mem_elec,
            "OPEX_RO_replace": C_mem_replace,
            "OPEX_RO_carbon": C_carbon,
            "OPEX_RO_total": OPEX_RO_total,
            "PROFIT_RO_freshwater": freshwater_profit,
        }

    @staticmethod
    def get_param_copy():
        return copy.deepcopy(Opex._get_param())

    @staticmethod
    def set_param_dict(new_param: dict):
        cur = Opex._get_param()
        cur.clear()
        cur.update(copy.deepcopy(new_param))
