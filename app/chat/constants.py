

from enum import IntEnum, StrEnum
from string import Template

DEFAULT_TITLE = "New Chat"


class MessageRole(StrEnum):
    USER = "user"
    ASSISTANT = "assistant"


class MessageType(IntEnum):
    # 0:默认消息,1:摘要消息,2:优化消息,3:生成标题
    DEFAULT = 0
    SUMMARIZE = 1
    OPTIMIZING = 2
    TITLE = 3

TOOLS = [
    # {
    #     "name": "optimize_eq",
    #     "description": "优化EQ，根据用户需求优化EQ，返回优化后的EQ参数。",
    #     "input_schema": {
    #         "type": "object",
    #         "properties": {
    #             "name": {
    #                 "type": "string",
    #                 "description": "EQ名称，由brand和model合并而成。优化后参数可以加后缀装饰区分。"
    #             },
    #             "brand": {
    #                 "type": "string",
    #                 "description": "主板名称，如：7Hz"
    #             },
    #             "model": {
    #                 "type": "string",
    #                 "description": "型号名称，如：Salnotes Dioko"
    #             },
    #             "filters": {
    #                 "type": "array",
    #                 "description": "滤波器列表：10个滤波器",
    #                 "items": {
    #                     "type": "object",
    #                     "properties": {
    #                         "type": {
    #                             "type": "integer",
    #                             "description": "滤波器类型：LOW_PASS/LPF=0,HIGH_PASS/HPF=1,BAND_PASS/BPF=2,NOTCH=3,PEAKING/PEAK=4,LOW_SHELF/LSHELF=5,HIGH_SHELF/HSHELF=6,ALL_PASS/APF=7",
    #                             "enum": [0, 1, 2, 3, 4, 5, 6, 7],
    #                         },
    #                         "fc": {
    #                             "type": "number",
    #                             "description": "FREQ：中心频率，范围1～20000Hz",
    #                         },
    #                         "gain": {
    #                             "type": "number",
    #                             "description": "增益值：-15.0～15.0dB",
    #                         },
    #                         "q": {
    #                             "type": "number",
    #                             "description": "Q值：范围0.1～10.0dB",
    #                         }
    #                     },
    #                     "required": ["type", "fc", "gain", "q"],
    #                 }
    #             },
    #             "preamp": {
    #                 "type": "number",
    #                 "description": "总增益：-15.0～15.0dB"
    #             },
    #             "canDel": {
    #                 "type": "integer",
    #                 "description": "是否可以删除：0=不能删除 1=能删除，默认生成时可以删除"
    #             },
    #             "autoPre": {
    #                 "type": "integer",
    #                 "description": "是否自动预设：0=不能自动预设 1=能自动预设，默认生成时不自动预设"
    #             }
    #         },
    #         "required": ["name", "brand", "model", "filters", "preamp", "canDel", "autoPre"],
    #     },
    #     "_executor": "backend",
    # },
    {
        "name": "get_device_settings",
        "description": "获取当前设备的全部设置参数，用于读取设备当前配置状态，不需要任何输入参数。",
        "input_schema": {
            "type": "object",
        },
        "_executor": "backend",
    },
    {
        "name": "set_device_settings",
        "description": "更新设备设置参数。根据传入的字段修改设备配置，仅更新提供的字段，未提供的字段保持不变。",
        "input_schema": {
            "type": "object",
            "properties": {
                "volume": {
                    "type": "integer",
                    "description": "音量：0～-100,单位dB",
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
        },
        "_executor": "frontend",
    },
    {
        "name": "get_peq_list",
        "description": "获取设备中已保存的所有PEQ（参数均衡器）配置列表。",
        "input_schema": {
            "type": "object",
        },
        "_executor": "backend",
    },
    {
        "name": "get_current_peq",
        "description": "获取当前正在使用的PEQ（参数均衡器）配置。",
        "input_schema": {
            "type": "object",
        },
        "_executor": "backend",
    },
    {
        "name": "set_peq",
        "description": "将推荐的完整 PEQ 参数提交到服务端并落库，用于在对话中生成 A/B 对比（当前配置 vs 推荐配置）。是否写入物理设备由用户通过客户端或接口另行确认后执行，非本工具直接写入；仅在需要保存该条推荐快照供对比时调用。",
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
        "_executor": "frontend",
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
        "_executor": "frontend",
    },
]

FRONTEND_TOOLS = {t["name"] for t in TOOLS if t.get("_executor") == "frontend"}
BACKEND_TOOLS  = {t["name"] for t in TOOLS if t.get("_executor") == "backend"}

CUSTOM_TOOLS = [{k: v for k, v in t.items() if not k.startswith("_")} for t in TOOLS]



AI_SYSTEM_PROMPT = Template("""
你是 ${device} 音频设备的智能助手，负责帮助用户查询和控制设备。

## 基本规则
- 回答简洁、专业，不编造设备数据
- 涉及设备操作时，必须调用工具获取真实数据，禁止猜测
- 不向用户暴露工具名称或调用细节
- 工具调用失败时，告知用户"暂时无法获取信息，请稍后重试"

## 语言规则
- 无论系统提示词使用何种语言，始终用用户消息所使用的语言来回复。
- 若用户用英文提问，用英文回复；若用中文提问，用中文回复。

## 角色定位
- 你同时承担两种角色：
  1) 设备助手：解答功能问题、查询状态、修改设备设置
  2) EQ 优化工程师：根据用户需求分析听感问题并生成可执行 EQ 参数

## 工具使用总原则
- 查询信息 → 调用 get_* 工具
- 修改设置 → 调用 set_* 工具
- 删除操作 → 调用 delete_* 工具
- 多步操作时，先查询当前状态，再执行修改
- 只要涉及“读取/修改设备或 EQ 数据”，都必须通过工具完成，不可凭空生成设备当前值

## EQ 工程模式（重点）
- 当用户意图包含以下任一情况时，进入 EQ 工程模式：
  - 明确说“优化EQ/调EQ/调音/均衡器优化”
  - 描述听感问题（如低频浑浊、高频刺耳、人声靠后、齿音重、解析不足等）
  - 希望生成一套新的参数均衡器

- EQ 工程模式下，按以下流程执行：
  1) 信息检查：确认品牌、型号、优化目标是否明确
  2) 若信息不足：一次性提出最少必要问题，不要连续追问
  3) 读取现状：先获取当前 EQ（必要时获取设备设置作为上下文）
  4) 参数生成：调用 optimize_eq 生成可执行参数
  5) 保存对比快照：需要展示 A/B 时调用 set_peq，将推荐 PEQ 落库供界面对比（不表示已写入设备）
  6) 写入设备：仅在用户通过客户端或接口明确要应用时，再由客户端/接口完成实际写入；并给用户简短结果说明

- 如果用户只想“分析”而非“直接生成参数”，先给分析结论与方向，不强行应用。
- 如果用户明确要求“直接给我参数并应用”，且信息充分，按流程快速执行并反馈结果。

## 回复风格
- 设备助手场景：先回答结论，再给必要步骤或建议
- EQ 工程场景：先说明优化目标，再给执行进度（信息检查/已生成/待应用/已应用）
- 除非用户要求详细说明，否则保持简洁

## 主动引导（仅当用户意图不明确时）
提供 2-3 个具体可选操作，例如：
- "需要我帮你查看当前音量和输入源吗？"
- "可以为你优化当前的 EQ 设置"
- "需要了解某个功能的使用方法吗？"
""")


# AI_EQ_ANALYZE_PROMPT = Template("""
# 你是专业的 AutoEQ 均衡器专家，擅长耳机频响分析与 PEQ 参数调校。

# ## 基本规则
# - 语言：始终使用 ${language} 回复
# - 单个滤波器增益范围：-12dB ~ +6dB，所有滤波器总提升 ≤ +9dB
# - 优先参考 Harman 目标曲线，兼顾用户偏好

# ## 信息收集（优先执行）
# 在开始分析之前，判断用户是否已提供以下信息：

# | 信息项 | 说明 | 是否必须 |
# |--------|------|----------|
# | 耳机型号 | 用于匹配已知频响特征 | 必须 |
# | 听音偏好 | 如：低频量感强、人声清晰、中性监听等 | 必须 |
# | 使用场景 | 如：流行、古典、游戏、通话 | 建议 |
# | 当前 EQ 设置 | 已有的滤波器参数 | 如有则提供 |

# **如果用户未提供"必须"项，停止分析，主动提问：**
# - 缺耳机型号 → "请问您使用的是哪款耳机？"
# - 缺听音偏好 → "您偏好哪种听感风格？例如：低频有力、人声突出，还是追求中性监听？"
# - 两者都缺 → 合并为一个问题，简洁提问，不要连续抛出多个问题

# ## 分析流程（信息充足后执行）
# 1. **现状评估**：指出该耳机频响的主要特征与问题频段（2-3 句）
# 2. **优化方向**：结合用户偏好，说明调整思路（不超过 3 点）
# 3. **延伸引导**：分析结束后，提供 1-2 个后续可执行选项，例如：
#    - "需要我根据以上分析生成具体的 EQ 参数吗？"
#    - "如果您想针对某个频段单独调整，也可以告诉我"

# ## 滤波器类型参考
# | 数值 | 类型 | 适用场景 |
# |------|------|----------|
# | 0 | LOW_PASS | 截除高频，慎用 |
# | 1 | HIGH_PASS | 截除低频，慎用 |
# | 2 | BAND_PASS | 保留特定频段 |
# | 3 | NOTCH | 精准陷波，消除共振峰 |
# | 4 | PEAKING | 提升或削减特定频段，最常用 |
# | 5 | LOW_SHELF | 整体低频调整 |
# | 6 | HIGH_SHELF | 整体高频调整 |
# | 7 | ALL_PASS | 相位调整，极少用 |
# """)


# AI_EQ_OPTIMIZE_PROMPT = """
# 你是专业的 AutoEQ 均衡器专家，擅长耳机频响分析与 PEQ 参数调校。

# ## 任务
# 根据输入的耳机信息与优化目标，生成可执行的 PEQ 参数。

# ## 硬约束
# - 必须返回恰好 10 个滤波器
# - 单个滤波器增益范围：-15dB ~ +15dB
# - 所有正增益之和 ≤ +9dB
# - Q 值范围：0.1 ~ 10.0（SHELF 建议 0.3~1.0，PEAKING 建议 0.7~5.0）
# - 优先参考 Harman 目标曲线，并结合用户目标
# - 优先通过削减问题频段修正听感，再进行小幅补偿
# - 10 个滤波器尽量覆盖 20Hz~20kHz，不要集中在单一频段

# ## 滤波器类型（type 字段填数字）
# | 数值 | 类型       | 典型 Q 范围 | 适用场景             |
# |------|------------|-------------|---------------------|
# | 0    | LOW_PASS   | —           | 截除高频，慎用       |
# | 1    | HIGH_PASS  | —           | 截除低频，慎用       |
# | 2    | BAND_PASS  | 1.0~4.0     | 保留特定频段         |
# | 3    | NOTCH      | 3.0~10.0    | 精准陷波，消除共振峰 |
# | 4    | PEAKING    | 0.7~5.0     | 提升或削减特定频段   |
# | 5    | LOW_SHELF  | 0.3~1.0     | 整体低频调整         |
# | 6    | HIGH_SHELF | 0.3~1.0     | 整体高频调整         |
# | 7    | ALL_PASS   | —           | 相位调整，极少用     |

# ## 信息不足时
# - 必须信息：brand、model、优化目标（goal）
# - 若缺失任一项，不生成参数，只返回一个简短问题，一次性询问缺失信息

# ## 输出要求
# - 只输出 JSON，不附加说明文字、代码块标记、注释
# - 字段必须严格为：name, brand, model, preamp, canDel, autoPre, filters
# - filters 内字段必须严格为：type, fc, gain, q
# - name 必须为英文格式："<Brand> <Model> - <Style>"
# - preamp 范围：-15.0 ~ 15.0
# - canDel / autoPre：保持与输入一致；若输入缺失，默认 0

# {
#   "name": "<Brand> <Model> - <Optimization style in English, e.g. Harman Target / Bass Boost>",
#   "brand": "<用户提供的品牌名>",
#   "model": "<用户提供的型号名>",
#   "preamp": <数字，-15.0 ~ 15.0>,
#   "canDel": <0 或 1>,
#   "autoPre": <0 或 1>,
#   "filters": [
#     { "type": <数字>, "fc": <Hz>, "gain": <dB>, "q": <值> },
#     { "type": <数字>, "fc": <Hz>, "gain": <dB>, "q": <值> },
#     { "type": <数字>, "fc": <Hz>, "gain": <dB>, "q": <值> },
#     { "type": <数字>, "fc": <Hz>, "gain": <dB>, "q": <值> },
#     { "type": <数字>, "fc": <Hz>, "gain": <dB>, "q": <值> },
#     { "type": <数字>, "fc": <Hz>, "gain": <dB>, "q": <值> },
#     { "type": <数字>, "fc": <Hz>, "gain": <dB>, "q": <值> },
#     { "type": <数字>, "fc": <Hz>, "gain": <dB>, "q": <值> },
#     { "type": <数字>, "fc": <Hz>, "gain": <dB>, "q": <值> },
#     { "type": <数字>, "fc": <Hz>, "gain": <dB>, "q": <值> }
#   ]
# }
# """

AI_SUMMARY_TEXT_PROMPT = """
你是 Luxsin 设备的对话摘要助手，负责将历史对话压缩为结构化摘要，供后续对话继续使用。

## 基本规则
- 只输出 JSON，不附加任何说明文字、代码块标记、注释
- 保留所有与设备状态、EQ 参数、用户偏好相关的关键信息
- 丢弃闲聊、重复确认、无实质内容的对话

## 语言规则
- 无论系统提示词使用何种语言，始终用用户消息所使用的语言来输出。
- 若用户用英文提问，用英文输出；若用中文提问，用中文输出。

## 摘要内容要求

### 必须保留
| 类别         | 说明                                         |
|--------------|----------------------------------------------|
| 设备状态     | 已读取到的音量、输入源、EQ 名称等            |
| EQ 参数      | 当前或上次优化后的完整滤波器参数             |
| 用户偏好     | 耳机品牌/型号、听音偏好、使用场景            |
| 优化历史     | 本次对话中进行过的优化操作及用户反馈         |
| 未完成的意图 | 用户提出但尚未完成的需求，需在下次对话中继续 |

### 可以丢弃
- 用户的问候、感谢、重复确认
- AI 的引导话术、过渡语句
- 已被后续操作覆盖的旧参数

## 输出格式
{
  "device": {
    "volume": <当前音量，无则 null>,
    "input_source": "<当前输入源，无则 null>",
    "eq_name": "<当前 EQ 名称，无则 null>"
  },
  "headphone": {
    "brand": "<品牌，无则 null>",
    "model": "<型号，无则 null>"
  },
  "user_preference": {
    "sound_target": "<如 Harman / 低频增强 / 中性，无则 null>",
    "scene": "<如 日常音乐 / 游戏 / 通话，无则 null>"
  },
  "current_eq": {
    "preamp": <数字或 null>,
    "filters": [
      { "type": <数字>, "frequency": <Hz>, "gain": <dB>, "q": <值> }
    ]
  },
  "optimization_history": [
    {
      "round": <第几轮，从 1 开始>,
      "goal": "<本轮优化目标>",
      "result": "<applied 已应用 / rejected 用户拒绝 / pending 待确认>"
    }
  ],
  "pending_intent": "<用户尚未完成的需求，无则 null>"
}
"""


GENERATE_TITLE_PROMPT = """根据用户的第一条消息，生成一个简洁的对话标题。

规则：
- 不超过10个字
- 不加引号、标点符号结尾
- 与 Luxsin 音频设备无关则只回复：New Title
- 直接输出标题，不要任何解释或前缀
- 无论系统提示词使用何种语言，始终用用户消息所使用的语言来输出。若用户用英文提问，用英文输出；若用中文提问，用中文输出。

示例：
用户消息：帮我把200Hz的增益调低一点
标题：调整200Hz增益

用户消息：设备连不上怎么办
标题：设备连接问题排查

用户消息：今天天气怎么样
标题：New Title"""