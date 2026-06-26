# OpenIrri — Sprinkler System Design

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.20052019.svg)](https://doi.org/10.5281/zenodo.20052019)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/)
[![Streamlit](https://img.shields.io/badge/built%20with-Streamlit-ff4b4b.svg)](https://streamlit.io)

> Open-source companion software to a SoftwareX article.
> An end-to-end, browser-based decision-support tool for the design of
> pressurised solid-set sprinkler irrigation systems.

**Live web application (no installation required):**
👉 <https://sprinkler-system-design.streamlit.app/>

## Features

- Reference and crop evapotranspiration following FAO-56 (Penman–Monteith).
- Sprinkler selection from a parameterised catalogue with overlap and
  uniformity diagnostics.
- Operational design module (irrigation interval, set time, application rate,
  automatic field subdivision into subplots).
- Interactive pipe-network layout on a graph-paper canvas with grid snapping,
  angle and length constraints, and automatic valve placement.
- Hydraulic design with Hazen–Williams friction losses, Christiansen
  multi-outlet F-factor correction, per-segment pipe sizing and head-loss
  propagation.
- Pump selection and duty-point matching against an editable pump database.
- Automatic Bill-of-Quantities aggregation and cost estimation.
- DXF / Excel / PDF report export.
- Optional cloud project storage via Google Earth Engine assets.

## Documentation

A complete user manual covering every module, with screenshots and an
engineering-formula appendix, is provided as **Supplementary Data S4** of the
SoftwareX article (50 tables, 12 sections + 4 appendices).

## Quick start (local installation)

```bash
git clone https://github.com/El-Naggar8876/pyirri.git
cd pyirri
python -m venv .venv
# Windows PowerShell:
.\.venv\Scripts\Activate.ps1
# macOS / Linux:
# source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

The application opens in your default browser at <http://localhost:8501>.
No login is required.

### Docker

```bash
docker build -t pyirri .
docker run --rm -p 8501:8501 pyirri
```

## Optional: Google Earth Engine cloud storage

Project documents can optionally be persisted to Google Earth Engine assets.
The application runs without this feature.

To enable it, **each user must supply their own Google Cloud credentials**:

1. Create a Google Cloud project and a service account with the
   *Earth Engine Resource Admin* role.
2. Enable the Earth Engine API for that project.
3. Copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml` and
   paste your own project id, service-account email and PEM private key.
4. Restart the application.

Credentials are **never** committed: the populated `secrets.toml` is
git-ignored.

## Repository layout

```
.
├── app.py                # Streamlit entry-point
├── modules/              # Engineering and UI modules
├── components/           # Reusable UI helpers
├── config/               # Theme and runtime configuration
├── pump_database_seed.json
├── requirements.txt
├── Dockerfile
├── CITATION.cff
├── LICENSE
└── README.md
```

## Reproducing the SoftwareX case study

The illustrative wheat case study reported in Section 4 of the SoftwareX
article can be reproduced from the project-state snapshot supplied as
**Supplementary Data S1** (`Supplementary_Data_S1_OpenIrri_CaseStudy_Wheat.json`).
Step-by-step instructions are given in **Supplementary Data S2**
(*Reproduction Guide*) and an independent FAO-56 hand calculation that
validates the principal water-balance numbers is provided as
**Supplementary Data S3**.

## How to cite

Please cite both the SoftwareX article and the archived software release
(see [CITATION.cff](CITATION.cff)):

> El-Naggar, A.G. (2026). *OpenIrri: an open-source Python platform for solid-set
> sprinkler irrigation system design.* SoftwareX (in review).

> El-Naggar, A.G. (2026). *OpenIrri — an open-source web application for the
> design of solid-set sprinkler irrigation systems* (v1.0.2). Zenodo.
> <https://doi.org/10.5281/zenodo.20052019>

## Testing and validation

```bash
pip install -r requirements.txt -r requirements-dev.txt
pytest tests/ --cov=modules                  # regression & edge-case tests
python validation/hydraulic_benchmark.py     # EPANET 2.2 cross-check
```

The hydraulic engine is cross-checked against the official US-EPA EPANET 2.2
solver; see [`validation/`](validation/) and [`ARCHITECTURE.md`](ARCHITECTURE.md).

## License

Released under the [MIT License](LICENSE).

## Contact

A.G. El-Naggar — <a.elnaggar@un-ihe.org>
Land and Water Management Department, IHE Delft Institute for Water Education,
Delft, The Netherlands.
