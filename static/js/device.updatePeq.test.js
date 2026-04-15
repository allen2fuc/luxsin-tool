const test = require("node:test");
const assert = require("node:assert/strict");

const { Luxsin, decodeCustomBase64 } = require("./device.js");

test("updatePeq posts encoded payload to fixed device IP", async () => {
    let capturedUrl = "";
    let capturedOptions = null;

    const originalFetch = global.fetch;
    global.fetch = async (url, options) => {
        capturedUrl = url;
        capturedOptions = options;
        return {
            ok: true,
            status: 200,
            statusText: "OK",
            text: async () => "",
        };
    };

    try {
        const client = new Luxsin("10.0.0.119");
        // name: "Ziigaat Odyssey - Bright High Frequency",
        await client.updatePeq({
            name: "Ziigaat Odyssey1",
            brand: "Ziigaat",
            model: "Odyssey",
            filters: [
                { type: 5, frequency: 32, gain: 2.5, q: 0.7 },
                { type: 4, frequency: 60, gain: 2.5, q: 1 },
                { type: 4, frequency: 110, gain: 1.5, q: 1.2 },
                { type: 4, frequency: 280, gain: -3, q: 1 },
                { type: 4, frequency: 700, gain: -1, q: 1.4 },
                { type: 4, frequency: 2000, gain: 2, q: 2 },
                { type: 4, frequency: 4000, gain: 2, q: 2.5 },
                { type: 4, frequency: 5500, gain: -1.5, q: 3 },
                { type: 4, frequency: 8000, gain: -1.5, q: 2.5 },
                { type: 6, frequency: 10000, gain: 3.5, q: 0.7 },
            ],
            preamp: -5.5,
            canDel: 1,
            autoPre: 0,
        }).then(res => console.log("res", res)).catch(console.error);;

        assert.equal(capturedUrl, "http://10.0.0.119/dev/info.cgi");
        assert.equal(capturedOptions.method, "POST");
        assert.equal(
            capturedOptions.headers["Content-Type"],
            "application/x-www-form-urlencoded"
        );
        assert.match(capturedOptions.body, /^json=/);

        const encoded = capturedOptions.body.slice("json=".length);
        const decoded = decodeCustomBase64(encoded);
        const payload = JSON.parse(decoded);
        const peqChange = payload.peqChange;

        assert.equal(peqChange.name, "Ziigaat Odyssey1");
        assert.equal(peqChange.brand, "Ziigaat");
        assert.equal(peqChange.model, "Odyssey");
        assert.equal(peqChange.preamp, -5.5);
        assert.equal(peqChange.canDel, 1);
        assert.equal(peqChange.autoPre, 0);
        assert.equal(peqChange.filters.length, 10);
        assert.equal(typeof peqChange.filters[0].type, "number");
        assert.equal(peqChange.filters[0].type, 5);
        assert.equal(peqChange.filters[0].frequency, 32);
        assert.equal(peqChange.filters[1].type, 4);
        assert.equal(peqChange.filters[9].type, 6);
        assert.equal(peqChange.filters[9].frequency, 10000);
    } finally {
        global.fetch = originalFetch;
    }
});
