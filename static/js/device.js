/**
 * Luxsin X9 前级功放 HTTP API 客户端（非官方，风险自负）。
 * 请勿发送越界参数；错误设置可能损坏设备。
 *
 * 协议：HTTP，端口 80。
 * 编码：设备使用自定义 Base64 字母表 → 标准 Base64 → JSON。
 *
 * 浏览器直连功放：`http://{IP}`；部分接口返回「自定义字母表 Base64」编码的 JSON，需先解码。
 * 典型用法：`new Luxsin("10.0.0.119")`，再调用 `syncData()`、`syncPeq()`、`updatePeq()` 等。
 */

// ─────────────────────────────────────────────
// 自定义 Base64 编解码（与设备固件约定一致）
// ─────────────────────────────────────────────

const ALPHABET_CUSTOM   = "KLMPQRSTUVWXYZABCGHdefIJjkNOlmnopqrstuvwxyzabcghiDEF34501289+67/";
const ALPHABET_STANDARD = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";

/**
 * 将设备返回的自定义 Base64 字符串解码为 UTF-8 文本。
 * @param {string} encoded
 * @returns {string} 解码后的 UTF-8 文本
 */
function decodeCustomBase64(encoded) {
    let translated = "";
    for (let i = 0; i < encoded.length; i++) {
        const char  = encoded.charAt(i);
        const index = ALPHABET_CUSTOM.indexOf(char);
        translated += index !== -1 ? ALPHABET_STANDARD.charAt(index) : char;
    }
    const raw   = atob(translated);
    const bytes = new Uint8Array(raw.length);
    for (let i = 0; i < raw.length; i++) {
        bytes[i] = raw.charCodeAt(i);
    }
    return new TextDecoder("utf-8").decode(bytes);
}

/**
 * 将普通字符串（如 JSON）编码为 POST 表单所需的自定义 Base64。
 * @param {string} text
 * @returns {string} 自定义字母表 Base64 字符串
 */
function encodeCustomBase64(text) {
    const bytes   = new TextEncoder().encode(text);
    let   binary  = "";
    bytes.forEach(b => (binary += String.fromCharCode(b)));
    const b64      = btoa(binary);
    let   encoded  = "";
    for (let i = 0; i < b64.length; i++) {
        const char  = b64.charAt(i);
        const index = ALPHABET_STANDARD.indexOf(char);
        encoded += index !== -1 ? ALPHABET_CUSTOM.charAt(index) : char;
    }
    return encoded;
}

// ─────────────────────────────────────────────
// 常量：输入源 / 输出 / PEQ 滤波器类型（与设备索引一致）
// ─────────────────────────────────────────────

/** 输入源索引 */
const INPUT = Object.freeze({
    USB:      0,
    USB_C:    1,
    COAXIAL:  2,
    OPTICAL:  3,
    BLUETOOTH:4,
    HDMI_ARC: 5,
    RCA:      6,
});

/** 输出目标索引 */
const OUTPUT = Object.freeze({
    XLR:     0,
    RCA:     1,
    HEADSET: 2,
    XLR_RCA: 3,
});

/** PEQ 类型名 → 设备 API 所需整数 */
const PEQ_FILTER_TYPE = Object.freeze({
    LOW_PASS:   0,
    HIGH_PASS:  1,
    BAND_PASS:  2,
    NOTCH:      3,
    PEAKING:    4,   // 设备用 "PEAKING"（非 "PEAK"）
    PEAK:       4,   // 别名，便于调用
    LOW_SHELF:  5,
    HIGH_SHELF: 6,
    ALL_PASS:   7,
});

/**
 * 滤波器类型转整数；已是 number 则原样返回。
 * @param {string|number} type
 * @returns {number}
 */
function peqTypeToInt(type) {
    if (typeof type === "number") return type;
    const idx = PEQ_FILTER_TYPE[String(type).toUpperCase()];
    if (idx === undefined) throw new Error(`Unknown PEQ filter type: "${type}"`);
    return idx;
}

// ─────────────────────────────────────────────
// Luxsin 设备 API 封装
// ─────────────────────────────────────────────

class Luxsin {
    /**
     * @param {string} ip  设备局域网 IP，如 "10.0.0.119"
     * @param {number} [timeout=5000]  请求超时（毫秒）
     */
    constructor(ip, timeout = 5000) {
        this.baseUrl = `http://${ip}`;
        this.timeout = timeout;
    }

    /**
     * 内部请求：超时、HTTP 状态检查。
     * @private
     */
    async _fetch(url, options = {}) {
        const controller = new AbortController();
        const timer = setTimeout(() => controller.abort(), this.timeout);
        try {
            const res = await fetch(url, { ...options, signal: controller.signal });
            if (!res.ok) throw new Error(`HTTP ${res.status} ${res.statusText}`);
            return res;
        } finally {
            clearTimeout(timer);
        }
    }

    /**
     * 修改设备设置（action=setting）。
     * @param {object} params 设置参数
     * @returns {Promise<void>}
     */
    async setting(params = {}) {
        const qs = new URLSearchParams({ action: "setting", ...params }).toString();
        const url = `${this.baseUrl}/dev/info.cgi?${qs}`;
        await this._fetch(url);
    }

    // ── 接口 1：整机状态 ────────────────────────

    /**
     * 获取设备完整同步数据（解码后 JSON）。
     * @returns {Promise<object>}
     */
    async syncData() {
        const url = `${this.baseUrl}/dev/info.cgi?action=syncData`;
        const res = await this._fetch(url);
        const encoded = await res.text();
        return JSON.parse(decodeCustomBase64(encoded));
    }

    // ── 接口 2：PEQ 列表与当前选中项 ────────────

    /**
     * 获取全部 PEQ；每条 `filters` 会解析为数组对象。
     * @returns {Promise<object>}
     */
    async syncPeq() {
        const url = `${this.baseUrl}/dev/info.cgi?action=syncPeq`;
        const res = await this._fetch(url);
        const encoded = await res.text();
        const result =  JSON.parse(decodeCustomBase64(encoded));

        result.peq = result.peq.map(item => {
            return {
                name: item.name,
                brand: item.brand,
                model: item.model,
                filters: JSON.parse(item.filters),
                preamp:  Number(item.preamp.toFixed(1)), // 保留一位小数
                canDel: item.canDel,
                autoPre: item.autoPre,
            };
        });

        return result;
    }

    /**
     * 当前选中的 PEQ 配置（依赖 peqSelect 索引）。
     * @returns {Promise<object>}
     */
    async currentPeq() {
        const data = await this.syncPeq();
        return data.peq[data.peqSelect];
    }

    // ── 接口 3：变更计数（轮询用）───────────────

    /**
     * 轻量轮询：读取 msgCount，判断设备是否有本地操作变更。
     * @returns {Promise<number>}
     */
    async getMsgCount() {
        const url = `${this.baseUrl}/msgCount`;
        const res = await this._fetch(url);
        const text = await res.text();
        return parseInt(text.trim(), 10);
    }

    // ── 接口 4：写入 / 删除 PEQ（POST，表单 json=自定义 Base64）──

    /**
     * 更新或新增一条 PEQ；滤波器 type 会转为设备所需整数。
     * @param {object} peq  PEQ 配置对象
     */
    async updatePeq(peq) {
        // peq= {name: 'Ziigaat Odyssey - Bright High Frequency', brand: 'Ziigaat', model: 'Odyssey', filters: Array(10), preamp: -5.5, …}
        console.log("peq", peq);
        // type 必须发整数（设备不接受字符串类型名）
        const params = {
            name: peq.name,
            filters: peq.filters.map(f => ({
                ...f,
                type: peqTypeToInt(f.type),
            })),
            preamp: peq.preamp,
            canDel: peq.canDel,
            autoPre: peq.autoPre,
            brand: peq.brand,
            model: peq.model,
        };
        const payload = JSON.stringify({ peqChange: params });
        console.log("payload", payload);
        const body    = `json=${encodeCustomBase64(payload)}`;
        // body=json=nEVikJRPNSRgk5erAwbrOvRckHU8UuyyNImqjJCpd5G2l0ZunHKcUQVENImxmMLUNImxUQkEkJR4kI2snHUbUvkyOTGulwYrAuc9UwG2lSerAsebUvkEkJR4kI2snHU8YFUbUvmqNI1rAsUgZHirlHU8YM10oHD9UwG2lSerAsCbUvkEkJR4kI2snHU8ZsKbUvmqNI1rAsUgZHirlHU8YJ3bnEV3nJLuUsx3XMVvlvfDmIfgj0trAsQDYMirk5RyOrU8YH14XMVDUsxDXsV6XTbrmTuikHU8ZMirkwVulJfuOvZ2UsxEAPKbUvmqNI1rAr3FXMVDUsxDoHD9UwG2lSerAsCbUvkEkJR4kI2snHU8ZFKiXMVwjIugUsxcYHirlHU8YH13oHD9UwG2lSerAsCbUvkEkJR4kI2snHU8YsKiYMirk5RyOrU8YrirlHU8Yw3bnEV3nJLuUsx3XMVvlvfDmIfgj0trAsCiYPKbUvmqNI1rAsUbUwQrAsUgZJ3bnEV3nJLuUsx3XMVvlvfDmIfgj0trAse4YPKbUvmqNI1rAr3DXsebUwQrAsZ6XTbrmTuikHU8ZMirkwVulJfuOvZ2Usx1YPKiXMVwjIugUsxcYH14XMVDUsxEXsf6XTbrmTuikHU8ZrirkwVulJfuOvZ2UsxDYPKiYMirk5RyOrU8YE14XMVDUsxiXsm6JHirlTVujI4iUsxcZH14XMVsjI2QkIirAsQbUvR4mS6ClverAsKbUvVEjI2tUsxrIvuyk5RqmMUbUv4hkSfbUsxrd5G2l0ZunHV6oC==
        console.log("body", body);
        const url     = `${this.baseUrl}/dev/info.cgi`;
        await this._fetch(url, {
            method:  "POST",
            headers: { "Content-Type": "application/x-www-form-urlencoded" },
            body,
        });
    }

    /**
     * 按名称删除 PEQ（可多条）。
     * @param {string[]|object} params  名称数组，或含 `name` 的对象
     * @returns {Promise<string>} 响应正文
     */
    async deletePeqs(params) {
        const names = Array.isArray(params) ? params : [params.name || params];
        const payload = JSON.stringify({ peqRemove: names });
        const body = `json=${encodeCustomBase64(payload)}`;
        const url = `${this.baseUrl}/dev/info.cgi`;
        const res = await this._fetch(url, {
            method: "POST",
            headers: { "Content-Type": "application/x-www-form-urlencoded" },
            body,
        });
        return await res.text();
    }
}

// ─────────────────────────────────────────────
// Node / 打包环境导出
// ─────────────────────────────────────────────

if (typeof module !== "undefined" && module.exports) {
    module.exports = { Luxsin: Luxsin, INPUT, OUTPUT, PEQ_FILTER_TYPE, decodeCustomBase64, encodeCustomBase64 };
}
