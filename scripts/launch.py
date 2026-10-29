"""Start the local EasyResearch server and open it in the default browser.

This launcher intentionally leaves the server attached to its console: closing
the console ends the session. It never installs packages or changes a library.
"""
from __future__ import annotations

import http.client
import importlib.util
import json
from pathlib import Path
import socket
import subprocess
import sys
import threading
import time
import webbrowser

ROOT = Path(__file__).resolve().parents[1]
API_DIR = ROOT / "services" / "api"
URL = "http://127.0.0.1:8000/"
HOST = "127.0.0.1"
PORT = 8000
REQUIRED = {"fastapi": "fastapi", "uvicorn": "uvicorn", "pydantic": "pydantic",
            "pypdf": "pypdf", "multipart": "python-multipart"}


def probe_server(host=HOST, port=PORT):
    """Return easyresearch, other, or free; never consult a proxy."""
    try:
        with socket.create_connection((host, port), timeout=0.5):
            pass
    except OSError:
        return "free"
    conn = http.client.HTTPConnection(host, port, timeout=1)
    try:
        conn.request("GET", "/api/health", headers={"Host": f"{host}:{port}"})
        response = conn.getresponse()
        if response.status != 200:
            return "other"
        body = response.read(65537)
        if len(body) > 65536:
            return "other"
        data = json.loads(body)
        if not isinstance(data, dict) or data.get("status") != "ok" or data.get("pdf_parser") != "pypdf":
            return "other"
        return "easyresearch"
    except (OSError, ValueError, http.client.HTTPException):
        return "other"
    finally:
        conn.close()


def missing_packages():
    missing = []
    for module, package in REQUIRED.items():
        try:
            if importlib.util.find_spec(module) is None:
                missing.append(package)
        except (ImportError, ValueError):
            missing.append(package)
    return missing


def open_browser():
    try:
        if not webbrowser.open(URL):
            print("브라우저를 자동으로 열지 못했습니다. 아래 주소를 직접 여세요:", URL)
    except Exception:
        print("브라우저를 자동으로 열지 못했습니다. 아래 주소를 직접 여세요:", URL)


def main(*, require_free=False):
    if sys.version_info < (3, 9):
        print("Python 3.9 이상이 필요합니다. 현재 버전:", sys.version.split()[0])
        return 1
    if not API_DIR.is_dir():
        print("앱 파일을 찾지 못했습니다. 실행 파일을 EasyResearch 폴더 안에 두세요.")
        return 1

    state = probe_server()
    if state == "easyresearch":
        if require_free:
            print("다른 보관함이 실행 중입니다. 종료한 뒤 다시 실행하세요.")
            return 1
        print("EasyResearch가 이미 실행 중인 것으로 보입니다. 기존 앱을 엽니다.")
        print("실행 중인 앱의 자료 폴더는 이 실행 도구에서 확인할 수 없습니다.")
        open_browser()
        return 0
    if state == "other":
        print("8000번 포트를 다른 프로그램이 사용하고 있어 앱을 열지 않았습니다.")
        print("해당 프로그램을 종료한 뒤 다시 실행하세요.")
        return 1

    missing = missing_packages()
    if missing:
        print("필요한 Python 패키지가 없습니다:", ", ".join(missing))
        print("다음 명령으로 설치한 뒤 다시 실행하세요:")
        print(f'"{sys.executable}" -m pip install -r "{ROOT / "services" / "api" / "requirements.txt"}"')
        return 1

    print("EasyResearch를 시작하고 있습니다. 창을 열어 두면 앱을 사용할 수 있습니다.", flush=True)
    print("앱을 안전하게 종료하려면 이 창에서 Ctrl+C를 누르세요.", flush=True)
    try:
        process = subprocess.Popen([sys.executable, "-m", "uvicorn", "app.main:app",
                                    "--host", HOST, "--port", str(PORT), "--no-use-colors"], cwd=str(API_DIR),
                                   stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace", bufsize=1)
    except OSError as exc:
        print("서버를 시작하지 못했습니다:", exc)
        return 1

    listening = threading.Event()

    def show_server_output():
        for line in process.stderr:
            print(line, end="", file=sys.stderr, flush=True)
            # This message is emitted only after uvicorn binds its socket. It
            # prevents a race with a different server starting on the port.
            if "Uvicorn running on http://127.0.0.1:8000" in line:
                listening.set()

    threading.Thread(target=show_server_output, daemon=True).start()
    try:
        deadline = time.monotonic() + 25
        while time.monotonic() < deadline:
            code = process.poll()
            if code is not None:
                print("서버 시작에 실패했습니다. 위 오류를 확인하세요. 종료 코드:", code)
                return 1
            if listening.is_set() and probe_server() == "easyresearch":
                # Do not open an unrelated server if our child has already died.
                if process.poll() is not None:
                    print("서버가 시작 직후 종료되었습니다. 위 오류를 확인하세요.")
                    return 1
                print("앱이 준비되었습니다:", URL, flush=True)
                open_browser()
                return process.wait()
            time.sleep(0.2)
        print("서버 준비 시간이 초과됐습니다. 위 오류를 확인하세요.")
        return 1
    except KeyboardInterrupt:
        print("\nEasyResearch를 종료하고 있습니다.")
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.terminate()
            process.wait(timeout=5)
        return 0
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()


if __name__ == "__main__":
    raise SystemExit(main())
