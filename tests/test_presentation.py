"""Contratos del panel local: tareas permitidas, HTTP y procesos reales."""
import http.client
import json
import sys
import threading
import time

import pytest

from src.macetas import presentation as panel


@pytest.mark.parametrize("task", [t["id"] for t in panel.TASKS])
def test_tasks_are_fixed_python_commands(task):
    commands = panel.task_commands(task, {"method": "euler", "step_h": "0.5"})
    assert commands
    assert all(c[:5] == [sys.executable, "-X", "utf8", "-u", "-m"] for c in commands)
    assert not any("git" in c for c in commands)
    if task == "optimize":
        assert commands[0][-1] == "results/presentation/optimization"
    if task == "experiments":
        assert "--method" not in commands[0]


@pytest.mark.parametrize("options", [{"method": "shell"}, {"step_h": "0; echo bad"}, {"step_h": -1}])
def test_reject_arbitrary_options(options):
    with pytest.raises(ValueError):
        panel.task_commands("simulate", options)


def test_reject_unknown_task():
    with pytest.raises(ValueError):
        panel.task_commands("git push")


def test_trajectory_uses_exported_values():
    payload = panel.trajectory_payload("experiments", "O1", 13001)
    assert payload["data_origin"] in ("public", "synthetic")
    assert len(payload["seeds"]) == 30
    assert payload["trajectory"][-1]["irrigation_ml"] == pytest.approx(float(payload["metrics"]["total_irrigation_ml"]))
    assert payload["events"][-1]["kind"] == "final_refill"
    with pytest.raises(ValueError):
        panel.trajectory_payload("experiments", "X0", 13001)


@pytest.fixture
def server(tmp_path, monkeypatch):
    monkeypatch.setattr(panel, "ROOT", tmp_path)
    server = panel.make_server(0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield server
    server.shutdown()
    server.server_close()
    thread.join(timeout=2)


def request(server, method, path, body=None, headers=None):
    connection = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=5)
    connection.request(method, path, json.dumps(body) if body is not None else None, headers or {})
    response = connection.getresponse()
    status, content, response_headers = response.status, response.read(), dict(response.getheaders())
    connection.close()
    return status, content, response_headers


def test_http_serves_assets_and_blocks_traversal(server):
    status, content, headers = request(server, "GET", "/")
    assert status == 200 and b"Laboratorio de riego" in content
    assert "frame-ancestors 'none'" in headers["Content-Security-Policy"]
    assert request(server, "GET", "/app.js")[0] == 200
    assert request(server, "GET", "/files/../../README.md")[0] == 404
    assert request(server, "GET", "/%2e%2e/presentation.py")[0] == 404


def test_http_execution_and_origin_guard(server, monkeypatch):
    monkeypatch.setattr(panel, "task_commands", lambda task, options: [[sys.executable, "-c", "print('panel test completed')"]])
    state = json.loads(request(server, "GET", "/api/state")[1])
    headers = {"Origin": f"http://127.0.0.1:{server.server_port}", "X-Panel-Token": state["token"]}
    assert request(server, "POST", "/api/run", {"task": "simulate"})[0] == 403
    assert request(server, "POST", "/api/run", {"task": "simulate"}, {**headers, "Origin": "https://example.com"})[0] == 403
    assert request(server, "POST", "/api/run", {"task": "simulate"}, headers)[0] == 202
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        state = json.loads(request(server, "GET", "/api/state")[1])
        if state["job"]["status"] != "running":
            break
        time.sleep(.02)
    assert state["job"]["status"] == "success"
    assert state["job"]["exit_code"] == 0
    assert "panel test completed" in state["job"]["log"]


def test_runner_blocks_concurrent_tasks_and_preserves_failure(tmp_path, monkeypatch):
    monkeypatch.setattr(panel, "ROOT", tmp_path)
    monkeypatch.setattr(panel, "task_commands", lambda task, options: [[sys.executable, "-c", "import time; time.sleep(.2); raise SystemExit(7)"]])
    runner = panel.TaskRunner()
    runner.start("test", {})
    with pytest.raises(RuntimeError):
        runner.start("test", {})
    deadline = time.monotonic()+5
    while runner.snapshot()["job"]["status"] == "running" and time.monotonic()<deadline:
        time.sleep(.02)
    assert runner.snapshot()["job"]["status"] == "error"
    assert runner.snapshot()["job"]["exit_code"] == 7
