
import base64

ALPHABET_CUSTOM   = "KLMPQRSTUVWXYZABCGHdefIJjkNOlmnopqrstuvwxyzabcghiDEF34501289+67/"
ALPHABET_STANDARD = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"

def decode_custom_base64(encoded: str) -> str:
    """
    Decode a custom-Base64 encoded string into UTF-8 string
    """
    # Step 1: 自定义表 -> 标准 Base64 表
    translated_chars = []
    for ch in encoded:
        try:
            index = ALPHABET_CUSTOM.index(ch)
            translated_chars.append(ALPHABET_STANDARD[index])
        except ValueError:
            translated_chars.append(ch)

    translated = "".join(translated_chars)

    # Step 2: Base64 解码
    raw_bytes = base64.b64decode(translated)

    # Step 3: UTF-8 解码
    return raw_bytes.decode("utf-8")


def encode_custom_base64(text: str) -> str:
    """
    Encode a UTF-8 string into custom Base64
    """
    # Step 1: UTF-8 -> bytes
    raw_bytes = text.encode("utf-8")

    # Step 2: 标准 Base64 编码
    b64 = base64.b64encode(raw_bytes).decode("ascii")

    # Step 3: 标准表 -> 自定义表
    encoded_chars = []
    for ch in b64:
        try:
            index = ALPHABET_STANDARD.index(ch)
            encoded_chars.append(ALPHABET_CUSTOM[index])
        except ValueError:
            encoded_chars.append(ch)

    return "".join(encoded_chars)
