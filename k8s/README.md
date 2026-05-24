# Kubernetes — credit-default-api

Helm chart that deploys the FastAPI scoring service with everything a
production team would expect: HPA, PDB, NetworkPolicy, ServiceAccount,
ServiceMonitor, configurable init container for model fetching, and TLS-ready
Ingress.

## Layout

```
k8s/
  helm/credit-default-api/      Helm chart (this is the deploy unit)
    Chart.yaml
    values.yaml                 default values
    values-prod.yaml            production overrides
    templates/
      _helpers.tpl
      deployment.yaml           Deployment + initContainers + probes + securityContext
      service.yaml              ClusterIP
      ingress.yaml              optional nginx + cert-manager
      configmap.yaml            non-secret config (LOG_LEVEL, MODEL_VERSION, ...)
      secret.yaml               only rendered when .Values.secrets is non-empty
      hpa.yaml                  HPA v2 with CPU + memory targets
      pdb.yaml                  PodDisruptionBudget
      networkpolicy.yaml        ingress from ingress-nginx only; egress to DNS + 443
      serviceaccount.yaml       IRSA-ready annotations
      servicemonitor.yaml       Prometheus Operator (optional)
      NOTES.txt                 printed after install
  argocd-application.yaml       GitOps Application for Argo CD
```

## Local smoke (kind + Docker Desktop)

```bash
# 1) ensure Kubernetes is enabled in Docker Desktop, OR create a kind cluster:
kind create cluster --name credit-default

# 2) build the image locally and load it into kind
docker build -f docker/Dockerfile.api -t loan-default-api:dev .
kind load docker-image loan-default-api:dev --name credit-default

# 3) lint the chart
helm lint k8s/helm/credit-default-api

# 4) install
helm upgrade --install credit-default-api k8s/helm/credit-default-api \
  -n credit-default --create-namespace \
  --set image.repository=loan-default-api \
  --set image.tag=dev \
  --set image.pullPolicy=Never

# 5) port-forward + curl
kubectl -n credit-default port-forward svc/credit-default-api 8000:80
curl http://localhost:8000/health
```

## Production (EKS, GitOps)

1. Provision the EKS cluster + IRSA role with the Phase 5 Terraform.
2. Install Argo CD in the cluster (out of scope here).
3. Apply `argocd-application.yaml`:
   ```bash
   kubectl apply -n argocd -f k8s/argocd-application.yaml
   ```
4. Every push to `main` rebuilds the image (via `build-deploy.yml`), updates
   `values-prod.yaml` with the new `image.tag`, and Argo CD rolls it out.

## Model loading strategies

| Mode | When to use | How to enable |
| --- | --- | --- |
| Baked into image | One artifact per image version, immutable | Modify `docker/Dockerfile.api` to `COPY models/ /app/models` at build time |
| `modelInit` initContainer | Decouple image build from model promotion | Set `modelInit.enabled=true` + `modelInit.modelUri=s3://...` + IRSA role on the SA |
| PVC + sidecar sync | When you want a shared model cache | Custom — not provided here |

Default is empty `models/` volume → pod fails health check unless one of the
above is configured.

## Security posture

- Non-root container, no privilege escalation, all capabilities dropped.
- NetworkPolicy denies all by default; explicitly allows ingress only from
  `ingress-nginx` namespace and egress to DNS + HTTPS.
- Secrets rendered as a Kubernetes Secret only when explicitly set; production
  should use External Secrets Operator pulling from AWS Secrets Manager.
