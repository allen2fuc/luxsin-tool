

from enum import IntEnum, StrEnum

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
