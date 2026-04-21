/**
 * Luxsin 聊天页：浏览器 UI，经 SSE 对接 FastAPI，可选浏览器内调用设备（Luxsin）。
 *
 * 依赖：static/js/device.js（Luxsin）、marked（Markdown）。
 * 流程：GET /sse/messages 拉历史 → POST /sse/question 流式回复 → SSE 若出现 type=tool_use 则用 device.js 执行 → POST /chat/tool_result 回传，服务端继续同一轮流。
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
    const toolbarActions = document.querySelector(".toolbar-actions");

    const confirmModal = document.getElementById("confirm-modal");
    const confirmPanel = document.getElementById("confirm-modal-panel");
    const confirmTitle = document.getElementById("confirm-modal-title");
    const confirmBody = document.getElementById("confirm-modal-body");
    const confirmIcon = document.getElementById("confirm-modal-icon");
    const confirmOk = document.getElementById("confirm-modal-ok");
    const confirmCancel = document.getElementById("confirm-modal-cancel");

    /** @type {((value: boolean) => void) | null} */
    let modalResolve = null;
    /** 打开弹窗前的焦点元素（关闭时恢复） */
    let lastFocusedBeforeModal = null;

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

        lastFocusedBeforeModal = document.activeElement;
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
        const active = document.activeElement;
        if (active && confirmModal.contains(active) && typeof active.blur === "function") {
            active.blur();
        }
        confirmModal.hidden = true;
        confirmModal.setAttribute("aria-hidden", "true");
        if (lastFocusedBeforeModal && typeof lastFocusedBeforeModal.focus === "function") {
            lastFocusedBeforeModal.focus();
        } else if (document.body && typeof document.body.focus === "function") {
            document.body.focus();
        }
        lastFocusedBeforeModal = null;
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

    /** 与后端 app/chat/constants.py 的 MessageType 对齐 */
    const MESSAGE_TYPE = {
        DEFAULT: 0,
        SUMMARIZE: 1,
        OPTIMIZING: 2,
        TITLE: 3,
    };

    /** 设备 MAC 缓存（与 /sse/chats 查询一致） */
    let cachedMac = null;
    /** 当前选中的会话 ID，与 QuestionRequest.chat_id 对应 */
    let currentChatId = null;
    /** 最近 4h token 消耗显示节点 */
    let recentConsumptionEl = null;
    /** 优化记录按钮 */
    let optimizationRecordsBtn = null;
    /** 配置按钮 */
    let configBtn = null;
    /** 新建会话按钮 */
    let newChatBtn = null;
    /** token 轮询定时器 */
    let consumptionTimer = null;

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
     * @param {{ id?: string, role: string, content: string, type?: number, before_peq?: object|null, after_peq?: object|null, applied?: boolean, applied_at?: string|null, created_at?: string }} row
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
        return {
            id: row.id,
            role,
            content: c,
            type: Number(row.type ?? 0),
            before_peq: row.before_peq || null,
            after_peq: row.after_peq || null,
            applied: !!row.applied,
            applied_at: row.applied_at || null,
            created_at: row.created_at,
        };
    }

    function _fc(f) {
        return Number(f?.fc ?? f?.frequency ?? 0);
    }

    function buildEqCurve(eq) {
        const points = [];
        const minF = 20;
        const maxF = 20000;
        const n = 220;
        const preamp = Number(eq?.preamp ?? 0) || 0;
        const filters = Array.isArray(eq?.filters) ? eq.filters : [];
        for (let i = 0; i < n; i++) {
            const t = i / (n - 1);
            const f = minF * Math.pow(maxF / minF, t);
            let g = preamp;
            for (const flt of filters) {
                const fc = _fc(flt);
                const gain = Number(flt?.gain ?? 0) || 0;
                const q = Math.max(0.15, Number(flt?.q ?? 1) || 1);
                if (fc <= 0) continue;
                const x = Math.log2(f / fc);
                const bw = 1 / q;
                g += gain * Math.exp(-(x * x) / (2 * bw * bw));
            }
            points.push({ freq: f, gain: g });
        }
        return points;
    }

    function drawEqCompare(canvas, eqA, eqB, labelA = "A", labelB = "B") {
        const ctx = canvas.getContext("2d");
        if (!ctx) return;
        const w = canvas.width;
        const h = canvas.height;
        ctx.clearRect(0, 0, w, h);
        ctx.fillStyle = "#121826";
        ctx.fillRect(0, 0, w, h);

        const a = buildEqCurve(eqA);
        const b = buildEqCurve(eqB);
        const allGains = a.map((p) => p.gain).concat(b.map((p) => p.gain));
        const gMin = Math.min(-12, Math.floor(Math.min(...allGains) - 1));
        const gMax = Math.max(12, Math.ceil(Math.max(...allGains) + 1));
        const pad = { l: 36, r: 12, t: 12, b: 24 };
        const plotW = w - pad.l - pad.r;
        const plotH = h - pad.t - pad.b;
        const xOf = (freq) =>
            pad.l + ((Math.log10(freq) - Math.log10(20)) / (Math.log10(20000) - Math.log10(20))) * plotW;
        const yOf = (gain) => pad.t + ((gMax - gain) / (gMax - gMin || 1)) * plotH;

        ctx.strokeStyle = "rgba(255,255,255,0.15)";
        ctx.lineWidth = 1;
        [20, 50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000].forEach((f) => {
            const x = xOf(f);
            ctx.beginPath();
            ctx.moveTo(x, pad.t);
            ctx.lineTo(x, h - pad.b);
            ctx.stroke();
        });
        [-12, -6, 0, 6, 12].forEach((g) => {
            const y = yOf(g);
            ctx.beginPath();
            ctx.moveTo(pad.l, y);
            ctx.lineTo(w - pad.r, y);
            ctx.stroke();
        });

        // 横轴坐标标签
        ctx.fillStyle = "rgba(255,255,255,0.72)";
        ctx.font = "11px system-ui, -apple-system, Segoe UI, sans-serif";
        ctx.textAlign = "center";
        ctx.textBaseline = "top";
        [20, 50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000].forEach((f) => {
            const x = xOf(f);
            const label = f >= 1000 ? `${f / 1000}k` : String(f);
            ctx.fillText(label, x, h - pad.b + 6);
        });

        // Y 轴坐标标签（dB）
        ctx.fillStyle = "rgba(255,255,255,0.72)";
        ctx.font = "11px system-ui, -apple-system, Segoe UI, sans-serif";
        ctx.textAlign = "right";
        ctx.textBaseline = "middle";
        [-12, -6, 0, 6, 12].forEach((g) => {
            const y = yOf(g);
            const label = g > 0 ? `+${g}` : String(g);
            ctx.fillText(label, pad.l - 6, y);
        });
        ctx.textAlign = "left";
        ctx.textBaseline = "bottom";
        ctx.fillText("dB", 6, pad.t - 2);

        const drawLine = (pts, color) => {
            ctx.strokeStyle = color;
            ctx.lineWidth = 2;
            ctx.beginPath();
            pts.forEach((p, idx) => {
                const x = xOf(p.freq);
                const y = yOf(p.gain);
                if (idx === 0) ctx.moveTo(x, y);
                else ctx.lineTo(x, y);
            });
            ctx.stroke();
        };
        drawLine(a, "#5bbcff");
        drawLine(b, "#ffb347");

        // 图例
        const legendX = w - 220;
        const legendY = pad.t + 8;
        const legendLineW = 22;
        ctx.font = "12px system-ui, -apple-system, Segoe UI, sans-serif";
        ctx.textAlign = "left";
        ctx.textBaseline = "middle";

        ctx.strokeStyle = "#5bbcff";
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.moveTo(legendX, legendY);
        ctx.lineTo(legendX + legendLineW, legendY);
        ctx.stroke();
        ctx.fillStyle = "rgba(255,255,255,0.9)";
        ctx.fillText(labelA, legendX + legendLineW + 8, legendY);

        ctx.strokeStyle = "#ffb347";
        ctx.beginPath();
        ctx.moveTo(legendX, legendY + 18);
        ctx.lineTo(legendX + legendLineW, legendY + 18);
        ctx.stroke();
        ctx.fillStyle = "rgba(255,255,255,0.9)";
        ctx.fillText(labelB, legendX + legendLineW + 8, legendY + 18);
    }

    /**
     * 渲染优化记录列表：显示时间/应用或回滚/原始名/优化名，点击条目后显示 A/B 曲线。
     * @param {Array<{id: string, created_at: string, before_peq: object, after_peq: object, applied: boolean}>} records
     */
    function renderOptimizationRecords(records) {
        if (!Array.isArray(records) || records.length === 0) {
            addMsg("tool", "No optimization records in current chat.");
            return;
        }

        const box = document.createElement("div");
        box.className = "msg tool";
        box.style.whiteSpace = "normal";

        const title = document.createElement("div");
        title.textContent = "Optimization Records";
        title.style.marginBottom = "8px";
        box.appendChild(title);

        const listWrap = document.createElement("div");
        listWrap.style.display = "grid";
        listWrap.style.gap = "6px";
        listWrap.style.marginBottom = "10px";
        box.appendChild(listWrap);

        const status = document.createElement("div");
        status.style.opacity = "0.9";
        status.style.marginBottom = "8px";
        status.textContent = "Select one record to preview A/B curve (A=Before, B=After).";
        box.appendChild(status);

        const canvas = document.createElement("canvas");
        canvas.width = 680;
        canvas.height = 260;
        canvas.style.width = "100%";
        canvas.style.display = "none";
        box.appendChild(canvas);

        records.forEach((r, idx) => {
            const at = r.created_at ? new Date(r.created_at).toLocaleString() : "-";
            const stateText = r.applied ? "应用" : "回滚";
            const beforeName = r?.before_peq?.name || "(unnamed)";
            const afterName = r?.after_peq?.name || "(unnamed)";

            const row = document.createElement("div");
            row.style.display = "grid";
            row.style.gridTemplateColumns = "1fr auto auto";
            row.style.gap = "8px";
            row.style.alignItems = "center";

            const itemBtn = document.createElement("button");
            itemBtn.type = "button";
            itemBtn.className = "btn-secondary";
            itemBtn.style.textAlign = "left";
            itemBtn.style.width = "100%";
            itemBtn.style.padding = "8px 10px";
            itemBtn.textContent = `${idx + 1}. ${at} | ${stateText} | ${beforeName} -> ${afterName}`;
            itemBtn.addEventListener("click", async () => {
                try {
                    const ip = await getDeviceIp();
                    const device = new Luxsin(ip);
                    const currentEq = await device.currentPeq();
                    drawEqCompare(
                        canvas,
                        currentEq || {},
                        r.after_peq || {},
                        `Current`,
                        `Recommended`
                    );
                    canvas.style.display = "block";
                    status.textContent = `Selected #${idx + 1}: A=Current(${currentEq?.name || "current"}), B=Recommended(${afterName})`;
                } catch (err) {
                    status.textContent = `加载当前EQ失败: ${formatDeviceToolError(err)}`;
                }
            });

            const btnApply = document.createElement("button");
            btnApply.type = "button";
            btnApply.className = "btn-secondary";
            btnApply.textContent = "应用";

            const btnRollback = document.createElement("button");
            btnRollback.type = "button";
            btnRollback.className = "btn-secondary";
            btnRollback.textContent = "回滚";

            const refreshActionButtons = () => {
                const appliedNow = !!r.applied;
                btnApply.disabled = appliedNow;
                btnRollback.disabled = !appliedNow;
                btnApply.style.opacity = appliedNow ? "0.55" : "1";
                btnRollback.style.opacity = appliedNow ? "1" : "0.55";
            };

            const applyEq = async (peq, actionLabel) => {
                const ok = await confirmDeviceWrite({
                    title: actionLabel === "应用" ? "Apply Optimized EQ" : "Rollback EQ",
                    body:
                        `${actionLabel}该条优化记录到设备？\n\n` +
                        `Name: ${peq?.name || "(unnamed)"}\n\n` +
                        "· Agree: write to device\n" +
                        "· Cancel: do nothing",
                    variant: "warning",
                    okLabel: actionLabel,
                });
                if (!ok) return;
                btnApply.disabled = true;
                btnRollback.disabled = true;
                try {
                    const ip = await getDeviceIp();
                    const device = new Luxsin(ip);
                    await device.updatePeq(peq || {});
                    const appliedNow = actionLabel === "应用";
                    const appliedRes = await fetch(
                        "/sse/update_message_applied?message_id=" +
                            encodeURIComponent(String(r.id)) +
                            "&applied=" +
                            encodeURIComponent(String(appliedNow)),
                        { method: "POST" }
                    );
                    if (!appliedRes.ok) {
                        throw new Error(`update_message_applied failed: HTTP ${appliedRes.status}`);
                    }
                    r.applied = appliedNow;
                    const nextState = r.applied ? "应用" : "回滚";
                    itemBtn.textContent = `${idx + 1}. ${at} | ${nextState} | ${beforeName} -> ${afterName}`;
                    refreshActionButtons();
                    const currentEq = await device.currentPeq();
                    drawEqCompare(
                        canvas,
                        currentEq || {},
                        r.after_peq || {},
                        `Current`,
                        `Recommended`
                    );
                    canvas.style.display = "block";
                    status.textContent = `记录 #${idx + 1} 已${actionLabel}。图表已刷新：A=Current(${currentEq?.name || "current"}), B=Recommended(${afterName})`;
                } catch (err) {
                    status.textContent = `${actionLabel}失败: ${formatDeviceToolError(err)}`;
                } finally {
                    refreshActionButtons();
                }
            };

            btnApply.addEventListener("click", () => applyEq(r.after_peq, "应用"));
            btnRollback.addEventListener("click", () => applyEq(r.before_peq, "回滚"));
            refreshActionButtons();

            row.appendChild(itemBtn);
            row.appendChild(btnApply);
            row.appendChild(btnRollback);
            listWrap.appendChild(row);
        });

        chatEl.appendChild(box);
        chatEl.scrollTop = chatEl.scrollHeight;
    }

    /**
     * 拉取并展示当前会话优化记录。
     */
    async function showOptimizationRecords() {
        if (!currentChatId) {
            addMsg("tool", "No chat selected.");
            return;
        }
        if (optimizationRecordsBtn) optimizationRecordsBtn.disabled = true;
        try {
            const res = await fetch(
                "/sse/optimization_records?chat_id=" + encodeURIComponent(currentChatId)
            );
            if (!res.ok) {
                addMsg("tool", `Load optimization records failed: HTTP ${res.status}`);
                return;
            }
            const records = await res.json();
            renderOptimizationRecords(records);
        } catch (err) {
            addMsg("tool", `Load optimization records failed: ${err?.message || String(err)}`);
        } finally {
            if (optimizationRecordsBtn) optimizationRecordsBtn.disabled = false;
        }
    }

    /**
     * 刷新最近4小时 token 消耗。
     */
    async function refreshRecentConsumption() {
        if (!recentConsumptionEl) return;
        try {
            const mac = await ensureMac();
            if (!mac) {
                recentConsumptionEl.textContent = "Recent 4h Tokens: -";
                return;
            }
            const res = await fetch(
                "/sse/recent_consumption?mac=" + encodeURIComponent(mac)
            );
            if (!res.ok) {
                recentConsumptionEl.textContent = `Recent 4h Tokens: HTTP ${res.status}`;
                return;
            }
            const data = await res.json();
            const raw = data?.consumption;
            const val =
                raw && typeof raw === "object" && "total_tokens" in raw
                    ? raw.total_tokens
                    : typeof raw === "number"
                      ? raw
                      : 0;
            recentConsumptionEl.textContent = `Recent 4h Tokens: ${Number(val || 0)}`;
        } catch {
            recentConsumptionEl.textContent = "Recent 4h Tokens: n/a";
        }
    }

    /**
     * 弹出并更新 AI 配置（base_url / api_key / model）。
     */
    async function openConfigEditor() {
        if (configBtn) configBtn.disabled = true;
        try {
            const mac = await ensureMac();
            if (!mac) {
                addMsg("tool", "Cannot load config: no device MAC.");
                return;
            }
            const res = await fetch("/chat/get_config?mac=" + encodeURIComponent(mac));
            if (!res.ok) {
                addMsg("tool", `Load config failed: HTTP ${res.status}`);
                return;
            }
            const data = await res.json();
            const cfg = data?.config;
            if (!cfg?.id) {
                addMsg("tool", "Load config failed: missing config id.");
                return;
            }

            const baseUrl = window.prompt("base_url", cfg.base_url || "");
            if (baseUrl === null) return;
            const apiKey = window.prompt("api_key", cfg.api_key || "");
            if (apiKey === null) return;
            const model = window.prompt("model", cfg.model || "");
            if (model === null) return;

            const saveRes = await fetch(
                "/chat/update_config?config_id=" + encodeURIComponent(String(cfg.id)),
                {
                    method: "PATCH",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        base_url: baseUrl,
                        api_key: apiKey,
                        model: model,
                    }),
                }
            );
            if (!saveRes.ok) {
                const errText = await saveRes.text();
                addMsg("tool", `Save config failed: HTTP ${saveRes.status} ${errText.slice(0, 160)}`);
                return;
            }
            addMsg("tool", "Config updated successfully.");
        } catch (err) {
            addMsg("tool", `Config update failed: ${err?.message || String(err)}`);
        } finally {
            if (configBtn) configBtn.disabled = false;
        }
    }

    /**
     * 初始化工具栏上的优化记录按钮与 token 指标。
     */
    function initOptimizationControls() {
        if (!toolbarActions) return;
        newChatBtn = document.createElement("button");
        newChatBtn.type = "button";
        newChatBtn.className = "btn-secondary";
        newChatBtn.textContent = "+";
        newChatBtn.title = "New chat";
        newChatBtn.setAttribute("aria-label", "New chat");
        newChatBtn.addEventListener("click", async () => {
            currentChatId = null;
            chatEl.innerHTML = "";
            try {
                const mac = await ensureMac();
                if (mac) {
                    localStorage.removeItem(chatIdStorageKey(mac));
                }
            } catch (_) {
                // ignore storage sync errors
            }
            if (chatSelect) {
                chatSelect.value = "";
                chatSelect.selectedIndex = -1;
            }
            addMsg("tool", "Started a new chat. Next message will create a new session.");
        });

        optimizationRecordsBtn = document.createElement("button");
        optimizationRecordsBtn.type = "button";
        optimizationRecordsBtn.className = "btn-secondary";
        optimizationRecordsBtn.textContent = "Optimization Records";
        optimizationRecordsBtn.addEventListener("click", showOptimizationRecords);

        configBtn = document.createElement("button");
        configBtn.type = "button";
        configBtn.className = "btn-secondary";
        configBtn.textContent = "Config";
        configBtn.addEventListener("click", openConfigEditor);

        recentConsumptionEl = document.createElement("span");
        recentConsumptionEl.style.marginLeft = "8px";
        recentConsumptionEl.style.opacity = "0.9";
        recentConsumptionEl.textContent = "Recent 4h Tokens: -";

        toolbarActions.appendChild(newChatBtn);
        toolbarActions.appendChild(configBtn);
        toolbarActions.appendChild(optimizationRecordsBtn);
        toolbarActions.appendChild(recentConsumptionEl);
    }

    /**
     * 开始轮询最近4小时 token 消耗。
     */
    function startConsumptionPolling() {
        if (consumptionTimer) clearInterval(consumptionTimer);
        void refreshRecentConsumption();
        consumptionTimer = setInterval(() => {
            void refreshRecentConsumption();
        }, 20000);
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
     * 拉取当前 chat_id 的消息并渲染。
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
     * 渲染一条 OPTIMIZING 类型的历史消息：显示按钮，点击后 toggle A/B 对比图。
     * @param {{ id?: string, after_peq?: object|null, before_peq?: object|null, applied?: boolean, created_at?: string }} msg
     */
    function renderOptimizingMessage(msg) {
        const box = document.createElement("div");
        box.className = "msg tool";
        box.style.whiteSpace = "normal";

        const afterName = msg.after_peq?.name || "(unnamed)";
        const beforeName = msg.before_peq?.name || "(unnamed)";
        const at = msg.created_at ? new Date(msg.created_at).toLocaleString() : "";

        const title = document.createElement("div");
        title.style.marginBottom = "8px";
        box.appendChild(title);

        const actions = document.createElement("div");
        actions.style.display = "flex";
        actions.style.gap = "8px";
        box.appendChild(actions);

        const viewBtn = document.createElement("button");
        viewBtn.type = "button";
        viewBtn.className = "btn-secondary";
        viewBtn.textContent = "View comparison";
        actions.appendChild(viewBtn);

        const actionBtn = document.createElement("button");
        actionBtn.type = "button";
        actionBtn.className = "btn-secondary";
        actions.appendChild(actionBtn);

        const canvas = document.createElement("canvas");
        canvas.width = 680;
        canvas.height = 260;
        canvas.style.width = "100%";
        canvas.style.display = "none";
        canvas.style.marginTop = "8px";
        box.appendChild(canvas);

        const status = document.createElement("div");
        status.style.opacity = "0.9";
        status.style.marginTop = "6px";
        box.appendChild(status);

        // 根据 applied 状态刷新标题和操作按钮文案
        const refreshStateUi = () => {
            const stateText = msg.applied ? "应用" : "回滚";
            title.textContent = `EQ Optimization${at ? " · " + at : ""} · ${stateText} · ${beforeName} -> ${afterName}`;
            actionBtn.textContent = msg.applied ? "回滚" : "应用";
        };
        refreshStateUi();

        let shown = false;
        const redrawCanvas = async () => {
            const ip = await getDeviceIp();
            const device = new Luxsin(ip);
            const currentEq = await device.currentPeq();
            drawEqCompare(
                canvas,
                currentEq || {},
                msg.after_peq || {},
                "Current",
                "Recommended"
            );
            status.textContent = `A=Current(${currentEq?.name || "current"}), B=Recommended(${afterName})`;
        };

        viewBtn.addEventListener("click", async () => {
            if (shown) {
                canvas.style.display = "none";
                status.textContent = "";
                viewBtn.textContent = "View comparison";
                shown = false;
                return;
            }
            viewBtn.disabled = true;
            try {
                await redrawCanvas();
                canvas.style.display = "block";
                viewBtn.textContent = "Hide comparison";
                shown = true;
            } catch (err) {
                status.textContent = `Failed to load current EQ: ${formatDeviceToolError(err)}`;
            } finally {
                viewBtn.disabled = false;
            }
        });

        actionBtn.addEventListener("click", async () => {
            // applied=true 当前按钮是"回滚"，目标 peq = before_peq
            // applied=false 当前按钮是"应用"，目标 peq = after_peq
            const toApply = !msg.applied;
            const actionLabel = toApply ? "应用" : "回滚";
            const targetPeq = toApply ? msg.after_peq : msg.before_peq;

            const ok = await confirmDeviceWrite({
                title: toApply ? "Apply Optimized EQ" : "Rollback EQ",
                body:
                    `${actionLabel}该条优化记录到设备？\n\n` +
                    `Name: ${targetPeq?.name || "(unnamed)"}\n\n` +
                    "· Agree: write to device\n" +
                    "· Cancel: do nothing",
                variant: "warning",
                okLabel: actionLabel,
            });
            if (!ok) return;

            actionBtn.disabled = true;
            try {
                const ip = await getDeviceIp();
                const device = new Luxsin(ip);
                await device.updatePeq(targetPeq || {});
                if (msg.id) {
                    const res = await fetch(
                        "/sse/update_message_applied?message_id=" +
                            encodeURIComponent(String(msg.id)) +
                            "&applied=" +
                            encodeURIComponent(String(toApply)),
                        { method: "POST" }
                    );
                    if (!res.ok) {
                        throw new Error(`update_message_applied failed: HTTP ${res.status}`);
                    }
                }
                msg.applied = toApply;
                refreshStateUi();
                if (shown) {
                    await redrawCanvas();
                } else {
                    status.textContent = `已${actionLabel}。`;
                }
            } catch (err) {
                status.textContent = `${actionLabel}失败: ${formatDeviceToolError(err)}`;
            } finally {
                actionBtn.disabled = false;
            }
        });

        chatEl.appendChild(box);
    }

    /**
     * 将服务端单条 message 渲染到聊天区。
     * @param {{ role: string, content: string|Array, type?: number, before_peq?: object|null, after_peq?: object|null, applied?: boolean, created_at?: string }} msg
     */
    function renderHistoryMessage(msg) {
        if (
            msg.type === MESSAGE_TYPE.OPTIMIZING &&
            msg.before_peq &&
            msg.after_peq
        ) {
            renderOptimizingMessage(msg);
            return;
        }
        // before/after 缺失的 OPTIMIZING 消息（例如用户输入那一条）直接跳过
        if (msg.type === MESSAGE_TYPE.OPTIMIZING) {
            return;
        }

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
                const toolCount = c.filter((b) => b && b.type === "tool_use").length;
                if (texts.trim()) {
                    addMsg("assistant", "Assistant: " + texts);
                }
                if (toolCount > 0) {
                    addMsg(
                        "tool",
                        toolCount === 1
                            ? "Completed 1 tool call."
                            : `Completed ${toolCount} tool calls.`
                    );
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
     * 将设备 HTTP 异常转为可读说明（与后端 tool 结果语义对齐）。
     * @param {unknown} err
     * @returns {string}
     */
    function formatDeviceToolError(err) {
        if (!err) return "Unknown error";
        if (err.name === "AbortError") {
            return "Device request timed out (check IP, LAN, or device power).";
        }
        const msg = String(err.message || err);
        if (/Failed to fetch|NetworkError|Load failed|network|connection/i.test(msg)) {
            return "Cannot reach the device (check IP, firewall, or HTTP access).";
        }
        return msg;
    }

    /**
     * 执行设备异步操作，成功返回 { ok: true, content }，失败返回 { ok: false, message }（与后端 optimize_eq 等一致）。
     * @param {() => Promise<*>} fn
     * @returns {Promise<{ ok: true, content: * } | { ok: false, message: string }>}
     */
    async function runDeviceTool(fn) {
        try {
            const data = await fn();
            return { ok: true, content: data === undefined ? null : data };
        } catch (err) {
            return { ok: false, message: formatDeviceToolError(err) };
        }
    }

    /**
     * 执行单个 tool_use。写/删类操作先弹窗；用户拒绝或设备/网络异常时 ok 为 false。
     * @param {Luxsin} device
     * @param {{ id: string, name: string, input?: object }} toolCall
     * @returns {Promise<{ ok: true, content: * } | { ok: false, message: string }>}
     */
    async function executeToolCall(device, toolCall) {
        const input = toolCall.input || {};
        switch (toolCall.name) {
            case "get_device_settings":
                return runDeviceTool(() => device.syncData());
            case "get_peq_list":
                return runDeviceTool(async () => {
                    const peq = await device.syncPeq();
                    return peq.peq.map((item) => item.name);
                });
            case "get_current_peq":
                return runDeviceTool(() => device.currentPeq());
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
                    return { ok: false, message: "User rejected: No device settings modified." };
                }
                return runDeviceTool(async () => {
                    await device.setting(input);
                    return "OK";
                });
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
                    return { ok: false, message: "User rejected: No PEQ added or updated." };
                }
                return runDeviceTool(() => device.updatePeq(input).then(() => "OK"));
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
                    return { ok: false, message: "User rejected: No PEQ deleted." };
                }
                return runDeviceTool(() => device.deletePeqs(input));
            }
            default:
                return { ok: false, message: `Unsupported tool: ${toolCall.name}` };
        }
    }

    // ─────────────────────────────────────────────
    // SSE：POST 响应体流式解析（text/event-stream）
    // ─────────────────────────────────────────────

    /**
     * 将工具执行结果以 JSON 对象 POST 给服务端（与 ToolResultRequest.content 一致）。
     * @param {string} toolUseId
     * @param {unknown} resultPayload
     */
    async function postToolResult(toolUseId, resultPayload) {
        const content =
            resultPayload !== null &&
            typeof resultPayload === "object" &&
            !Array.isArray(resultPayload)
                ? resultPayload
                : { result: String(resultPayload ?? "") };
        const res = await fetch("/chat/tool_result", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ tool_use_id: toolUseId, content }),
        });
        if (!res.ok) {
            const t = await res.text();
            throw new Error(`tool_result failed: HTTP ${res.status} ${t.slice(0, 200)}`);
        }
    }

    /**
     * SSE 单条 payload：type=tool_use 时执行设备工具并回传。
     * @param {object} payload
     */
    async function handleToolUseSsePayload(payload) {
        const raw = payload.content;
        const blocks = Array.isArray(raw) ? raw : raw != null ? [raw] : [];
        let calls = blocks.filter((b) => b && b.type === "tool_use");
        if (calls.length === 0 && raw && typeof raw === "object" && raw.id && raw.name) {
            calls = [raw];
        }
        if (calls.length === 0) return;

        const ip = await getDeviceIp();
        if (!ip) throw new Error("No device IP provided");
        const device = new Luxsin(ip);

        for (const call of calls) {
            let result;
            try {
                result = await executeToolCall(device, call);
            } catch (err) {
                result = { ok: false, message: formatDeviceToolError(err) };
            }
            await postToolResult(call.id, result);
        }
    }

    /**
     * body.question 为本轮用户输入字符串。
     * 流式帧为 SSE，每行 data: 后为 JSON，type 为 text | tool_use | done | error。
     * 必须收到至少一次 type === "done" 才视为本轮完成；否则返回 false，调用方勿恢复发送。
     * @param {{ question: string, language?: number }} body
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
        let receivedDone = false;

        const handlePayload = async (payload) => {
            if (payload.type === "error") {
                addMsg("tool", String(payload.content ?? "Request error"));
                receivedDone = true;
                return;
            }
            if (payload.type === "text") {
                appendMsgContent(assistantLine, payload.content);
                return;
            }
            if (payload.type === "tool_use") {
                const n = Array.isArray(payload.content)
                    ? payload.content.filter((x) => x && x.type === "tool_use").length
                    : payload.content && payload.content.type === "tool_use"
                      ? 1
                      : 0;
                const toolStatusLine = addMsg(
                    "tool",
                    n <= 1 ? "Running tool call…" : `Found ${n} tool calls, running…`
                );
                try {
                    await handleToolUseSsePayload(payload);
                    setMsgContent(
                        toolStatusLine,
                        n <= 1 ? "Completed 1 tool call." : `Completed ${n} tool calls.`
                    );
                } catch (err) {
                    setMsgContent(
                        toolStatusLine,
                        `Tool execution failed: ${err?.message || String(err)}`
                    );
                }
                return;
            }
            if (payload.type === "done") {
                receivedDone = true;
            }
        };

        const parseAndHandleEvent = async (rawEvent) => {
            const dataLines = rawEvent
                .split("\n")
                .filter((line) => line.startsWith("data:"))
                .map((line) => line.slice(5).trim());
            if (dataLines.length === 0) return;
            const dataText = dataLines.join("\n");
            let payload;
            try {
                payload = JSON.parse(dataText);
            } catch {
                return;
            }
            try {
                await handlePayload(payload);
            } catch (e) {
                addMsg("tool", String(e?.message || e));
                receivedDone = true;
            }
        };

        while (true) {
            const { value, done } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            const events = buffer.split("\n\n");
            buffer = events.pop() || "";

            for (const rawEvent of events) {
                await parseAndHandleEvent(rawEvent);
            }
        }

        if (buffer.trim()) {
            await parseAndHandleEvent(buffer);
        }

        if (!receivedDone) {
            addMsg(
                "tool",
                "The reply stream ended before completion. Refresh the page to continue."
            );
            return false;
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
            void refreshRecentConsumption();
        });
    }

    sendBtn.addEventListener("click", sendQuestion);
    inputEl.addEventListener("keydown", (e) => {
        if (e.key === "Enter") sendQuestion();
    });
    if (clearBtn) {
        clearBtn.addEventListener("click", clearMessages);
    }

    initOptimizationControls();
    startConsumptionPolling();
    void hydrateInitialMessages();
})();
