import streamlit as st
import re

import logging

from luxsin.client import get_peq_list, get_settings, update_settings

logging.basicConfig(
    level=logging.INFO, format='%(asctime)s - %(name)s:%(lineno)d - %(levelname)s - %(message)s', 
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

st.title("Luxsin device access control")


def load_data(ip: str):
    try:
        # change_detection = device_client.change_detection()
        # st.success(f"Change detection: {change_detection} success")
        device_status = get_settings(ip)
        # st.markdown(f"```json\n{json.dumps(device_status, indent=4)}\n```")
        st.success(f"Welcome to {device_status['device']}")

        language_options = ["English", "Traditional Chinese", "Simplified Chinese"]

        st.sidebar.markdown(f"## {device_status['device']}")

        language_checkbox = st.sidebar.selectbox("Language", options=language_options, index=device_status['language'], key="language")
        if language_checkbox != language_options[device_status['language']]:
            update_settings(ip, {"language": language_options.index(language_checkbox)})

        volume_slider = st.sidebar.slider("Volume", min_value=0, max_value=200, value=device_status["volume"], key="volume")
        if volume_slider != device_status["volume"]:
            update_settings(ip, {"volume": volume_slider})

        peq_status = get_peq_list(ip)
        # st.markdown(f"```json\n{json.dumps(peq_status, indent=4)}\n```")
        peq_options = [item['name'] for item in peq_status['peq']]
        peq_select = st.sidebar.selectbox("PEQ", options=peq_options, index=peq_status['peqSelect'], key="peq")
        if peq_select != peq_options[peq_status['peqSelect']]:
            update_settings(ip, {"peqSelect": peq_options.index(peq_select)})

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
if ip and ip.strip() and re.match(r'^[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}$', ip):
    load_data(ip)
else:
    st.error("Please enter a valid IP address")