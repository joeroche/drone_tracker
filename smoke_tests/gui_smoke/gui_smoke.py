from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import cv2
import numpy as np
import requests
import yaml


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Smoke test the localhost tracker GUI and capture screenshots")
    parser.add_argument("--config", default="config/default.yaml")
    parser.add_argument("--screenshots", default="artifacts/gui_smoke")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument(
        "--browser-executable",
        help="optional Chromium executable for environments without Playwright's bundled browser",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    screenshots = Path(args.screenshots)
    screenshots.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        smoke_config = Path(tmp) / "smoke.yaml"
        fixture_dir = Path(tmp) / "objects"
        _write_fixture_images(fixture_dir)
        _write_smoke_config(Path(args.config), smoke_config, Path(tmp))
        proc = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "drone_tracker.gui.app",
                str(smoke_config),
                "--port",
                str(args.port),
                "--mock",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        try:
            _wait_for_server(args.port)
            _capture_with_playwright(
                args.port,
                fixture_dir,
                screenshots,
                args.browser_executable,
            )
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
        print(f"screenshots written to {screenshots}")
    return 0


def _wait_for_server(port: int) -> None:
    deadline = time.time() + 20
    url = f"http://127.0.0.1:{port}/api/config"
    while time.time() < deadline:
        try:
            if requests.get(url, timeout=0.5).status_code == 200:
                return
        except requests.RequestException:
            time.sleep(0.2)
    raise RuntimeError("GUI server did not start")


def _capture_with_playwright(
    port: int,
    fixture_dir: Path,
    screenshots: Path,
    browser_executable: str | None,
) -> None:
    try:
        from playwright.sync_api import sync_playwright
    except Exception as exc:
        raise RuntimeError("playwright is required for screenshot smoke tests") from exc

    with sync_playwright() as p:
        launch_options = {}
        if browser_executable:
            launch_options["executable_path"] = browser_executable
        browser = p.chromium.launch(**launch_options)
        page = browser.new_page(viewport={"width": 1440, "height": 960})
        page.goto(f"http://127.0.0.1:{port}", wait_until="networkidle")
        page.screenshot(path=str(screenshots / "01_drone_boot.png"), full_page=True)
        page.wait_for_timeout(1000)
        page.screenshot(path=str(screenshots / "02_drone_live.png"), full_page=True)
        page.get_by_role("button", name="Face").click()
        page.fill("#profileName", "friend")
        page.screenshot(path=str(screenshots / "03_face_enrollment_empty.png"), full_page=True)
        page.get_by_role("button", name="Object").click()
        page.fill("#profileName", "cola can")
        page.fill("#prompt", "soda can")
        page.fill("#directory", str(fixture_dir))
        page.get_by_role("button", name="Enroll").click()
        page.wait_for_selector(".review-card")
        page.fill("#directory", "")
        page.screenshot(path=str(screenshots / "04_object_enrollment_review.png"), full_page=True)
        page.wait_for_timeout(1000)
        page.screenshot(path=str(screenshots / "05_object_live.png"), full_page=True)
        mobile = browser.new_page(viewport={"width": 390, "height": 900})
        mobile.goto(f"http://127.0.0.1:{port}", wait_until="networkidle")
        mobile.screenshot(path=str(screenshots / "06_mobile_layout.png"), full_page=True)
        browser.close()


def _write_fixture_images(directory: Path) -> None:
    if directory.exists():
        shutil.rmtree(directory)
    directory.mkdir(parents=True)
    for index in range(3):
        image = np.zeros((180, 140, 3), dtype=np.uint8)
        image[:] = (18 + index * 12, 24, 32)
        cv2.rectangle(image, (34, 20), (106, 160), (40, 210 - index * 20, 140 + index * 30), -1)
        cv2.rectangle(image, (44, 42), (96, 128), (240, 240, 220), -1)
        cv2.putText(image, "CAN", (47, 92), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (20, 30, 35), 2)
        cv2.imwrite(str(directory / f"can_{index}.jpg"), image)


def _write_smoke_config(source: Path, dest: Path, tmp_dir: Path) -> None:
    data = yaml.safe_load(source.read_text(encoding="utf-8"))
    data["camera"]["mode"] = "synthetic"
    data["detection"]["face"]["backend"] = "haar"
    data["detection"]["face"]["profiles_dir"] = str(tmp_dir / "profiles" / "faces")
    data["detection"]["face"]["blur_threshold"] = 0.0
    data["detection"]["object"]["backend"] = "center"
    data["detection"]["object"]["profiles_dir"] = str(tmp_dir / "profiles" / "objects")
    data["detection"]["object"]["blur_threshold"] = 1.0
    data["detection"]["object"]["local_verify"] = False
    dest.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
