from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, Field
from typing import Optional
import time
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger("aiops")

APP_VERSION = "1.0.0"
GAP_SEC = 120
MAX_HOP = 1

app = FastAPI(title="AIOps Incident Pipeline",
              version=APP_VERSION,
              description="Correlate alerts, find Root Cause Analysis, and suggest actions",
              )

class Alert(BaseModel):
    id: str
    ts: str
    service: str
    metric: str
    severity: str
    value: float
    threshold: float
    labels: Optional[dict] = Field(default_factory=dict)

class IncidentRequest(BaseModel):
    alerts: list[Alert]

class Cluster(BaseModel):
    cluster_id: str
    alert_count: int
    services: list[str]
    time_range: list[str]

class RootCause(BaseModel):
    service: str
    confidence: float
    reasoning: str

class IncidentResponse(BaseModel):
    clusters: list[Cluster]
    root_cause: RootCause
    recommended_actions: list[str]


@app.middleware("http")
async def add_timing(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    duration_ms = (time.perf_counter() - start) * 1000
    response.headers["X-Processing-Time-ms"] = f"{duration_ms:.1f}"
    logger.info(
        "%s %s %s %.1fms",
        request.method,
        request.url.path,
        response.status_code,
        duration_ms
    )
    return response

@app.get("/healthz")
def healthz():
    return {"status": "ok"}

@app.get("/readyz")
def readyz():
    checks = {
        "app":  True,
        "pipeline_config": GAP_SEC > 0 and MAX_HOP >= 0,
    }

    if not all(checks.values()):
        raise HTTPException(status_code=503, detail=checks)
    
    return {
        "status": "ready",
        "checks": checks
    }

@app.get("/version")
def version():
    return {
        "app": APP_VERSION,
        "pipeline_config": {
            "correlate_gap_sec": GAP_SEC,
            "correlate_max_hop": MAX_HOP,
            "rca_method": "rule-based-stub",
        }
    }

def simple_correlate(alerts: list[dict]) -> list[dict]:
    if not alerts:
        return []
    
    services = sorted({a['service'] for a in alerts})
    timestamps = sorted({a['ts'] for a in alerts})

    return [
        {
            "cluster_id": "c-000",
            "alert_count": len(alerts),
            "services": services,
            "time_range": [timestamps[0], timestamps[-1]],
        }
    ]

def simple_rca(alerts: list[dict]) -> dict:
    service_count = {}

    for alert in alerts:
        service = alert['service']
        service_count[service] = service_count.get(service, 0) + 1

    root_service = max(service_count, key=service_count.get)

    return {
        "service": root_service,
        "confidence": 0.7,
        "reasoning": f"Service {root_service} has the most alerts ({service_count[root_service]})"
    }

def process_batch(alerts: list[dict]) -> dict:
    clusters = simple_correlate(alerts)

    if not clusters:
        return {
            "clusters": [],
            "root_cause": {
                "service": "unknown",
                "confidence": 0.0,
                "reasoning": "No alerts were provided.",
            },
            "recommended_actions": [],
        }
    
    root_cause = simple_rca(alerts)

    return {
        "clusters": clusters,
        "root_cause": root_cause,
        "recommended_actions": [
            "Check recent deploys for the suspected root-cause service.",
            "Inspect service metrics, logs, and dependency errors.",
            "Escalate to the owning team if severity remains critical.",
        ],
    }

@app.post("/incident", response_model=IncidentResponse)
def post_incident(req: IncidentRequest):
    if not req.alerts:
        raise HTTPException(status_code=400, detail="Empty alert list")

    alerts_dict = [alert.model_dump() for alert in req.alerts]

    try:
        result = process_batch(alerts_dict)
        return IncidentResponse(**result)
    except Exception as exc:
        logger.error("Pipeline failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Pipeline error")