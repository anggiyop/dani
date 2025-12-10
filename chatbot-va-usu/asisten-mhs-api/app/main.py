from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .routers import services, tickets

app = FastAPI(title="Asisten Mahasiswa API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(services.router)
app.include_router(tickets.router)

@app.get("/v1/util/healthz")
def healthz():
    return {"ok": True}
