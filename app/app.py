from datetime import date, datetime, time, timedelta

import pandas as pd
import pydeck as pdk
import streamlit as st
from sqlalchemy import text

from db import get_engine


st.set_page_config(page_title="Day in the Sky", page_icon="✈️", layout="wide")

REGIONS = {
    # Widths are degrees of longitude, tuned for useful detail at each
    # region's default viewport. They are not equal-area distances.
    "North America": {"bounds": (14, 72, -170, -50), "view": (39, -105, 2.8), "cell_width": 1.0},
    "Europe": {"bounds": (34, 72, -25, 45), "view": (52, 10, 3.4), "cell_width": 0.5},
    "Japan": {"bounds": (24, 46, 122, 146), "view": (36, 138, 4.8), "cell_width": 0.15},
    "India": {"bounds": (6, 36, 68, 98), "view": (22, 79, 4.2), "cell_width": 0.35},
    "Australia + NZ": {"bounds": (-50, -10, 110, 180), "view": (-29, 145, 3.2), "cell_width": 0.75},
    "Global": {"bounds": (-90, 90, -180, 180), "view": (25, 0, 1.2), "cell_width": 1.5},
}


@st.cache_data(ttl=300, show_spinner=False)
def load_day(day: date, region: str) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Load PostgreSQL aggregates for one UTC day and coverage region."""
    start = datetime.combine(day, time.min)
    end = start + timedelta(days=1)
    min_lat, max_lat, min_lon, max_lon = REGIONS[region]["bounds"]
    cell_width = REGIONS[region]["cell_width"]
    cell_height = cell_width * 0.8660254
    engine = get_engine()

    # These latitude/longitude cells are deliberately coarse. They keep the
    # dashboard query small without requiring PostGIS or a pipeline change.
    hex_sql = text("""
        SELECT
            ingested_at AS bucket,
            floor((longitude + 180.0) / :cell_width)::integer AS cell_x,
            floor((latitude + 90.0) / :cell_height)::integer AS cell_y,
            count(*)::integer AS aircraft_count
        FROM analytics.fact_aircraft_positions
        WHERE ingested_at >= :start_at
          AND ingested_at < :end_at
          AND on_ground IS FALSE
          AND longitude BETWEEN :min_lon AND :max_lon
          AND latitude BETWEEN :min_lat AND :max_lat
        GROUP BY 1, 2, 3
        ORDER BY 1, 2, 3
    """)
    totals_sql = text("""
        SELECT ingested_at AS bucket,
               count(DISTINCT icao24)::integer AS aircraft_count
        FROM analytics.fact_aircraft_positions
        WHERE ingested_at >= :start_at AND ingested_at < :end_at
          AND on_ground IS FALSE
          AND longitude BETWEEN :min_lon AND :max_lon
          AND latitude BETWEEN :min_lat AND :max_lat
        GROUP BY 1 ORDER BY 1
    """)
    airlines_sql = text("""
        SELECT COALESCE(NULLIF(airline_name, ''), 'Unknown') AS airline,
               count(DISTINCT icao24)::integer AS aircraft_count
        FROM analytics.fact_aircraft_positions
        WHERE ingested_at >= :start_at AND ingested_at < :end_at
          AND on_ground IS FALSE
          AND longitude BETWEEN :min_lon AND :max_lon
          AND latitude BETWEEN :min_lat AND :max_lat
        GROUP BY 1 ORDER BY aircraft_count DESC LIMIT 12
    """)
    params = {
        "start_at": start, "end_at": end,
        "cell_width": cell_width, "cell_height": cell_height,
        "min_lat": min_lat, "max_lat": max_lat,
        "min_lon": min_lon, "max_lon": max_lon,
    }
    with engine.connect() as conn:
        return (
            pd.read_sql(hex_sql, conn, params=params),
            pd.read_sql(totals_sql, conn, params=params),
            pd.read_sql(airlines_sql, conn, params=params),
        )


def hexagon(lon: float, lat: float, cell_width: float, cell_height: float) -> list[list[float]]:
    """Return a flat-top hexagon centered on a SQL grid cell."""
    return [
        [lon + cell_width * dx, lat + cell_height * dy]
        for dx, dy in ((-0.5, 0), (-0.25, 0.5), (0.25, 0.5),
                       (0.5, 0), (0.25, -0.5), (-0.25, -0.5), (-0.5, 0))
    ]


def map_frame(hexes: pd.DataFrame, bucket: pd.Timestamp, cell_width: float, cell_height: float) -> pd.DataFrame:
    frame = hexes[hexes["bucket"] == bucket].copy()
    if frame.empty:
        return pd.DataFrame(columns=["polygon", "aircraft_count", "tooltip"])
    frame["longitude"] = (frame["cell_x"] + 0.5) * cell_width - 180
    frame["latitude"] = (frame["cell_y"] + 0.5) * cell_height - 90
    frame["polygon"] = [hexagon(lon, lat, cell_width, cell_height) for lon, lat in zip(frame.longitude, frame.latitude)]
    frame["tooltip"] = frame["aircraft_count"].map(lambda n: f"{n:,} observations")
    return frame


@st.cache_data(ttl=300, show_spinner=False)
def load_bin(bucket: pd.Timestamp, cell_x: int, cell_y: int, cell_width: float, cell_height: float) -> pd.DataFrame:
    """Load aircraft in one selected grid cell and ingestion bucket."""
    query = text("""
        SELECT icao24, callsign, airline_name, aircraft_registration_number,
               aircraft_type, latitude, longitude, baro_altitude, velocity
        FROM analytics.fact_aircraft_positions
        WHERE ingested_at = :bucket
          AND on_ground IS FALSE
          AND floor((longitude + 180.0) / :cell_width)::integer = :cell_x
          AND floor((latitude + 90.0) / :cell_height)::integer = :cell_y
        ORDER BY airline_name NULLS LAST, callsign NULLS LAST, icao24
    """)
    with get_engine().connect() as conn:
        return pd.read_sql(query, conn, params={
            "bucket": bucket,
            "cell_x": cell_x,
            "cell_y": cell_y,
            "cell_width": cell_width,
            "cell_height": cell_height,
        })


def clicked_bin(event) -> tuple[int, int] | None:
    """Extract cell coordinates from a Streamlit PyDeck selection event."""
    try:
        objects = event.selection.objects
        selected = objects.get("hexbin-layer", [])
        if selected:
            return int(selected[0]["cell_x"]), int(selected[0]["cell_y"])
    except (AttributeError, KeyError, IndexError, TypeError, ValueError):
        pass
    return None


st.title("Day in the Sky")
st.caption("Five-minute airborne ADS-B observation density. Select a region and time to scrub through the day.")

selected_day = st.date_input("UTC date", value=date.today() - timedelta(days=1))
selected_region = st.selectbox("ADS-B coverage region", list(REGIONS))
selected_cell_width = REGIONS[selected_region]["cell_width"]
selected_cell_height = selected_cell_width * 0.8660254
try:
    hexes, totals, airlines = load_day(selected_day, selected_region)
except Exception as exc:
    st.error(f"Could not load dashboard data: {exc}")
    st.stop()

if hexes.empty:
    st.warning("No airborne observations were found for this date.")
    st.stop()

times = sorted(pd.to_datetime(hexes["bucket"]).unique())
selected_time = st.select_slider("Time (UTC)", options=times, format_func=lambda x: pd.Timestamp(x).strftime("%H:%M"))
frame = map_frame(hexes, pd.Timestamp(selected_time), selected_cell_width, selected_cell_height)
max_count = max(1, int(hexes["aircraft_count"].quantile(0.98)))
if not frame.empty:
    # Deep blue for sparse cells through bright yellow for dense cells gives
    # stronger separation than a mostly-red palette.
    frame["color"] = frame["aircraft_count"].clip(upper=max_count).map(
        lambda n: [int(25 + 230 * n / max_count), int(25 + 195 * n / max_count), int(115 - 90 * n / max_count), 220]
    )

layer = pdk.Layer(
    "PolygonLayer",
    id="hexbin-layer",
    data=frame,
    get_polygon="polygon",
    get_fill_color="color",
    get_line_color=[90, 45, 10, 80],
    line_width_min_pixels=0.2,
    pickable=True,
    auto_highlight=True,
)
center_lat, center_lon, zoom = REGIONS[selected_region]["view"]
view = pdk.ViewState(latitude=center_lat, longitude=center_lon, zoom=zoom, min_zoom=1, max_zoom=8)
event = st.pydeck_chart(
    pdk.Deck(layers=[layer], initial_view_state=view, tooltip={"text": "{tooltip}"}),
    width="stretch",
    on_select="rerun",
    selection_mode="single-object",
)

selected_bin = clicked_bin(event)
if selected_bin is not None:
    selected_x, selected_y = selected_bin
    aircraft = load_bin(pd.Timestamp(selected_time), selected_x, selected_y, selected_cell_width, selected_cell_height)
    st.subheader(f"Aircraft in selected hexbin at {pd.Timestamp(selected_time):%H:%M} UTC")
    st.caption(f"Grid cell ({selected_x}, {selected_y}) · {len(aircraft):,} aircraft")
    st.dataframe(aircraft, width='stretch', hide_index=True)

left, right = st.columns(2)
with left:
    st.subheader("Airborne aircraft over time")
    chart = totals.copy()
    chart["bucket"] = pd.to_datetime(chart["bucket"]).dt.strftime("%H:%M")
    st.line_chart(chart.set_index("bucket")["aircraft_count"], y_label="Distinct aircraft")
with right:
    st.subheader("Top airlines by airborne count")
    st.bar_chart(airlines.set_index("airline")["aircraft_count"], horizontal=True)
