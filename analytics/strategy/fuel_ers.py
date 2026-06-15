class FuelERSManager:
    """Track fuel and ERS deployment recommendations."""

    ERS_MODES = {0: "None", 1: "Medium", 2: "Hotlap", 3: "Overtake"}

    def evaluate(self, status):
        """status: dict from logger get_player_status / live_timing"""
        alerts = []
        fuel_laps = status.get("fuel_remaining_laps", 0)
        ers_mode = status.get("ers_deploy_mode", 0)
        current_lap = status.get("current_lap_num", 0)
        total_laps = status.get("total_laps", 53)

        if fuel_laps and fuel_laps < 3:
            alerts.append({
                "message": f"Low fuel — {fuel_laps:.1f} laps remaining at current pace",
                "severity": "critical",
            })
        elif fuel_laps and fuel_laps < 5:
            alerts.append({
                "message": f"Fuel saving recommended — {fuel_laps:.1f} laps remaining",
                "severity": "warning",
            })

        laps_remaining = total_laps - current_lap if total_laps else 0
        if laps_remaining > 10 and ers_mode == 3:
            alerts.append({
                "message": "ERS Overtake mode — consider Medium for stint management",
                "severity": "info",
            })
        elif laps_remaining <= 5 and ers_mode < 2:
            alerts.append({
                "message": "Final laps — deploy ERS Overtake mode",
                "severity": "info",
            })

        return alerts
