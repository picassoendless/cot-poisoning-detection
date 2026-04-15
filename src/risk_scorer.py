"""
risk_scorer.py

Ensemble Risk Scorer.

Combines signals from all three detection layers into a single risk score
and risk band (low / medium / high) used by the inline gateway to decide
whether to allow, flag, or block a triage response.

Default weights (tunable via config.yaml):
    Layer 1 (pattern)    : 0.25
    Layer 2 (behavioral) : 0.45
    Layer 3 (llm_judge)  : 0.30
"""

from typing import Dict, Optional


DEFAULT_WEIGHTS = {
    "layer1": 0.25,
    "layer2": 0.45,
    "layer3": 0.30,
}

DEFAULT_THRESHOLDS = {
    "medium": 0.35,
    "high": 0.65,
}


class RiskScorer:
    """Ensemble scorer that fuses Layer 1/2/3 results into a risk band."""

    def __init__(
        self,
        weights: Optional[Dict[str, float]] = None,
        thresholds: Optional[Dict[str, float]] = None,
    ):
        self.weights = weights or dict(DEFAULT_WEIGHTS)
        self.thresholds = thresholds or dict(DEFAULT_THRESHOLDS)

    def score(
        self,
        layer1_result: Optional[Dict] = None,
        layer2_result: Optional[Dict] = None,
        layer3_result: Optional[Dict] = None,
    ) -> Dict:
        """
        Compute ensemble risk.

        Args:
            layer1_result: PatternDetector.detect() output
            layer2_result: BehavioralDetector.detect_drift() output
            layer3_result: LLMJudge.judge() output

        Returns:
            {
                "risk_score": float (0.0-1.0),
                "risk_band":  "low" | "medium" | "high",
                "action":     "allow" | "flag" | "block",
                "signals":    {layer1, layer2, layer3},
                "explanation": str
            }
        """

        l1 = self._layer1_risk(layer1_result)
        l2 = self._layer2_risk(layer2_result)
        l3 = self._layer3_risk(layer3_result)

        total_weight = 0.0
        total_risk = 0.0
        if layer1_result is not None:
            total_risk += l1 * self.weights["layer1"]
            total_weight += self.weights["layer1"]
        if layer2_result is not None:
            total_risk += l2 * self.weights["layer2"]
            total_weight += self.weights["layer2"]
        if layer3_result is not None:
            total_risk += l3 * self.weights["layer3"]
            total_weight += self.weights["layer3"]

        risk_score = total_risk / total_weight if total_weight > 0 else 0.0

        if risk_score >= self.thresholds["high"]:
            band, action = "high", "block"
        elif risk_score >= self.thresholds["medium"]:
            band, action = "medium", "flag"
        else:
            band, action = "low", "allow"

        explanation = self._explain(l1, l2, l3, risk_score, band)

        return {
            "risk_score": round(risk_score, 3),
            "risk_band": band,
            "action": action,
            "signals": {
                "layer1": round(l1, 3) if layer1_result is not None else None,
                "layer2": round(l2, 3) if layer2_result is not None else None,
                "layer3": round(l3, 3) if layer3_result is not None else None,
            },
            "explanation": explanation,
        }

    @staticmethod
    def _layer1_risk(r: Optional[Dict]) -> float:
        if not r:
            return 0.0
        return float(r.get("risk_score", 0.0))

    @staticmethod
    def _layer2_risk(r: Optional[Dict]) -> float:
        if not r:
            return 0.0
        base = 0.0
        if r.get("has_drift"):
            base = 0.6
        if r.get("severity_downgrade"):
            base = max(base, 0.85)
        if r.get("escalation_suppressed"):
            base = max(base, 0.95)
        return base

    @staticmethod
    def _layer3_risk(r: Optional[Dict]) -> float:
        if not r:
            return 0.0
        return float(r.get("risk_score", 0.0))

    @staticmethod
    def _explain(l1: float, l2: float, l3: float, score: float, band: str) -> str:
        parts = []
        if l1 > 0:
            parts.append(f"pattern={l1:.2f}")
        if l2 > 0:
            parts.append(f"behavioral={l2:.2f}")
        if l3 > 0:
            parts.append(f"judge={l3:.2f}")
        if not parts:
            return f"No risk signals. score={score:.2f} band={band}"
        return f"Risk {band.upper()} (score={score:.2f}); signals: " + ", ".join(parts)


def test_risk_scorer():
    """Smoke test."""

    scorer = RiskScorer()

    clean = scorer.score(
        layer1_result={"has_poison": False, "risk_score": 0.0, "matched_patterns": []},
        layer2_result={"has_drift": False, "severity_downgrade": False, "escalation_suppressed": False},
        layer3_result={"poisoned": False, "confidence": 0.9, "risk_score": 0.05},
    )

    poisoned = scorer.score(
        layer1_result={"has_poison": True, "risk_score": 0.8, "matched_patterns": ["deescalation_bias", "statistical_manipulation"]},
        layer2_result={"has_drift": True, "severity_downgrade": True, "escalation_suppressed": True},
        layer3_result={"poisoned": True, "confidence": 0.9, "risk_score": 0.9},
    )

    print("=" * 60)
    print("RISK SCORER TEST")
    print("=" * 60)
    print("Clean case:")
    print(f"  score={clean['risk_score']}  band={clean['risk_band']}  action={clean['action']}")
    print(f"  {clean['explanation']}")

    print("\nPoisoned case:")
    print(f"  score={poisoned['risk_score']}  band={poisoned['risk_band']}  action={poisoned['action']}")
    print(f"  {poisoned['explanation']}")

    if clean["risk_band"] == "low" and poisoned["risk_band"] == "high":
        print("\n>> PASS")
    else:
        print("\n>> FAIL")


if __name__ == "__main__":
    test_risk_scorer()
