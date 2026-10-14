#!/usr/bin/env python3
"""Exercise the real reward HTTP process and render its deterministic receipt."""

from __future__ import annotations

import hashlib
import http.client
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import sys
import time

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "demo"
WIDTH, HEIGHT = 1280, 720
FONT_SANS = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT_MONO = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"
SOURCE_MANIFEST = DEMO / "source-manifest.json"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git_blob(path: Path) -> str:
    return subprocess.check_output(
        ["git", "hash-object", str(path)], cwd=ROOT, text=True
    ).strip()


def verify_source() -> dict:
    manifest = json.loads(SOURCE_MANIFEST.read_text())
    for relative, expected in manifest["files"].items():
        path = ROOT / relative
        actual_sha = sha256(path)
        actual_blob = git_blob(path)
        if actual_sha != expected["sha256"] or actual_blob != expected["git_blob"]:
            raise SystemExit(
                f"source drift: {relative} (sha256={actual_sha}, git_blob={actual_blob})"
            )
    return manifest


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def request(port: int, method: str, path: str, body: bytes = b"", headers=None):
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    connection.request(method, path, body=body, headers=headers or {})
    response = connection.getresponse()
    payload = response.read().decode("utf-8")
    content_type = response.getheader("Content-Type")
    connection.close()
    return {"status": response.status, "content_type": content_type, "body": payload}


def json_post(port: int, payload: dict):
    body = json.dumps(payload, separators=(",", ":")).encode()
    return request(
        port,
        "POST",
        "/v1/rewards/edit-similarity",
        body,
        {"Content-Type": "application/json", "Content-Length": str(len(body))},
    )


def capture_receipt(manifest: dict) -> dict:
    test = subprocess.run(
        [sys.executable, "-m", "pytest", "--rootdir=.", "apps/reward/tests", "-q"],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=True,
    )
    port = free_port()
    env = os.environ.copy()
    env["REWARD_PORT"] = str(port)
    process = subprocess.Popen(
        [sys.executable, "apps/reward/app/main.py"],
        cwd=ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    try:
        deadline = time.monotonic() + 10
        while True:
            try:
                health = request(port, "GET", "/healthz")
                break
            except OSError:
                if time.monotonic() >= deadline:
                    raise RuntimeError("reward service failed to start")
                time.sleep(0.05)

        unchanged = json_post(
            port,
            {"candidate": "Hi Ava — your replacement ships today.", "edited": "Hi Ava — your replacement ships today."},
        )
        rewritten = json_post(
            port,
            {"candidate": "Hello Ava — your replacement is on the way.", "edited": "Hi Ava, your replacement ships today."},
        )
        malformed_body = b'{"candidate":'
        malformed = request(
            port,
            "POST",
            "/v1/rewards/edit-similarity",
            malformed_body,
            {"Content-Type": "application/json", "Content-Length": str(len(malformed_body))},
        )
        oversized = request(
            port,
            "POST",
            "/v1/rewards/edit-similarity",
            b"{}",
            {"Content-Type": "application/json", "Content-Length": "65537"},
        )
        metrics = request(port, "GET", "/metrics")
    finally:
        process.terminate()
        process.wait(timeout=5)

    assert health["status"] == 200
    assert unchanged["status"] == 200 and json.loads(unchanged["body"])["score"] == 1.0
    rewritten_json = json.loads(rewritten["body"])
    assert rewritten["status"] == 200 and 0.0 <= rewritten_json["score"] < 1.0
    assert malformed["status"] == 400
    assert oversized["status"] == 413
    for outcome in ("success", "validation_error", "payload_too_large"):
        assert f'outcome="{outcome}"' in metrics["body"]

    test_summary_match = re.search(r"(\d+ passed)", test.stdout)
    if not test_summary_match:
        raise RuntimeError(f"unexpected pytest output: {test.stdout}")
    receipt = {
        "scope": "deterministic fixture text; no model-quality or business-correlation claim",
        "recorded_source_commit": manifest["recorded_source_commit"],
        "source_files": manifest["files"],
        "tests": test_summary_match.group(1),
        "requests": {
            "health": health,
            "unchanged": unchanged,
            "rewritten": rewritten,
            "malformed": malformed,
            "oversized": oversized,
            "metrics": metrics,
        },
    }
    (DEMO / "receipt.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    return receipt


def font(size: int, bold: bool = False, mono: bool = False):
    path = FONT_MONO if mono else FONT_BOLD if bold else FONT_SANS
    return ImageFont.truetype(path, size)


def background() -> Image.Image:
    image = Image.new("RGB", (WIDTH, HEIGHT), "#080B17")
    pixels = image.load()
    for y in range(HEIGHT):
        for x in range(WIDTH):
            glow = max(0.0, 1.0 - (((x - 1080) / 700) ** 2 + ((y - 80) / 500) ** 2))
            pixels[x, y] = (8 + int(12 * glow), 11 + int(8 * glow), 23 + int(27 * glow))
    return image


def rounded(draw, box, fill, outline=None, width=1, radius=22):
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def header(draw, step: str, title: str, subtitle: str):
    draw.text((64, 42), "RLaaS  /  REWARD", font=font(16, bold=True), fill="#9EA7C4")
    rounded(draw, (1120, 38, 1214, 72), "#17243A", "#39E6B0", 1, 17)
    draw.text((1147, 47), step, font=font(14, bold=True), fill="#39E6B0")
    draw.text((64, 101), title, font=font(43, bold=True), fill="#F4F7FF")
    draw.text((66, 162), subtitle, font=font(20), fill="#AAB5D4")


def footer(draw):
    draw.line((64, 658, 1216, 658), fill="#222C46", width=1)
    draw.text(
        (64, 675),
        "ACTUAL LOCAL HTTP FLOW   •   FIXTURE TEXT   •   NO MODEL-QUALITY OR BUSINESS-CORRELATION CLAIM",
        font=font(13, bold=True),
        fill="#7884A6",
    )


def code_card(draw, box, title, lines, accent="#7C6CFF"):
    rounded(draw, box, "#0D1325", "#283454", 2, 22)
    x1, y1, x2, _ = box
    draw.ellipse((x1 + 22, y1 + 21, x1 + 32, y1 + 31), fill=accent)
    draw.text((x1 + 43, y1 + 15), title, font=font(15, bold=True), fill="#D8DFF5")
    draw.line((x1 + 20, y1 + 48, x2 - 20, y1 + 48), fill="#222C46", width=1)
    y = y1 + 70
    for text, color in lines:
        draw.text((x1 + 26, y), text, font=font(17, mono=True), fill=color)
        y += 31


def make_scenes(receipt: dict) -> list[Path]:
    unchanged = json.loads(receipt["requests"]["unchanged"]["body"])
    rewritten = json.loads(receipt["requests"]["rewritten"]["body"])
    commit = receipt["recorded_source_commit"][:12]
    scenes = []

    image = background(); draw = ImageDraw.Draw(image)
    header(draw, "01", "Edits become a bounded signal", "A real deterministic endpoint replaces the reward placeholder.")
    code_card(draw, (64, 235, 1216, 603), "POST /v1/rewards/edit-similarity", [
        ("candidate  →  generated draft", "#AAB5D4"),
        ("edited     →  final user text", "#AAB5D4"),
        ("", "#AAB5D4"),
        ("score = 1 − levenshtein_distance / max(lengths)", "#39E6B0"),
        ("range: 0.0 … 1.0  •  identical text: 1.0", "#7C6CFF"),
    ])
    footer(draw); scenes.append(save_scene(image, 1))

    image = background(); draw = ImageDraw.Draw(image)
    header(draw, "02", "Unchanged draft", "The local service returns an exact 1.0 similarity score.")
    code_card(draw, (64, 235, 755, 603), "REQUEST", [
        ('"candidate": "Hi Ava — your replacement ships today."', "#D8DFF5"),
        ('"edited":    "Hi Ava — your replacement ships today."', "#D8DFF5"),
        ("HTTP 200", "#39E6B0"),
    ])
    rounded(draw, (793, 235, 1216, 603), "#0D1325", "#39E6B0", 2, 22)
    draw.text((836, 278), "NORMALIZED SCORE", font=font(15, bold=True), fill="#8D99B8")
    draw.text((836, 335), f'{unchanged["score"]:.2f}', font=font(90, bold=True), fill="#39E6B0")
    draw.text((838, 463), f'distance  {unchanged["distance"]}', font=font(20, mono=True), fill="#D8DFF5")
    draw.text((838, 501), f'length    {unchanged["candidate_length"]}', font=font(20, mono=True), fill="#D8DFF5")
    footer(draw); scenes.append(save_scene(image, 2))

    image = background(); draw = ImageDraw.Draw(image)
    header(draw, "03", "Rewritten draft", "A visible edit yields a lower score and the exact distance used.")
    code_card(draw, (64, 235, 755, 603), "REQUEST", [
        ('candidate  "Hello Ava — your replacement is on the way."', "#AAB5D4"),
        ('edited     "Hi Ava, your replacement ships today."', "#F4F7FF"),
        ("HTTP 200", "#39E6B0"),
    ])
    rounded(draw, (793, 235, 1216, 603), "#0D1325", "#7C6CFF", 2, 22)
    draw.text((836, 278), "NORMALIZED SCORE", font=font(15, bold=True), fill="#8D99B8")
    draw.text((836, 335), f'{rewritten["score"]:.3f}', font=font(82, bold=True), fill="#A998FF")
    draw.text((838, 463), f'distance  {rewritten["distance"]}', font=font(20, mono=True), fill="#D8DFF5")
    draw.text((838, 501), f'lengths   {rewritten["candidate_length"]} → {rewritten["edited_length"]}', font=font(20, mono=True), fill="#D8DFF5")
    footer(draw); scenes.append(save_scene(image, 3))

    image = background(); draw = ImageDraw.Draw(image)
    header(draw, "04", "Bad inputs fail closed", "Strict JSON validation and body limits are exercised over HTTP.")
    for y, status, label, detail, color in [
        (246, "400", "Malformed JSON", "request rejected before scoring", "#FFB454"),
        (386, "413", "Oversized body", "65,537 bytes exceeds the 65,536-byte cap", "#FF6E8B"),
    ]:
        rounded(draw, (64, y, 1216, y + 112), "#0D1325", color, 2, 20)
        draw.text((92, y + 29), status, font=font(36, bold=True), fill=color)
        draw.text((214, y + 23), label, font=font(24, bold=True), fill="#F4F7FF")
        draw.text((214, y + 61), detail, font=font(17), fill="#AAB5D4")
    footer(draw); scenes.append(save_scene(image, 4))

    metrics = receipt["requests"]["metrics"]["body"].splitlines()[2:]
    image = background(); draw = ImageDraw.Draw(image)
    header(draw, "05", "Prometheus sees every outcome", "Counters come from the same local process after the scored and rejected requests.")
    code_card(draw, (64, 235, 1216, 603), "GET /metrics  →  HTTP 200", [(line, "#39E6B0" if " 0" not in line else "#7884A6") for line in metrics])
    footer(draw); scenes.append(save_scene(image, 5))

    image = background(); draw = ImageDraw.Draw(image)
    header(draw, "06", "Reproducible, guarded, honest", "The demo reruns tests, verifies source bytes, then calls the service.")
    code_card(draw, (64, 235, 1216, 603), "VERIFICATION RECEIPT", [
        (f"source commit  {commit}", "#A998FF"),
        (f"reward tests   {receipt['tests']}", "#39E6B0"),
        ("source guard   SHA-256 + Git blob identity", "#39E6B0"),
        ("scope          deterministic fixture text", "#D8DFF5"),
        ("not claimed    satisfaction, quality, or business impact", "#FFB454"),
    ])
    footer(draw); scenes.append(save_scene(image, 6))
    return scenes


def save_scene(image: Image.Image, number: int) -> Path:
    path = DEMO / f"scene-{number:02d}.png"
    image.save(path, optimize=True)
    return path


def render_media(scenes: list[Path]) -> None:
    concat = DEMO / "scenes.txt"
    lines = []
    for path in scenes:
        lines.extend([f"file '{path.name}'", "duration 2.4"])
    lines.append(f"file '{scenes[-1].name}'")
    concat.write_text("\n".join(lines) + "\n")

    subprocess.run([
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-threads", "1",
        "-f", "concat", "-safe", "0", "-i", str(concat), "-vf", "fps=30,format=yuv420p",
        "-c:v", "libx264", "-preset", "slow", "-crf", "20", "-movflags", "+faststart",
        str(DEMO / "reward-edit-similarity.mp4"),
    ], cwd=DEMO, check=True)
    subprocess.run([
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-threads", "1",
        "-i", str(DEMO / "reward-edit-similarity.mp4"),
        "-vf", "fps=12,scale=960:-1:flags=lanczos,split[s0][s1];[s0]palettegen=max_colors=128[p];[s1][p]paletteuse=dither=bayer",
        "-loop", "0", str(DEMO / "reward-edit-similarity.gif"),
    ], check=True)

    artifacts = {}
    for name in ("reward-edit-similarity.mp4", "reward-edit-similarity.gif", "receipt.json"):
        path = DEMO / name
        artifacts[name] = {"bytes": path.stat().st_size, "sha256": sha256(path)}
    (DEMO / "artifacts.json").write_text(json.dumps(artifacts, indent=2, sort_keys=True) + "\n")
    concat.unlink()
    for path in scenes:
        path.unlink()


def main() -> None:
    manifest = verify_source()
    receipt = capture_receipt(manifest)
    scenes = make_scenes(receipt)
    render_media(scenes)
    print(json.dumps(json.loads((DEMO / "artifacts.json").read_text()), indent=2))


if __name__ == "__main__":
    main()
