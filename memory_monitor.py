"""
Warns if system memory is about to bust. nohup and leave in the background.
"""

import psutil as psu
from time import sleep
from util.external_notifs import notification_backend

MACHINE_NAME = "machine" # enter machine name
NOTIFY_METHOD = 'telegram' # change to notification service
USE_THRESHOLD = 0.95 # alert threshold
INTERVAL_S = 30

while True:
    ram_info = psu.virtual_memory()
    ram_usage = ram_info.used / ram_info.total
    if ram_usage > USE_THRESHOLD:
        notification_backend(NOTIFY_METHOD, f"!!!WARNING!!! RAM usage for '{MACHINE_NAME}' at {ram_usage*100:.2f}%!")
    sleep(INTERVAL_S)