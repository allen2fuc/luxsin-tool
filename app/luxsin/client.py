import json

import httpx

from .schemas import parse_filter_type
from .crypto import decode_custom_base64, encode_custom_base64

TIMEOUT = 3

def get_device_settings(ip: str) -> dict:
    response = httpx.get(f"http://{ip}/dev/info.cgi?action=syncData", timeout=TIMEOUT)
    if response.status_code == 200:
        decoded_content = decode_custom_base64(response.text)
        return json.loads(decoded_content)
    else:
        raise Exception(f"Failed to get device status: {response.status_code}")

def set_device_settings(ip: str, params) -> str:
    settings = {"action": "setting", **params}
    response = httpx.get(f"http://{ip}/dev/info.cgi", params=settings, timeout=TIMEOUT)
    if response.status_code == 200:
        return response.text
    else:
        raise Exception(f"Failed to update settings: {response.status_code}")

def get_peq_list(ip: str) -> list[str]:
    peq_data = get_peq_data(ip)
    return [item["name"] for item in peq_data["peq"]]

def get_current_peq(ip: str) -> dict:
    peq_data = get_peq_data(ip)
    peq_index = peq_data["peqSelect"]
    peq_item = peq_data["peq"][peq_index]
    peq_item['filters'] = [{
        "type": parse_filter_type(filter['type']),
        "fc": filter['fc'],
        "gain": filter['gain'],
        "q": filter['q'],
    } for filter in peq_item['filters']]
    return peq_item

def set_peq(ip: str, params) -> dict:
    eq_params = json.dumps({"peqChange": params})
    secret_text = encode_custom_base64(eq_params)
    response = httpx.post(f"http://{ip}/dev/info.cgi", headers={
        "Content-Type": 'application/x-www-form-urlencoded; charset=utf-8'
    }, data={"json": secret_text}, timeout=TIMEOUT)
    if response.status_code == 200:
        return response.text
    else:
        raise Exception(f"Failed to update PEQ configuration: {response.status_code}")

def delete_peqs(ip: str, params) -> dict:
    eq_params = json.dumps({"peqRemove": params})
    secret_text = encode_custom_base64(eq_params)
    response = httpx.post(f"http://{ip}/dev/info.cgi", headers={
        "Content-Type": 'application/x-www-form-urlencoded; charset=utf-8'
    }, data={"json": secret_text}, timeout=TIMEOUT)
    if response.status_code == 200:
        return response.text
    else:
        raise Exception(f"Failed to delete PEQ configuration: {response.status_code}")

def get_msg_count(ip: str) -> int:
    response = httpx.get(f"http://{ip}/msgCount", timeout=TIMEOUT)
    if response.status_code == 200:
        return int(response.text)
    else:
        raise Exception(f"Failed to get change detection: {response.status_code}")

def get_peq_data(ip: str) -> dict:
    response = httpx.get(f"http://{ip}/dev/info.cgi?action=syncPeq", timeout=TIMEOUT)
    if response.status_code == 200:
        result = json.loads(decode_custom_base64(response.text))
        for item in result['peq']:
            item['filters'] = json.loads(item['filters'])
        return result
    else:
        raise Exception(f"Failed to get PEQ status: {response.status_code}")