from luxsin.client import delete_peqs, get_current_peq, get_device_settings, get_peq_list, set_device_settings, set_peq
from string import Template


MAX_TOOL_ROUNDS = 10

LANGUAGE_NAME = [
    "English",
    "繁体中文",
    "简体中文",
]

TOOLS = [
    {
        "name": "get_device_settings",
        "description": "获取当前设备的全部设置参数，用于读取设备当前配置状态，不需要任何输入参数。",
        "input_schema": {
            "type": "object",
        },
    },
    {
        "name": "set_device_settings",
        "description": "更新设备设置参数。根据传入的字段修改设备配置，仅更新提供的字段，未提供的字段保持不变。",
        "input_schema": {
            "type": "object",
            "properties": {
                "volume": {
                    "type": "integer",
                    "description": "音量：0～200，默认80",
                },
                "language": {
                    "type": "integer",
                    "description": "语言：0=英语 1=繁体 2=简体",
                },
                "input": {
                    "type": "integer",
                    "description": "IO页 Input：0=USB-B 1=USB-C 2=同轴 3=光纤 4=蓝牙 5=HDMI 6=模拟RCA 7=U盘",
                },
                "output": {
                    "type": "integer",
                    "description": "IO页 Output：0=XLR 1=RCA 2=XLR/RCA 3=耳机",
                },
                "version": {
                    "type": "integer",
                    "description": "版本代码",
                },
                "device": {
                    "type": "string",
                    "description": "设备名称，X8默认Luxsin-X8, X9默认Luxsin-X9",
                },
                "audioFormat": {
                    "type": "string",
                    "description": "音频格式，X8默认DSD64 2.82MHz",
                },
                "vu": {
                    "type": "integer",
                    "description": "VU表：0=vu1 ... 13=vu14",
                },
                "vu_count": {
                    "type": "integer",
                    "description": "VU数量, X8默认16个",
                },
                "screenLight": {
                    "type": "integer",
                    "description": "屏幕亮度：0=较亮 1=中等 2=较暗",
                },
                "screenOff": {
                    "type": "integer",
                    "description": "屏幕关闭：0=常亮 1=30秒 2=1分钟 3=3分钟 4=5分钟",
                },
                "sleep": {
                    "type": "integer",
                    "description": "休眠：0=关闭 1=1分钟 2=5分钟 3=10分钟 4=15分钟",
                },
                "buttonLight": {
                    "type": "integer",
                    "description": "旋钮亮度：0=关闭 1=较亮 2=中等 3=较暗",
                },
                "buttonShort": {
                    "type": "integer",
                    "description": "按键短按配置, X8默认1",
                },
                "autoHome": {
                    "type": "integer",
                    "description": "自动返回首页：0=关闭 1=20秒 2=40秒 3=60秒",
                },
                "width_enable": {
                    "type": "integer",
                    "description": "声场宽度开关, 0=关闭 1=启用",
                },
                "width_value": {
                    "type": "integer",
                    "description": "声场宽度：0～100",
                },
                "color_enable": {
                    "type": "integer",
                    "description": "音调开关",
                },
                "color_bass_gain": {
                    "type": "number",
                    "description": "低音增益：-10.0～10.0",
                },
                "color_mid_gain": {
                    "type": "number",
                    "description": "中音增益：-10.0～10.0",
                },
                "color_treble_gain": {
                    "type": "number",
                    "description": "高音增益：-10.0～10.0",
                },
                "loudness_enable": {
                    "type": "integer",
                    "description": "响度开关, 0=关闭 1=启用",
                },
                "loudness_threshold_gain": {
                    "type": "integer",
                    "description": "响度阈值",
                },
                "loudness_bass_gain": {
                    "type": "number",
                    "description": "响度低音",
                },
                "loudness_treble_gain": {
                    "type": "number",
                    "description": "响度高音",
                },
                "subwoofer_enable": {
                    "type": "integer",
                    "description": "低音炮输出开关，0=关闭 1=启用",
                },
                "subwoofer_value": {
                    "type": "integer",
                    "description": "低通频率：40～300，默认70",
                },
                "subwoofer_gain": {
                    "type": "integer",
                    "description": "低音增强：-15～15，默认0",
                },
                "subwoofer_rate": {
                    "type": "integer",
                    "description": "Low pass slope：6～48db/oct",
                },
                "subwoofer_mix_type": {
                    "type": "integer",
                    "description": "输出方式：0=单声道 1=立体声",
                },
                "subwoofer_delay_main": {
                    "type": "integer",
                    "description": "延时-左-主箱：0～1920",
                },
                "subwoofer_delay_main_r": {
                    "type": "integer",
                    "description": "延时-右-主箱：0～1920，X8默认None表示不启用",
                },
                "subwoofer_delay": {
                    "type": "integer",
                    "description": "延时-左-低音炮：0～1920",
                },
                "crossfeed_enable": {
                    "type": "integer",
                    "description": "交叉反馈开关，0=关闭 1=启用",
                },
                "crossfeed_value": {
                    "type": "integer",
                    "description": "交叉反馈：0=Default 1=Popular 2=Relax",
                },
                "analogGain": {
                    "type": "integer",
                    "description": "模拟增益",
                },
                "dacVolumeDirect": {
                    "type": "integer",
                    "description": "DAC音量直通",
                },
                "dacImpedance": {
                    "type": "integer",
                    "description": "DAC阻抗",
                },
                "bt_status": {
                    "type": "integer",
                    "description": "蓝牙状态，0=未连接 1=已连接",
                },
                "msgCount": {
                    "type": "integer",
                    "description": "消息计数",
                },
                "mac": {
                    "type": "string",
                    "description": "MAC地址",
                },
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
        "name": "set_peq",
        "description": "新增或更新一个PEQ配置。如果提供的name已存在，则更新该配置；如果不存在，则创建新的PEQ配置。",
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "EQ名称，由brand和model合并而成。优化后参数可以加后缀装饰区分。"
                },
                "brand": {
                    "type": "string",
                    "description": "主板名称，如：7Hz"
                },
                "model": {
                    "type": "string",
                    "description": "型号名称，如：Salnotes Dioko"
                },
                "filters": {
                    "type": "array",
                    "description": "滤波器列表：10个滤波器",
                    "items": {
                        "type": "object",
                        "properties": {
                            "type": {
                                "type": "integer",
                                "description": "滤波器类型：LOW_PASS/LPF=0,HIGH_PASS/HPF=1,BAND_PASS/BPF=2,NOTCH=3,PEAKING/PEAK=4,LOW_SHELF/LSHELF=5,HIGH_SHELF/HSHELF=6,ALL_PASS/APF=7",
                                "enum": [0, 1, 2, 3, 4, 5, 6, 7],
                            },
                            "fc": {
                                "type": "number",
                                "description": "FREQ：中心频率，范围1～20000Hz",
                            },
                            "gain": {
                                "type": "number",
                                "description": "增益值：-15.0～15.0dB",
                            },
                            "q": {
                                "type": "number",
                                "description": "Q值：范围0.1～10.0dB",
                            }
                        },
                        "required": ["type", "fc", "gain", "q"],
                    }
                },
                "preamp": {
                    "type": "number",
                    "description": "总增益：-15.0～15.0dB"
                },
                "canDel": {
                    "type": "integer",
                    "description": "是否可以删除：0=不能删除 1=能删除，默认生成时可以删除"
                },
                "autoPre": {
                    "type": "integer",
                    "description": "是否自动预设：0=不能自动预设 1=能自动预设，默认生成时不自动预设"
                }
            },
            "required": ["name", "brand", "model", "filters", "preamp", "canDel", "autoPre"],
        },
    },
    {
        "name": "delete_peqs",
        "description": "删除一个或多个PEQ",
        "input_schema": {
            "type": "object",
            "properties": {
                "names": {
                    "type": "array",
                    "description": "PEQ名称列表",
                    "items": {"type": "string", "description": "PEQ名称"},
                }
            },
            "required": ["names"],
        },
    },
]

FUNCTION_MAP = {
    "get_device_settings": get_device_settings,
    "set_device_settings": set_device_settings,
    "get_peq_list": get_peq_list,
    "get_current_peq": get_current_peq,
    "set_peq": set_peq,
    "delete_peqs": delete_peqs,
}

AI_SYSTEM_PROMPT = Template("""
你是一个 Luxsin 设备的智能助手，负责帮助用户查询和控制设备。

【语言要求】
- 当前设备语言：${language}
- 你必须始终使用 ${language} 与用户交流

【你的能力】
- 查询设备状态（如音量、输入源、EQ 等）
- 修改设备设置（如音量、EQ、模式等）
- 解释设备功能和参数含义
- 在必要时调用工具获取或设置设备数据

【行为规范】
- 回答要简洁、清晰、专业
- 如果用户请求涉及设备控制，应优先调用工具，而不是凭空猜测
- 如果信息不确定，应提示用户或调用工具确认
- 不要编造设备数据

【工具调用规则】
- 查询类问题 → 调用读取类工具（如 get_*）
- 设置类问题 → 调用写入类工具（如 set_*）
- 不要向用户暴露工具调用细节

【主动建议（新增）】
- 当用户表达不清、不知道要做什么，或仅进行闲聊时：
  - 主动提供可执行的建议
  - 引导用户可以进行的操作，例如：
    - 查看当前设备状态
    - 调整音量或输入源
    - 切换或优化 EQ
- 建议要简洁，并给出明确选项（不要过多）

现在请根据用户的问题提供帮助。
""")


AI_EQ_OPTIMIZE_PROMPT = Template("""
你是一个 Luxsin 设备的智能助手，同时也是一名专业的音频工程师和 AutoEQ 调音专家，负责帮助用户优化设备的 EQ 设置。

【语言要求】
- 当前设备语言：${language}
- 所有回答必须使用 ${language}
- 表达应清晰、简洁、专业，避免冗长

【你的职责】
- 根据用户需求（如音乐类型、听感偏好、设备类型）优化 EQ 参数
- 提供科学、合理的调音建议（基于频段作用，如低频/中频/高频）
- 在必要时解释每个 EQ 参数的作用（如增益、Q值、频率）
- 优先给出“可直接应用”的设置，而不是只讲理论

【工具使用规则】
- 当需要读取当前设备 EQ 或参数时，调用工具获取数据
- 当用户明确要求“应用/设置/修改 EQ”时，调用工具写入设备
- 不要编造设备数据，所有设备状态必须通过工具获取

【调音原则】
- 避免极端增益（一般建议在 ±6dB 内）
- 优先小幅多段调整，而不是单点大幅调整
- 根据常见听感优化：
  - 低频（20–200Hz）：影响下潜与力度
  - 中频（200Hz–2kHz）：影响人声与主体
  - 高频（2kHz–20kHz）：影响细节与通透感
- 避免失真、刺耳或浑浊

【交互风格】
- 如果用户描述模糊（如“更好听”），主动引导补充信息
- 优先输出结构化结果，例如：
  1. 调整建议
  2. 参数说明
  3. 是否应用到设备
- 不要输出与 EQ 无关的内容
""")