import argparse
import asyncio
import dataclasses
import json
from pathlib import Path
from typing import Any

from ..config import AppConfig, load_config
from ..enrollment import EnrollmentJob, apply_review, job_to_dict, run_face_enrollment, run_object_enrollment
from ..profiles import list_profiles
from ..runtime import TrackerRuntime


def create_app(cfg: AppConfig, dry_run: bool = True, mock: bool = False) -> Any:
    from fastapi import FastAPI, HTTPException, WebSocket
    from fastapi.responses import HTMLResponse, StreamingResponse
    from fastapi.staticfiles import StaticFiles

    app = FastAPI(title="Trifold Tracker")
    runtime = TrackerRuntime(cfg, dry_run=dry_run, mock=mock)
    jobs: dict[str, EnrollmentJob] = {}
    static_dir = Path(__file__).resolve().parent / "static"
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

    @app.get("/", response_class=HTMLResponse)
    def index() -> str:
        return (static_dir / "index.html").read_text(encoding="utf-8")

    @app.get("/api/config")
    def api_config() -> dict[str, Any]:
        state = dataclasses.asdict(runtime.state())
        return {
            "state": state,
            "profiles": {
                "face": list_profiles(cfg.detection.face.profiles_dir, "face"),
                "object": list_profiles(cfg.detection.object.profiles_dir, "object"),
            },
        }

    @app.post("/api/mode")
    async def api_mode(payload: dict[str, Any]) -> dict[str, Any]:
        try:
            runtime.set_mode(str(payload.get("mode", "")), payload.get("profile_id") or None)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"ok": True, "state": dataclasses.asdict(runtime.state())}

    @app.post("/api/enroll/face")
    async def api_enroll_face(payload: dict[str, Any]) -> dict[str, Any]:
        try:
            job = run_face_enrollment(str(payload["directory"]), str(payload["profile_name"]), cfg.detection.face)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        jobs[job.job_id] = job
        runtime.emit("log", message=f"face enrollment {job.status}: {job.accepted_count} accepted")
        return job_to_dict(job)

    @app.post("/api/enroll/object")
    async def api_enroll_object(payload: dict[str, Any]) -> dict[str, Any]:
        try:
            job = run_object_enrollment(str(payload["directory"]), str(payload["profile_name"]), str(payload["prompt"]), cfg.detection.object)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        jobs[job.job_id] = job
        runtime.emit("log", message=f"object enrollment {job.status}: {job.accepted_count} accepted")
        return job_to_dict(job)

    @app.get("/api/enroll/{job_id}")
    async def api_enroll_status(job_id: str) -> dict[str, Any]:
        if job_id not in jobs:
            raise HTTPException(status_code=404, detail="enrollment job not found")
        return job_to_dict(jobs[job_id])

    @app.post("/api/enroll/{job_id}/accept")
    async def api_enroll_accept(job_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        return _review(job_id, str(payload["item_id"]), True)

    @app.post("/api/enroll/{job_id}/reject")
    async def api_enroll_reject(job_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        return _review(job_id, str(payload["item_id"]), False)

    def _review(job_id: str, item_id: str, accepted: bool) -> dict[str, Any]:
        if job_id not in jobs:
            raise HTTPException(status_code=404, detail="enrollment job not found")
        job = jobs[job_id]
        base_dir = cfg.detection.face.profiles_dir if job.mode == "face" else cfg.detection.object.profiles_dir
        apply_review(job, item_id, accepted, base_dir)
        runtime.emit("log", message=f"review {job.mode}: {job.accepted_count} accepted")
        return job_to_dict(job)

    @app.post("/api/tracking/start")
    async def api_tracking_start() -> dict[str, Any]:
        runtime.start()
        return {"ok": True, "state": dataclasses.asdict(runtime.state())}

    @app.post("/api/tracking/stop")
    async def api_tracking_stop() -> dict[str, Any]:
        runtime.stop()
        return {"ok": True, "state": dataclasses.asdict(runtime.state())}

    @app.post("/api/tracking/pause")
    async def api_tracking_pause() -> dict[str, Any]:
        runtime.pause()
        return {"ok": True, "state": dataclasses.asdict(runtime.state())}

    @app.post("/api/tracking/resume")
    async def api_tracking_resume() -> dict[str, Any]:
        runtime.resume()
        return {"ok": True, "state": dataclasses.asdict(runtime.state())}

    @app.post("/api/controller/center")
    async def api_center() -> dict[str, Any]:
        ok = runtime.center()
        return {"ok": ok, "state": dataclasses.asdict(runtime.state())}

    @app.post("/api/dry-run")
    async def api_dry_run(payload: dict[str, Any]) -> dict[str, Any]:
        runtime.set_dry_run(bool(payload.get("enabled", True)))
        return {"ok": True, "state": dataclasses.asdict(runtime.state())}

    @app.get("/api/video.mjpg")
    def api_video() -> StreamingResponse:
        def frames() -> Any:
            while True:
                jpeg = runtime.latest_jpeg()
                yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + jpeg + b"\r\n"
                import time

                time.sleep(0.08)

        return StreamingResponse(frames(), media_type="multipart/x-mixed-replace; boundary=frame")

    @app.websocket("/api/events")
    async def api_events(websocket: WebSocket) -> None:
        await websocket.accept()
        await websocket.send_text(json.dumps({"type": "snapshot", "state": dataclasses.asdict(runtime.state())}, separators=(",", ":")))
        while True:
            event = await asyncio.to_thread(runtime.next_event, 15.0)
            if event is None:
                event = {"type": "heartbeat"}
            await websocket.send_text(json.dumps(event, separators=(",", ":")))

    app.state.runtime = runtime
    app.state.enrollment_jobs = jobs
    return app


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the trifold tracker localhost GUI")
    parser.add_argument("config", nargs="?", default="config/local.yaml")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--live", action="store_true", help="send controller commands instead of dry-run")
    parser.add_argument("--mock", action="store_true", help="use synthetic frames and mock detections")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    import uvicorn

    app = create_app(load_config(args.config), dry_run=not args.live, mock=args.mock)
    uvicorn.run(app, host=args.host, port=args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
