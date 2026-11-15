import fs from "node:fs/promises";
import path from "node:path";
import { chromium } from "playwright";
import { execFileSync } from "node:child_process";
const ROOT = process.cwd(),
  OUT = path.join(ROOT, "artifacts/pehchaan-walkthrough");
const chapters = JSON.parse(
  await fs.readFile(path.join(OUT, "chapters.json"), "utf8"),
);
const cards = await fs.readFile(
  path.join(ROOT, "assets/video/cards.html"),
  "utf8",
);
const BASE = "http://localhost:3000",
  API = "http://localhost:8000/api/v1";
const resume = process.argv.includes("--resume");
let output = resume
  ? JSON.parse(
      await fs
        .readFile(path.join(OUT, "capture-progress.json"), "utf8")
        .catch(() => "[]"),
    )
  : [];
const redo = new Set(
  (process.argv.find((v) => v.startsWith("--redo=")) || "")
    .split("=")[1]
    ?.split(",") || [],
);
output = output.filter((c) => !redo.has(c.id));
const ids = resume
  ? JSON.parse(
      await fs
        .readFile(path.join(ROOT, ".runtime/video-ids.json"), "utf8")
        .catch(() => "{}"),
    )
  : {};
let { orderId, sessionId, campaignId } = ids;
let agentCapture;
async function request(route, body) {
  const r = await fetch(API + route, {
    method: body === undefined ? "GET" : "POST",
    headers: {
      "content-type": "application/json",
      "Idempotency-Key": crypto.randomUUID(),
    },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const data = await r.json();
  if (!r.ok) throw new Error(route + ": " + JSON.stringify(data));
  return data;
}
const browser = await chromium.launch({
  headless: true,
  args: [
    "--use-fake-ui-for-media-stream",
    "--use-fake-device-for-media-stream",
    `--use-file-for-fake-audio-capture=${OUT}/audio/microphone.wav`,
  ],
});
const context = await browser.newContext({
  viewport: { width: 1600, height: 900 },
  recordVideo: {
    dir: path.join(OUT, "raw"),
    size: { width: 1600, height: 900 },
  },
  permissions: ["microphone"],
  deviceScaleFactor: 1,
  acceptDownloads: true,
  ...(resume
    ? {
        storageState: JSON.parse(
          await fs
            .readFile(path.join(ROOT, ".runtime/video-state.json"), "utf8")
            .catch(() => "{}"),
        ),
      }
    : {}),
});

async function overlay(p, c, index) {
  await p.evaluate(
    ({ c, index, total }) => {
      document.getElementById("film-style")?.remove();
      document.getElementById("film-top")?.remove();
      document.getElementById("film-bottom")?.remove();
      document.getElementById("film-pointer")?.remove();
      const style = document.createElement("style");
      style.id = "film-style";
      style.textContent = `html{scroll-behavior:smooth}body{padding-top:66px!important}.sidebar{top:66px!important}.topbar{top:66px!important}.main-content{padding-bottom:160px!important}#film-top{position:fixed;inset:0 0 auto;height:66px;z-index:2147483600;background:#fff;border-bottom:1px solid #c5e4f4;display:flex;align-items:center;padding:0 34px;gap:24px;font:500 15px Arial,sans-serif;color:#002970;pointer-events:none}#film-top b{font-size:22px;letter-spacing:-.7px}#film-top .topic{margin-left:auto;color:#007cae;font-size:12px;letter-spacing:1.5px}#film-top .part{font-size:11px;color:#7694ae;border-left:1px solid #d9e9f4;padding-left:20px}#film-bottom{position:fixed;bottom:22px;left:50%;transform:translateX(-50%);z-index:2147483600;max-width:1350px;min-width:820px;box-sizing:border-box;text-align:center;padding:16px 34px;background:rgba(0,36,90,.94);border:1px solid #43bde3;border-radius:11px;box-shadow:0 4px 30px #00297024;color:white;font:400 19px/1.5 Arial,sans-serif;white-space:pre-line;pointer-events:none}#film-bottom strong{display:block;color:#8ce1ff;font-size:11px;font-weight:500;letter-spacing:1.2px;margin-bottom:5px;text-transform:uppercase}#film-pointer{position:fixed;z-index:2147483640;width:16px;height:20px;background:#00a8dc;clip-path:polygon(0 0,0 100%,31% 69%,57% 100%,74% 90%,48% 61%,94% 61%);filter:drop-shadow(1px 1px 2px white);pointer-events:none;left:-50px;top:-50px}.film-click{position:fixed;width:45px;height:45px;border:2px solid #00baf2;border-radius:50%;z-index:2147483639;pointer-events:none;animation:filmClick .65s ease-out forwards}@keyframes filmClick{from{transform:scale(.2);opacity:1}to{transform:scale(1.5);opacity:0}}[data-nextjs-toast],[data-nextjs-dialog-overlay]{display:none!important}`;
      document.head.append(style);
      const top = document.createElement("div");
      top.id = "film-top";
      top.innerHTML = `<b>pehchaan <span style="color:#00baf2">/</span></b><span>${c.title}</span><span class="topic">${c.eyebrow}</span><span class="part">${String(index + 1).padStart(2, "0")} / ${total}</span>`;
      document.body.append(top);
      const bottom = document.createElement("div");
      bottom.id = "film-bottom";
      const strong = document.createElement("strong");
      strong.textContent = c.eyebrow;
      bottom.append(strong, document.createTextNode(c.caption));
      document.body.append(bottom);
      const pointer = document.createElement("div");
      pointer.id = "film-pointer";
      document.body.append(pointer);
      window.addEventListener("pointermove", (e) => {
        pointer.style.left = e.clientX + "px";
        pointer.style.top = e.clientY + "px";
      });
      window.addEventListener("pointerdown", (e) => {
        const ring = document.createElement("div");
        ring.className = "film-click";
        ring.style.left = e.clientX - 22 + "px";
        ring.style.top = e.clientY - 22 + "px";
        document.body.append(ring);
        setTimeout(() => ring.remove(), 700);
      });
    },
    { c, index, total: chapters.length },
  );
}
async function click(p, loc) {
  await loc.waitFor({ state: "visible", timeout: 60000 });
  await loc.evaluate((el) =>
    el.scrollIntoView({ block: "center", behavior: "instant" }),
  );
  await p.waitForTimeout(180);
  const box = await loc.boundingBox();
  if (box) {
    const from = await p.evaluate(() => ({
      x:
        Number(
          document.getElementById("film-pointer")?.style.left.replace("px", ""),
        ) || 300,
      y:
        Number(
          document.getElementById("film-pointer")?.style.top.replace("px", ""),
        ) || 100,
    }));
    for (let i = 1; i <= 10; i++) {
      await p.mouse.move(
        from.x + ((box.x + box.width / 2 - from.x) * i) / 10,
        from.y + ((box.y + box.height / 2 - from.y) * i) / 10,
      );
      await p.waitForTimeout(18);
    }
  }
  await loc.click();
  await p.waitForTimeout(350);
}
const btn = (p, name) => p.getByRole("button", { name, exact: true });
const main = (p) => p.getByRole("main");
if (redo.has("haggle_request")) {
  const prep = await context.newPage();
  await prep.goto(BASE + "/dashboard");
  await prep.evaluate(() => localStorage.removeItem("pehchaan-session"));
  await prep.close();
}

async function nav(p, route) {
  const names = {
    dashboard: "Overview",
    customers: "Customer Intelligence",
    comeback: "Comeback Engine",
    soundbox: "Soundbox Simulator",
    haggle: "Haggle Arena",
    agents: "Agent Command Center",
    firewall: "Mandate Firewall",
    ledger: "Transaction Ledger",
    catalog: "Product Catalogue",
    settings: "Settings",
  };
  await click(
    p,
    p
      .getByRole("navigation")
      .getByRole("link", { name: new RegExp("^" + names[route]) }),
  );
  await main(p).getByRole("heading", { level: 1 }).waitFor();
}
async function record(id, route, action) {
  const c = chapters.find((x) => x.id === id),
    index = chapters.indexOf(c);
  const p = await context.newPage();
  const made = Date.now();
  p.setDefaultTimeout(60000);
  p.on("pageerror", (e) => console.log("PAGEERROR", id, e.message));
  await p.goto(BASE + "/" + (route || "dashboard"), {
    waitUntil: "domcontentloaded",
  });
  await main(p).getByRole("heading", { level: 1 }).waitFor();
  await p.waitForTimeout(450);
  if (!route) {
    await p.setContent(cards, { waitUntil: "domcontentloaded" });
    await p.evaluate((id) => window.showCard(id), id);
    await p.waitForTimeout(80);
  }
  await overlay(p, c, index);
  const start = Date.now();
  console.log("RECORD", id, "target", c.duration, flush());
  try {
    if (action) await action(p);
    const remaining = c.duration - (Date.now() - start) / 1000;
    if (remaining > 0) await p.waitForTimeout(remaining * 1000);
  } catch (e) {
    await p.screenshot({
      path: path.join(OUT, "failed-" + id + ".png"),
      fullPage: true,
    });
    throw new Error(id + ": " + e.message);
  }
  const captureDuration = (Date.now() - start) / 1000;
  const beforeClose = Date.now();
  const video = p.video();
  await p.screenshot({ path: path.join(OUT, id + "-frame.png") });
  await p.close();
  const raw = path.join(OUT, "raw", id + ".webm");
  await video.saveAs(raw);
  const probe = JSON.parse(
    execFileSync(
      "ffprobe",
      ["-v", "error", "-show_entries", "format=duration", "-of", "json", raw],
      { encoding: "utf8" },
    ),
  );
  const rawDuration = Number(probe.format.duration);
  const tail = (Date.now() - beforeClose) / 1000;
  const trim = Math.max(0, rawDuration - captureDuration - 0.3);
  const entry = {
    ...c,
    raw_path: raw,
    trim_start: trim,
    capture_duration: Math.min(captureDuration, rawDuration - trim),
    recording_wall_seconds: (Date.now() - made) / 1000,
  };
  output.push(entry);
  await fs.writeFile(
    path.join(OUT, "capture-progress.json"),
    JSON.stringify(output, null, 2),
  );
  await context.storageState({
    path: path.join(ROOT, ".runtime/video-state.json"),
  });
  await fs.writeFile(
    path.join(ROOT, ".runtime/video-ids.json"),
    JSON.stringify({ orderId, sessionId, campaignId }),
  );
  console.log(
    "CAPTURED",
    id,
    "seconds",
    captureDuration.toFixed(1),
    "trim",
    trim.toFixed(1),
  );
  return entry;
}
function flush() {
  return "";
}
if (!resume) await request("/demo/reset", {});
const actions = {
  overview: async (p) => {
    await p.waitForTimeout(2200);
    await p
      .getByRole("combobox", { name: "Dashboard date range" })
      .selectOption("7");
    await p.waitForTimeout(2300);
    await p
      .getByRole("combobox", { name: "Dashboard date range" })
      .selectOption("30");
    await p.waitForTimeout(1800);
    await p.mouse.wheel(0, 510);
    await p.waitForTimeout(2500);
    await p.mouse.wheel(0, -510);
  },
  customers: async (p) => {
    await p.waitForTimeout(1200);
    await click(p, p.getByRole("button", { name: /^View customer / }).first());
    await p.waitForTimeout(2400);
    await p.getByRole("dialog").evaluate((el) => {
      el.scrollTo({ top: 430, behavior: "smooth" });
    });
    await p.waitForTimeout(2100);
    await click(
      p,
      p.getByRole("button", { name: "Close dialog", exact: true }),
    );
    await p.mouse.wheel(0, 650);
  },
  comeback: async (p) => {
    await click(p, btn(p, "Create campaign"));
    const d = p.getByRole("dialog");
    await d
      .getByLabel("Campaign name")
      .fill("Welcome back · Pehchaan walkthrough");
    await d.getByLabel("Target segment").selectOption("At-Risk + Declining");
    await d.getByLabel("Offer amount (₹)").fill("15");
    await d.getByLabel("Minimum bill (₹)").fill("250");
    await p.waitForTimeout(1500);
    const res = p.waitForResponse(
      (r) =>
        r.url().endsWith("/api/v1/campaigns") &&
        r.request().method() === "POST",
    );
    await click(
      p,
      d.getByRole("button", { name: "Create campaign", exact: true }),
    );
    campaignId = (await (await res).json()).id;
    await p.waitForTimeout(1800);
  },
  experiment: async (p) => {
    await click(p, btn(p, "Approve & launch campaign"));
    await p.waitForTimeout(1700);
    const done = p.waitForResponse((r) =>
      r.url().includes("/simulate-redemptions"),
    );
    await click(p, btn(p, "Simulate redemptions"));
    await done;
    await p.waitForTimeout(1800);
    await p.mouse.wheel(0, 560);
    await p.waitForTimeout(1600);
  },
  soundbox: async (p) => {
    await p.getByRole("checkbox", { name: "Spoken responses" }).uncheck();
    await p
      .getByRole("combobox", { name: "Assistant language" })
      .selectOption("hi-IN");
    await p.waitForTimeout(700);
    const result = p.waitForResponse((r) => r.url().endsWith("/voice/chat"));
    await click(p, btn(p, "Start microphone recording"));
    const dur = Number(
      execFileSync(
        "ffprobe",
        [
          "-v",
          "error",
          "-show_entries",
          "format=duration",
          "-of",
          "default=noprint_wrappers=1:nokey=1",
          OUT + "/audio/microphone.wav",
        ],
        { encoding: "utf8" },
      ),
    );
    await p.waitForTimeout((dur + 0.25) * 1000);
    await click(p, btn(p, "Stop recording"));
    const reply = await (await result).json();
    if (reply.provider !== "sarvam")
      throw new Error("Genuine Sarvam voice interpretation unavailable");
    await btn(p, "Approve action").waitFor();
    await p.waitForTimeout(1000);
    await click(p, btn(p, "Approve action"));
    await p.waitForTimeout(1200);
    await p
      .getByRole("combobox", { name: "Assistant language" })
      .selectOption("mr-IN");
  },
  haggle_request: async (p) => {
    const chooser = p.waitForEvent("filechooser");
    await click(p, btn(p, "Upload parchi"));
    const extraction = p.waitForResponse((r) =>
      r.url().endsWith("/documents/extract"),
    );
    await (await chooser).setFiles(OUT + "/rate-card.png");
    const extracted = await (await extraction).json();
    if (extracted.provider !== "sarvam")
      throw new Error("Parchi document provider unavailable");
    await p.waitForTimeout(1300);
    await p
      .getByRole("textbox", { name: "Buyer requirement", exact: true })
      .fill(
        "Office groceries: 100 kg rice, 100 kg wheat flour, 80 litres sunflower oil, 200 packs snacks and 20 kg tea. Maximum total budget INR 40000. Delivery by Friday.",
      );
    await p.waitForTimeout(1000);
    const parsed = p.waitForResponse((r) =>
      r.url().endsWith("/haggle/parse-requirement"),
    );
    await click(p, btn(p, "Parse request"));
    const result = await (await parsed).json();
    if (!result.items?.length) throw new Error("Buyer parsing unavailable");
    await p.waitForTimeout(1600);
    await p.mouse.wheel(0, 300);
  },
  haggle_rounds: async (p) => {
    const created = p.waitForResponse(
      (r) =>
        r.url().endsWith("/haggle/sessions") && r.request().method() === "POST",
    );
    await click(p, btn(p, "Start negotiation"));
    sessionId = (await (await created).json()).id;
    agentCapture = record("agents", "agents", async (a) => {
      await a.waitForTimeout(3000);
      await click(
        a,
        a.locator(".flow-agent").filter({ hasText: "Negotiation Supervisor" }),
      );
      await a.waitForTimeout(3500);
      await a.mouse.wheel(0, 520);
      await a.waitForTimeout(2500);
      await a.mouse.wheel(0, -520);
    });
    await btn(p, "Pause").waitFor();
    await click(p, btn(p, "Pause"));
    await p.waitForTimeout(1400);
    await click(p, btn(p, "Resume"));
    await p
      .getByRole("heading", { name: "Best eligible deal", exact: true })
      .waitFor({ timeout: 100000 });
    await p.mouse.wheel(0, 450);
    await p.waitForTimeout(1200);
  },
  firewall: async (p) => {
    await p
      .getByRole("spinbutton", { name: "Proposed amount (₹)" })
      .fill("95000");
    await p.waitForTimeout(1000);
    const r = p.waitForResponse((r) => r.url().endsWith("/firewall/validate"));
    await click(p, btn(p, "Run firewall check"));
    if ((await (await r).json()).status !== "BLOCKED")
      throw new Error("Rogue proposal was not blocked");
    await p
      .locator(".decision-result")
      .evaluate((el) =>
        el.scrollIntoView({ block: "center", behavior: "smooth" }),
      );
    await p.waitForTimeout(8500);
    await p.mouse.wheel(0, 500);
    await p.waitForTimeout(2500);
    await p
      .locator(".decision-result")
      .evaluate((el) =>
        el.scrollIntoView({ block: "center", behavior: "smooth" }),
      );
  },
  order: async (p) => {
    await p.mouse.wheel(0, 470);
    await p.waitForTimeout(1000);
    await click(p, btn(p, "Review & confirm order"));
    const d = p.getByRole("dialog");
    await p.waitForTimeout(1700);
    await d.getByLabel("I approve this order as the merchant.").check();
    await p.waitForTimeout(1000);
    await d.getByLabel("I confirm the selected bundle as the buyer.").check();
    await p.waitForTimeout(1200);
    const r = p.waitForResponse(
      (r) => r.url().endsWith("/confirm") && r.request().method() === "POST",
    );
    await click(
      p,
      d.getByRole("button", { name: "Confirm simulated order", exact: true }),
    );
    orderId = (await (await r).json()).id;
    await p.waitForTimeout(1500);
  },
  ledger: async (p) => {
    const card = p
      .locator(".utility-order")
      .filter({ hasText: orderId.slice(0, 8).toUpperCase() });
    await click(p, card.getByRole("button", { name: "View order & timeline" }));
    await p.waitForTimeout(1000);
    await click(
      p,
      card.getByRole("button", { name: "Mark packed", exact: true }),
    );
    const chooser = p.waitForEvent("filechooser");
    await click(
      p,
      card.getByRole("button", { name: "Upload packing photo", exact: true }),
    );
    await (await chooser).setFiles(OUT + "/packing-reference.png");
    await p.waitForTimeout(1000);
    await click(
      p,
      card.getByRole("button", { name: "Confirm delivery", exact: true }),
    );
    await p.waitForTimeout(800);
    await p.getByRole("dialog").getByRole("checkbox").check();
    await click(p, btn(p, "Confirm demo delivery"));
    await click(
      p,
      card.getByRole("button", {
        name: "Release simulated settlement",
        exact: true,
      }),
    );
    await p.waitForTimeout(1200);
  },
  catalogue: async (p) => {
    await click(p, btn(p, "Add product"));
    const d = p.getByRole("dialog");
    for (const [label, value] of [
      ["Product name", "Premium Moong Dal"],
      ["Category", "Pulses"],
      ["Unit", "kg"],
      ["Supplier", "Reviewed wholesale supplier"],
      ["Selling price (₹)", "145"],
      ["Available stock", "80"],
      ["Purchase cost (₹)", "115"],
      ["Minimum selling price (₹)", "125"],
    ])
      await d.getByLabel(label, { exact: true }).fill(value);
    await p.waitForTimeout(1200);
    await click(p, d.getByRole("button", { name: "Add product", exact: true }));
    await click(p, btn(p, "Import catalogue"));
    const csv =
      "name,category,unit,selling_price,available_stock,purchase_price,minimum_selling_price,supplier\nChana Dal,Pulses,kg,125,60,95,110,Reviewed sample supplier\n";
    const imported = p.waitForResponse((r) =>
      r.url().endsWith("/catalog/import"),
    );
    await p
      .getByLabel("Upload catalogue CSV", { exact: true })
      .setInputFiles({
        name: "catalogue-import.csv",
        mimeType: "text/csv",
        buffer: Buffer.from(csv),
      });
    await imported;
    await p.waitForTimeout(700);
    await click(p, btn(p, "Import catalogue"));
    const r = p.waitForResponse((r) => r.url().endsWith("/documents/extract"));
    await p
      .getByLabel("Upload rate card document", { exact: true })
      .setInputFiles(OUT + "/rate-card.png");
    const extracted = await (await r).json();
    if (extracted.provider !== "sarvam")
      throw new Error("Real document provider unavailable");
    await p.waitForTimeout(2000);
    await p
      .getByRole("dialog")
      .evaluate((el) => el.scrollTo({ top: 250, behavior: "smooth" }));
    await p.waitForTimeout(1200);
  },
  operations: async (p) => {
    await click(p, btn(p, "Export transactions"));
    await click(p, btn(p, "Import transactions"));
    const d = p.getByRole("dialog");
    await click(
      p,
      d.getByRole("button", {
        name: "Download transaction template",
        exact: true,
      }),
    );
    const csv =
      "customer_token,amount,category,created_at\nPK-0001,321.45,Grocery," +
      new Date().toISOString() +
      "\n";
    await d
      .getByLabel("Transaction CSV file", { exact: true })
      .setInputFiles({
        name: "merchant-transactions.csv",
        mimeType: "text/csv",
        buffer: Buffer.from(csv),
      });
    await p.waitForTimeout(1000);
    await click(p, d.getByRole("button", { name: "Import CSV", exact: true }));
    await nav(p, "settings");
    await p
      .getByRole("combobox", {
        name: "Default assistant language",
        exact: true,
      })
      .selectOption("mr-IN");
    await click(p, btn(p, "Save language"));
    await p.waitForTimeout(1000);
  },
};
try {
  for (const c of chapters) {
    if (output.some((x) => x.id === c.id)) {
      console.log("CACHED", c.id);
      continue;
    }
    if (c.id === "agents") {
      await agentCapture;
      continue;
    }
    if (
      [
        "intro",
        "problem",
        "solution",
        "architecture",
        "usp",
        "business",
        "closing",
      ].includes(c.id)
    )
      await record(c.id, null);
    else {
      const routes = {
        overview: "dashboard",
        customers: "customers",
        comeback: "comeback",
        experiment: "comeback",
        soundbox: "soundbox",
        haggle_request: "haggle",
        haggle_rounds: "haggle",
        firewall: "firewall",
        order: "haggle",
        ledger: "ledger",
        catalogue: "catalog",
        operations: "ledger",
      };
      await record(c.id, routes[c.id], actions[c.id]);
    }
  }
  const ordered = chapters.map((c) => output.find((x) => x.id === c.id));
  await fs.writeFile(
    path.join(OUT, "capture.json"),
    JSON.stringify(ordered, null, 2),
  );
  console.log("ALL CAPTURED", ordered.length);
} finally {
  await context.close();
  await browser.close();
}
