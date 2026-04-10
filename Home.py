import json
import streamlit as st

from app.luxsin.client import get_device_settings, set_device_settings
from app.luxsin.constants import AI_SYSTEM_PROMPT, LANGUAGE_NAME, MAX_TOOL_ROUNDS, TOOLS
from app.luxsin.utils import execute_tool, is_accessible, is_valid_ip, load_models
from anthropic import Anthropic

st.set_page_config(
    page_title="Luxsin Home",
    page_icon="🎧",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        "Get Help": "https://www.baidu.com",
        "Report a bug": "https://www.luxsin.com/support",
        "About": "https://www.luxsin.com",
    },
)

if "ip" not in st.session_state:
    st.session_state["ip"] = None
if "base_url" not in st.session_state:
    st.session_state["base_url"] = None
if "api_key" not in st.session_state:
    st.session_state["api_key"] = None
if "model" not in st.session_state:
    st.session_state["model"] = ""


@st.dialog("Luxsin Settings", icon="🛠️", dismissible=False)
def settings():
    ip = st.text_input("Luxsin Device IP", placeholder="192.168.1.1")

    base_url = st.text_input("AI Base URL", placeholder="https://api.anthropic.com")

    api_key = st.text_input("AI API Key", placeholder="sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx")

    model_ids = load_models(base_url)
    model = st.selectbox("AI Models", options=model_ids, index=0, disabled=True if not model_ids else False)

    if st.button("Save Settings", icon="💾"):

        if not (ip and ip.strip() and is_valid_ip(ip) and is_accessible(ip)):
            st.toast("Please enter a valid IP address", icon="🚨")
            return

        if not (base_url and api_key):
            st.toast("Please enter a valid Base URL and API Key", icon="🚨")
            return

        if not model:
            st.toast("Please select a model", icon="🚨")
            return

        st.session_state["ip"] = ip
        st.session_state["base_url"] = base_url
        st.session_state["api_key"] = api_key
        st.session_state["model"] = model

        st.toast("Settings saved", icon="✅")
        st.rerun()

if (
    "ip" not in st.session_state or not st.session_state["ip"] or
    "base_url" not in st.session_state or not st.session_state["base_url"] or
    "api_key" not in st.session_state or not st.session_state["api_key"] or
    "model" not in st.session_state or not st.session_state["model"]
):
    settings()
    st.stop()



if "messages" not in st.session_state:
    st.session_state.messages = []

device_settings = get_device_settings(st.session_state["ip"])

st.title(f"🎧 Welcome to {device_settings['device']}")

client = Anthropic(api_key=st.session_state["api_key"], base_url=st.session_state["base_url"])

language = st.sidebar.selectbox("Language", options=LANGUAGE_NAME, index=device_settings['language'])
if language != LANGUAGE_NAME[device_settings['language']]:
    set_device_settings(st.session_state["ip"], {"language": LANGUAGE_NAME.index(language)})

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if msg := st.chat_input("What is up?"):
    st.session_state.messages.append({"role": "user", "content": msg})
    with st.chat_message("user"):
        st.markdown(msg)

    def response_generator():

        current_prompt = AI_SYSTEM_PROMPT.substitute(language=language)

        for _ in range(MAX_TOOL_ROUNDS):

            with client.messages.stream(
                system=current_prompt,
                model=st.session_state["model"],
                # model="claude-3-haiku-20240307",
                messages=st.session_state["messages"][-11:],
                tools=TOOLS,
                max_tokens=4096,
            ) as stream:
                for event in stream:
                    if event.type == "text":
                        yield event.text
                
                final_message = stream.get_final_message()
                
                tool_uses = [
                    {'type': blk.type, 'id': blk.id, 'name': blk.name, 'input': blk.input}
                    for blk in final_message.content if blk.type == "tool_use"
                ]

                if not tool_uses:
                    break

                st.session_state.messages.append({"role": "assistant", "content": tool_uses})

                tool_results = []
                for tool_use in tool_uses:
                    kwargs = {"ip": st.session_state["ip"]}
                    if tool_use['input']:
                        kwargs["params"] = tool_use['input']

                    tool_result = execute_tool(tool_use['name'], kwargs)
                    result_str = tool_result if isinstance(tool_result, str) else json.dumps(tool_result)
                    content = {'type': "tool_result",'tool_use_id': tool_use['id'], "content": result_str}

                    tool_results.append(content)

                st.session_state.messages.append({"role": "user", "content": tool_results })

    with st.chat_message("assistant"):
        response = st.write_stream(response_generator())
    st.session_state.messages.append({"role": "assistant", "content": response})