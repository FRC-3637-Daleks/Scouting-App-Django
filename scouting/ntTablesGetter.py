"""
Robot status monitor for FRC Team 3637
Connects to NetworkTables and writes robot status (enabled/disabled/not connected)
plus the latest Unix timestamp to a text file next to this script.

Install:  pip install pyntcore
Run:      python robot_status.py
"""

import ntcore

import time
import os


# ── Configuration ─────────────────────────────────────────────────────────────
TEAM        = 3637
POLL_HZ     = 5  # how often to update the file

# ── NetworkTables ─────────────────────────────────────────────────────────────
inst = ntcore.NetworkTableInstance.getDefault()
inst.startClient4("status-monitor")
inst.setServerTeam(TEAM)

# FMSInfo/FMSControlData is a bitfield published by the roboRIO.
# Bit 0 = enabled, bit 1 = auto, bit 2 = test, bit 3 = e-stop, bit 5 = ds attached
fms_table = inst.getTable("FMSInfo")
control_data_sub = fms_table.getIntegerTopic("FMSControlData").subscribe(0)


#States: ENABLED, DISABLED, NOT_CONNECTED
def get_status() -> str:
    if not inst.isConnected():
        return "NOT_CONNECTED"
    control_data = control_data_sub.get()
    return "ENABLED" if (control_data & 0x01) else "DISABLED"
