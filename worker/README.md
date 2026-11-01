# Phone activation worker (Cloudflare, free plan)
1. Workers & Pages > KV > Create a namespace named `91tv-pair`.
2. Workers & Pages > Create > Worker, name it `ninetyone-pair`, paste `worker.js`, Deploy.
3. Worker > Settings > Bindings > Add > KV namespace: variable name `PAIR`, namespace `91tv-pair`.
4. Copy the worker address (https://ninetyone-pair.<account>.workers.dev) into `docs/activate/index.html` (API) and `Lic.kt` (PAIR_API).
