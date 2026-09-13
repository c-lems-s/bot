import time

from . import BRAZE_APIKEY, BRAZE_DEVICEID, BRAZE_SESSIONID, BRAZE_USERAPPID
from datetime import datetime, timezone
from .helper import HTTPPost

"""
Télémétrie Braze (facultative). Reproduit les évènements que le site web
envoie. Non nécessaire pour commander : activée seulement si
enable_analytics est vrai dans la config.
"""


def SendBrazeEventSS():
    timestamp = time.time()
    url = "https://sdk.fra-01.braze.eu/api/v3/data/"

    headers = {
        "Host": "sdk.fra-01.braze.eu",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:147.0) Gecko/20100101 Firefox/147.0",
        "Accept": "*/*",
        "Accept-Language": "fr,fr-FR;q=0.9,en-US;q=0.8,en;q=0.7",
        "Accept-Encoding": "gzip, deflate, br",
        "Content-Type": "application/json",
        "X-Requested-With": "XMLHttpRequest",
        "X-Braze-Api-Key": BRAZE_APIKEY,
        "X-Braze-Triggersrequest": "true",
        "X-Braze-Datarequest": "true",
        "Origin": "https://www.kfc.fr",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "cross-site",
        "Pragma": "no-cache",
        "Cache-Control": "no-cache",
        "Te": "trailers",
    }

    payload = {
        "respond_with": {"triggers": True, "config": {"config_time": 0}},
        "events": [
            {"name": "ss", "time": round(timestamp, 2), "data": {}, "session_id": BRAZE_SESSIONID}
        ],
        "device": {
            "browser": "Firefox",
            "browser_version": "147.0",
            "os_version": "Windows",
            "resolution": "1920x1080",
            "locale": "fr",
            "time_zone": "Europe/Paris",
            "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:147.0) Gecko/20100101 Firefox/147.0",
        },
        "api_key": BRAZE_APIKEY,
        "time": int(timestamp),
        "sdk_version": "3.5.1",
        "device_id": BRAZE_DEVICEID,
        "sdk_metadata": ["npm"],
    }

    r, c = HTTPPost(url, headers=headers, json=payload)
    if r is None:
        return None
    return c


def SendBrazeEventCommandComplete(storeName, items):
    timestamp = time.time()
    url = "https://sdk.fra-01.braze.eu/api/v3/data/"

    headers = {
        "Host": "sdk.fra-01.braze.eu",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:147.0) Gecko/20100101 Firefox/147.0",
        "Accept": "*/*",
        "Accept-Language": "fr,fr-FR;q=0.9,en-US;q=0.8,en;q=0.7",
        "Accept-Encoding": "gzip, deflate, br",
        "Content-Type": "application/json",
        "X-Requested-With": "XMLHttpRequest",
        "X-Braze-Api-Key": BRAZE_APIKEY,
        "Origin": "https://www.kfc.fr",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "cross-site",
        "Te": "trailers",
    }

    dt = datetime.fromtimestamp(round(timestamp, 2), tz=timezone.utc)
    timestamp_string = dt.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"

    data = {
        "respond_with": {"user_id": BRAZE_USERAPPID, "config": {"config_time": 1764321896}},
        "events": [
            {
                "name": "ce",
                "time": round(timestamp, 2),
                "data": {"n": "KFC_Complete_Purchase", "p": {"orderTime": timestamp_string}},
                "session_id": BRAZE_SESSIONID,
                "user_id": BRAZE_USERAPPID,
            }
        ],
        "attributes": [
            {"user_id": BRAZE_USERAPPID, "custom": {"KFC_Catering_Store_Name": storeName}}
        ],
        "api_key": BRAZE_APIKEY,
        "time": int(timestamp),
        "sdk_version": "3.5.1",
        "device_id": BRAZE_DEVICEID,
    }

    for item in items:
        data["events"].append(
            {
                "name": "p",
                "time": round(timestamp, 2),
                "data": {"pid": item["name"], "c": "EUR", "p": "0.00", "q": item["quantity"], "pr": {}},
                "session_id": BRAZE_SESSIONID,
                "user_id": BRAZE_USERAPPID,
            }
        )

    r, c = HTTPPost(url, headers=headers, json=data)
    if r is None:
        print(f"[-] {c}")
        return None
    return c


def SendBrazeCheckin():
    timestamp = time.time()
    url = "https://sdk.fra-01.braze.eu/api/v3/data/"

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:147.0) Gecko/20100101 Firefox/147.0",
        "Accept": "*/*",
        "Accept-Language": "fr,fr-FR;q=0.9,en-US;q=0.8,en;q=0.7",
        "Accept-Encoding": "gzip, deflate, br",
        "Content-Type": "application/json",
        "X-Requested-With": "XMLHttpRequest",
        "X-Braze-Api-Key": BRAZE_APIKEY,
        "X-Braze-Triggersrequest": "true",
        "X-Braze-Datarequest": "true",
        "Origin": "https://www.kfc.fr",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "cross-site",
        "Te": "trailers",
    }

    payload = {
        "respond_with": {"triggers": True, "user_id": BRAZE_USERAPPID, "config": {"config_time": 1764321896}},
        "events": [
            {"name": "se", "time": round(timestamp - 1000, 2), "data": {"d": 1608.115}, "session_id": BRAZE_SESSIONID, "user_id": BRAZE_USERAPPID},
            {"name": "ss", "time": round(timestamp, 2), "data": {}, "session_id": BRAZE_SESSIONID, "user_id": BRAZE_USERAPPID},
            {
                "name": "ce",
                "time": round(timestamp, 2),
                "data": {"n": "KFC_Check_In", "p": {"KFC_Check_In": dt_now()}},
                "session_id": BRAZE_SESSIONID,
                "user_id": BRAZE_USERAPPID,
            },
        ],
        "api_key": BRAZE_APIKEY,
        "time": int(timestamp),
        "sdk_version": "3.5.1",
        "device_id": BRAZE_DEVICEID,
        "sdk_metadata": ["npm"],
    }

    r, c = HTTPPost(url, headers=headers, json=payload)
    if r is None:
        return None
    return c


def dt_now():
    return datetime.now().strftime("%m/%d/%Y %I:%M %p")
