"""Экспорт PDF из Markdown через локальный Chromium DevTools."""
import argparse
import base64
import json
from pathlib import Path
import re
import subprocess
import tempfile
from time import monotonic, sleep
import urllib.request

import markdown
from websocket import create_connection

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "report"

STYLE = """
@page { size: A4; margin: 16mm 17mm 16mm; }
body { font: 10.5pt/1.32 "Calibri", "Arial", sans-serif; color: #0f172a; }
h1, h2 { color: #1e3a8a; line-height: 1.12; break-after: avoid; }
h1 { font-size: 25pt; margin: 4pt 0 8pt; }
h2 { font-size: 15pt; margin: 16pt 0 7pt; }
p { margin: 0 0 7pt; widows: 3; orphans: 3; }
figure { margin: 9pt 0 8pt; break-inside: avoid; }
figure img { width: 100%; display: block; }
figcaption { color: #475569; font-size: 9pt; margin-top: 3pt; }
table { width: 100%; border-collapse: collapse; font-size: 8pt; margin: 7pt 0 10pt; }
th, td { border: 1px solid #cbd5e1; padding: 4pt; text-align: left; overflow-wrap: anywhere; }
th { background: #dbeafe; color: #1e3a8a; }
tr { break-inside: avoid; }
a { color: #1d4ed8; }
* { print-color-adjust: exact; }
"""


def report_html():
    def image(match):
        alt, relative = match.groups()
        path = (REPORT / relative).resolve()
        assert path.is_relative_to(ROOT / "figures") and path.suffix == ".png"
        data = base64.b64encode(path.read_bytes()).decode()
        return f'<figure><img alt="{alt}" src="data:image/png;base64,{data}"><figcaption>{alt}</figcaption></figure>'

    source = (REPORT / "REPORT.md").read_text(encoding="utf-8")
    body = markdown.markdown(source, extensions=["tables"])
    body = re.sub(r'<p><img alt="([^"]+)" src="([^"]+)" /></p>', image, body)
    return f'<!doctype html><html lang="ru"><meta charset="utf-8"><style>{STYLE}</style>{body}'


def chromium_pdf(port, doc):
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    new_url = f"http://127.0.0.1:{port}/json/new?{doc.as_uri()}"
    with opener.open(urllib.request.Request(new_url, method="PUT"), timeout=15) as source:
        tab = json.load(source)
    ws = create_connection(tab["webSocketDebuggerUrl"], suppress_origin=True, timeout=60)
    seq = 0

    def call(method, **params):
        nonlocal seq
        seq += 1
        ws.send(json.dumps(dict(id=seq, method=method, params=params)))
        while True:
            value = json.loads(ws.recv())
            if value.get("id") == seq:
                if "error" in value:
                    raise RuntimeError(value["error"])
                return value["result"]

    try:
        deadline = monotonic() + 20
        while monotonic() < deadline:
            try:
                state = call("Runtime.evaluate", expression=(
                    "document.readyState === 'complete' && !!document.querySelector('h1')"
                ), returnByValue=True)
                if state.get("result", {}).get("value"):
                    break
            except RuntimeError:
                pass
            sleep(.25)
        else:
            raise RuntimeError("Страница отчёта не загрузилась")
        info = call("Runtime.evaluate", expression="""(async()=> {
            await document.fonts.ready;
            const images=[...document.images]; await Promise.all(images.map(i=>i.decode()));
            return {title:document.querySelector('h1').innerText,
                    images:images.length, tables:document.querySelectorAll('table').length};
        })()""", awaitPromise=True, returnByValue=True)
        verify = info["result"]["value"]
        assert "краудфандинговой платформы" in verify["title"] and verify["images"] >= 8 and verify["tables"] == 3
        pdf = base64.b64decode(call("Page.printToPDF", printBackground=True, preferCSSPageSize=True)["data"])
        pages = len(re.findall(rb"/Type\s*/Page\b", pdf))
        assert pdf.startswith(b"%PDF-") and pages >= 5 and len(pdf) >= 100_000
        (REPORT / "Отчёт.pdf").write_bytes(pdf)
        print(f"PDF: {pages} страниц, {verify['images']} графиков, {verify['tables']} таблицы, {len(pdf)} байт")
    finally:
        ws.close()
        try:
            opener.open(f"http://127.0.0.1:{port}/json/close/{tab['id']}", timeout=5).close()
        except OSError:
            pass


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("chromium", type=Path, nargs="?")
    parser.add_argument("--debug-port", type=int)
    args = parser.parse_args()
    if args.debug_port is None and args.chromium is None:
        parser.error("укажите путь к Chromium или порт локального DevTools")
    local = ROOT / ".local"
    local.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(dir=local, prefix="report-print-",
                                     ignore_cleanup_errors=True) as directory:
        temp = Path(directory)
        doc = temp / "report.html"
        doc.write_text(report_html(), encoding="utf-8")
        if args.debug_port:
            chromium_pdf(args.debug_port, doc)
            return
        profile = temp / "browser"
        proc = subprocess.Popen([str(args.chromium), "--headless", "--no-proxy-server",
                                 "--remote-debugging-port=0", f"--user-data-dir={profile}", "about:blank"])
        try:
            active = profile / "DevToolsActivePort"
            end = monotonic() + 45
            while not active.exists() and monotonic() < end and proc.poll() is None:
                sleep(.2)
            if not active.exists():
                raise RuntimeError("Локальный Chromium не открыл порт проверки PDF")
            chromium_pdf(int(active.read_text().splitlines()[0]), doc)
        finally:
            if proc.poll() is None:
                proc.terminate()
                proc.wait(timeout=15)


if __name__ == "__main__":
    main()
