"""Validate installed prerequisites; this is not the repository application."""

import io
import socket
import threading
import time

import httpx
import pandas as pd
import uvicorn
from fastapi import FastAPI, File, UploadFile
from strands import tool


@tool
def net_amount(csv_text: str) -> float:
    """Compute the net transaction amount from CSV data.

    Args:
        csv_text: CSV content containing an amount column.
    """
    frame = pd.read_csv(io.StringIO(csv_text))
    return float(frame["amount"].sum())


app = FastAPI()


@app.post("/validate-upload")
async def validate_upload(file: UploadFile = File(...)):
    content = (await file.read()).decode("utf-8")
    return {"net_amount": net_amount(content)}


csv_text = "date,amount\n2026-09-01,1000\n2026-09-02,-250\n"
assert net_amount(csv_text) == 750.0
listener = socket.socket()
listener.bind(("127.0.0.1", 0))
port = listener.getsockname()[1]
server = uvicorn.Server(uvicorn.Config(app, log_level="warning"))
thread = threading.Thread(target=server.run, kwargs={"sockets": [listener]}, daemon=True)
thread.start()
try:
    deadline = time.monotonic() + 10
    while not server.started:
        if not thread.is_alive() or time.monotonic() > deadline:
            raise RuntimeError("Uvicorn failed to start within 10 seconds")
        time.sleep(0.05)
    with httpx.Client(trust_env=False, timeout=5) as client:
        response = client.post(
            f"http://127.0.0.1:{port}/validate-upload",
            files={"file": ("transactions.csv", csv_text, "text/csv")},
        )
        response.raise_for_status()
        assert response.json() == {"net_amount": 750.0}, response.text
        schema = client.get(f"http://127.0.0.1:{port}/openapi.json")
        schema.raise_for_status()
        assert "/validate-upload" in schema.json()["paths"]
    print("PASS: CSV upload -> FastAPI/Uvicorn -> Strands tool -> pandas, net amount 750")
    print("PASS: HTTP API schema served; no model inference performed")
finally:
    server.should_exit = True
    thread.join(timeout=10)
    listener.close()
    if thread.is_alive():
        raise RuntimeError("Smoke server did not stop")
