# F1 25 Advanced Telemetry & Strategy Engine

A local, privacy-first race engineer and post-session coach for F1 25. Runs as a PyQt6 second-monitor dashboard with live strategy alerts, tire analysis, track radar, and meter-by-meter delta coaching.

## Quick Start

```bash
pip install -r requirements.txt
python main.py
```

Configure UDP ports and strategy thresholds in `config.yaml`. The app listens on **20777** and forwards a copy to **20778** for SimHub coexistence.

## Architecture

| Layer | Stack |
|-------|-------|
| Language | Python 3 |
| Database | SQLite |
| UI | PyQt6 + pyqtgraph |
| Networking | UDP listener + forwarder (F1 25 format 2025) |

```
Game :20777 → TelemetryLogger → SQLite
                    ↓ forward
              SimHub :20778
```

## Dashboard Tabs

- **Live** — timing, sectors, tire wear/temps, stint summary, strategy alerts, degradation chart
- **Coach** — delta traces, slip angle report, setup history, session export
- **Track Map** — 20-car radar from Motion packet
- **History** — session picker, lap table, setup archive

## Feature Status

### Phase 0: Core Pipeline ✅
- [x] UDP listener with batched SQLite writes
- [x] UDP forwarder for SimHub (20777 → 20778)
- [x] Packet parsers: Motion (0), Session (1), Lap (2), Setup (5), Telemetry (6), Status (7), Damage (10)
- [x] Lap completion with `lastLapTimeInMS` and `sector_3_ms`
- [x] Schema migrations (wear columns, session_time, drs, indexes)
- [x] `requirements.txt` + `config.yaml`

### Phase 1: Live Engineer ✅
- [x] Tabbed PyQt6 dashboard
- [x] Live timing with sector coloring
- [x] Four-corner tire wear + temps
- [x] Stint summary (`laps_until_cliff`)
- [x] Strategy alerts: pit window, push/save, dirty air, fuel/ERS
- [x] Track radar (Motion positions)
- [x] Connection health indicator

### Phase 2: Post-Session Coach ✅
- [x] Delta analyzer (distance-binned comparison)
- [x] Coach panel with speed/input charts
- [x] Slip angle detection
- [x] Setup evolution history
- [x] HTML session report export

### Phase 3: Polish ✅
- [x] AI difficulty scaler
- [x] Session picker + delete
- [x] pytest suite with golden packet fixtures

### Future / Deprioritized
- [ ] Web dashboard (FastAPI) — PyQt6 chosen instead
- [ ] Cloud sync
- [ ] In-game transparent overlays
- [ ] MoTeC export

## Testing

```bash
pytest tests/ -v
```

## Project Structure

```
f1_telemetry_app/
├── config.yaml
├── requirements.txt
├── main.py
├── telemetry/
│   ├── logger.py
│   ├── proxy.py
│   └── packets/
├── database/db_manager.py
├── analytics/
│   ├── stint_analyzer.py
│   ├── delta_analyzer.py
│   ├── slip_angle.py
│   └── strategy/
├── ui/
│   ├── dashboard.py
│   ├── live_panel.py
│   ├── coach_panel.py
│   ├── track_map.py
│   └── history_panel.py
└── tests/
```
