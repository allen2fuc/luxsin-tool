import re
import streamlit as st
from anthropic import Anthropic
import requests

from luxsin.client import get_settings, update_settings
from luxsin.luxsin import LANGUAGE_NAME

client = Anthropic(
    api_key=st.secrets["ANTHROPIC_API_KEY"],
    base_url=st.secrets["ANTHROPIC_BASE_URL"]
)

@st.cache_data
def load_models() -> list[str]:
    res = requests.get(f"https://api.jiekou.ai/openai/v1/models")
    return [model["id"] for model in res.json()["data"]]

models = load_models()
selected_model = st.sidebar.selectbox("Model", options=models, index=models.index("claude-3-haiku-20240307"))

if "anthropic_model" not in st.session_state:
    st.session_state.anthropic_model = selected_model

ip = st.sidebar.text_input("Device IP", key="ip", placeholder="192.168.1.1")
if not (ip and ip.strip() and re.match(r'^[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}$', ip)):
    st.warning("Please enter a valid IP address")
    st.stop()

try:
    settings = get_settings(ip)
except Exception as e:
    st.error(f"Failed to get device settings: {e}. Please enter a valid IP address.")
    st.stop()

st.title(f"Welcome to {settings['device']}")
language = st.sidebar.selectbox("Language", options=LANGUAGE_NAME, index=settings['language'])
if language != LANGUAGE_NAME[settings['language']]:
    update_settings(ip, {"language": LANGUAGE_NAME.index(language)})

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if msg := st.chat_input("What is up?"):
    st.session_state.messages.append({"role": "user", "content": msg})
    with st.chat_message("user"):
        st.markdown(msg)

    def response_generator():
        with client.messages.stream(
            model=st.session_state.anthropic_model,
            messages=st.session_state.messages,
            max_tokens=4096,
        ) as stream:
            for event in stream:
                if event.type == "text":
                    yield event.text

    with st.chat_message("assistant"):
        response = st.write_stream(response_generator())
    st.session_state.messages.append({"role": "assistant", "content": response})