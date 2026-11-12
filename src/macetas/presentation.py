"""Panel local de presentación. Ejecuta únicamente tareas conocidas del proyecto."""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import json
from pathlib import Path
import secrets
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, unquote, urlparse
import uuid
import webbrowser


ROOT = Path(__file__).resolve().parents[2]
ASSETS = Path(__file__).parent / "presentation_assets"
OUTPUT = "results/presentation"

# Sistema real del proyecto: datos públicos de Chase (2026), macetas de enset.
DATA_CONFIG = "data/reference/chase2026_enset/converted/data_config.json"
PARAMETERS = "results/calibration/public_enset/parametros_modelo.json"
BASE = "configs/base_enset.json"
EXPERIMENTS = "results/experiments/public_enset"
VALIDATION = "results/validation/public_enset"
COMPARISON = "results/tables/comparacion_real_enset.md"

TASKS = [
    {"id": "simulate", "title": "Simular maceta", "detail": "Política base · Euler o RK4 · maceta E12 del enset", "group": "demo"},
    {"id": "experiments", "title": "Comparar políticas", "detail": "B0 / O0 / B1 / O1 · 30 semillas reservadas · enset", "group": "demo"},
    {"id": "validate-model", "title": "Verificar el modelo", "detail": "Casos analíticos, conservación y convergencia", "group": "evidence"},
    {"id": "validate-data", "title": "Revisar datos reales", "detail": "Calidad de los pesajes de Chase (2026) · 21 macetas", "group": "evidence"},
    {"id": "calibrate", "title": "Calibrar con datos reales", "detail": "Ventana de ajuste (7 días) · parámetros por maceta", "group": "evidence"},
    {"id": "validation", "title": "Validar predicciones", "detail": "Predice la segunda semana sin recalibrar", "group": "evidence"},
    {"id": "plots", "title": "Regenerar figuras", "detail": "Figuras PNG/PDF desde las tablas del enset", "group": "evidence"},
    {"id": "tests", "title": "Ejecutar todas las pruebas", "detail": "Suite completa de pytest · resultado real en consola", "group": "evidence"},
    {"id": "optimize", "title": "Ejecutar PSO", "detail": "Proceso largo · 30 búsquedas por variante · salida separada", "group": "advanced"},
]


def task_commands(task, options=None):
    options = options or {}
    method = options.get("method", "rk4")
    step = str(options.get("step_h", "0.25"))
    if method not in ("euler", "rk4") or step not in ("0.125", "0.25", "0.5", "1"):
        raise ValueError("Método o paso no admitido.")
    python = [sys.executable, "-X", "utf8", "-u", "-m"]
    commands = {
        "simulate": [python + ["src.macetas", "simulate", "--config", "configs/model_public_enset.json",
                     "--parameters", PARAMETERS, "--base", BASE, "--pot-id", "E12", "--method", method,
                     "--step-h", step, "--out", f"{OUTPUT}/simulation"]],
        "experiments": [python + ["src.macetas.experiments", "--config", "configs/experiments_enset.json",
                                   "--out", f"{OUTPUT}/experiments"]],
        "validate-model": [python + ["src.macetas", "validate-model", "--out", f"{OUTPUT}/verification"]],
        "validate-data": [python + ["src.macetas", "validate-data", "--config", DATA_CONFIG]],
        # Escribe en data/reference/.../converted/salidas (no versionado); no toca results/calibration.
        "calibrate": [python + ["src.macetas", "calibrate", "--config", "configs/model_public_enset.json"]],
        "validation": [python + ["src.macetas.validation", "--data-config", DATA_CONFIG,
                       "--parameters", PARAMETERS, "--method", method,
                       "--step-h", step, "--out", f"{OUTPUT}/validation"]],
        "plots": [python + ["src.macetas.plots", "--experiments", experiment_root().relative_to(ROOT).as_posix(),
                            "--validation", validation_root().relative_to(ROOT).as_posix(),
                            "--out", f"{OUTPUT}/figures"]],
        "tests": [python + ["pytest", "-q", "--assert=plain", f"--basetemp={OUTPUT}/ui-tests-{uuid.uuid4().hex[:10]}"]],
        "optimize": [python + ["src.macetas", "optimize", "--config", "configs/pso_enset.json",
                               "--out", f"{OUTPUT}/optimization"]],
    }
    if task not in commands:
        raise ValueError("Tarea desconocida.")
    return commands[task]


def experiment_root():
    candidate = ROOT / OUTPUT / "experiments"
    return candidate if (candidate / "runs.csv").exists() else ROOT / EXPERIMENTS


def validation_root():
    candidate = ROOT / OUTPUT / "validation"
    return candidate if (candidate / "errors.csv").exists() else ROOT / VALIDATION


def validation_origin(root):
    path = root / "validation_manifest.json"
    if not path.exists():
        return None
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if manifest.get("real_validation"):
        return "observed"
    return "public" if manifest.get("public_reference_validation") else "synthetic"


def figure_paths():
    """Figuras de la presentación: experimentos y validación del enset (o las regeneradas)."""
    generated = sorted((ROOT / OUTPUT / "figures").glob("*.png"))
    if generated:
        return generated
    experiments = [ROOT / EXPERIMENTS / "figures" / f"{name}.png" for name in ("01_system", "02_policies", "03_sensitivity")]
    return [p for p in experiments + [ROOT / VALIDATION / "figures/04_validation_all.png"] if p.is_file()]


def real_status():
    if not (ROOT / COMPARISON).is_file():
        return "Comparación con el sistema real: falta results/tables/comparacion_real_enset.md."
    return ("Comparación con el sistema real (Chase, 2026): las plantas control recibieron unos 273 mL/día; "
            "la simulación base aplica 370 y la optimizada 298 (−19.5 % en pares factibles). "
            "La mejora es simulada: la política no se aplicó en plantas reales. Tabla: " + COMPARISON + ".")


def read_rows(path):
    if not path.exists():
        return []
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def trajectory_payload(source="experiments", condition="B0", seed=None):
    if source not in ("experiments", "simulation") or condition not in ("B0", "O0", "B1", "O1"):
        raise ValueError("Fuente o condición desconocida.")
    if source == "simulation":
        root = ROOT / OUTPUT / "simulation"
        rows = read_rows(root / "trayectoria.csv")
        events = read_rows(root / "riegos.csv")
        metrics_path = root / "metricas.json"
        metrics = json.loads(metrics_path.read_text(encoding="utf-8")) if metrics_path.exists() else {}
        limit = json.loads((ROOT / BASE).read_text(encoding="utf-8"))["simulation"]["safe_deficit_ml"]
        seeds, chosen = [], None
    else:
        root = experiment_root()
        runs = read_rows(root / "runs.csv")
        seeds = sorted({int(r["seed"]) for r in runs})
        chosen = int(seed) if seed is not None else (seeds[0] if seeds else None)
        selected = [r for r in runs if r["condition"] == condition and int(r["seed"]) == chosen]
        if not selected:
            raise ValueError("No hay resultados para esta condición y semilla. Ejecute la comparación.")
        metrics = selected[0]
        rows = [r for r in read_rows(root / "trajectory.csv") if r["condition"] == condition and int(r["seed"]) == chosen]
        events = [r for r in read_rows(root / "events.csv") if r["condition"] == condition and int(r["seed"]) == chosen]
        limit = float(metrics["safe_deficit_ml"])
    if not rows:
        raise ValueError("Ejecute primero la simulación para ver su trayectoria.")
    return {"trajectory": [{"timestamp": r["timestamp"], "stage": r["stage"],
                            "deficit_ml": float(r["deficit_ml"]), "irrigation_ml": float(r["irrigation_ml"]),
                            "drainage_ml": float(r["drainage_ml"])} for r in rows],
            "events": [{"timestamp": r["timestamp"], "kind": r["kind"],
                        "irrigation_ml": float(r["irrigation_ml"])} for r in events],
            "metrics": metrics, "safe_deficit_ml": limit, "seeds": seeds, "seed": chosen,
            "source": source, "condition": condition, "data_origin": rows[0]["data_origin"]}


class TaskRunner:
    def __init__(self):
        self.lock = threading.Lock()
        self.job = None
        self.history = []

    def snapshot(self):
        with self.lock:
            return {"job": json.loads(json.dumps(self.job)), "history": self.history.copy()}

    def start(self, task, options):
        commands = task_commands(task, options)
        with self.lock:
            if self.job and self.job["status"] == "running":
                raise RuntimeError("Hay una tarea en ejecución. Espere a que termine.")
            self.job = {"id": uuid.uuid4().hex, "task": task, "status": "running", "log": "",
                        "started_at": datetime.now(timezone.utc).isoformat(), "exit_code": None,
                        "commands": [subprocess.list2cmdline(c) for c in commands]}
            job_id = self.job["id"]
        threading.Thread(target=self._run, args=(commands,), daemon=True).start()
        return job_id

    def _append(self, line):
        with self.lock:
            self.job["log"] = (self.job["log"] + line)[-150_000:]

    def _run(self, commands):
        code = 0
        try:
            for command in commands:
                self._append("\n> " + subprocess.list2cmdline(command) + "\n")
                with subprocess.Popen(command, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                      text=True, encoding="utf-8", errors="replace",
                                      creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)) as process:
                    for line in process.stdout:
                        self._append(line)
                    code = process.wait()
                if code:
                    break
        except Exception as error:
            self._append(f"\nError al ejecutar: {error}\n")
            code = 1
        with self.lock:
            self.job.update(status="success" if code == 0 else "error", exit_code=code,
                            finished_at=datetime.now(timezone.utc).isoformat())
            self.history.append({k: self.job[k] for k in ("task", "status", "exit_code", "started_at")})
            completed = self.job.copy()
        output = ROOT / OUTPUT / "logs"
        output.mkdir(parents=True, exist_ok=True)
        (output / f"{completed['id']}.json").write_text(json.dumps(completed, ensure_ascii=False, indent=2), encoding="utf-8")


def make_server(port=8765):
    runner, token = TaskRunner(), secrets.token_urlsafe(32)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def send_body(self, body, mime="application/json; charset=utf-8", status=200):
            self.send_response(status)
            self.send_header("Content-Type", mime)
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; object-src 'none'; frame-ancestors 'none'")
            self.end_headers()
            self.wfile.write(body)

        def send_json(self, value, status=200):
            self.send_body(json.dumps(value, ensure_ascii=False, allow_nan=False).encode("utf-8"), status=status)

        def do_GET(self):
            parsed = urlparse(self.path)
            try:
                if parsed.path == "/api/state":
                    figures = figure_paths()
                    candidates = [("Ejecuciones CSV", experiment_root() / "runs.csv"),
                                  ("Resumen CSV", experiment_root() / "summary.csv"),
                                  ("Diferencias pareadas CSV", experiment_root() / "paired.csv"),
                                  ("Conservación CSV", experiment_root() / "balance.csv"),
                                  ("Validación CSV", validation_root() / "errors.csv"),
                                  ("Comparación real (Parte 6)", ROOT / COMPARISON),
                                  ("Convergencia CSV", ROOT / OUTPUT / "verification/convergencia.csv")]
                    artifacts = [{"label": name, "url": "/files/" + p.relative_to(ROOT / "results").as_posix()}
                                 for name, p in candidates if p.is_file()]
                    self.send_json({**runner.snapshot(), "token": token, "tasks": TASKS, "artifacts": artifacts,
                                    "summary": read_rows(experiment_root() / "summary.csv"),
                                    "validation": read_rows(validation_root() / "errors.csv"),
                                    "validation_origin": validation_origin(validation_root()),
                                    "figures": ["/files/" + p.relative_to(ROOT / "results").as_posix() for p in figures],
                                    "real_status": real_status()})
                elif parsed.path == "/api/trajectory":
                    query = parse_qs(parsed.query)
                    self.send_json(trajectory_payload(query.get("source", ["experiments"])[0],
                                                     query.get("condition", ["B0"])[0], query.get("seed", [None])[0]))
                else:
                    import mimetypes
                    if parsed.path.startswith("/files/"):
                        base, relative = ROOT / "results", unquote(parsed.path[len("/files/"):])
                    else:
                        base, relative = ASSETS, "index.html" if parsed.path == "/" else unquote(parsed.path.lstrip("/"))
                    file = (base / relative).resolve()
                    if not file.is_relative_to(base.resolve()) or not file.is_file():
                        self.send_json({"error": "Archivo no encontrado."}, 404)
                        return
                    self.send_body(file.read_bytes(), mimetypes.guess_type(file.name)[0] or "application/octet-stream")
            except (ValueError, KeyError, OSError) as error:
                self.send_json({"error": str(error)}, 400)

        def do_POST(self):
            expected = {f"http://127.0.0.1:{self.server.server_port}", f"http://localhost:{self.server.server_port}"}
            if self.headers.get("Origin") not in expected or self.headers.get("X-Panel-Token") != token:
                self.send_json({"error": "Solicitud local no autorizada."}, 403)
                return
            if self.path != "/api/run":
                self.send_json({"error": "Ruta desconocida."}, 404)
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= 4096:
                    raise ValueError("Tamaño de solicitud no admitido.")
                body = json.loads(self.rfile.read(length))
                self.send_json({"job_id": runner.start(body["task"], body.get("options", {}))}, 202)
            except RuntimeError as error:
                self.send_json({"error": str(error)}, 409)
            except (ValueError, KeyError, TypeError) as error:
                self.send_json({"error": str(error)}, 400)

    return ThreadingHTTPServer(("127.0.0.1", port), Handler)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()
    server = make_server(args.port)
    url = f"http://127.0.0.1:{server.server_port}"
    print(f"Panel de presentación: {url}\nCtrl+C para cerrar.", flush=True)
    if not args.no_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
