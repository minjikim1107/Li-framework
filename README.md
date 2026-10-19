<img width="2362" height="723" alt="image" src="https://github.com/user-attachments/assets/8d07f31d-cf45-42be-8a82-6e3c03215dab" /># Lithium-recovery TEA reproducibility package

# Lithium-recovery TEA reproducibility package

This repository provides the Python source code and fixed process-simulation output workbooks used for pathway-level techno-economic analysis (TEA), Monte Carlo uncertainty analysis, sensitivity analysis, capacity analysis, freshwater/by-product credit analysis, labor-cost comparison, and future electricity/maturity scenarios.

It is a source-code package, not a compiled standalone application. Aspen models, Aspen data-extraction scripts, mathematical unit-process models, life-cycle assessment (LCA) calculations, and figure-generation code are not included. The supplied workbooks are already-generated unit-process outputs; this package does not rerun the process simulations.

## System requirements

- **Reference environment:** 64-bit Windows 11; Python 3.13.5.
- **Python dependencies:** pinned in [`requirements.txt`](requirements.txt): NumPy 2.2.5, pandas 2.3.0, openpyxl 3.1.5, and XlsxWriter 3.2.9.
- **Hardware:** an ordinary desktop or laptop is sufficient. No GPU, cluster, Aspen license, or other non-standard hardware is required to run the analyses with the supplied workbooks. Aspen is needed only if you independently want to regenerate Aspen process-simulation outputs.
- **Other operating systems:** the scripts use Python and repository-relative paths, but macOS and Linux have not been validated for this release.
- **Excel:** Microsoft Excel is not required; Excel files are read and written through the listed Python packages.

The project was tested with Python 3.13.5 and the dependency versions listed above. Use the repository root as the working directory for the commands below. Script paths are also resolved relative to the scripts, so they do not depend on the shell's current directory.

## Installation

Install Python 3.13.5 (64-bit), then open a terminal in the repository root and create an isolated environment.

### Windows PowerShell

```powershell
python --version
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

If PowerShell does not allow environment activation, call the environment's Python directly:

```powershell
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

### macOS or Linux (not validated for this release)

```bash
python3.13 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

**Typical installation time:** approximately 2–10 minutes on a normal desktop with a stable internet connection. This is an estimate; download speed and the existing Python/pip setup affect the time.

## Bundled data

`TEA/EXCEL/` contains 44 Excel workbooks: 11 pathways for each of four brine locations (`Atacama`, `Zabuye`, `Uyuni`, and `GSL`). These are fixed unit-process simulation outputs used as TEA inputs. They are sufficient to run the analyses in this repository, but they are not raw Aspen files or the source code for the unit-process models.

Each workbook contains one worksheet per technology in that pathway. For example, `NE_prep_carb.xlsx` contains `NE`, `PREP`, and `CARB` worksheets. The bundled workbooks should be treated as templates for the expected worksheet names, column names, and data layout.

## Quick demo

Run the deterministic TEA for all 44 bundled pathway/location combinations from the repository root:

```bash
python TEA/TEA_code/TEA.py
```

In VS Code, open the repository root, select the Python 3.13.5 environment created above, open `TEA/TEA_code/TEA.py`, and choose **Run Python File**.

The script reads the workbooks under `TEA/EXCEL/` and writes:

- `TEA/TEA_code/TEA_result.xlsx` — deterministic summary for all lakes and pathways.
- `TEA/TEA_code/analysis_results/` — lake/pathway detail workbooks and the combined pathway summary.

The deterministic demo is expected to take approximately 1–3 minutes on a typical desktop. This is a planning estimate rather than a guaranteed benchmark; spreadsheet storage speed and computer performance can change the runtime. The script regenerates these output files, so copy any outputs you want to preserve before running it.

## Running the analyses

Run commands from the repository root. Each script can also be launched directly with the VS Code Python Run button.

| Script                                                          | Analysis                                                                            | Main output location                                                 |
| --------------------------------------------------------------- | ----------------------------------------------------------------------------------- | -------------------------------------------------------------------- |
| `TEA/TEA_code/TEA.py`                                         | Deterministic pathway TEA                                                           | `TEA/TEA_code/TEA_result.xlsx`, `TEA/TEA_code/analysis_results/` |
| `TEA/TEA_code/MC.py`                                          | Monte Carlo LCOL draws, statistics, rankings, and variable impacts (including PRCC) | `TEA/TEA_code/MC/MC_draws.csv`, `TEA/TEA_code/MC/MC_result.xlsx` |
| `TEA/TEA_code/Sensitivity.py`                                 | Full signed ΔLCOL/PRCC results and the selected-variable table                     | `TEA/TEA_code/sensitivity_results/`                                |
| `TEA/TEA_code/TEA_scenario_analysis.py`                       | 2020–2050 electricity-mix and technology-maturity scenarios                        | `TEA/TEA_code/scenario_results/`                                   |
| `TEA/TEA_code/capacity_analysis/Capacity_analysis.py`         | 10, approximately 20 (baseline), and 40 kt/y nominal-input capacity cases           | `TEA/TEA_code/capacity_analysis/`                                  |
| `TEA/TEA_code/Byproduct_analysis/Byproduct_analysis.py`       | Freshwater/by-product credit robustness                                             | `TEA/TEA_code/Byproduct_analysis/`                                 |
| `TEA/TEA_code/labor_cost_comparison/labor_cost_comparison.py` | Fixed versus location-specific operator wage comparison                             | `TEA/TEA_code/labor_cost_comparison/`                              |

To regenerate the quantitative analyses in sequence, run:

```bash
python TEA/TEA_code/TEA.py
python TEA/TEA_code/MC.py
python TEA/TEA_code/Sensitivity.py
python TEA/TEA_code/TEA_scenario_analysis.py
python TEA/TEA_code/capacity_analysis/Capacity_analysis.py
python TEA/TEA_code/Byproduct_analysis/Byproduct_analysis.py
python TEA/TEA_code/labor_cost_comparison/labor_cost_comparison.py
```

The Monte Carlo default is 3,000 draws per lake. It takes substantially longer than the deterministic demo and writes large output files. `Sensitivity.py` uses the Monte Carlo draws; if the required draws are not present, it runs the Monte Carlo calculation first. Scenario, capacity, credit, and labor analyses can also be run independently after the deterministic baseline has been generated.

## Using your own process-simulation outputs

The analyses expect process-simulation outputs in the same workbook structure as the supplied files. To use different process outputs for one of the supported locations:

1. Generate or obtain the unit-process outputs separately; Aspen and mathematical unit-process models are outside this repository.
2. Replace the corresponding workbook(s) in `TEA/EXCEL/<location>/`, retaining the expected pathway filenames and worksheet names. For example, `TEA/EXCEL/Atacama/NE_prep_carb.xlsx` must contain `NE`, `PREP`, and `CARB` worksheets.
3. Preserve the input column names, units, and data layout of the matching bundled workbook. Use it as the schema template; the TEA code reads named fields from these sheets.
4. Run `python TEA/TEA_code/TEA.py` to regenerate the deterministic results, followed by the desired analyses.

The four location identifiers currently supported are `Atacama`, `Zabuye`, `Uyuni`, and `GSL`. Adding a new lake or country is not a data-only operation: its location-specific economic assumptions and the analysis location lists must also be configured and validated in the code.

## Reproducibility notes

- `TEA/TEA_code/Economic.py`, `heat_price_mapping.py`, and `project_paths.py` provide shared economic calculations, energy-price mappings, and paths; executable analyses import them.
- For MVR pathways, only the residual external heater duty (`MVR_heat`) is costed as auxiliary electric heating. `E_heater = Q_external / (3.6 × 0.99)` kWh and `Heat_OPEX = E_heater × electricity price`. Future electricity-mix cases derive heat price from the corresponding electricity price. MED steam pricing and the existing heat-emissions factor (`0.0000623 t CO₂/MJ-heat`) are unchanged.
- The fixed Monte Carlo seed and draw count are defined in `TEA/TEA_code/MC.py`. The generated Monte Carlo outputs are not bundled; running the script recreates them.
- Internal identifiers such as `RESIN` and `mult_price_RESIN` are retained to preserve the calculation/data interface. Manuscript-facing sensitivity labels use “sorbent.”
