"""Runtime resilience constants shared by the ROM scanner."""

# Keep scanner timing configuration on a module-level constant so it remains
# available even when RomScanService is used through the compatibility
# monkey-patch layer in rom_scan_engine.py.
HEARTBEAT_SECONDS = 5.0
