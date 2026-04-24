# Sprinkler Irrigation Design

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/)
[![Streamlit](https://img.shields.io/badge/built%20with-Streamlit-ff4b4b.svg)](https://streamlit.io)

> Open-source companion software to a SoftwareX article.
> An end-to-end, browser-based decision-support tool for the design of
> pressurised sprinkler irrigation systems.

## Features

- Reference and crop evapotranspiration following FAO-56 (Penman–Monteith).
- Sprinkler selection from a parameterised catalogue with overlap and
  uniformity diagnostics.
- Operational-design module (set time, number of sets, application rate).
- Interactive pipe-network layout on a graph-paper canvas with snapping,
  angle and length constraints.
- Hydraulic design with Hazen–Williams / Darcy–Weisbach friction losses,
  per-segment pipe sizing, and head-loss propagation.
- Pump selection and duty-point matching against a pump database.
- Bill of quantities and cost estimation.
- DXF / Excel / PDF report export.
- Optional cloud project storage via Google Earth Engine assets.

## Quick start

### Local

```bash
git clone https://github.com/TODO/sprinkler-design-softwarex.git
cd sprinkler-design-softwarex
python -m venv .venv
.\.venv\Scripts\Activate.ps1   # Windows PowerShell
pip install -r requirements.txt
streamlit run app.py
```

The application opens in your default browser at <http://localhost:8501>.
No login is required.

### Docker

```bash
docker build -t sprinkler-design-softwarex .
docker run --rm -p 8501:8501 sprinkler-design-softwarex
```

## Optional: Google Earth Engine cloud storage

Project documents can be persisted to Google Earth Engine assets under
`projects/<project>/assets/SprinklerDesignSoftwareX`.  This feature is fully
optional — the application runs without it.

1. Create a Google Cloud project and a service account with the
   *Earth Engine Resource Admin* role.
2. Enable the Earth Engine API.
3. Copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml` and
   paste the project id, service-account email and PEM private key.
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
├── sample_data/          # Example inputs reproducing the figures
├── docs/                 # Methods notes and figure briefs
├── requirements.txt
├── Dockerfile
├── CITATION.cff
├── LICENSE
└── README.md
```

## Reproducing the figures in the paper

The `sample_data/` folder contains an example project (climate, crop,
sprinkler catalogue, field geometry) that reproduces every numerical figure
reported in the SoftwareX article.  See [docs/REPRODUCIBILITY.md](docs/REPRODUCIBILITY.md).

## How to cite

If you use this software in academic work, please cite the SoftwareX article
listed in [CITATION.cff](CITATION.cff).  After acceptance, this README will
display a Zenodo DOI badge minted from the GitHub Release.

## License

Released under the [MIT License](LICENSE).
