"""
risk_scorer.py

Ensemble Risk Scorer — v2, tiered OR logic.

Defence-in-depth principle:
    If ANY layer raises an alarm, the system acts on it.
    Multiple layers agreeing upgrades the severity.

Tiered logic:
    ┌────────────────────────────────────────┬────────────┬────────┐
    │ Condition                              │ Risk band  │ Action │
    ├────────────────────────────────────────┼────────────┼────────┤
    │ No layer fires                         │ low        │ allow  │
    │ L1 fires only (pattern match)          │ medium     │ flag   │
    │ L2 fires only (drift detected)         │ medium     │ flag   │
    │ L3 fires only (judge flags)            │ medium     │ flag   │
    │ L1 + L2  agree                         │ high       │ block  │
    │ L1 + L3  agree                         │ high       │ block  │
    │ L2 + L3  agree                         │ high       │ block  │
    │ All three agree                        │ high       │ block  │
    └────────────────────────────────────────┴────────────┴────────┘

Why this beats weighted average:
    Weighted average requires ALL layers to contribute positively.
    When L2 and L3 return 0 (they didn't detect anything), they drag
    the ensemble score below the threshold even when L1 is shouting.
    OR logic treats each layer as an independent witness — one witness
    is enough to flag, two or more witnesses block.

Numeric risk score is still computed for reporting and threshold tuning,
but the band decision uses the tiered logic above.
"""

from typing import Dict, Optional


class RiskScorer:
    """Ensemble scorer using tiered OR logic for defence-in-depth."""

    def score(
        self,
        layer1_result: Optional[Dict] = None,
        layer2_result: Optional[Dict] = None,
        layer3_result: Optional[Dict] = None,
    ) -> Dict:
        """
        Compute ensemble risk from up to three layer signals.

        Args:
            layer1_result: PatternDetector.detect() output
            layer2_result: BehavioralDetector.detect_drift() output
            layer3_result: LLMJudge.judge() output

        Returns:
            {
                "risk_score":  float (0.0-1.0),
                "risk_band":   "low" | "medium" | "high",
                "action":      "allow" | "flag" | "block",
                "signals":     {layer1, layer2, layer3},
                "layers_fired": [list of firing layer names],
                "explanation": str
            }
        """

        # --- per-layer binary fire decision ---
        l1_fires = bool(layer1_result and layer1_result.get('has_poison', False))
        l2_fires = bool(layer2_result and layer2_result.get('has_drift', False))
        l3_fires = bool(layer3_result and layer3_result.get('poisoned', False))

        layers_fired = (
            (['layer1'] if l1_fires else []) +
            (['layer2'] if l2_fires else []) +
            (['layer3'] if l3_fires else [])
        )
        n_fired = len(layers_fired)

        # --- tiered band decision (OR logic) ---
        if n_fired == 0:
            band, action = 'low', 'allow'
        elif n_fired == 1:
            band, action = 'medium', 'flag'
        else:
            # 2 or more layers agree → block
            band, action = 'high', 'block'

        # --- numeric score for reporting (capped per band) ---
        l1_num = float((layer1_result or {}).get('risk_score', 0.0))
        l2_num = self._l2_num(layer2_result)
        l3_num = float((layer3_result or {}).get('risk_score', 0.0))

        # Weighted numeric, but floored by band so it's consistent with the decision
        raw = (l1_num * 0.25) + (l2_num * 0.45) + (l3_num * 0.30)
        if band == 'low':
            risk_score = min(raw, 0.34)
        elif band == 'medium':
            risk_score = max(min(raw, 0.64), 0.35)
        else:
            risk_score = max(raw, 0.65)

        explanation = self._explain(layers_fired, risk_score, band, l1_num, l2_num, l3_num)

        return {
            'risk_score':   round(risk_score, 3),
            'risk_band':    band,
            'action':       action,
            'signals': {
                'layer1': round(l1_num, 3) if layer1_result is not None else None,
                'layer2': round(l2_num, 3) if layer2_result is not None else None,
                'layer3': round(l3_num, 3) if layer3_result is not None else None,
            },
            'layers_fired': layers_fired,
            'explanation':  explanation,
        }

    @staticmethod
    def _l2_num(r: Optional[Dict]) -> float:
        if not r:
            return 0.0
        if r.get('escalation_suppressed'):
            return 0.95
        if r.get('severity_downgrade'):
            return 0.85
        if r.get('has_drift'):
            return 0.60
        return 0.0

    @staticmethod
    def _explain(fired, score, band, l1, l2, l3) -> str:
        if not fired:
            return f'No signals detected. score={score:.2f} band={band}'
        parts = []
        if l1 > 0:
            parts.append(f'pattern={l1:.2f}')
        if l2 > 0:
            parts.append(f'behavioral={l2:.2f}')
        if l3 > 0:
            parts.append(f'judge={l3:.2f}')
        return (
            f'Risk {band.upper()} (score={score:.2f}) — '
            f'{len(fired)} layer(s) fired: {", ".join(fired)}. '
            f'Signals: {", ".join(parts)}'
        )


def test_risk_scorer():
    scorer = RiskScorer()

    cases = [
        ("All clean",        None,  None,  None,   False, False, False),
        ("L1 only",          0.80,  None,  None,   True,  False, False),
        ("L2 only",          None,  True,  None,   False, True,  False),
        ("L3 only",          None,  None,  True,   False, False, True),
        ("L1 + L2",          0.80,  True,  None,   True,  True,  False),
        ("L1 + L3",          0.80,  None,  True,   True,  False, True),
        ("L2 + L3",          None,  True,  True,   False, True,  True),
        ("All three",        0.80,  True,  True,   True,  True,  True),
    ]

    print("=" * 60)
    print("RISK SCORER v2 TEST (tiered OR logic)")
    print("=" * 60)

    all_pass = True
    for name, l1_score, l2_drift, l3_poison, exp_l1, exp_l2, exp_l3 in cases:
        l1 = {'has_poison': exp_l1, 'risk_score': l1_score or 0.0} if exp_l1 or l1_score is not None else None
        l2 = {'has_drift': exp_l2, 'severity_downgrade': False, 'escalation_suppressed': False} if l2_drift is not None else None
        l3 = {'poisoned': exp_l3, 'confidence': 0.9, 'risk_score': 0.9 if exp_l3 else 0.05} if l3_poison is not None else None

        r = scorer.score(l1, l2, l3)
        n = sum([exp_l1, exp_l2, exp_l3])
        expected_band = 'low' if n == 0 else ('medium' if n == 1 else 'high')
        ok = r['risk_band'] == expected_band
        if not ok:
            all_pass = False
        print(f"  {name:20s}  fired={len(r['layers_fired'])}  "
              f"band={r['risk_band']:6s}  score={r['risk_score']:.2f}  "
              f"{'PASS' if ok else 'FAIL'}")

    print()
    print(">> PASS" if all_pass else ">> FAIL - check cases above")


if __name__ == "__main__":
    test_risk_scorer()
