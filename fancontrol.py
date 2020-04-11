#!/usr/bin/env python3

import datetime
import glob
import re
import shutil
import subprocess
import time

# paths to binaries
ipmitool = shutil.which("ipmitool")
hddtemp = shutil.which("hddtemp")

# temperatures for cpu cooling override
# script polls cpu temp once a second
# if cpu temp goes above temps["cpu"]["override"], all fans will be set to 100%
# if cpu temp goes below temps["cpu"]["normal"], cpu fan will return to 50%, hd fans will return to previous speed
#
# hd target temperatures
# if any hd temp >= temps["hdds"]["high"], fans["hdds"]["high"] will be set
# if any hd temp == temps["hdds"]["medium_high"], fans["hdds"]["medium_high"] will be set
# if any hd temp == temps["hdds"]["medium_low"], fans["hdds"]["medium_low"] will be set
# if all hd temps <= temps["hdds"]["low"], fans["hdds"]["low"] will be set
temps = {
    "cpu": {"current": 100, "normal": 60, "override": 69},
    "hdds": {
        "current": 100,
        "high": 41,
        "medium_high": 40,
        "medium_low": 39,
        "low": 38,
    },
}

# normal cpu fan speed, as a % of max
# this value is set when the script starts and when not in cpu temperature override mode
# hd fan speeds, expressed as % of max
fans = {
    "cpu": {
        "default": 100,
        "high": 100,
        "medium_high": 75,
        "medium_low": 50,
        "low": 25,
        "current": 100,
    },
    "hdds": {
        "default": 100,
        "high": 100,
        "medium_high": 75,
        "medium_low": 50,
        "low": 25,
        "current": 100,
    },
}

fans["cpu"]["current"] = fans["cpu"]["default"]
fans["hdds"]["current"] = fans["hdds"]["default"]

hdd_polling_interval = 60  # hd temperature polling interval in seconds
hdd_last_checked = time.time()

cpu_polling_interval = 5
cpu_override = False

def get_hdds():
  return sorted(glob.glob("/dev/sd?"))

def set_fan_speeds(cpu_fan_speed: int, hdd_fan_speed: int):
    subprocess.check_output(
        [
            ipmitool,
            "raw",
            "0x3a",
            "0x01",
            hex(cpu_fan_speed),
            hex(hdd_fan_speed),
            hex(hdd_fan_speed),
            hex(hdd_fan_speed),
            hex(hdd_fan_speed),
            hex(hdd_fan_speed),
            hex(hdd_fan_speed),
            hex(hdd_fan_speed),
        ]
    )


cpufan_max_speed = 3000
hdfan_max_speed = 2800
exhaustfan_max_speed = 2200

def get_cpu_fan_speed():
    try:
        return int(
            re.search(
                re.compile(
                    r"^FAN1.*\|\s([0-9][0-9][0-9]|[0-9][0-9][0-9][0-9])\sRPM$",
                    re.MULTILINE,
                ),
                subprocess.check_output([ipmitool, "sdr", "type", "Fan"]).decode(
                    "utf-8"
                ),
            ).group(1)
        )
    except Exception as e:
        print(f"exception in get_cpu_fan_speed: {e}")


def get_cpu_temp():
    try:
        return int(
            re.search(
                re.compile(r"^CPU\sTemp.*\|\s([0-9][0-9])\sdegrees\sC$", re.MULTILINE),
                subprocess.check_output(
                    [ipmitool, "sdr", "type", "Temperature"]
                ).decode("utf-8"),
            ).group(1)
        )
    except Exception as e:
        print(f"exception in get_cpu_temp: {e}")
        set_fan_speeds(fans["cpu"]["high"], fans["hdds"]["high"])
        print(f"cpu temp detection failure, all fans set to 100%")


def check_cpu_temp():
    global fans
    global cpu_override
    try:
        current_cpu_temp = get_cpu_temp()
        if current_cpu_temp > temps["cpu"]["override"] and cpu_override == False:
            set_fan_speeds(fans["cpu"]["high"], fans["hdds"]["high"])
            cpu_override = True
            print(f"cpu temp > {temps['cpu']['override']}C, all fans set to 100%")
        elif current_cpu_temp < temps["cpu"]["normal"] and cpu_override == True:
            set_fan_speeds(fans["cpu"]["current"], fans["hdds"]["current"])
            cpu_override = False
            print(
                f"cpu temp < {temps['cpu']['normal']}C, cpu fan set to {fans['cpu']['default']}%"
            )
    except Exception as e:
        print(f"exception in check_cpu_temp: {e}")


def get_hdd_fan_speed():
    try:
        return int(
            re.search(
                re.compile(
                    r"^FAN3.*\|\s([0-9][0-9][0-9]|[0-9][0-9][0-9][0-9])\sRPM$",
                    re.MULTILINE,
                ),
                subprocess.check_output([ipmitool, "sdr", "type", "Fan"]).decode(
                    "utf-8"
                ),
            ).group(1)
        )
    except Exception as e:
        print(f"exception in get_hdd_fan_speed: {e}")


def get_exhaust_fan_speed():
    try:
        return int(
            re.search(
                re.compile(
                    r"^FAN5.*\|\s([0-9][0-9][0-9]|[0-9][0-9][0-9][0-9])\sRPM$",
                    re.MULTILINE,
                ),
                subprocess.check_output([ipmitool, "sdr", "type", "Fan"]).decode(
                    "utf-8"
                ),
            ).group(1)
        )
    except Exception as e:
        print(f"exception in get_exhaust_fan_speed: {e}")


def hdtemp(dev):
    try:
        temp = subprocess.check_output([hddtemp, dev])
        temp = re.match("^.*([0-9][0-9])°C$", temp.decode("utf-8"))
        temp = temp.group(1)
        return temp
    except Exception as e:
        print(f"exception in hdtemp: {e}")
        set_fan_speeds(fans["cpu"]["high"], fans["hdds"]["high"])
        print(f"hd temp detection failure, all fans set to 100%")


def check_hdd_temps(hdds):
    hdtemps = []
    global hdd_last_checked
    global fans

    if not cpu_override:
        for hdd in hdds:
            hdtemps.append(int(hdtemp(hdd)))
        if any(x >= temps["hdds"]["high"] for x in hdtemps):
            fans["hdds"]["current"] = fans["hdds"]["high"]
            set_fan_speeds(fans["cpu"]["current"], fans["hdds"]["current"])
            print(
                f"hd temp >= {temps['hdds']['high']}C fans set to {fans['hdds']['high']}%"
            )
        elif any(x == temps["hdds"]["medium_high"] for x in hdtemps):
            fans["hdds"]["current"] = fans["hdds"]["medium_high"]
            set_fan_speeds(fans["cpu"]["current"], fans["hdds"]["current"])
            print(
                f"hd temp {temps['hdds']['medium_high']}C, fans set to {fans['hdds']['medium_high']}%"
            )
        elif any(x == temps["hdds"]["medium_low"] for x in hdtemps):
            fans["hdds"]["current"] = fans["hdds"]["medium_low"]
            set_fan_speeds(fans["cpu"]["current"], fans["hdds"]["current"])
            print(
                f"hd temp {temps['hdds']['medium_low']}C, fans set to {fans['hdds']['medium_low']}%"
            )
        elif all(x <= temps["hdds"]["low"] for x in hdtemps):
            fans["hdds"]["current"] = fans["hdds"]["low"]
            set_fan_speeds(fans["cpu"]["current"], fans["hdds"]["current"])
            print(
                f"hd temp <= {temps['hdds']['low']}C, fans set to {fans['hdds']['low']}"
            )
    else:
        print(f"cpu temp override active, no action taken on hd fans")

    hdd_last_checked = time.time()


if __name__ == "__main__":
    print(f"ipmitool executable at {ipmitool}")
    print(f"hddtemp executable at {hddtemp}")
    print(f"initial hard drives: {', '.join(get_hdds())}")

    while True:
        check_cpu_temp()
        if time.time() - hdd_last_checked >= hdd_polling_interval:
            check_hdd_temps(get_hdds())
        time.sleep(cpu_polling_interval)
