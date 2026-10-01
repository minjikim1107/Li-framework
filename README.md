# Lithium-recovery TEA reproducibility package

This package contains the economic calculation, Monte Carlo analysis, and tabular sensitivity analyses used for the manuscript. It does not contain Aspen models, Aspen extraction scripts, LCA calculations, or figure-generation code.

## Environment

Tested with Python 3.13.5 and the versions in `requirements.txt`. Install with `python -m pip install -r requirements.txt`.

## Inputs and outputs

`TEA/EXCEL/{Atacama,Zabuye,Uyuni,GSL}/` contains 11 pathway input workbooks per lake (44 total). These are fixed process-model outputs; the scripts do not rerun Aspen or the mathematical unit-process models.

`TEA/TEA_code/TEA_result.xlsx` and `TEA/TEA_code/analysis_results/` contain the current deterministic baseline and pathway detail workbooks. They are included so the post-processing analyses can also be run directly. Running `TEA.py` regenerates them from the 44 inputs.

Other generated tables are not bundled; each analysis writes its own outputs when run.

Run any script directly with the VS Code Python Run button or from a shell. Paths are resolved from each script, not from the shell working directory.

| Script                                                          | Purpose                                                                                                        | Output                                     |
| --------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------- | ------------------------------------------ |
| `TEA/TEA_code/TEA.py`                                         | Deterministic pathway TEA                                                                                      | `TEA_result.xlsx`, `analysis_results/` |
| `TEA/TEA_code/MC.py`                                          | Monte Carlo draws, LCOL statistics, ranks, and variable impacts including PRCC                                 | `MC/MC_draws.csv`, `MC/MC_result.xlsx` |
| `TEA/TEA_code/Sensitivity.py`                                 | Full signed ΔLCOL/PRCC table and manuscript-selected sensitivity table; runs`MC.py` first if no draws exist | `sensitivity_results/`                   |
| `TEA/TEA_code/TEA_scenario_analysis.py`                       | 2020–2050 electricity-mix and maturity scenarios                                                              | `scenario_results/`                      |
| `TEA/TEA_code/capacity_analysis/Capacity_analysis.py`         | 10/~20/40 kt/y nominal-input capacity sensitivity                                                              | `capacity_analysis/`                     |
| `TEA/TEA_code/Byproduct_analysis/Byproduct_analysis.py`       | Freshwater/by-product credit robustness                                                                        | `Byproduct_analysis/`                    |
| `TEA/TEA_code/labor_cost_comparison/labor_cost_comparison.py` | Fixed versus lake-specific operator wage comparison                                                            | `labor_cost_comparison/`                 |

`Economic.py`, `heat_price_mapping.py`, and `project_paths.py` are shared calculation/configuration modules; they are imported by the executable scripts.

Recommended order for a complete regeneration: `TEA.py`, `MC.py`, `Sensitivity.py`, followed by the independent scenario, capacity, credit, and labor analyses. The default Monte Carlo run uses 3,000 draws per lake and produces large files; generated MC files are intentionally not bundled with the source package.

Internal identifiers such as `RESIN` and `mult_price_RESIN` are retained to preserve the calculation/data interface. Manuscript-facing sensitivity labels use “sorbent”.
