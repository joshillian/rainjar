# Rainjar

A local rainfall monitoring dashboard built with Streamlit. Track precipitation across multiple US locations with current conditions, forecasts, radar data, and historical trends.

## Features

- **Current conditions** — live weather via Open-Meteo
- **MRMS radar precipitation** — high-resolution daily totals from Iowa State Mesonet
- **14-day forecast** — precipitation amounts and probability
- **Historical analysis** — monthly/yearly totals with trend lines (configurable 1-10 years)
- **Year vs normal** — compare current year rainfall against climatological averages
- **Multi-location** — monitor multiple zip codes in tabbed views

## Setup

```bash
pip install -r requirements.txt
```

## Usage

```bash
streamlit run app.py
```

Edit `config.py` to add or remove monitored locations:

```python
ZIP_CODES = {
    "76524": "Eddy, TX",
    "50613": "Cedar Falls, IA",
    "59715": "Bozeman, MT",
}
```

## Data Sources

- [Open-Meteo](https://open-meteo.com/) — current conditions, forecasts, and historical archives
- [Iowa State Mesonet](https://mesonet.agron.iastate.edu/) — MRMS radar-derived precipitation
