# Blue-Green Deployment System — Student Portal

A working local blue-green deployment demo: a Flask "Student Portal" app,
containerized, running as two live instances (**blue** and **green**) behind
Nginx, with health checks, Prometheus/Grafana monitoring, a Jenkins CI/CD
pipeline, and Kubernetes manifests for the next step up.

## What's actually runnable right now (just needs Docker)

- Flask app: login, register, dashboard, attendance, assignments, profile, admin panel
- Postgres database + Redis cache
- Nginx reverse proxy that can flip live traffic between blue/green with **zero downtime**
- `scripts/switch.sh` — health-checks the target color, then switches, with automatic abort if unhealthy
- Prometheus scraping both app instances + Grafana for dashboards
- Jenkins pipeline definition (`jenkins/Jenkinsfile`) ready to point at this repo
- Pytest test suite

## What's included as manifests/config but needs extra infrastructure

- `k8s/` — Kubernetes manifests. These need a real cluster (minikube, kind, or
  a cloud provider) to apply; they won't run from docker-compose alone.
- Cloud deployment (AWS/Azure/GCP), ELK logging stack, and Istio service mesh
  are described in the original roadmap doc but are genuinely separate,
  larger projects — standing them up means provisioning real cloud
  infrastructure, which isn't something a zip file can do. The `k8s/` folder
  is the on-ramp to that when you're ready.

---

## 1. Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (includes Docker Compose) — you said you already have this
- [VS Code](https://code.visualstudio.com/) with the **Docker** and **Python** extensions (recommended, not required)
- Git (optional, only needed if you want to push this to GitHub for the Jenkins/webhook part)

You do **not** need Python installed locally — everything runs inside containers.

## 2. Run it

```bash
# unzip the project, then from the project root:
docker compose up --build
```

First run will take a minute or two to build images and pull Postgres/Redis/Prometheus/Grafana.

Once it's up:

| What | URL |
|---|---|
| App (via Nginx, "production" entry point) | http://localhost:8080 |
| Blue directly (debug) | http://localhost:8081 |
| Green directly (debug) | http://localhost:8082 |
| Prometheus | http://localhost:9090 |
| Grafana (login admin/admin) | http://localhost:3000 |

Demo login: `admin@example.com` / `admin123` (auto-created on first run), or register your own account at `/register`.

## 3. Try the blue-green switch

Open http://localhost:8080 — notice the badge in the navbar says **BLUE v1.0.0**.

In another terminal:

```bash
chmod +x scripts/switch.sh   # first time only
./scripts/switch.sh green
```

Refresh http://localhost:8080 — it now says **GREEN v1.1.0**, with no downtime
and no dropped requests. Run `./scripts/switch.sh blue` to switch back.

If the target color isn't healthy, the script aborts and leaves traffic
exactly where it was — that's the automatic-rollback-on-failed-deploy
behavior from the roadmap doc, implemented for real.

## 4. Run the tests

```bash
docker compose exec backend-blue pytest ../tests -v
```

(or install `backend/requirements.txt` into a local venv and run `pytest tests/` if you prefer running outside Docker)

## 5. Try the CI/CD pipeline (optional)

```bash
docker compose -f jenkins/docker-compose.jenkins.yml up -d
```

Open http://localhost:8090, finish the Jenkins setup wizard (it'll show you
how to get the initial admin password from the container logs), then create
a Pipeline job pointing at this repo with script path `jenkins/Jenkinsfile`.
Push this project to a GitHub repo first and add a webhook so pushes
auto-trigger builds.

## 6. Growing into Kubernetes / cloud (next steps, not included as running code)

1. Install `kubectl` and either `minikube` or `kind` for a local cluster.
2. Push your image to Docker Hub or GitHub Container Registry (the Jenkinsfile already does this).
3. `kubectl apply -f k8s/` — creates blue/green Deployments, a Service, an Ingress, and an HPA.
4. To switch traffic in K8s: `kubectl patch service student-portal -p '{"spec":{"selector":{"color":"green"}}}'`
5. For a cloud provider (AWS EKS / Azure AKS / GCP GKE), the manifests are the
   same — only the cluster creation step differs, and each provider has its
   own free tutorial for that (search "\<provider\> EKS/AKS/GKE quickstart").

## Project structure

```
blue-green-system/
├── backend/              Flask app (source of truth for both blue & green images)
├── nginx/                Reverse proxy + the active_upstream.conf that gets switched
├── scripts/switch.sh     Blue-green traffic switcher with health check + auto-abort
├── monitoring/           Prometheus config (Grafana runs with defaults)
├── jenkins/              Jenkinsfile + a compose file to run Jenkins itself
├── k8s/                  Kubernetes manifests (needs a real cluster)
├── tests/                Pytest suite
└── docker-compose.yml    Runs the whole local stack
```

## Troubleshooting

- **Port already in use**: something else on your machine is using 8080/5432/6379/9090/3000 — edit the `ports:` mappings in `docker-compose.yml`.
- **`switch.sh` says "command not found" on Windows**: run it from Git Bash or WSL, not PowerShell/cmd — it's a bash script.
- **Changes to `backend/` not showing up**: run `docker compose up --build` again (or add a bind mount + `--reload` for live dev; ask if you want that wired in).
