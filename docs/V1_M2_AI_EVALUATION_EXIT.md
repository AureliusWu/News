# M2 adjusted exit: approved AI evaluation

Decision: 2026-10-01. The user explicitly selected the previously proposed AI evaluation exit and requested continued implementation.

## Engineering exit

M2 is accepted with limitations for matcher `title-summary-v4`. Independent human annotation is no longer an engineering blocker under this adjusted exit. This decision does not create independent human gold labels or establish a formal V1.0.0 release.

Frozen labels: `artifacts/v1-m2-holdout-20261001/review/ai-labels-unseen240.json`.
SHA-256: `3245565e55f999ff2adc43646f3871633e3f2a370b0f6f47e547ea58a9045bc0`.

| Measure | Result |
| --- | --- |
| Reviewed pairs | 240 |
| Scored / uncertain | 238 / 2 |
| TP / FP / FN / TN | 15 / 0 / 15 / 208 |
| Sample precision | 100%, on 15 predicted-positive pairs |
| Sample recall | 50%, on 30 labelled-positive pairs |
| Origin | AI semantic review |
| Independent human gold | No |
| Untouched holdout after tuning | No |

Labels were frozen before initial prediction inspection. The sample was subsequently reused while tuning v4, so it is now a development regression set, not an untouched holdout. It is not population-representative. No labels, event history or aliases were reset to make a gate pass.

The version-bound machine-readable decision is `backend/config/event_quality_gate.json`. A changed matcher requires a new evaluation decision; it must not inherit v4 acceptance automatically.

## Preserved release gates

Seven-day production freshness / scheduled collection, actual deployed candidate smoke, browser cache/PWA upgrade, mobile/device acceptance, capacity and formal release evidence remain separate gates. Historical local tests and one fresh production point are not substitutes.

Previous handoffs that list independent human200 annotation as an unresolved M2 decision are superseded only on this specific exit-method decision. Their test evidence and other caveats remain valid.
