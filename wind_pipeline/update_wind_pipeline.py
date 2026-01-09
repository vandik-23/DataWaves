# update_wind_pipeline.py

import io
import os
import numpy as np
import pandas as pd
import requests
from sqlalchemy import create_engine, text
from dateutil import tz
from urllib.parse import quote_plus

def fetch_stations(engine):
    q = "SELECT station_id, COALESCE(local_tz,'Europe/Zurich') AS local_tz FROM stations"
    return pd.read_sql(q, engine)


def fetch_recent_csv(station_id: str) -> pd.DataFrame:
    st = station_id.lower()
    # correct path includes station subdirectory:
    url = f"{BASE}/{st}/ogd-smn_{st}_t_recent.csv"
    r = SESSION.get(url, timeout=30)
    r.raise_for_status()
    return pd.read_csv(io.BytesIO(r.content), sep=";", encoding="cp1252")

def find_time_col(df):
    # Common header names seen in OGD files
    candidates = ("reference_timestamp")
    low = {c.lower(): c for c in df.columns}
    for c in candidates:
        if c in low:
            return low[c]
    # fallback to first column
    return df.columns[1]

def prepare_rows(df_raw, station_tz, local_start=None, local_end=None):
    tcol = find_time_col(df_raw)
    ts_utc = pd.to_datetime(df_raw[tcol], errors="coerce", dayfirst=True, utc=True)

    tz_loc = tz.gettz(station_tz or "Europe/Zurich")
    ts_local = ts_utc.dt.tz_convert(tz_loc).dt.tz_localize(None)

    df = df_raw.assign(tz_utc=ts_utc.dt.tz_convert("UTC").dt.tz_localize(None),
                       tz_local=ts_local)

    if local_start is not None:
        s_local = pd.Timestamp(local_start, tz=tz_loc).tz_convert(tz_loc).tz_localize(None)
        df = df[df["tz_local"] >= s_local]
    if local_end is not None:
        e_local = pd.Timestamp(local_end, tz=tz_loc).tz_convert(tz_loc).tz_localize(None)
        df = df[df["tz_local"] <= e_local]

    temp_c        = pd.to_numeric(df.get(PAR_TEMP), errors="coerce")
    wind_speed_ms = pd.to_numeric(df.get(PAR_WS),   errors="coerce")
    wind_dir_deg  = pd.to_numeric(df.get(PAR_WD),   errors="coerce")

    out = pd.DataFrame({
        "tz_utc":   df["tz_utc"].dt.floor("10min"),
        "tz_local": df["tz_local"].dt.floor("10min"),
        "data_type": "observation",
        "temp_c":   temp_c.round(2),
        "temp_unit": "C",
        "wind_speed_ms": wind_speed_ms.round(3),
        "wind_speed_temp_unit": "m/s",
        "wind_dir_deg":  wind_dir_deg.round(1),
        "source_info": "meteoswiss",
    }).dropna(subset=["tz_utc","tz_local","wind_speed_ms","wind_dir_deg"])

    return out

# compute timestamps from last 48 h back from now
def last_48h_window_utc(now_utc=None):
    """Return (start_utc, end_utc) as naive UTC pandas Timestamps aligned to 10-min grid."""
    if now_utc is None:
        now_utc = pd.Timestamp.utcnow()
    end_utc = now_utc.floor("10min")
    start_utc = end_utc - pd.Timedelta(hours=48)
    # Make them naive (match your tz_utc DATETIME column)
    return start_utc.tz_localize(None), end_utc.tz_localize(None)

# filter the computed timestamps
def filter_last_48h(frame):
    if frame.empty:
        return frame
    start_utc, end_utc = last_48h_window_utc()
    # Ensure tz_utc is datetime64[ns] naive
    f = frame.copy()
    f["tz_utc"] = pd.to_datetime(f["tz_utc"])
    return f[(f["tz_utc"] >= start_utc) & (f["tz_utc"] <= end_utc)]

def drop_existing_in_window(engine, station_id, frame_48h):
    if frame_48h.empty:
        return frame_48h
    start_utc = frame_48h["tz_utc"].min()
    end_utc   = frame_48h["tz_utc"].max()
    sql = """
      SELECT tz_utc
      FROM meteo_obs
      WHERE station_id = :station_id
        AND tz_utc BETWEEN :start_utc AND :end_utc
    """
    existing = pd.read_sql(
        text(sql),
        engine,  # <- pass engine, not a transactional connection
        params={"station_id": station_id, "start_utc": start_utc, "end_utc": end_utc}
    )
    if existing.empty:
        return frame_48h
    existing_set = set(pd.to_datetime(existing["tz_utc"]))
    return frame_48h[~frame_48h["tz_utc"].isin(existing_set)]

# upsert new data in the DB
def upsert_obs_last48h(engine, station_id, frame):
    f48 = filter_last_48h(frame)
    if f48.empty:
        return 0
    f_new = drop_existing_in_window(engine, station_id, f48)
    if f_new.empty:
        return 0

    f_new = f_new.copy()
    f_new["station_id"] = station_id

    sql = """
    INSERT INTO meteo_obs
      (station_id, tz_utc, tz_local, data_type,
       temp_c, temp_unit, wind_speed_ms, wind_speed_temp_unit, wind_dir_deg, source_info)
    VALUES
      (:station_id, :tz_utc, :tz_local, :data_type,
       :temp_c, :temp_unit, :wind_speed_ms, :wind_speed_temp_unit, :wind_dir_deg, :source_info)
    ON DUPLICATE KEY UPDATE
       temp_c=VALUES(temp_c),
       temp_unit=VALUES(temp_unit),
       wind_speed_ms=VALUES(wind_speed_ms),
       wind_speed_temp_unit=VALUES(wind_speed_temp_unit),
       wind_dir_deg=VALUES(wind_dir_deg),
       source_info=VALUES(source_info);
    """
    rows = f_new[["station_id","tz_utc","tz_local","data_type",
                  "temp_c","temp_unit","wind_speed_ms","wind_speed_temp_unit",
                  "wind_dir_deg","source_info"]].to_dict(orient="records")

    # independent transaction; auto-rollback on exception
    from sqlalchemy import text
    with engine.begin() as conn:
        for i in range(0, len(rows), 800):
            conn.execute(text(sql), rows[i:i+800])
    return len(f_new)

############################################################################################

engine = create_engine(
    f"mysql+pymysql://{os.getenv('DB_USER')}:{os.getenv('DB_PASS')}@"
    f"{os.getenv('DB_HOST')}:{int(os.getenv('DB_PORT', 3306))}/{os.getenv('DB_NAME')}")

# Optional: limit by local time window (e.g., this year to today); leave as None to load all "recent"
LOCAL_START = "2025-02-01 00:00"   # Europe/Zurich (or None)
LOCAL_END   = None

# Meteoswiss CONSTANTS 
BASE = "https://data.geo.admin.ch/ch.meteoschweiz.ogd-smn"
PAR_TEMP = "tre200s0"   # °C
PAR_WS   = "fve010z0"   # m/s (requested)
PAR_WD   = "dkl010z0"   # degrees (from-direction)

SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": "wind-pipeline/1.0 (+your.email@example.com)",
    "Accept": "text/csv,*/*;q=0.1"})

############################################################################################

# ==== RUN DAILYUPDATE (48h only) ====
stations = fetch_stations(engine)
total = 0
for _, row in stations.iterrows():
    st = row["station_id"]
    tz_name = row.get("local_tz") or "Europe/Zurich"
    try:
        raw = fetch_recent_csv(st)
        prepared = prepare_rows(raw, tz_name, local_start=None, local_end=None)
        n = upsert_obs_last48h(engine, st, prepared)
        print(f"[{st}] upserted {n} rows (last 48h).")
        total += n
    except Exception as e:
        print(f"[{st}] ERROR: {e}")
        # Optional: drop tainted connections from pool after a DB error
        engine.dispose()
print(f"Done. Total rows upserted: {total}")