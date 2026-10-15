from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.falkor import store

app = FastAPI(title="Continuum", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    try:
        store.client.select_graph("_health").query("RETURN 1")
        db = "up"
    except Exception as e:
        db = f"down: {e}"
    return {"status": "ok", "falkordb": db}


@app.get("/")
def root():
    return {"name": "Continuum", "status": "scaffold"}
