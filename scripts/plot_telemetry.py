import sqlite3
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

# Connect to the local database
db_path = Path(__file__).resolve().parents[1] / "database" / "f1_telemetry.db"
conn = sqlite3.connect(db_path)

# 1. Fetch the last 1500 high-frequency telemetry rows (approx. 50 seconds of driving at 30Hz)
query = """
SELECT lap_distance, speed, throttle, brake, gear, steer
FROM telemetry 
WHERE lap_distance > 0.0
ORDER BY id DESC 
LIMIT 1500
"""
df = pd.read_sql_query(query, conn)

# 2. Reverse the dataframe so it plots chronologically (left to right)
df = df.iloc[::-1].reset_index(drop=True)

if df.empty:
    print("Not enough data to plot! Drive a lap first.")
    exit()

# 3. Create the standard dual-axis telemetry plot
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 6), sharex=True)
fig.suptitle("F1 25 Micro-Telemetry Trace", fontsize=16, fontweight='bold')

# Top Chart: Speed and Gear
ax1.plot(df['lap_distance'], df['speed'], color='cyan', linewidth=2, label="Speed (km/h)")
ax1.set_ylabel("Speed")
ax1.grid(True, linestyle='--', alpha=0.6)
ax1.legend(loc="upper left")

# Bottom Chart: Throttle and Brake Inputs
ax2.plot(df['lap_distance'], df['throttle'], color='green', linewidth=2, label="Throttle (0-1)")
ax2.plot(df['lap_distance'], df['brake'], color='red', linewidth=2, label="Brake (0-1)")
ax2.set_xlabel("Lap Distance (Meters)")
ax2.set_ylabel("Pedal Input")
ax2.grid(True, linestyle='--', alpha=0.6)
ax2.legend(loc="upper left")

plt.tight_layout()
plt.show()

conn.close()

