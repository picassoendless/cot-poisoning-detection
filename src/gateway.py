"""
gateway.py

Inline FastAPI gateway for the three-layer CoT poisoning detection system.

A production deployment would sit between the enterprise RAG retriever and the
triage LLM. The gateway:

    1. Runs Layer 1 (pattern) on the retrieved context (fail-fast, cheap).
    2. Runs Layer 2 (behavioral drift) by classifying clean vs. suspect
       context (only if Layer 1 gives a medium signal).
    3. Runs Layer 3 (LLM-as-Judge) on the reasoning chain.
    4. Fuses the signals via RiskScorer.
    5. Returns allow / flag / block to the caller.

Run with:
    uvicorn src.gateway:app --host 0.0.0.0 --port 8080
or  python run.py --gateway
"""

import os
import sys
from typing import Dict, Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from fastapi import FastAPI, HTTPException
    from pydantic import BaseModel
except ImportError:
    FastAPI = None
    BaseModel = object
    HTTPException = Exception

from pattern_detector import PatternDetector
from behavioral_detector import BehavioralDetector
from llm_judge import LLMJudge
from risk_scorer import RiskScorer
from llm_client import LLMTriageClient


# ---------------------------------------------------------------------------
# Pydantic request / response models
# ---------------------------------------------------------------------------

if FastAPI is not None:

    class TriageRequest(BaseModel):
        case_title: str
        case_description: str
        context: str                       # possibly poisoned retrieved context
        clean_context: Optional[str] = None  # known-good baseline, if available
        enable_layer2: bool = True
        enable_layer3: bool = True

    class TriageResponse(BaseModel):
        risk_score: float
        risk_band: str
        action: str
        signals: Dict
        triage_decision: Dict
        layer1: Dict
        layer2: Optional[Dict] = None
        layer3: Optional[Dict] = None
        explanation: str


# ---------------------------------------------------------------------------
# Shared singletons
# ---------------------------------------------------------------------------

_llm: Optional[LLMTriageClient] = None
_l1: Optional[PatternDetector] = None
_l2: Optional[BehavioralDetector] = None
_l3: Optional[LLMJudge] = None
_scorer: Optional[RiskScorer] = None


def _get_components():
    """Lazy-init detection components once per process."""
    global _llm, _l1, _l2, _l3, _scorer
    if _llm is None:
        _llm = LLMTriageClient()
        _l1 = PatternDetector()
        _l2 = BehavioralDetector(llm_client=_llm)
        _l3 = LLMJudge(llm_client=_llm)
        _scorer = RiskScorer()
    return _llm, _l1, _l2, _l3, _scorer


def evaluate_request(
    case_title: str,
    case_description: str,
    context: str,
    clean_context: Optional[str] = None,
    enable_layer2: bool = True,
    enable_layer3: bool = True,
) -> Dict:
    """
    Core evaluation pipeline. Usable without FastAPI (unit tests, CLI).
    """
    llm, l1, l2, l3, scorer = _get_components()

    # Layer 1 (cheap)
    l1_result = l1.detect(context)

    # Primary triage decision
    triage = llm.classify_case(case_title, case_description, context)

    # Layer 2 (requires a clean baseline; skipped if none supplied)
    l2_result = None
    if enable_layer2 and clean_context and clean_context != context:
        l2_result = l2.detect_drift(
            case={"title": case_title, "description": case_description},
            clean_context=clean_context,
            poisoned_context=context,
        )

    # Layer 3
    l3_result = None
    if enable_layer3:
        l3_result = l3.judge(case_title, case_description, context, triage)

    # Ensemble
    ens = scorer.score(layer1_result=l1_result, layer2_result=l2_result, layer3_result=l3_result)

    return {
        "risk_score": ens["risk_score"],
        "risk_band": ens["risk_band"],
        "action": ens["action"],
        "signals": ens["signals"],
        "triage_decision": triage,
        "layer1": l1_result,
        "layer2": l2_result,
        "layer3": l3_result,
        "explanation": ens["explanation"],
    }


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

if FastAPI is not None:
    app = FastAPI(
        title="CoT Poisoning Detection Gateway",
        version="1.0.0",
        description="Inline three-layer defense against Chain-of-Thought poisoning in enterprise RAG deployments.",
    )

    @app.get("/health")
    def health():
        return {"status": "ok", "service": "cot-poisoning-gateway"}

    @app.post("/triage", response_model=TriageResponse)
    def triage(req: TriageRequest):
        try:
            return evaluate_request(
                case_title=req.case_title,
                case_description=req.case_description,
                context=req.context,
                clean_context=req.clean_context,
                enable_layer2=req.enable_layer2,
                enable_layer3=req.enable_layer3,
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

else:
    app = None  # FastAPI not installed


def run_gateway(host: str = "0.0.0.0", port: int = 8080):
    """Launch the gateway via uvicorn."""
    if FastAPI is None:
        raise RuntimeError(
            "FastAPI is not installed. Run: pip install fastapi uvicorn pydantic"
        )
    import uvicorn
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    run_gateway()
