"""Raindrop — local rainfall monitor dashboard."""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import date, timedelta
import numpy as np

from config import ZIP_CODES
from weather import (
    zip_to_coords,
    fetch_current,
    fetch_mrms_daily,
    fetch_mrms_recent,
    fetch_historical,
    monthly_totals,
    yearly_totals,
    monthly_normals,
)

st.set_page_config(page_title="Raindrop", page_icon="🌧️", layout="wide")
st.title("🌧️ Raindrop — Rainfall Monitor")

MONTH_NAMES = [
    "", "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
]

WMO_CODES = {
    0: "Clear", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
    45: "Foggy", 48: "Rime fog", 51: "Light drizzle", 53: "Drizzle",
    55: "Heavy drizzle", 61: "Light rain", 63: "Rain", 65: "Heavy rain",
    71: "Light snow", 73: "Snow", 75: "Heavy snow", 77: "Snow grains",
    80: "Light showers", 81: "Showers", 82: "Heavy showers",
    85: "Light snow showers", 86: "Snow showers",
    95: "Thunderstorm", 96: "Thunderstorm + hail", 99: "Thunderstorm + heavy hail",
}


def mm_to_in(mm):
    if mm is None:
        return 0.0
    return mm / 25.4


@st.cache_data(ttl=900)  # cache 15 min
def load_current(zip_code):
    lat, lon = zip_to_coords(zip_code)
    return fetch_current(lat, lon), lat, lon


@st.cache_data(ttl=900)
def load_mrms(zip_code):
    lat, lon = zip_to_coords(zip_code)
    yesterday = date.today() - timedelta(days=1)
    daily = fetch_mrms_daily(lat, lon, yesterday)
    recent = fetch_mrms_recent(lat, lon, days=30)
    return daily, recent


@st.cache_data(ttl=3600)  # cache 1 hour
def load_historical(zip_code, years):
    lat, lon = zip_to_coords(zip_code)
    return fetch_historical(lat, lon, years)


# --- Sidebar ---
st.sidebar.header("Settings")
history_years = st.sidebar.slider("Years of history", 1, 10, 5)

st.sidebar.markdown("---")
st.sidebar.markdown("**Monitored Locations**")
for zc, label in ZIP_CODES.items():
    st.sidebar.markdown(f"- {label} ({zc})")
st.sidebar.markdown("_Edit `config.py` to change zip codes_")

# --- Main content: tabs per zip code ---
if not ZIP_CODES:
    st.warning("No zip codes configured. Edit `config.py` to add some.")
    st.stop()

tabs = st.tabs([f"{label} ({zc})" for zc, label in ZIP_CODES.items()])

for tab, (zip_code, label) in zip(tabs, ZIP_CODES.items()):
    with tab:
        try:
            # Current conditions
            current_data, lat, lon = load_current(zip_code)
            cur = current_data["current"]
            daily = current_data["daily"]

            # MRMS radar precipitation
            mrms_daily, mrms_recent = load_mrms(zip_code)
            precip_yesterday = mrms_daily.get("mrms_precip_in", 0) or 0
            precip_7d = mrms_recent.tail(7)["mrms_precip_in"].sum() if "mrms_precip_in" in mrms_recent.columns else 0
            precip_30d = mrms_recent["mrms_precip_in"].sum() if "mrms_precip_in" in mrms_recent.columns else 0

            # Current weather card
            col1, col2, col3, col4, col5 = st.columns(5)
            weather_desc = WMO_CODES.get(cur.get("weather_code", 0), "Unknown")
            col1.metric("Now", weather_desc)
            col2.metric("Temperature", f"{cur['temperature_2m'] * 9/5 + 32:.0f}°F")
            col3.metric("Yesterday (MRMS)", f"{precip_yesterday:.2f} in")
            col4.metric("Last 7 Days", f"{precip_7d:.2f} in")
            col5.metric("Last 30 Days", f"{precip_30d:.2f} in")

            # Recent daily rainfall bar chart (MRMS)
            if not mrms_recent.empty and "mrms_precip_in" in mrms_recent.columns:
                st.subheader("Recent Daily Rainfall (MRMS Radar)")
                fig_recent = px.bar(
                    mrms_recent, x="date", y="mrms_precip_in",
                    labels={"mrms_precip_in": "Precipitation (in)", "date": "Date"},
                )
                fig_recent.update_layout(height=300, margin=dict(t=10))
                st.plotly_chart(fig_recent, use_container_width=True)

            # 14-day forecast
            st.subheader("14-Day Precipitation Forecast")
            forecast_df = pd.DataFrame({
                "Date": pd.to_datetime(daily["time"]),
                "Precipitation (in)": [mm_to_in(v) for v in daily["precipitation_sum"]],
                "Rain Chance (%)": daily["precipitation_probability_max"],
                "High (°F)": [t * 9/5 + 32 if t is not None else None for t in daily["temperature_2m_max"]],
                "Low (°F)": [t * 9/5 + 32 if t is not None else None for t in daily["temperature_2m_min"]],
            })

            fig_forecast = go.Figure()
            fig_forecast.add_trace(go.Bar(
                x=forecast_df["Date"], y=forecast_df["Precipitation (in)"],
                name="Precip (in)", marker_color="steelblue",
            ))
            fig_forecast.add_trace(go.Scatter(
                x=forecast_df["Date"], y=forecast_df["Rain Chance (%)"] / 100 * forecast_df["Precipitation (in)"].max(),
                name="Rain probability", yaxis="y2", line=dict(color="orange", dash="dot"),
            ))
            fig_forecast.update_layout(
                yaxis=dict(title="Precipitation (in)"),
                yaxis2=dict(title="Probability", overlaying="y", side="right",
                            range=[0, forecast_df["Precipitation (in)"].max() * 1.2]),
                height=350, margin=dict(t=10),
                legend=dict(orientation="h", yanchor="bottom", y=1.02),
            )
            st.plotly_chart(fig_forecast, use_container_width=True)

            # Forecast table
            display_df = forecast_df.copy()
            display_df["Date"] = display_df["Date"].dt.strftime("%a %b %d")
            st.dataframe(display_df, use_container_width=True, hide_index=True)

            # Historical data
            st.subheader(f"Historical Rainfall ({history_years}-Year)")
            hist_df = load_historical(zip_code, history_years)

            # Monthly totals chart
            monthly = monthly_totals(hist_df)
            monthly["label"] = monthly.apply(
                lambda r: f"{MONTH_NAMES[int(r['month'])]} {int(r['year'])}", axis=1
            )

            fig_monthly = px.bar(
                monthly.tail(24),  # last 24 months
                x="label", y="precipitation_in",
                labels={"precipitation_in": "Precipitation (in)", "label": "Month"},
                title="Monthly Precipitation (last 24 months)",
            )
            fig_monthly.update_layout(height=350, margin=dict(t=40))
            st.plotly_chart(fig_monthly, use_container_width=True)

            # Yearly totals
            yearly = yearly_totals(hist_df)
            fig_yearly = px.bar(
                yearly, x="year", y="precipitation_in",
                labels={"precipitation_in": "Total (in)", "year": "Year"},
                title="Annual Precipitation Totals",
            )
            # Add trend line
            if len(yearly) >= 3:
                z = np.polyfit(yearly["year"], yearly["precipitation_in"], 1)
                yearly["trend"] = np.polyval(z, yearly["year"])
                fig_yearly.add_trace(go.Scatter(
                    x=yearly["year"], y=yearly["trend"],
                    mode="lines", name="Trend",
                    line=dict(color="red", dash="dash"),
                ))
                trend_dir = "increasing" if z[0] > 0 else "decreasing"
                st.caption(
                    f"Trend: {z[0]:+.2f} in/year ({trend_dir}) — "
                    f"Average: {yearly['precipitation_in'].mean():.1f} in/year"
                )
            fig_yearly.update_layout(height=350, margin=dict(t=40))
            st.plotly_chart(fig_yearly, use_container_width=True)

            # Monthly normals (climatological averages)
            normals = monthly_normals(hist_df)
            normals["month_name"] = normals["month"].apply(lambda m: MONTH_NAMES[int(m)])

            fig_normals = px.bar(
                normals, x="month_name", y="avg_monthly_precip_in",
                labels={"avg_monthly_precip_in": "Avg Precip (in)", "month_name": "Month"},
                title=f"Average Monthly Rainfall ({history_years}-Year Normals)",
            )
            fig_normals.update_layout(height=300, margin=dict(t=40))
            st.plotly_chart(fig_normals, use_container_width=True)

            # Current year vs normal
            st.subheader("This Year vs Normal")
            current_year = date.today().year
            cy_data = hist_df[hist_df["time"].dt.year == current_year].copy()
            if not cy_data.empty:
                cy_data["month"] = cy_data["time"].dt.month
                cy_monthly = cy_data.groupby("month")["precipitation_sum"].sum().reset_index()
                cy_monthly.columns = ["month", "this_year_mm"]
                cy_monthly["this_year_in"] = cy_monthly["this_year_mm"] / 25.4

                comparison = normals.merge(cy_monthly, on="month", how="left").fillna(0)
                comparison["month_name"] = comparison["month"].apply(lambda m: MONTH_NAMES[int(m)])

                fig_comp = go.Figure()
                fig_comp.add_trace(go.Bar(
                    x=comparison["month_name"], y=comparison["avg_monthly_precip_in"],
                    name="Normal", marker_color="lightgray",
                ))
                fig_comp.add_trace(go.Bar(
                    x=comparison["month_name"], y=comparison["this_year_in"],
                    name=str(current_year), marker_color="steelblue",
                ))
                fig_comp.update_layout(
                    barmode="group", height=350, margin=dict(t=10),
                    yaxis_title="Precipitation (in)",
                    legend=dict(orientation="h", yanchor="bottom", y=1.02),
                )
                st.plotly_chart(fig_comp, use_container_width=True)

                # YTD summary
                ytd_actual = cy_monthly["this_year_in"].sum()
                ytd_months = cy_monthly["month"].max()
                ytd_normal = normals[normals["month"] <= ytd_months]["avg_monthly_precip_in"].sum()
                diff = ytd_actual - ytd_normal
                diff_pct = (diff / ytd_normal * 100) if ytd_normal > 0 else 0

                mcol1, mcol2, mcol3 = st.columns(3)
                mcol1.metric("YTD Rainfall", f"{ytd_actual:.2f} in")
                mcol2.metric("YTD Normal", f"{ytd_normal:.2f} in")
                mcol3.metric("Difference", f"{diff:+.2f} in ({diff_pct:+.0f}%)")
            else:
                st.info("No data yet for current year.")

        except Exception as e:
            st.error(f"Error loading data for {label} ({zip_code}): {e}")
