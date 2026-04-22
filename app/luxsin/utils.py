import ipaddress
import re
from typing import Any

from .constants import FUNCTION_MAP

from .client import get_msg_count

def is_valid_ip(ip: str) -> bool:
    if ip is None or ip.strip() == "":
        return False
    if not re.match(r'^[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}$', ip):
        return False
    try:
        ipaddress.ip_address(ip)
        return True
    except ValueError:
        return False

# 判断接口是否能访问
def is_accessible(ip: str) -> bool:
    try:
        msg_count = get_msg_count(ip)
        return msg_count >= 0
    except Exception:
        return False

def execute_tool(func_name: str, args: dict) -> Any:
    func = FUNCTION_MAP[func_name]
    return func(**args)