

import json
from typing import Annotated, Any, Optional
from pydantic import AfterValidator, BaseModel, BeforeValidator, Field


class DeviceSetting(BaseModel):
    volume: Annotated[int, Field(default=80, ge=0, le=200, description="音量：0～200，默认80")]
    language: Annotated[int, Field(ge=0, le=2, description="语言：0=英语 1=繁体 2=简体")]

    # IO
    input: Annotated[int, Field(default=4, ge=0, le=100, description="IO页 Input：0=USB-B 1=USB-C 2=同轴 3=光纤 4=蓝牙 5=HDMI 6=模拟RCA 7=U盘")]
    output: Annotated[int, Field(default=3, ge=0, le=3, description="IO页 Output：0=XLR 1=RCA 2=XLR/RCA 3=耳机")]

    # Version
    version: Annotated[int, Field(description="版本代码")]

    device: Annotated[str, Field(description="设备名称，X8默认Luxsin-X8, X9默认Luxsin-X9", examples=["Luxsin-X8"])]

    audioFormat: Annotated[Optional[str], Field(None, description="音频格式，X8默认DSD64 2.82MHz", examples=["DSD64 2.82MHz"])]

    # General Settings
    vu: Annotated[int, Field(default=8, ge=0, le=13, description="VU表：0=vu1 ... 13=vu14")]
    vu_count: Annotated[int, Field(default=16, description="VU数量, X8默认16个")]
    screenLight: Annotated[int, Field(default=1, ge=0, le=2, description="屏幕亮度：0=较亮 1=中等 2=较暗")]
    screenOff: Annotated[int, Field(default=0, ge=0, le=4, description="屏幕关闭：0=常亮 1=30秒 2=1分钟 3=3分钟 4=5分钟")]
    sleep: Annotated[int, Field(default=0,ge=0, le=4, description="休眠：0=关闭 1=1分钟 2=5分钟 3=10分钟 4=15分钟")]
    buttonLight: Annotated[int, Field(default=2,ge=0, le=3, description="旋钮亮度：0=关闭 1=较亮 2=中等 3=较暗")]
    buttonShort: Annotated[int, Field(default=1, description="按键短按配置, X8默认1")]
    autoHome: Annotated[int, Field(default=0,ge=0, le=3, description="自动返回首页：0=关闭 1=20秒 2=40秒 3=60秒")]
    knob_breathlight: Annotated[int, Field(default=0, ge=0, le=1, description="旋钮熄屏呼吸灯：0=开启 1=关闭")]

    # Audio Settings
    balance: Annotated[Optional[int], Field(None, description="左右平衡：-15～15")]
    pcm: Annotated[int, Field(default=2, ge=0, le=5, description="滤波特性：0=快速滚降 1=慢速滚降 2=短延时快速 3=短延时慢速 4=超慢速 5=低离散短延迟")]
    dacGain: Annotated[int, Field(default=2,ge=0, le=2, description="耳机增益：0=低 1=中 2=高")]
    soundStep: Annotated[int, Field(default=1,ge=0, le=3, description="音量步进：0=0.5dB 1=1dB 2=2dB 3=3dB")]
    bootSound: Annotated[int, Field(default=0, description="耳机音量：0=默认 -5db~-30db")]
    xlr: Annotated[int, Field(default=0,ge=0, le=1, description="XLR端口极性：0=正常 1=反向")]
    dacArc: Annotated[int, Field(default=0,ge=0, le=1, description="ARC模式：0=ARC 1=EARC")]

    # Home
    dsp_enable: Annotated[int, Field(default=1,ge=0, le=1, description="Bypass开关：0=关闭 1=启用")]
    bt_play: Annotated[Optional[int], Field(default=None, description="蓝牙播放状态：1=暂停/播放，默认None表示没连接蓝牙")]

    # PEQ
    peqSelect: Annotated[int, Field(default=0,ge=0, le=1, description="PEQ选择的索引下标，0=第一个PEQ 1=第二个PEQ。切换PEQ时，需要设置此值")]
    peqEnable: Annotated[int, Field(default=1,ge=0, le=1, description="PEQ开关：0=关闭 1=启用")]

    # Scene
    scene_enable: Annotated[int, Field(default=0,ge=0, le=1, description="场景启用")]
    scene_value: Annotated[int, Field(default=0,description="场景值")]

    # Effect
    audio_enable: Annotated[int, Field(ge=0, le=1, description="Effect总开关：0=关闭 1=启用")]
    effect_enable: Annotated[int, Field(ge=0, le=1, description="Effect样式开关")]
    effect_value: Annotated[int, Field(ge=0, le=15, description="Effect样式：0=古典 1=舞曲 2=流行 ... 15=慢摇")]

    width_enable: Annotated[int, Field(default=0,ge=0, le=1, description="声场宽度开关, 0=关闭 1=启用")]
    width_value: Annotated[int, Field(default=25, ge=0, le=100, description="声场宽度：0～100")]

    color_enable: Annotated[int, Field(ge=0, le=1, description="音调开关")]
    color_bass_gain: Annotated[float, Field(ge=-10.0, le=10.0, description="低音增益：-10.0～10.0")]
    color_mid_gain: Annotated[float, Field(ge=-10.0, le=10.0, description="中音增益：-10.0～10.0")]
    color_treble_gain: Annotated[float, Field(ge=-10.0, le=10.0, description="高音增益：-10.0～10.0")]

    loudness_enable: Annotated[int, Field(default=0,ge=0, le=1, description="响度开关, 0=关闭 1=启用")]
    loudness_threshold_gain: Annotated[int, Field(default=-15,description="响度阈值")]
    loudness_bass_gain: Annotated[float, Field(default=70,description="响度低音")]
    loudness_treble_gain: Annotated[float, Field(default=70, description="响度高音")]

    subwoofer_enable: Annotated[int, Field(default=0,ge=0, le=1, description="低音炮输出开关，0=关闭 1=启用")]
    subwoofer_value: Annotated[int, Field(default=70,ge=40, le=300, description="低通频率：40～300，默认70")]
    subwoofer_gain: Annotated[int, Field(default=0,ge=-15, le=15, description="低音增强：-15～15，默认0")]
    subwoofer_rate: Annotated[int, Field(description="Low pass slope：6～48db/oct")]
    subwoofer_mix_type: Annotated[int, Field(default=0, ge=0, le=1, description="输出方式：0=单声道 1=立体声")]

    subwoofer_delay_main: Annotated[int, Field(ge=0, le=1920, description="延时-左-主箱：0～1920")]
    subwoofer_delay_main_r: Annotated[Optional[int], Field(default=None, ge=0, le=1920, description="延时-右-主箱：0～1920，X8默认None表示不启用")]
    subwoofer_delay: Annotated[int, Field(ge=0, le=1920, description="延时-左-低音炮：0～1920")]
    subwoofer_delay_r: Annotated[Optional[int], Field(default=None, ge=0, le=1920, description="延时-右-低音炮：0～1920，X8默认None表示不启用")]

    crossfeed_enable: Annotated[int, Field(default=0,ge=0, le=1, description="交叉反馈开关，0=关闭 1=启用")]
    crossfeed_value: Annotated[int, Field(default=0,ge=0, le=2, description="交叉反馈：0=Default 1=Popular 2=Relax")]

    # Other
    analogGain: Annotated[int, Field(default=0,description="模拟增益")]
    dacVolumeDirect: Annotated[int, Field(default=0,description="DAC音量直通")]
    dacImpedance: Annotated[int, Field(default=1,description="DAC阻抗")]
    bt_status: Annotated[int, Field(default=0, description="蓝牙状态，0=未连接 1=已连接")]
    msgCount: Annotated[int, Field(description="消息计数")]
    mac: Annotated[str, Field(length=17, description="MAC地址")]


FILTER_TYPE_MAPPING: dict[str, int] = {
    "LOW_PASS": 0,
    "LPF": 0,

    "HIGH_PASS": 1,
    "HPF": 1,

    "BAND_PASS": 2,
    "BPF": 2,

    "NOTCH": 3,

    "PEAKING": 4,
    "PEAK": 4,

    "LOW_SHELF": 5,
    "LSHELF": 5,

    "HIGH_SHELF": 6,
    "HSHELF": 6,

    "ALL_PASS": 7,
    "APF": 7,
}

def parse_filter_type(filter_type: Any) -> int:
    """解析滤波器类型"""
    if isinstance(filter_type, str):
        return FILTER_TYPE_MAPPING.get(filter_type.upper(), 0)
    elif isinstance(filter_type, int):
        return filter_type
    else:
        raise ValueError(f"Invalid filter type: {filter_type}")

# 将float数据保留2位小数
def round_float(value: float) -> float:
    return round(value, 2)

class Filter(BaseModel):
    type: Annotated[int, Field(..., ge=0, le=7, description="滤波器类型：LOW_PASS/LPF=0,HIGH_PASS/HPF=1,BAND_PASS/BPF=2,NOTCH=3,PEAKING/PEAK=4,LOW_SHELF/LSHELF=5,HIGH_SHELF/HSHELF=6,ALL_PASS/APF=7"), BeforeValidator(parse_filter_type)]
    fc: Annotated[float, Field(..., ge=1, le=20000, description="FREQ：中心频率，范围1～20000Hz")]
    gain: Annotated[float, Field(..., ge=-15.0, le=15.0, description="增益值：-15.0～15.0dB")]
    q: Annotated[float, Field(..., ge=0.1, le=10.0, description="Q值：范围0.1～10.0dB")]


# 解析filters列表，如果是字符串，需要解析为数组
def parse_filters(filters: Any) -> list[Filter]:
    if isinstance(filters, str):
        json_filters = json.loads(filters)
        return [Filter.model_validate(filter) for filter in json_filters]
    elif isinstance(filters, list):
        return [Filter.model_validate(filter) for filter in filters]
    else:
        raise ValueError(f"Invalid filters: {filters}")

class PEQItem(BaseModel):
    name: Annotated[str, Field(..., description="EQ名称，由brand和model合并而成。优化后参数可以加后缀装饰区分。")]
    brand: Annotated[Optional[str], Field(None, description="主板名称，如：7Hz")]
    model: Annotated[Optional[str], Field(None, description="型号名称，如：Salnotes Dioko")]
    filters: Annotated[list[Filter], Field(..., min_length=10, max_length=10, description="滤波器列表：10个滤波器"), BeforeValidator(parse_filters)]
    preamp: Annotated[float, Field(..., ge=-15.0, le=15.0, description="总增益：-15.0～15.0dB"), AfterValidator(round_float)]
    canDel: Annotated[int, Field(default=1, ge=0, le=1, description="是否可以删除：0=不能删除 1=能删除，默认生成时可以删除")]
    autoPre: Annotated[int, Field(default=0, ge=0, le=1, description="是否自动预设：0=不能自动预设 1=能自动预设，默认生成时不自动预设")]

class PEQData(BaseModel):
    peqSelect: Annotated[int, Field(default=0, description="PEQ选择，当前选中的PEQ索引下标")]
    peqEnable: Annotated[int, Field(default=1, ge=0, le=1, description="PEQ开关：0=关闭 1=启用")]
    peq: Annotated[list[PEQItem], Field(default_factory=list, description="PEQ列表")]
    msgCount: Annotated[int, Field(description="消息计数")]

class MacInfo(BaseModel):
    mac: Annotated[str, Field(description="设备的MAC地址")]