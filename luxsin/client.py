import json

import httpx
from .crypto import decode_custom_base64, encode_custom_base64


def get_settings(ip: str) -> dict:
    response = httpx.get(f"http://{ip}/dev/info.cgi?action=syncData")
    if response.status_code == 200:
        decoded_content = decode_custom_base64(response.text)
        return json.loads(decoded_content)
    else:
        raise Exception(f"Failed to get device status: {response.status_code}")

def update_settings(ip: str, settings: dict) -> str:
    settings = {"action": "setting", **settings}
    response = httpx.get(f"http://{ip}/dev/info.cgi", params=settings)
    if response.status_code == 200:
        return response.text
    else:
        raise Exception(f"Failed to update settings: {response.status_code}")

def get_peq_list(ip: str) -> dict:
    response = httpx.get(f"http://{ip}/dev/info.cgi?action=syncPeq")
    if response.status_code == 200:
        result = json.loads(decode_custom_base64(response.text))
        for item in result['peq']:
            item['filters'] = json.loads(item['filters'])
        return result
    else:
        raise Exception(f"Failed to get PEQ status: {response.status_code}")

def update_peq(ip: str, item: dict) -> dict:
    eq_params = json.dumps({"peqChange": item})
    secret_text = encode_custom_base64(eq_params)
    response = httpx.post(f"http://{ip}/dev/info.cgi", headers={
        "Content-Type": 'application/x-www-form-urlencoded; charset=utf-8'
    }, data={"json": secret_text})
    if response.status_code == 200:
        return response.text
    else:
        raise Exception(f"Failed to update PEQ configuration: {response.status_code}")

def delete_peq(ip: str, name: str) -> dict:
    eq_params = json.dumps({"peqRemove": [name]})
    secret_text = encode_custom_base64(eq_params)
    response = httpx.post(f"http://{ip}/dev/info.cgi", headers={
        "Content-Type": 'application/x-www-form-urlencoded; charset=utf-8'
    }, data={"json": secret_text})
    if response.status_code == 200:
        return response.text
    else:
        raise Exception(f"Failed to delete PEQ configuration: {response.status_code}")

def get_msg_count(ip: str) -> int:
    response = httpx.get(f"http://{ip}/msgCount")
    if response.status_code == 200:
        return int(response.text)
    else:
        raise Exception(f"Failed to get change detection: {response.status_code}")
