import streamlit as st
import re

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


import httpx
import logging

logging.basicConfig(
    level=logging.INFO, format='%(asctime)s - %(name)s:%(lineno)d - %(levelname)s - %(message)s', 
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

class DeviceClient:
    def __init__(self, ip: str):
        self.ip = ip

    def get_device_status(self) -> dict:
        response = httpx.get(f"http://{self.ip}/dev/info.cgi?action=syncData")
        if response.status_code == 200:
            decoded_content = decode_custom_base64(response.text)
            return json.loads(decoded_content)
        else:
            raise Exception(f"Failed to get device status: {response.status_code}")

    def update_settings(self, settings: dict) -> str:
        settings = {"action": "setting", **settings}
        response = httpx.get(f"http://{self.ip}/dev/info.cgi", params=settings)
        if response.status_code == 200:
            return response.text
        else:
            raise Exception(f"Failed to update settings: {response.status_code}")

    def get_peq_status(self) -> dict:
        response = httpx.get(f"http://{self.ip}/dev/info.cgi?action=syncPeq")
        if response.status_code == 200:
            result = json.loads(decode_custom_base64(response.text))
            for item in result['peq']:
                item['filters'] = json.loads(item['filters'])
            return result
        else:
            raise Exception(f"Failed to get PEQ status: {response.status_code}")

    def change_detection(self) -> int:
        response = httpx.get(f"http://{self.ip}/msgCount")
        if response.status_code == 200:
            return int(response.content)
        else:
            raise Exception(f"Failed to get change detection: {response.status_code}")

    def update_peq_configuration(self, peq_configuration: dict) -> dict:
        response = httpx.post(f"http://{self.ip}/dev/info.cgi?action=syncPeq", json=peq_configuration)
        if response.status_code == 200:
            logger.info(f"Updated PEQ configuration: {peq_configuration}")
        else:
            raise Exception(f"Failed to update PEQ configuration: {response.status_code}")

    def _peq_filter_type_convert(self, filter_type_str: str) -> str:
        filter_type = ["LOW_PASS", "HIGH_PASS", "BAND_PASS", "NOTCH", "PEAKING", "PEAK", "LOW_SHELF", "HIGH_SHELF", "ALL_PASS"]
        return filter_type.index(filter_type_str)


import json
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

st.title("Luxsin device access control")


def load_data(device_client):
    try:
        # change_detection = device_client.change_detection()
        # st.success(f"Change detection: {change_detection} success")
        device_status = device_client.get_device_status()
        # st.markdown(f"```json\n{json.dumps(device_status, indent=4)}\n```")
        st.success(f"Welcome to {device_status['device']}")

        language_options = ["English", "Traditional Chinese", "Simplified Chinese"]

        st.sidebar.markdown(f"## {device_status['device']}")

        language_checkbox = st.sidebar.selectbox("Language", options=language_options, index=device_status['language'], key="language")
        if language_checkbox != language_options[device_status['language']]:
            device_client.update_settings({"language": language_options.index(language_checkbox)})

        volume_slider = st.sidebar.slider("Volume", min_value=0, max_value=200, value=device_status["volume"], key="volume")
        if volume_slider != device_status["volume"]:
            device_client.update_settings({"volume": volume_slider})

        peq_status = device_client.get_peq_status()
        # st.markdown(f"```json\n{json.dumps(peq_status, indent=4)}\n```")
        peq_options = [item['name'] for item in peq_status['peq']]
        peq_select = st.sidebar.selectbox("PEQ", options=peq_options, index=peq_status['peqSelect'], key="peq")
        if peq_select != peq_options[peq_status['peqSelect']]:
            device_client.update_settings({"peqSelect": peq_options.index(peq_select)})

        # Use the selectbox value, not peq_status['peqSelect']: after update_settings the
        # in-memory peq_status is still from before the write, so the old index would be stale.
        peq_select: int = peq_options.index(peq_select)
        current_peq = peq_status['peq'][peq_select]
        
        # st.markdown(f"```json\n{json.dumps(current_peq, indent=4)}\n```")
        st.markdown(f"Name: *{current_peq['name']}*, Preamp: *{round(current_peq['preamp'], 2)} dB*, autoPre: *{current_peq['autoPre']}*, canDel: *{current_peq['canDel']}*, current: *{peq_select}*   ")

        peq_data = {'type': [], 'fc': [], 'gain': [], 'q': []}
        for filter in current_peq['filters']:
            peq_data['type'].append(filter['type'])
            peq_data['fc'].append(filter['fc'])
            peq_data['gain'].append(filter['gain'])
            peq_data['q'].append(filter['q'])
        df = pd.DataFrame(peq_data)
        st.write(df)

        # ====== 频率范围 ======
        fs = 48000  # 采样率
        freqs = np.logspace(np.log10(20), np.log10(20000), 1000)

        # ====== biquad peaking EQ ======
        def peaking_eq(f, fc, gain_db, Q, fs):
            A = 10 ** (gain_db / 40)
            w0 = 2 * np.pi * fc / fs
            alpha = np.sin(w0) / (2 * Q)

            b0 = 1 + alpha * A
            b1 = -2 * np.cos(w0)
            b2 = 1 - alpha * A
            a0 = 1 + alpha / A
            a1 = -2 * np.cos(w0)
            a2 = 1 - alpha / A

            w = 2 * np.pi * f / fs
            z = np.exp(1j * w)

            H = (b0 + b1 / z + b2 / (z**2)) / (a0 + a1 / z + a2 / (z**2))
            return 20 * np.log10(np.abs(H))

        # ====== 叠加所有滤波器 ======
        response = np.zeros_like(freqs)

        for f in peq_status['peq'][peq_select]['filters']:
            response += peaking_eq(freqs, f["fc"], f["gain"], f["q"], fs)

        # ====== 画图 ======
        fig, ax = plt.subplots()

        ax.semilogx(freqs, response)
        ax.set_xlabel("Frequency (Hz)")
        ax.set_ylabel("Gain (dB)")
        ax.set_title("EQ Curve")
        ax.grid(True, which="both", linestyle="--", alpha=0.5)

        ax.set_xlim(20, 20000)
        ax.set_ylim(-15, 15)

        st.pyplot(fig)
            
    except Exception as e:
        # 设备连接失败，可能设备未连接或IP地址不正确
        st.error(f"Device connection failed: {e}")

ip = st.text_input("Device IP", key="ip", placeholder="192.168.1.1")
device_client = DeviceClient(ip)
if ip and ip.strip() and re.match(r'^[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}$', ip):
    load_data(device_client)
else:
    st.error("Please enter a valid IP address")