# F1 25 Advanced Telemetry & Strategy Engine

A lightweight, multi-threaded Python application designed to act as a real-time race engineer and post-race analytical coach for F1 25. 

## Architecture
* **Language:** Python 3
* **Database:** SQLite (Self-contained, zero-configuration)
* **Networking:** Local UDP Socket Listener & Proxy Forwarder
* **Format:** F1 25 Official UDP Specification (2025 Format)

---

## Feature Backlog & Roadmap

### Phase 1: Core Pipeline (In Progress)
- [x] Create project environment and directory structure.
- [x] Initialize SQLite database and relational schema.
- [x] Build UDP Listener & Port Forwarder (allows simultaneous Crew Chief / Overlay use).
- [ ] Build binary struct Parser for F1 25 headers.
- [ ] Map `PacketLapData` to track live timing.
- [ ] Link incoming telemetry to the SQLite database.

### Phase 2: Live Strategy Engine (The "Brain")
- [ ] **Optimal Pit Window Calculator:** Use linear regression on `PacketCarDamageData` (tire wear percentage) over practice laps to predict the exact lap tires will hit the 70% degradation cliff.
- [ ] **Push vs. Save Tires Monitor:** Analyze surface and inner core tire temperatures. Output live alerts to push or lift-and-coast based on thermal windows.
- [ ] **Traffic & Dirty Air Logic:** Monitor delta to the car ahead. If within 1.5s for multiple laps, factor accelerated dirty-air tire wear into the pit strategy and suggest an undercut.
- [ ] **Dynamic AI Difficulty Scaler:** Compare user practice sector times against AI grid times. Recommend exact difficulty slider adjustments (1 click = ~0.1s).

### Phase 3: Post-Race Coaching & Analytics
- [ ] **Micro-Telemetry Delta Trace:** Compare throttle, braking, and steering inputs on current lap vs. fastest lap mapped by `m_lapDistance`. Identify exact braking points where time is lost.
- [ ] **Slip Angle Detection:** Compare car Yaw against Velocity Vector to detect micro-slides on corner exit that cause excess tire overheating.
- [ ] **Setup Evolution Linking:** Save `PacketCarSetupData` with every valid lap. Allow querying historical setups to find the optimal aero balance used at specific tracks in the past.
- [ ] **Fuel & ERS Manager:** Track battery deployment zones and calculate exact fuel burn per lap to dynamically update engine modes during race stints.

### Phase 4: User Interface
- [ ] **One-Button Execution:** Wrap the entire multi-threaded application into a single `main.py` start command.
- [ ] **Web Dashboard:** Build a lightweight FastAPI backend serving a local HTML/JS frontend to visualize the data on a second monitor or tablet.
- [ ] **Live Track Radar:** Plot all 20 cars on a 2D map using `worldPositionX` and `worldPositionZ` coordinates.