from asyncio import get_event_loop, new_event_loop, set_event_loop
from binascii import hexlify
from datetime import datetime
from json import dumps
from time import time_ns

from bleak import discover

# Configure update duration (update after n seconds)
UPDATE_DURATION = 1
MIN_RSSI = -60
AIRPODS_MANUFACTURER = 76
AIRPODS_DATA_LENGTH = 54
RECENT_BEACONS_MAX_T_NS = 10000000000  # 10 Seconds

recent_beacons = []


def get_best_result(device):
    recent_beacons.append({"time": time_ns(), "device": device})
    strongest_beacon = None
    i = 0
    while i < len(recent_beacons):
        if time_ns() - recent_beacons[i]["time"] > RECENT_BEACONS_MAX_T_NS:
            recent_beacons.pop(i)
            continue
        if (
            strongest_beacon is None
            or strongest_beacon.rssi < recent_beacons[i]["device"].rssi
        ):
            strongest_beacon = recent_beacons[i]["device"]
        i += 1

    if strongest_beacon != None and strongest_beacon.address == device.address:
        strongest_beacon = device

    return strongest_beacon


# Getting data with hex format
async def get_device():
    # Scanning for devices
    devices = await discover()
    for d in devices:
        # Checking for AirPods
        d = get_best_result(d)
        if (
            d.rssi >= MIN_RSSI
            and AIRPODS_MANUFACTURER in d.metadata["manufacturer_data"]
        ):
            data_hex = hexlify(
                bytearray(d.metadata["manufacturer_data"][AIRPODS_MANUFACTURER])
            )
            data_length = len(
                hexlify(
                    bytearray(d.metadata["manufacturer_data"][AIRPODS_MANUFACTURER])
                )
            )
            if data_length == AIRPODS_DATA_LENGTH:
                return data_hex
    return False


# Same as get_device() but it's standalone method instead of async
def get_data_hex():
    new_loop = new_event_loop()
    set_event_loop(new_loop)
    loop = get_event_loop()
    a = loop.run_until_complete(get_device())
    loop.close()
    return a


# Getting data from hex string and converting it to dict(json)
# Getting data from hex string and converting it to dict(json)
def get_data():
    raw = get_data_hex()

    # Return blank data if airpods not found
    if not raw:
        return dict(status=0, model="AirPods not found")

    flip: bool = is_flipped(raw)

    # On 7th position we can get AirPods model, gen1, gen2, Pro or Max
    if chr(raw[7]) == "e":
        model = "AirPodsPro"
    elif chr(raw[7]) == "3":
        model = "AirPods3"
    elif chr(raw[7]) == "f":
        model = "AirPods2"
    elif chr(raw[7]) == "2":
        model = "AirPods1"
    elif chr(raw[7]) == "a":
        model = "AirPodsMax"
    else:
        model = "unknown"

    # Checking left AirPod for availability and storing charge in variable
    status_tmp = int(f"{chr(raw[12 if flip else 13])}", 16)
    left_status = (
        100 if status_tmp == 10 else (status_tmp * 10 + 5 if status_tmp <= 10 else -1)
    )

    # Checking right AirPod for availability and storing charge in variable
    status_tmp = int(f"{chr(raw[13 if flip else 12])}", 16)
    right_status = (
        100 if status_tmp == 10 else (status_tmp * 10 + 5 if status_tmp <= 10 else -1)
    )

    # Checking AirPods case for availability and storing charge in variable
    status_tmp = int(f"{chr(raw[15])}", 16)
    case_status = (
        100 if status_tmp == 10 else (status_tmp * 10 + 5 if status_tmp <= 10 else -1)
    )

    # On 14th position we can get charge status of AirPods
    charging_status = int(f"{chr(raw[14])}", 16)
    charging_left: bool = (charging_status & (0b00000010 if flip else 0b00000001)) != 0
    charging_right: bool = (charging_status & (0b00000001 if flip else 0b00000010)) != 0
    charging_case: bool = (charging_status & 0b00000100) != 0

    # Return result info in dict format
    return dict(
        status=1,
        charge=dict(left=left_status, right=right_status, case=case_status),
        charging_left=charging_left,
        charging_right=charging_right,
        charging_case=charging_case,
        model=model,
        date=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        raw=raw.decode("utf-8"),
    )


# Return if left and right is flipped in the data
def is_flipped(raw):
    return int(f"{chr(raw[10])}", 16) & 0x02 == 0


def run():
    data = get_data()
    if data["status"] == 1:
        json_data = dumps(data)
        print(json_data)


if __name__ == "__main__":
    run()
