"""
Warns if system memory is about to bust. nohup and leave in the background.
"""

import psutil as psu
from time import sleep
from util.external_notifs import notification_backend

MACHINE_NAME = "pilot" # enter machine name
NOTIFY_METHOD = 'telegram' # change to notification service
USE_THRESHOLD = 0.98 # alert threshold
INTERVAL_S = 30

threshold_crossed = False
while True:
    ram_info = psu.virtual_memory()
    ram_usage = ram_info.used / ram_info.total
    if ram_usage > USE_THRESHOLD:
        if not threshold_crossed:
            notification_backend(NOTIFY_METHOD, f"!!!WARNING!!! RAM usage for '{MACHINE_NAME}' at {ram_usage*100:.2f}%!")
            threshold_crossed = True
    elif threshold_crossed:
        notification_backend(NOTIFY_METHOD, f"RAM usage for '{MACHINE_NAME}' has returned below threshold ({ram_usage*100:.2f}%).")
        threshold_crossed = False
    
    sleep(INTERVAL_S)
