# Token Usage Audit Dashboard Implementation Plan

1. Add migration 29 and a backend usage-audit module with request context,
   provider/estimated token extraction, safe persistence, and aggregation.
2. Refactor language-model provisioning to attach one per-call audit callback
   while preserving the resolved model and credential identity.
3. Scope authenticated HTTP and SSE work in auth middleware; propagate audit
   identity through source-processing, transformation, KG, and embedding jobs.
4. Add a user-scoped/admin-scoped usage router and response models; register it
   without changing deployment topology.
5. Add frontend API types/hooks, `/usage`, sidebar navigation, responsive charts
   and tables, admin filters, and all nine locale bundles.
6. Add backend/frontend tests, update the customization index, run targeted and
   full validation, then publish and merge a dedicated PR from current `main`.
