/**
 * Luxsin 聊天页：浏览器 UI，经 SSE 对接 FastAPI，可选浏览器内调用设备（Luxsin）。
 *
 * 依赖：static/js/device.js（Luxsin）、marked（Markdown）。
 * 流程：GET /sse/messages 拉历史 → POST /sse/question 流式回复 → 若含 tool_use 则用 device.js 执行 → 再 POST 工具结果续聊。
 */

(function () {
    // ─────────────────────────────────────────────
    // DOM 引用
    // ─────────────────────────────────────────────

    const chatEl = document.getElementById("chat");
    const inputEl = document.getElementById("question");
    const sendBtn = document.getElementById("send");
    const clearBtn = document.getElementById("clear");
    const chatSelect = document.getElementById("chat-select");

    const confirmModal = document.getElementById("confirm-modal");
    const confirmPanel = document.getElementById("confirm-modal-panel");
    const confirmTitle = document.getElementById("confirm-modal-title");
    const confirmBody = document.getElementById("confirm-modal-body");
    const confirmIcon = document.getElementById("confirm-modal-icon");
    const confirmOk = document.getElementById("confirm-modal-ok");
    const confirmCancel = document.getElementById("confirm-modal-cancel");

    /** @type {((value: boolean) => void) | null} */
    let modalResolve = null;

    /** 弹窗变体对应的图标（仅展示） */
    const VARIANT_ICONS = { default: "🛠️", warning: "⚙️", danger: "⚠️" };

    /**
     * 自定义居中确认框，替代 window.confirm，风格与暗色页一致。
     * @param {string | { title?: string, body: string, variant?: 'default'|'warning'|'danger', okLabel?: string, icon?: string }} options
     * @returns {Promise<boolean>} true 表示确认，false 表示取消
     */
    function showConfirmModal(options) {
        const o =
            typeof options === "string"
                ? {
                      title: "Confirm",
                      body: options,
                      variant: "default",
                      okLabel: "Agree",
                  }
                : {
                      title: options.title || "Confirm",
                      body: options.body || "",
                      variant: options.variant || "default",
                      okLabel: options.okLabel || "Agree",
                      icon: options.icon,
                  };

        if (!confirmModal || !confirmPanel || !confirmTitle || !confirmBody || !confirmOk || !confirmCancel) {
            return Promise.resolve(window.confirm(o.body));
        }

        confirmIcon.textContent = o.icon || VARIANT_ICONS[o.variant] || VARIANT_ICONS.default;
        confirmPanel.dataset.variant = o.variant;
        confirmTitle.textContent = o.title;
        confirmBody.textContent = o.body;
        confirmOk.textContent = o.okLabel;

        confirmModal.hidden = false;
        confirmModal.setAttribute("aria-hidden", "false");

        return new Promise((resolve) => {
            modalResolve = resolve;
            requestAnimationFrame(() => {
                if (o.variant === "danger") {
                    confirmCancel.focus();
                } else {
                    confirmOk.focus();
                }
            });
        });
    }

    /** 关闭弹窗并 resolve Promise */
    function closeConfirmModal(value) {
        if (!confirmModal) return;
        confirmModal.hidden = true;
        confirmModal.setAttribute("aria-hidden", "true");
        if (modalResolve) {
            modalResolve(value);
            modalResolve = null;
        }
    }

    /** 绑定确认 / 取消 / 遮罩点击 / Esc */
    function initConfirmModal() {
        if (!confirmOk || !confirmCancel || !confirmModal) return;
        confirmOk.addEventListener("click", () => closeConfirmModal(true));
        confirmCancel.addEventListener("click", () => closeConfirmModal(false));
        confirmModal.addEventListener("click", (e) => {
            if (e.target === confirmModal) closeConfirmModal(false);
        });
        document.addEventListener("keydown", (e) => {
            if (confirmModal && !confirmModal.hidden && e.key === "Escape") {
                e.preventDefault();
                closeConfirmModal(false);
            }
        });
    }

    initConfirmModal();

    /** localStorage 中缓存设备 IP 的键名 */
    const DEVICE_IP_KEY = "luxsin_device_ip";
    /** 无缓存时使用的默认设备 IP */
    const DEFAULT_DEVICE_IP = "10.0.0.119";

    /** 与后端 QuestionRequest.language 一致：0 EN / 1 繁体 / 2 简体 */
    const CHAT_LANGUAGE = 2;

    /** 设备 MAC 缓存（与 /sse/chats 查询一致） */
    let cachedMac = null;
    /** 当前选中的会话 ID，与 QuestionRequest.chat_id 对应 */
    let currentChatId = null;

    function chatIdStorageKey(mac) {
        return "luxsin_chat_id_" + mac;
    }

    /**
     * 从设备拉取 MAC，供 chats / question 请求使用。
     * @returns {Promise<string>}
     */
    async function ensureMac() {
        if (cachedMac) return cachedMac;
        const ip = await getDeviceIp();
        const d = new Luxsin(ip);
        const s = await d.syncData();
        cachedMac = String(s.mac ?? "");
        return cachedMac;
    }

    /**
     * 将数据库行转为与 renderHistoryMessage 一致的结构（content 可能是 JSON 字符串）。
     * @param {{ role: string, content: string }} row
     */
    function normalizeDbRow(row) {
        const role = row.role;
        let c = row.content;
        if (typeof c === "string") {
            const t = c.trim();
            if (t.startsWith("[") || t.startsWith("{")) {
                try {
                    c = JSON.parse(c);
                } catch (_) {
                    /* 保持原字符串 */
                }
            }
        }
        return { role, content: c };
    }

    /**
     * 填充会话下拉框。
     * @param {Array<{ id: string, title?: string }>} chats
     */
    function fillChatSelect(chats) {
        if (!chatSelect) return;
        chatSelect.innerHTML = "";
        chats.forEach((c) => {
            const opt = document.createElement("option");
            opt.value = c.id;
            opt.textContent = c.title || String(c.id).slice(0, 8) + "…";
            chatSelect.appendChild(opt);
        });
    }

    /**
     * 拉取当前 chat_id 的消息并渲染；若末尾为 user 则续跑 assistant。
     */
    async function loadMessagesForCurrentChat() {
        if (!currentChatId) {
            chatEl.innerHTML = "";
            return;
        }
        const res = await fetch(
            "/sse/messages?chat_id=" + encodeURIComponent(currentChatId)
        );
        if (!res.ok) return;
        const list = await res.json();
        chatEl.innerHTML = "";
        if (!Array.isArray(list) || list.length === 0) return;
        list.forEach((row) => renderHistoryMessage(normalizeDbRow(row)));
        chatEl.scrollTop = chatEl.scrollHeight;

        const ip = await getDeviceIp();
        const luxsin = new Luxsin(ip);
        const deviceSettings = await luxsin.syncData();

        const lastNorm = normalizeDbRow(list[list.length - 1]);
        if (lastNorm.role === "user") {
            sendBtn.disabled = true;
            const assistantLine = addMsg("assistant", "Assistant: ");
            const canSendAgain = await streamQuestion(
                { continue_pending: true, language: deviceSettings.language, device: deviceSettings.device, mac: deviceSettings.mac },
                assistantLine
            );
            if (canSendAgain) {
                sendBtn.disabled = false;
            }
        }
    }

    /**
     * 发送或工具链结束后同步当前会话 ID（新建会话后 chat_id 由列表第一条得到）。
     */
    async function syncChatIdAfterSend() {
        const mac = await ensureMac();
        if (!mac) return;
        const res = await fetch("/sse/chats?mac=" + encodeURIComponent(mac));
        if (!res.ok) return;
        const chats = await res.json();
        fillChatSelect(chats);
        if (chats.length === 0) return;
        if (!currentChatId || !chats.some((x) => x.id === currentChatId)) {
            currentChatId = chats[0].id;
            localStorage.setItem(chatIdStorageKey(mac), currentChatId);
            if (chatSelect) chatSelect.value = currentChatId;
        }
    }

    // ─────────────────────────────────────────────
    // Markdown 渲染（消息区 innerHTML）
    // ─────────────────────────────────────────────

    /**
     * 纯文本或 Markdown 转为 HTML；无 marked 时做 HTML 转义并保留换行。
     * @param {string} [text]
     * @returns {string}
     */
    function renderMarkdown(text) {
        if (typeof marked !== "undefined") {
            return marked.parse(text ?? "");
        }
        return String(text ?? "")
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/\n/g, "<br>");
    }

    /**
     * 设置整条消息的 HTML；dataset.raw 保存原文，便于流式拼接后整段重渲染。
     * @param {HTMLElement} node
     * @param {string} text
     */
    function setMsgContent(node, text) {
        node.dataset.raw = text;
        node.innerHTML = renderMarkdown(text);
    }

    /**
     * 流式追加 assistant 片段后整段重解析 Markdown。
     * @param {HTMLElement} node
     * @param {string} delta
     */
    function appendMsgContent(node, delta) {
        const raw = (node.dataset.raw || "") + delta;
        setMsgContent(node, raw);
    }

    /**
     * 追加一条气泡：user / assistant / tool。
     * @param {"user"|"assistant"|"tool"} role
     * @param {string} text
     * @returns {HTMLDivElement}
     */
    function addMsg(role, text) {
        const div = document.createElement("div");
        div.className = `msg ${role}`;
        setMsgContent(div, text);
        chatEl.appendChild(div);
        chatEl.scrollTop = chatEl.scrollHeight;
        return div;
    }

    /**
     * 将服务端单条 message 渲染到聊天区。
     * 仅恢复纯文本部分；工具调用 / 工具回传在刷新后与线上下文难以对齐，不展示。
     * @param {{ role: string, content: string|Array }} msg
     */
    function renderHistoryMessage(msg) {
        const role = msg.role;
        const c = msg.content;

        if (role === "user") {
            if (typeof c === "string") {
                addMsg("user", "You: " + c);
            }
            return;
        }

        if (role === "assistant") {
            if (typeof c === "string") {
                addMsg("assistant", "Assistant: " + c);
                return;
            }
            if (Array.isArray(c)) {
                const texts = c
                    .filter((b) => b && b.type === "text")
                    .map((b) => b.text || "")
                    .join("");
                if (texts.trim()) {
                    addMsg("assistant", "Assistant: " + texts);
                }
            }
        }
    }

    /**
     * 页面加载：按设备 MAC 拉取会话列表，恢复上次选中的 chat_id，再拉消息并渲染。
     */
    async function hydrateInitialMessages() {
        try {
            const mac = await ensureMac();
            if (!mac) return;
            const res = await fetch("/sse/chats?mac=" + encodeURIComponent(mac));
            if (!res.ok) return;
            const chats = await res.json();
            fillChatSelect(chats);
            let chatId = localStorage.getItem(chatIdStorageKey(mac));
            if (chatId && !chats.some((c) => c.id === chatId)) chatId = null;
            if (!chatId && chats.length) chatId = chats[0].id;
            if (chatId) {
                localStorage.setItem(chatIdStorageKey(mac), chatId);
                currentChatId = chatId;
                if (chatSelect) chatSelect.value = chatId;
                await loadMessagesForCurrentChat();
            } else {
                currentChatId = null;
            }
        } catch (err) {
            console.error("Failed to load chats/messages:", err?.message || err);
        }
    }

    /**
     * 清空服务端会话并刷新页面。
     */
    async function clearMessages() {
        if (!clearBtn) return;
        const ok = await showConfirmModal({
            title: "Clear conversation",
            body:
                "This removes all messages stored on the server. The list will be empty after refresh, and this cannot be undone.\n\nContinue?",
            variant: "danger",
            okLabel: "Clear",
        });
        if (!ok) return;
        if (!currentChatId) {
            addMsg("tool", "No chat selected.");
            return;
        }
        clearBtn.disabled = true;
        try {
            const res = await fetch(
                "/sse/clear?chat_id=" + encodeURIComponent(currentChatId),
                { method: "POST" }
            );
            if (!res.ok) {
                addMsg("tool", "Clear failed, please retry.");
                return;
            }
            window.location.reload();
        } catch (_) {
            addMsg("tool", "Clear failed (network).");
        } finally {
            clearBtn.disabled = false;
        }
    }

    // ─────────────────────────────────────────────
    // 设备 IP（localStorage 或默认值）
    // ─────────────────────────────────────────────

    /**
     * 从 localStorage 读取设备 IP；若无则写入默认并返回。
     * @returns {Promise<string>}
     */
    async function getDeviceIp() {
        const cached = localStorage.getItem(DEVICE_IP_KEY);
        if (cached) return cached;
        localStorage.setItem(DEVICE_IP_KEY, DEFAULT_DEVICE_IP);
        return DEFAULT_DEVICE_IP;
    }

    // ─────────────────────────────────────────────
    // 工具执行（浏览器内 Luxsin，名称与后端 TOOLS 一致）
    // ─────────────────────────────────────────────

    /**
     * 设备写操作前弹窗确认。
     * @param {string | { title?: string, body: string, variant?: string, okLabel?: string, icon?: string }} message
     * @returns {Promise<boolean>}
     */
    async function confirmDeviceWrite(message) {
        return showConfirmModal(message);
    }

    /**
     * 执行单个 tool_use。写/删类操作先弹窗；用户拒绝时返回字符串作为 tool_result。
     * @param {Luxsin} device
     * @param {{ id: string, name: string, input?: object }} toolCall
     * @returns {Promise<*>}
     */
    async function executeToolCall(device, toolCall) {
        const input = toolCall.input || {};
        switch (toolCall.name) {
            case "get_device_settings":
                return await device.syncData();
            case "get_peq_list": {
                const peq = await device.syncPeq();
                return peq.peq.map((item) => item.name);
            }
            case "get_current_peq":
                return await device.currentPeq();
            case "set_device_settings": {
                const ok = await confirmDeviceWrite({
                    title: "Apply device settings",
                    body:
                        "The assistant wants to write settings to your device (volume, I/O, display, and other options).\n\n" +
                        "· Agree: apply immediately to the device on your LAN\n" +
                        "· Cancel: do not change the device",
                    variant: "warning",
                    okLabel: "Apply",
                });
                if (!ok) {
                    return "User rejected: No device settings modified.";
                }
                await device.setting(input);
                return "OK";
            }
            case "set_peq": {
                const peqName = input && input.name != null ? String(input.name) : "(unnamed)";
                const ok = await confirmDeviceWrite({
                    title: "Save PEQ",
                    body:
                        "The assistant wants to add or overwrite a PEQ preset on the device.\n\n" +
                        `Name: ${peqName}\n\n` +
                        "· Agree: save to device storage\n" +
                        "· Cancel: discard this PEQ write",
                    variant: "warning",
                    okLabel: "Save",
                });
                if (!ok) {
                    return "User rejected: No PEQ added or updated.";
                }
                await device.updatePeq(input);
                return "OK";
            }
            case "delete_peqs": {
                const peqNames = input && input.names != null ? input.names.join(", ") : "(unspecified)";

                const ok = await confirmDeviceWrite({
                    title: "Delete PEQ",
                    body:
                        "The assistant wants to delete the following preset(s) from the device:\n\n" +
                        `${peqNames}\n\n` +
                        "Recovery may require re-sync or re-import. Please confirm before proceeding.\n\n" +
                        "· Delete: run immediately\n" +
                        "· Cancel: keep presets on the device",
                    variant: "danger",
                    okLabel: "Delete",
                });
                if (!ok) {
                    return "User rejected: No PEQ deleted.";
                }
                await device.deletePeqs(input);
                return "OK";
            }
            case "optimize_eq": {
                try {
                    const eq = await device.currentPeq();
                    const res = await fetch("/sse/optimize_eq", {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({
                            raw_peq: eq,
                        }),
                    });
                    if (!res.ok) {
                        const errText = await res.text();
                        throw new Error(`HTTP ${res.status}: ${errText.slice(0, 300)}`);
                    }
                    const data = await res.json();
                    return data.optimized_peq ?? {};
                } catch (err) {
                    return `Tool execution failed: ${err?.message || String(err)}`;
                }
            }
            default:
                throw new Error(`Unsupported tool: ${toolCall.name}`);
        }
    }

    /**
     * 依次执行多个 tool_use，返回 Anthropic 风格的 tool_result 列表（content 为字符串）。
     * @param {Array<{ id: string, name: string, input?: object }>} toolCalls
     * @returns {Promise<Array<{ type: string, tool_use_id: string, content: string }>>}
     */
    async function executeToolCalls(toolCalls) {
        const ip = await getDeviceIp();
        if (!ip) throw new Error("No device IP provided");
        const device = new Luxsin(ip);
        const results = [];

        for (const toolCall of toolCalls) {
            try {
                const content = await executeToolCall(device, toolCall);
                const text = typeof content === "string" ? content : JSON.stringify(content);
                results.push({ type: "tool_result", tool_use_id: toolCall.id, content: text});
            } catch (err) {
                results.push({
                    type: "tool_result",
                    tool_use_id: toolCall.id,
                    content: `Tool execution failed: ${err?.message || String(err)}`,
                });
            }
        }
        return results;
    }

    // ─────────────────────────────────────────────
    // SSE：POST 响应体流式解析（text/event-stream）
    // ─────────────────────────────────────────────

    /**
     * body.question 为字符串（用户）或 tool_result[]（工具回传后）；
     * body.continue_pending 为 true 时不带 question，在服务端已有末尾 user 上续生成。
     * 流式帧为 SSE，每行 data: 后为 JSON，type 为 text | done。
     * 必须收到至少一次 type === "done" 才视为本轮完成；否则返回 false，调用方勿恢复发送。
     * @param {{ question?: string|Array, continue_pending?: boolean, tool_names?: string[], language?: number }} body
     * @param {HTMLElement} assistantLine
     * @returns {Promise<boolean>} true 表示可再次发送；false 表示未收到 done，应保持禁用发送
     */
    async function streamQuestion(body, assistantLine) {
        const mac = await ensureMac();
        const payload = {
            ...body,
            mac,
            chat_id: currentChatId,
            language: body.language,
            device: body.device,
        };
        const response = await fetch("/sse/question", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
        });

        if (!response.ok || !response.body) {
            addMsg("tool", "Request failed, please try again.");
            return true;
        }

        const decoder = new TextDecoder("utf-8");
        const reader = response.body.getReader();
        let buffer = "";
        let pendingToolCalls = [];
        let receivedDone = false;

        const handlePayload = (payload) => {
            if (payload.type === "error") {
                addMsg("tool", String(payload.content ?? "Request error"));
                receivedDone = true;
                return;
            }
            if (payload.type === "text") {
                appendMsgContent(assistantLine, payload.content);
                return;
            }
            if (payload.type === "done") {
                receivedDone = true;
                const blocks = Array.isArray(payload.content) ? payload.content : [];
                pendingToolCalls = blocks.filter((x) => x && x.type === "tool_use");
            }
        };

        const parseAndHandleEvent = (rawEvent) => {
            const dataLines = rawEvent
                .split("\n")
                .filter((line) => line.startsWith("data:"))
                .map((line) => line.slice(5).trim());
            if (dataLines.length === 0) return;
            const dataText = dataLines.join("\n");
            try {
                handlePayload(JSON.parse(dataText));
            } catch (_) {
                // 半包或非法 JSON，跳过
            }
        };

        while (true) {
            const { value, done } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            const events = buffer.split("\n\n");
            buffer = events.pop() || "";

            for (const rawEvent of events) {
                parseAndHandleEvent(rawEvent);
            }
        }

        if (buffer.trim()) {
            parseAndHandleEvent(buffer);
        }

        if (!receivedDone) {
            addMsg(
                "tool",
                "The reply stream ended before completion. Refresh the page to continue."
            );
            return false;
        }

        if (pendingToolCalls.length > 0) {
            const n = pendingToolCalls.length;
            const toolStatusLine = addMsg(
                "tool",
                n === 1 ? "Running tool call…" : `Found ${n} tool calls, running…`
            );
            try {
                const toolResults = await executeToolCalls(pendingToolCalls);
                const toolNames = pendingToolCalls.map((x) => x.name);
                setMsgContent(
                    toolStatusLine,
                    n === 1 ? "Completed 1 tool call." : `Completed ${n} tool calls.`
                );
                return await streamQuestion(
                    { question: toolResults, tool_names: toolNames, language: body.language, mac: mac, device: body.device  },
                    assistantLine
                );
            } catch (err) {
                setMsgContent(
                    toolStatusLine,
                    `Tool execution failed: ${err?.message || String(err)}`
                );
                return true;
            }
        }
        return true;
    }

    // ─────────────────────────────────────────────
    // 发送用户输入
    // ─────────────────────────────────────────────

    async function sendQuestion() {
        if (sendBtn.disabled) return;
        const question = inputEl.value.trim();
        if (!question) return;

        addMsg("user", "You: " + question);
        inputEl.value = "";
        sendBtn.disabled = true;

        const ip = await getDeviceIp();
        const device = new Luxsin(ip);
        const deviceSettings = await device.syncData();

        const assistantLine = addMsg("assistant", "Assistant: ");
        const canSendAgain = await streamQuestion(
            { question, language: deviceSettings.language, device: deviceSettings.device, mac: deviceSettings.mac },
            assistantLine
        );
        if (canSendAgain) {
            sendBtn.disabled = false;
        }
        await syncChatIdAfterSend();
    }

    if (chatSelect) {
        chatSelect.addEventListener("change", async () => {
            currentChatId = chatSelect.value || null;
            const mac = await ensureMac();
            if (mac && currentChatId) {
                localStorage.setItem(chatIdStorageKey(mac), currentChatId);
            }
            await loadMessagesForCurrentChat();
        });
    }

    sendBtn.addEventListener("click", sendQuestion);
    inputEl.addEventListener("keydown", (e) => {
        if (e.key === "Enter") sendQuestion();
    });
    if (clearBtn) {
        clearBtn.addEventListener("click", clearMessages);
    }

    void hydrateInitialMessages();
})();
