import streamlit as st
import re

import logging

from luxsin.client import get_current_peq, get_peq_data, get_peq_list, get_device_settings, set_device_settings

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
        settings = get_device_settings(ip)
        st.success(f"Welcome to {settings['device']}")

        language_options = ["English", "Traditional Chinese", "Simplified Chinese"]

        st.sidebar.markdown(f"## {settings['device']}")

        language_checkbox = st.sidebar.selectbox("Language", options=language_options, index=settings['language'], key="language")
        if language_checkbox != language_options[settings['language']]:
            set_device_settings(ip, {"language": language_options.index(language_checkbox)})

        volume_slider = st.sidebar.slider("Volume", min_value=0, max_value=200, value=settings["volume"], key="volume")
        if volume_slider != settings["volume"]:
            set_device_settings(ip, {"volume": volume_slider})

        peq_data = get_peq_data(ip)
        peq_options = [item["name"] for item in peq_data["peq"]]
        peq_index = peq_data['peqSelect']
        current_peq = peq_data["peq"][peq_index]
        # st.markdown(f"```json\n{jon.dumps(peq_status, indent=4)}\n```")
        peq_select = st.sidebar.selectbox("PEQ", options=peq_options, index=peq_index)
        if peq_index != peq_options.index(peq_select):
            set_device_settings(ip, {"peqSelect": peq_options.index(peq_select)})
            st.rerun()
        
        st.markdown(f"Name: *{current_peq['name']}*, Preamp: *{round(current_peq['preamp'], 2)} dB*, autoPre: *{current_peq['autoPre']}*, canDel: *{current_peq['canDel']}*")

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

        for f in current_peq['filters']:
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

load_data(st.session_state["ip"])