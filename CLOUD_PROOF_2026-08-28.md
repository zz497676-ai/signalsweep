# SignalSweep Cloud Proof — 2026-08-28

This note records a read-only verification of the deployed Google Cloud service. It contains no credentials, tokens, coupon codes, or account details.

## Verified deployment

- Service: `signalsweep-agent`
- Region: `us-central1`
- Status: `Ready=True`, `ConfigurationsReady=True`, `RoutesReady=True`
- Cloud Run URL: `https://signalsweep-agent-5omgubz3cq-uc.a.run.app`
- Service-level maximum scale: `1`
- Runtime label: `created-by: adk`
- The service is private; requests require Google Cloud authentication.

## What to show in the demo

1. Cloud Run service name and `Ready` status.
2. The service URL and region.
3. The service-level maximum instance setting of `1` as the cost guard.
4. Return to SignalSweep and show the Gemini model/tool trace.

## Recheck command

```bash
gcloud run services describe signalsweep-agent \
  --region=us-central1 \
  --format='yaml(metadata.name,status.url,status.conditions,metadata.annotations)'
```
