from .client import delete_peqs, get_current_peq, get_device_settings, get_peq_list, set_device_settings, set_peq
from string import Template


MAX_TOOL_ROUNDS = 10

LANGUAGE_NAME = [
    "English",
    "繁体中文",
    "简体中文",
]


FUNCTION_MAP = {
    "get_device_settings": get_device_settings,
    "set_device_settings": set_device_settings,
    "get_peq_list": get_peq_list,
    "get_current_peq": get_current_peq,
    "set_peq": set_peq,
    "delete_peqs": delete_peqs,
}