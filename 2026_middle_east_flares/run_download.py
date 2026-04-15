"""Download 13 months of VIIRS data for Gulf states, save as parquet checkpoints."""
import io, time, pickle
from datetime import datetime, timedelta
from pathlib import Path
import pandas as pd
import requests

FIRMS_MAP_KEY = "2b1c34df0e49ece7703e69e48ab89256"
FIRMS_BASE = "https://firms.modaps.eosdis.nasa.gov/api/area/csv"
GULF_BBOX = "44,16,60,36"
SOURCES = ["VIIRS_SNPP_SP", "VIIRS_NOAA20_SP"]
START = "2022-10-01"
END = "2023-10-31"
OUT = Path("data/raw_gulf_oct22_oct23.parquet")
CHECKPOINT = Path("data/_download_checkpoint.pkl")
OUT.parent.mkdir(exist_ok=True)


def fetch(source, bbox, date_str, days=1):
    url = f"{FIRMS_BASE}/{FIRMS_MAP_KEY}/{source}/{bbox}/{days}/{date_str}"
    r = requests.get(url, timeout=120)
    if r.status_code == 400:
        return pd.DataFrame()
    r.raise_for_status()
    t = r.text.strip()
    if not t or t.startswith("<!") or t.startswith("{"):
        return pd.DataFrame()
    return pd.read_csv(io.StringIO(t))


# Resume from checkpoint if exists
if CHECKPOINT.exists():
    with open(CHECKPOINT, "rb") as f:
        state = pickle.load(f)
    dfs = state["dfs"]
    done_dates = state["done"]
    print(f"Resuming: {len(dfs)} chunks, {sum(len(d) for d in dfs):,} rows already")
else:
    dfs = []
    done_dates = set()

s = datetime.strptime(START, "%Y-%m-%d")
e = datetime.strptime(END, "%Y-%m-%d")
cur = s

while cur <= e:
    chunk = min((e - cur).days + 1, 5)
    ds = cur.strftime("%Y-%m-%d")

    if ds not in done_dates:
        for src in SOURCES:
            try:
                df = fetch(src, GULF_BBOX, ds, chunk)
                if not df.empty:
                    dfs.append(df)
            except requests.HTTPError as ex:
                if ex.response.status_code == 429:
                    print(f"  429 at {ds}, sleeping 90s...")
                    time.sleep(90)
                    # Retry once
                    try:
                        df = fetch(src, GULF_BBOX, ds, chunk)
                        if not df.empty:
                            dfs.append(df)
                    except Exception:
                        pass
                else:
                    print(f"  Error {ds} {src}: {ex}")
            time.sleep(0.3)

        done_dates.add(ds)

        # Checkpoint every 10 date chunks
        if len(done_dates) % 10 == 0:
            with open(CHECKPOINT, "wb") as f:
                pickle.dump({"dfs": dfs, "done": done_dates}, f)

    n = sum(len(d) for d in dfs)
    if cur.day <= 5:
        print(f"  {ds} ... {n:,} rows ({len(done_dates)} chunks done)")
    cur += timedelta(days=chunk)

# Combine and save
raw = pd.concat(dfs, ignore_index=True)
raw.columns = raw.columns.str.lower()
raw.to_parquet(OUT, index=False)
print(f"\nDone! {len(raw):,} rows saved to {OUT}")

# Cleanup checkpoint
if CHECKPOINT.exists():
    CHECKPOINT.unlink()
