"""Fetch weather data from Open-Meteo and MRMS via Iowa State Mesonet."""

from datetime import date, datetime, timedelta
import requests
import pandas as pd
import pgeocode


def zip_to_coords(zip_code: str) -> tuple[float, float]:
    """Convert US zip code to (latitude, longitude)."""
    nomi = pgeocode.Nominatim("us")
    result = nomi.query_postal_code(zip_code)
    if pd.isna(result.latitude):
        raise ValueError(f"Unknown zip code: {zip_code}")
    return round(result.latitude, 4), round(result.longitude, 4)


def fetch_current(lat: float, lon: float) -> dict:
    """Fetch current conditions + 14-day forecast from Open-Meteo."""
    resp = requests.get(
        "https://api.open-meteo.com/v1/forecast",
        params={
            "latitude": lat,
            "longitude": lon,
            "daily": "precipitation_sum,temperature_2m_max,temperature_2m_min,precipitation_probability_max",
            "current": "temperature_2m,relative_humidity_2m,precipitation,weather_code",
            "timezone": "auto",
            "forecast_days": 14,
        },
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


# --- MRMS via Iowa State Mesonet (radar-derived, ~1km resolution) ---

def fetch_mrms_daily(lat: float, lon: float, day: date) -> dict:
    """Fetch MRMS precipitation for a single day at a point."""
    url = f"https://mesonet.agron.iastate.edu/iemre/daily/{day.isoformat()}/{lat}/{lon}/json"
    resp = requests.get(url, timeout=15)
    resp.raise_for_status()
    return resp.json()["data"][0]


def fetch_mrms_range(lat: float, lon: float, start: date, end: date) -> list[dict]:
    """Fetch MRMS precipitation for a date range at a point."""
    url = (
        f"https://mesonet.agron.iastate.edu/iemre/multiday/"
        f"{start.isoformat()}/{end.isoformat()}/{lat}/{lon}/json"
    )
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    return resp.json()["data"]


def fetch_mrms_recent(lat: float, lon: float, days: int = 7) -> pd.DataFrame:
    """Fetch last N days of MRMS precipitation for a point."""
    end = date.today() - timedelta(days=1)  # yesterday (today may be incomplete)
    start = end - timedelta(days=days - 1)
    records = fetch_mrms_range(lat, lon, start, end)
    df = pd.DataFrame(records)
    df["date"] = pd.to_datetime(df["date"])
    return df


def fetch_historical(lat: float, lon: float, years: int = 5) -> pd.DataFrame:
    """Fetch daily historical precipitation for the last N years."""
    end = date.today() - timedelta(days=1)
    start = date(end.year - years, end.month, end.day)

    resp = requests.get(
        "https://archive-api.open-meteo.com/v1/archive",
        params={
            "latitude": lat,
            "longitude": lon,
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "daily": "precipitation_sum,temperature_2m_max,temperature_2m_min",
            "timezone": "auto",
        },
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()["daily"]
    df = pd.DataFrame(data)
    df["time"] = pd.to_datetime(df["time"])
    return df


def monthly_totals(df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate daily data into monthly precipitation totals."""
    df = df.copy()
    df["year"] = df["time"].dt.year
    df["month"] = df["time"].dt.month
    grouped = df.groupby(["year", "month"]).agg(
        precipitation_mm=("precipitation_sum", "sum"),
        avg_high_c=("temperature_2m_max", "mean"),
        avg_low_c=("temperature_2m_min", "mean"),
    ).reset_index()
    grouped["precipitation_in"] = grouped["precipitation_mm"] / 25.4
    return grouped


def yearly_totals(df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate daily data into yearly precipitation totals."""
    df = df.copy()
    df["year"] = df["time"].dt.year
    grouped = df.groupby("year").agg(
        precipitation_mm=("precipitation_sum", "sum"),
    ).reset_index()
    grouped["precipitation_in"] = grouped["precipitation_mm"] / 25.4
    return grouped


def monthly_normals(df: pd.DataFrame) -> pd.DataFrame:
    """Compute average monthly precipitation across all years (climatological normals)."""
    df = df.copy()
    df["month"] = df["time"].dt.month
    normals = df.groupby("month").agg(
        avg_precip_mm=("precipitation_sum", "mean"),
    ).reset_index()
    # mean of daily precip * ~30.4 days gives monthly average
    # But better: sum per month per year, then average across years
    df["year"] = df["time"].dt.year
    monthly = df.groupby(["year", "month"])["precipitation_sum"].sum().reset_index()
    normals = monthly.groupby("month")["precipitation_sum"].mean().reset_index()
    normals.columns = ["month", "avg_monthly_precip_mm"]
    normals["avg_monthly_precip_in"] = normals["avg_monthly_precip_mm"] / 25.4
    return normals
