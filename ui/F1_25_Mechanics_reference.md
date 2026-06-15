# F1 25 Telemetry & Game Mechanics: Master Reference

1. AI Difficulty Scaling & Career Mode

The AI difficulty setting dictates the pace of offline competitors and scales from 0 (easiest) to 110 (Alien). To program the Dynamic AI Scaler, you must use the game's internal time-to-difficulty conversion ratio:

    The Delta Rule: 1 point of AI difficulty translates to approximately 0.1 seconds of lap time delta.

    The High-End Curve: Above difficulty level 100, the scaling shifts, and 1 click equals approximately 0.2 seconds of lap time.

    Career Mode Isolation: In Career and My Team modes, cars have unequal baseline performance. Therefore, you must isolate the teammate delta, comparing your lap time strictly to your teammate in the identical car rather than the grid median.

    Data Harvesting: The most accurate data for the scaler is pulled during One-Shot Qualifying or Practice Programs (like the Qualifying Sim), where fuel is low and tires are fresh.

2. Tire Thermal & Degradation Model

The F1 25 physics engine simulates three distinct temperature zones per wheel, which directly dictate grip and wear:

    Surface Temperature (Skin): Fluctuates rapidly corner-by-corner. It spikes under wheel spin, sliding, or high-G cornering, and cools quickly on straights.

    Core Temperature (Carcass): This is the most critical metric. It is stable and changes slowly lap-by-lap. Consistently high surface temperatures will eventually bleed into and overheat the core.

    Brake Temperature: Cools rapidly but radiates heat directly into the tire core.

    Compound Windows: Each of the six dry compounds (C1 to C6) operates in a strict thermal window. The hardest C1 tire operates best between 90°C and 115°C, while the softest C6 tire operates between 65°C and 85°C.

    The Wear Cycle: When tires fall outside their optimal window (too cold or too hot), grip levels drop to 97-99%. This lack of grip induces sliding, which in turn drastically spikes surface temperatures and accelerates the physical wear rate. Pitting is generally required before wear reaches 65-75%.

3. Aerodynamics: Dirty Air & Slipstream

When trailing another car, your telemetry will show distinct behavioral shifts:

    Slipstream: On straights, following closely reduces drag, creating a top-speed advantage.

    Dirty Air: In corners, the turbulent wake from the leading car dramatically reduces downforce. When coding your dirty_air.py module, look for data correlations where steering angle (steer) increases but lateral G-force (g_lat) drops, indicating understeer caused by dirty air. This understeer forces the tires to scrub, spiking surface temperatures faster than in clean air.

4. Fuel & ERS Management

    Fuel Weight Penalty: Fuel weight directly impacts lap times, as a heavier car is slower to accelerate and harder to stop. Your fuel_ers.py prediction model will need to linearly subtract fuel weight from the lap time delta to accurately track pure pace.

    ERS Deployment: The game offers "Hold" and "Toggle" inputs for the Overtake ERS mode. Telemetry will output the active deployment mode, which drains the battery rapidly to increase straight-line speed.

5. UDP Telemetry Specifications

To ensure your Python logger catches everything seamlessly:

    Network: F1 25 transmits telemetry via UDP port 20777 by default.

    Format: The data format is "2025" and defaults to a 20Hz send rate, though your app should be optimized to catch up to 30Hz or 60Hz if the user increases it.

    Lap Completeness: The game's telemetry engine only registers official lap timing data during active timed laps; incomplete or out-laps do not broadcast valid lap timing arrays.
