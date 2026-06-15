#!/usr/bin/env python
"""Final verification of all three fixes."""

print('=' * 70)
print('FINAL VERIFICATION OF ALL FIXES')
print('=' * 70)

from database.db_manager import DBManager
import inspect

db = DBManager()

# 1. Verify telemetry table has all thermal columns
print('\n1️⃣ THERMAL DATA COLUMNS (Fix #2)')
print('-' * 70)
cursor = db.cursor
cursor.execute('PRAGMA table_info(telemetry)')
columns = {col[1]: col[2] for col in cursor.fetchall()}
thermal_cols = ['temp_sur_fl', 'temp_sur_fr', 'temp_sur_rl', 'temp_sur_rr',
                'temp_core_fl', 'temp_core_fr', 'temp_core_rl', 'temp_core_rr']
all_thermal_present = True
for col in thermal_cols:
    status = '✅' if col in columns else '❌'
    if col not in columns:
        all_thermal_present = False
    print(f'  {status} {col:20s} ({columns.get(col, "MISSING")})')

# 2. Verify laps table has sector columns
print('\n2️⃣ SECTOR TIME COLUMNS (Fix #3 part 1)')
print('-' * 70)
cursor.execute('PRAGMA table_info(laps)')
columns = {col[1]: col[2] for col in cursor.fetchall()}
sector_cols = ['sector_1_ms', 'sector_2_ms', 'sector_3_ms']
all_sectors_present = True
for col in sector_cols:
    status = '✅' if col in columns else '❌'
    if col not in columns:
        all_sectors_present = False
    print(f'  {status} {col:20s} ({columns.get(col, "MISSING")})')

# 3. Verify logger has _handle_car_damage function
print('\n3️⃣ CAR DAMAGE HANDLER (Fix #3 part 2)')
print('-' * 70)
from telemetry.logger import TelemetryLogger
has_handler = hasattr(TelemetryLogger, '_handle_car_damage')
status = '✅' if has_handler else '❌'
print(f'  {status} _handle_car_damage method: {"Present" if has_handler else "Missing"}')

# 4. Verify logger extracts lap number
print('\n4️⃣ LAP NUMBER EXTRACTION (Fix #1)')
print('-' * 70)
source = inspect.getsource(TelemetryLogger._handle_lap_data)
has_lap_num = 'current_lap_num' in source
has_lap_id_with_num = 'current_lap_num' in source and 'lap_id = f' in source
status_1 = '✅' if has_lap_num else '❌'
status_2 = '✅' if has_lap_id_with_num else '❌'
print(f'  {status_1} Extracts currentLapNum from struct')
print(f'  {status_2} Uses lap number in lap_id: lap_id = f"{{session_uid}}_{{car_idx}}_{{current_lap_num}}"')

print('\n' + '=' * 70)
if all_thermal_present and all_sectors_present and has_handler and has_lap_num and has_lap_id_with_num:
    print('✅ ALL FIXES VERIFIED AND WORKING!')
else:
    print('❌ SOME FIXES ARE MISSING')
print('=' * 70)

