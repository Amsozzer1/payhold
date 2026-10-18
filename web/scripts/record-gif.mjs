// Records docs/demo.gif from the static export: the seed 1 replay, then the featured held packet.
// Usage: node scripts/record-gif.mjs [--screens]   (expects `npm run build` to have written out/)
import { createServer } from "node:http";
import { readFile, mkdir, readdir, rm, rename } from "node:fs/promises";
import { extname, join, resolve } from "node:path";
import { execFileSync } from "node:child_process";
import { chromium } from "playwright";

const OUT = resolve("out");
const VIDEO = resolve("video");
const GIF = resolve("../docs/demo.gif");
const TYPES = { ".html": "text/html", ".js": "text/javascript", ".css": "text/css", ".png": "image/png", ".json": "application/json", ".txt": "text/plain" };
const screens = process.argv.includes("--screens");

const server = createServer(async (req, res) => {
  let path = decodeURIComponent(new URL(req.url, "http://x").pathname);
  if (path.endsWith("/")) path += "index.html";
  try {
    const body = await readFile(join(OUT, path));
    res.writeHead(200, { "content-type": TYPES[extname(path)] ?? "application/octet-stream" });
    res.end(body);
  } catch {
    res.writeHead(404).end();
  }
});
await new Promise((r) => server.listen(4173, "127.0.0.1", r));

const size = { width: 1280, height: 800 };
await rm(VIDEO, { recursive: true, force: true });
await mkdir(VIDEO, { recursive: true });
const browser = await chromium.launch();
const context = await browser.newContext({ viewport: size, deviceScaleFactor: 1, recordVideo: screens ? undefined : { dir: VIDEO, size } });
const page = await context.newPage();
const t0 = Date.now();
await page.goto("http://127.0.0.1:4173/");
await page.waitForSelector("#open-featured:not([disabled])");
await page.waitForFunction(() => document.body.innerText.includes("500 / 500"));
await page.waitForTimeout(1500);
if (screens) await page.screenshot({ path: join(VIDEO, "chart.png") });
await page.click("#open-featured");
await page.waitForSelector("#detail img");
await page.waitForFunction(() => [...document.querySelectorAll("#detail img")].every((i) => i.complete && i.naturalWidth > 0));
await page.waitForTimeout(6500);
if (screens) await page.screenshot({ path: join(VIDEO, "detail.png") });
const total = (Date.now() - t0) / 1000;
await context.close();
await browser.close();
server.close();

if (!screens) {
  const [webm] = (await readdir(VIDEO)).filter((f) => f.endsWith(".webm"));
  await rename(join(VIDEO, webm), join(VIDEO, "demo.webm"));
  execFileSync("ffmpeg", [
    "-y", "-loglevel", "error", "-i", join(VIDEO, "demo.webm"),
    "-vf", "fps=12,scale=1000:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=96:stats_mode=diff[p];[b][p]paletteuse=dither=bayer:bayer_scale=5:diff_mode=rectangle",
    GIF,
  ]);
  console.log(`recorded ${total.toFixed(1)} s -> ${GIF}`);
}
