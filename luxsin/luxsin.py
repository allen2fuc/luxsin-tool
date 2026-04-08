from .schemas import DeviceSetting, PEQItem

LANGUAGE_NAME = [
    "English",
    "繁体中文",
    "简体中文",
]

TOOLS = [
    {
        "name": "get_device_setting",
        "description": "获取当前设备的全部设置参数，用于读取设备当前配置状态，不需要任何输入参数。",
        "input_schema": {
            "type": "object",
        },
    },
    {
        "name": "set_device_setting",
        "description": "更新设备设置参数。根据传入的字段修改设备配置，仅更新提供的字段，未提供的字段保持不变。",
        "input_schema": {
            "type": "object",
            "properties": {
                f"{key}": {"type": value.get("type", "string"), "description": value.get("description", "")}
                for key, value in DeviceSetting.model_json_schema()["properties"].items()
            },
            "required": [],
        }
    },
    {
        "name": "get_peq_list",
        "description": "获取设备中已保存的所有PEQ（参数均衡器）配置列表。",
        "input_schema": {
            "type": "object",
        },
    },
    {
        "name": "get_current_peq",
        "description": "获取当前正在使用的PEQ（参数均衡器）配置。",
        "input_schema": {
            "type": "object",
        },
    },
    {
        "name": "add_or_update_peq",
        "description": "新增或更新一个PEQ配置。如果提供的name已存在，则更新该配置；如果不存在，则创建新的PEQ配置。",
        "input_schema": {
            "type": "object",
            "properties": {
                f"{key}": {"type": value.get("type", "string"), "description": value.get("description", "")}
                for key, value in PEQItem.model_json_schema()["properties"].items()
            },
            "required": [],
        },
    }
]
