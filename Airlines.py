"""
Bradley's Airline Navigator — explore airline fleets with the API Ninjas Airlines API.

Run:
    pip install -r requirements.txt
    streamlit run app.py

API key (any one of these works, checked in this order):
    1. .streamlit/secrets.toml  ->  API_NINJAS_KEY = "your-key"
    2. environment variable     ->  API_NINJAS_KEY=your-key
    3. paste it into the sidebar box while the app is running
"""
import os

import pandas as pd
import requests
import streamlit as st

API_URL = "https://api.api-ninjas.com/v1/airlines"
POPULAR = ["", "Singapore Airlines", "Lufthansa", "Emirates", "Qatar Airways", "Etihad Airways",
           "Air India", "British Airways", "Delta Air Lines", "Spirit Airlines", "Qantas"]

st.set_page_config(page_title="Bradley's Airline Navigator", page_icon="✈️", layout="wide")

st.markdown(
    """
<style>
.block-container {padding-top: 2rem; max-width: 1200px;}
.code-pill {background:#0f2a1d; color:#4ade80; padding:2px 8px; border-radius:6px;
            font-family:monospace; font-size:0.95rem;}
.info-line {font-size:1.05rem; margin:6px 0;}
.metric-card {background:#1a1f2b; border:1px solid #2a3142; border-radius:12px; padding:14px 18px;}
</style>
""",
    unsafe_allow_html=True,
)


# ---------------------------------------------------------------------------
# API key
# ---------------------------------------------------------------------------
def get_api_key() -> str:
    try:
        key = st.secrets.get("API_NINJAS_KEY", "")
    except Exception:  # no secrets.toml present
        key = ""
    return key or os.getenv("API_NINJAS_KEY", "")


with st.sidebar:
    st.header("🔑 API settings")
    api_key = get_api_key()
    if api_key:
        st.success("API key loaded.")
    else:
        api_key = st.text_input("API Ninjas key", type="password",
                                help="Get a free key at https://api-ninjas.com/register")
        st.caption("[Get a free key](https://api-ninjas.com/register) · "
                   "[Find your key](https://api-ninjas.com/profile)")
    show_json = st.checkbox("Show raw JSON response", value=False)


# ---------------------------------------------------------------------------
# API call (cached for 1 hour so repeat searches don't spend quota)
# ---------------------------------------------------------------------------
class AirlineAPIError(Exception):
    pass


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_airlines(name: str, key: str) -> list:
    try:
        resp = requests.get(API_URL, headers={"X-Api-Key": key},
                            params={"name": name}, timeout=10)
    except requests.exceptions.Timeout:
        raise AirlineAPIError("The Airlines API took too long to respond. Please try again.")
    except requests.exceptions.RequestException as e:
        raise AirlineAPIError(f"Could not reach the Airlines API: {e}")

    if resp.status_code in (401, 403):
        raise AirlineAPIError("Your API key was rejected. Check that it's correct and active.")
    if resp.status_code == 429:
        raise AirlineAPIError("Rate limit reached. Wait a moment and try again.")
    if resp.status_code != 200:
        try:
            detail = resp.json().get("error", resp.text)
        except ValueError:
            detail = resp.text
        raise AirlineAPIError(f"API error {resp.status_code}: {detail}")

    data = resp.json()
    if not isinstance(data, list):
        raise AirlineAPIError("Unexpected response format from the API.")
    return data


def fleet_table(fleet: dict) -> tuple[pd.DataFrame, int]:
    """Split the fleet dict into a model-count table and a total.
    The API includes a 'total' key alongside the model codes."""
    models = {k: int(v) for k, v in (fleet or {}).items()
              if k.lower() != "total" and isinstance(v, (int, float)) and v > 0}
    total = int(fleet.get("total", sum(models.values()))) if fleet else 0
    df = (pd.DataFrame(sorted(models.items(), key=lambda kv: -kv[1]),
                       columns=["Aircraft Model", "Count"]))
    return df, total


# ---------------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------------
st.title("🛫 Bradley's Airline Navigator")
st.write("Explore global airline fleet information using real-time data from the Airlines API.")

c1, c2 = st.columns([3, 2])
with c2:
    picked = st.selectbox("…or pick a popular airline", POPULAR,
                          format_func=lambda x: x or "Choose one")
with c1:
    typed = st.text_input("Enter the name of an airline (e.g., Singapore Airlines):",
                          value=picked)

query = typed.strip()

if not query:
    st.info("Type an airline name or pick one from the list to get started.")
    st.stop()

if not api_key:
    st.warning("Add your API Ninjas key in the sidebar to search. "
               "[Get a free key here](https://api-ninjas.com/register).")
    st.stop()

with st.spinner(f"Looking up {query}…"):
    try:
        airlines = fetch_airlines(query, api_key)
    except AirlineAPIError as e:
        st.error(f"⚠️ {e}")
        st.stop()

if not airlines:
    st.error(f"❌ No airline found matching **{query}**. Check the spelling or try the full name.")
    st.stop()

# The API matches partial names, so there can be several results.
if len(airlines) > 1:
    names = [a.get("name", "Unknown") for a in airlines]
    exact = next((i for i, n in enumerate(names) if n.lower() == query.lower()), 0)
    choice = st.selectbox(f"{len(airlines)} airlines matched — pick one:", names, index=exact)
    airline = airlines[names.index(choice)]
else:
    airline = airlines[0]

# --- Airline header --------------------------------------------------------
st.header(f"✈️ {airline.get('name', 'Unknown airline')}")
logo_col, info_col = st.columns([1, 2])
with logo_col:
    logo = airline.get("logo_url")
    if logo:
        st.image(logo, width=220)
    else:
        st.caption("No logo available.")
with info_col:
    iata = airline.get("iata") or "N/A"
    icao = airline.get("icao") or "N/A"
    st.markdown(f'<p class="info-line"><b>IATA Code:</b> <span class="code-pill">{iata}</span></p>'
                f'<p class="info-line"><b>ICAO Code:</b> <span class="code-pill">{icao}</span></p>',
                unsafe_allow_html=True)

# --- Fleet -----------------------------------------------------------------
st.subheader("🛩️ Fleet Composition")
df, total = fleet_table(airline.get("fleet"))

if df.empty:
    st.warning("Fleet details aren't available for this airline.")
else:
    m1, m2, m3 = st.columns(3)
    m1.metric("Total Fleet Size", total)
    m2.metric("Aircraft Types", len(df))
    m3.metric("Largest Type", f"{df.iloc[0]['Aircraft Model']} ({df.iloc[0]['Count']})")

    tab_table, tab_chart = st.tabs(["📋 Table", "📊 Chart"])
    with tab_table:
        # Wide layout like the reference: one column per model
        st.table(df.set_index("Aircraft Model").T.rename(index={"Count": "Aircraft"}))
    with tab_chart:
        st.bar_chart(df.set_index("Aircraft Model"), y="Count", horizontal=True)

    st.success(f"**Total Fleet Size:** {total}")

if show_json:
    st.subheader("Raw API response")
    st.json(airline)
