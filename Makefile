.PHONY: run frontend frontend-test-bib check ruff database lint api start-all stop-all status clean-cache worker worker-start worker-stop worker-restart
.PHONY: docker-buildx-prepare docker-buildx-clean docker-buildx-reset
.PHONY: docker-push docker-push-latest docker-release docker-build-local tag export-docs
.PHONY: parallel-up parallel-down parallel-status

# Get version from pyproject.toml
VERSION := $(shell python -c "import tomllib; print(tomllib.load(open('pyproject.toml', 'rb'))['project']['version'])")

# Image names for both registries
DOCKERHUB_IMAGE := lfnovo/open_notebook
GHCR_IMAGE := ghcr.io/lfnovo/open-notebook

# Build platforms
PLATFORMS := linux/amd64,linux/arm64

database:
	docker run -d --name surrealdb-v2 \
		-p 8001:8000 \
		-v ./surreal_data_v2:/mydata \
		-e SURREAL_EXPERIMENTAL_GRAPHQL=true \
		surrealdb/surrealdb:v2 \
		start --log info --user root --pass root rocksdb:/mydata/mydatabase.db

run:
	@echo "⚠️  Warning: Starting frontend only. For full functionality, use 'make start-all'"
	cd frontend && API_URL=http://localhost:5056 INTERNAL_API_URL=http://localhost:5056 npm run dev -- -H 0.0.0.0 -p 3001

frontend:
	cd frontend && API_URL=http://localhost:5056 INTERNAL_API_URL=http://localhost:5056 npm run dev -- -H 0.0.0.0 -p 3001

# Verify 参考文献 auto-numbering (run on your machine; requires Node/npm in PATH)
frontend-test-bib:
	cd frontend && npm run test -- --run src/lib/utils/source-references.bibliography.test.ts

lint:
	uv run python -m mypy .

ruff:
	ruff check . --fix

# === Docker Build Setup ===
docker-buildx-prepare:
	@docker buildx inspect multi-platform-builder >/dev/null 2>&1 || \
		docker buildx create --use --name multi-platform-builder --driver docker-container
	@docker buildx use multi-platform-builder

docker-buildx-clean:
	@echo "🧹 Cleaning up buildx builders..."
	@docker buildx rm multi-platform-builder 2>/dev/null || true
	@docker ps -a | grep buildx_buildkit | awk '{print $$1}' | xargs -r docker rm -f 2>/dev/null || true
	@echo "✅ Buildx cleanup complete!"

docker-buildx-reset: docker-buildx-clean docker-buildx-prepare
	@echo "✅ Buildx reset complete!"

# === Docker Build Targets ===

# Build production image for local platform only (no push)
docker-build-local:
	@echo "🔨 Building production image locally ($(shell uname -m))..."
	docker build \
		-t $(DOCKERHUB_IMAGE):$(VERSION) \
		-t $(DOCKERHUB_IMAGE):local \
		.
	@echo "✅ Built $(DOCKERHUB_IMAGE):$(VERSION) and $(DOCKERHUB_IMAGE):local"
	@echo "Run with: docker run -p 5056:5055 -p 3001:3000 $(DOCKERHUB_IMAGE):local"

# Build and push version tags ONLY (no latest) for both regular and single images
docker-push: docker-buildx-prepare
	@echo "📤 Building and pushing version $(VERSION) to both registries..."
	@echo "🔨 Building regular image..."
	docker buildx build --pull \
		--platform $(PLATFORMS) \
		--progress=plain \
		-t $(DOCKERHUB_IMAGE):$(VERSION) \
		-t $(GHCR_IMAGE):$(VERSION) \
		--push \
		.
	@echo "🔨 Building single-container image..."
	docker buildx build --pull \
		--platform $(PLATFORMS) \
		--progress=plain \
		-f Dockerfile.single \
		-t $(DOCKERHUB_IMAGE):$(VERSION)-single \
		-t $(GHCR_IMAGE):$(VERSION)-single \
		--push \
		.
	@echo "✅ Pushed version $(VERSION) to both registries (latest NOT updated)"
	@echo "  📦 Docker Hub:"
	@echo "    - $(DOCKERHUB_IMAGE):$(VERSION)"
	@echo "    - $(DOCKERHUB_IMAGE):$(VERSION)-single"
	@echo "  📦 GHCR:"
	@echo "    - $(GHCR_IMAGE):$(VERSION)"
	@echo "    - $(GHCR_IMAGE):$(VERSION)-single"

# Update v1-latest tags to current version (both regular and single images)
docker-push-latest: docker-buildx-prepare
	@echo "📤 Updating v1-latest tags to version $(VERSION)..."
	@echo "🔨 Building regular image with latest tag..."
	docker buildx build --pull \
		--platform $(PLATFORMS) \
		--progress=plain \
		-t $(DOCKERHUB_IMAGE):$(VERSION) \
		-t $(DOCKERHUB_IMAGE):v1-latest \
		-t $(GHCR_IMAGE):$(VERSION) \
		-t $(GHCR_IMAGE):v1-latest \
		--push \
		.
	@echo "🔨 Building single-container image with latest tag..."
	docker buildx build --pull \
		--platform $(PLATFORMS) \
		--progress=plain \
		-f Dockerfile.single \
		-t $(DOCKERHUB_IMAGE):$(VERSION)-single \
		-t $(DOCKERHUB_IMAGE):v1-latest-single \
		-t $(GHCR_IMAGE):$(VERSION)-single \
		-t $(GHCR_IMAGE):v1-latest-single \
		--push \
		.
	@echo "✅ Updated v1-latest to version $(VERSION)"
	@echo "  📦 Docker Hub:"
	@echo "    - $(DOCKERHUB_IMAGE):$(VERSION) → v1-latest"
	@echo "    - $(DOCKERHUB_IMAGE):$(VERSION)-single → v1-latest-single"
	@echo "  📦 GHCR:"
	@echo "    - $(GHCR_IMAGE):$(VERSION) → v1-latest"
	@echo "    - $(GHCR_IMAGE):$(VERSION)-single → v1-latest-single"

# Full release: push version AND update latest tags
docker-release: docker-push-latest
	@echo "✅ Full release complete for version $(VERSION)"

tag:
	@version=$$(grep '^version = ' pyproject.toml | sed 's/version = "\(.*\)"/\1/'); \
	echo "Creating tag v$$version"; \
	git tag "v$$version"; \
	git push origin "v$$version"


dev:
	docker compose -f docker-compose.dev.yml up --build 

full:
	docker compose -f docker-compose.full.yml up --build 


api:
	LOG_SERVICE=api uv run --env-file .env run_api.py

.PHONY: worker worker-start worker-stop worker-restart

worker: worker-start

worker-start:
	@echo "Starting surreal-commands worker..."
	LOG_SERVICE=worker uv run --env-file .env surreal-commands-worker --import-modules commands

worker-stop:
	@echo "Stopping surreal-commands worker..."
	pkill -f "surreal-commands-worker" || true

worker-restart: worker-stop
	@python -c "import time; time.sleep(2)"
	@$(MAKE) worker-start

# === Service Management ===
start-all:
	@echo "🚀 Starting Lumiton·Omax v2 (Database + API + Worker + Frontend)..."
	@echo "📊 Starting SurrealDB (port 8001)..."
	@docker run -d --name surrealdb-v2 \
		-p 8001:8000 \
		-v ./surreal_data_v2:/mydata \
		-e SURREAL_EXPERIMENTAL_GRAPHQL=true \
		surrealdb/surrealdb:v2 \
		start --log info --user root --pass root rocksdb:/mydata/mydatabase.db 2>/dev/null || docker start surrealdb-v2
	@python -c "import time; time.sleep(3)"
	@mkdir -p logs
	@echo ""
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@echo "  DB     8001 → logs/surrealdb.log"
	@echo "  API    :5056 → logs/api.log"
	@echo "  Worker       → logs/worker.log"
	@echo "  Web    :3001 → logs/frontend.log"
	@echo "  Ctrl+C stops all"
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@echo ""
	@trap 'kill 0; exit 0' INT TERM; \
	docker logs -f surrealdb-v2 2>&1 | tee logs/surrealdb.log | while IFS= read -r line; do printf '\033[35m[ DB]\033[0m %s\n' "$$line"; done & \
	LOG_SERVICE=api uv run run_api.py 2>&1 | while IFS= read -r line; do printf '\033[34m[API]\033[0m %s\n' "$$line"; done & \
	LOG_SERVICE=worker uv run --env-file .env surreal-commands-worker --import-modules commands 2>&1 | while IFS= read -r line; do printf '\033[33m[WRK]\033[0m %s\n' "$$line"; done & \
	(cd frontend && API_URL=http://localhost:5056 INTERNAL_API_URL=http://localhost:5056 npm run dev -- -H 0.0.0.0 -p 3001) 2>&1 | tee logs/frontend.log | while IFS= read -r line; do printf '\033[32m[WEB]\033[0m %s\n' "$$line"; done & \
	wait

stop-all:
	@echo "🛑 Stopping all Lumiton·Omax v2 services..."
	@pkill -f "next dev" || true
	@pkill -f "node .next/standalone/server.js" || true
	@pkill -f "surreal-commands-worker" || true
	@pkill -f "run_api.py" || true
	@pkill -f "uvicorn api.main:app" || true
	@pkill -f "docker logs.*surrealdb-v2" || true
	@docker stop surrealdb-v2 2>/dev/null || true
	@echo "✅ All services stopped!"

status:
	@echo "📊 Lumiton·Omax v2 Service Status:"
	@echo "Database (SurrealDB port 8001):"
	@docker ps --filter name=surrealdb-v2 --format "  ✅ Running" 2>/dev/null || echo "  ❌ Not running"
	@echo "API Backend (port 5056):"
	@pgrep -f "run_api.py\|uvicorn api.main:app" >/dev/null && echo "  ✅ Running" || echo "  ❌ Not running"
	@echo "Background Worker:"
	@pgrep -f "surreal-commands-worker" >/dev/null && echo "  ✅ Running" || echo "  ❌ Not running"
	@echo "Next.js Frontend (port 3001):"
	@pgrep -f "next dev" >/dev/null && echo "  ✅ Running" || echo "  ❌ Not running"

# === Documentation Export ===
export-docs:
	@echo "📚 Exporting documentation..."
	@uv run python scripts/export_docs.py
	@echo "✅ Documentation export complete!"

# === Cleanup ===
clean-cache:
	@echo "🧹 Cleaning cache directories..."
	@find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
	@find . -name ".mypy_cache" -type d -exec rm -rf {} + 2>/dev/null || true
	@find . -name ".ruff_cache" -type d -exec rm -rf {} + 2>/dev/null || true
	@find . -name ".pytest_cache" -type d -exec rm -rf {} + 2>/dev/null || true
	@find . -name "*.pyc" -type f -delete 2>/dev/null || true
	@find . -name "*.pyo" -type f -delete 2>/dev/null || true
	@find . -name "*.pyd" -type f -delete 2>/dev/null || true
	@echo "✅ Cache directories cleaned!"

# === Parallel Deployment (v2 alongside legacy) ===
parallel-up:
	@echo "🚀 Starting Lumiton·Omax v2 (parallel instance)..."
	docker compose -f docker-compose.parallel.yml --env-file .env.parallel up -d
	@echo "✅ v2 is running on:"
	@echo "   Frontend: http://localhost:8503"
	@echo "   API:      http://localhost:5056/docs"
	@echo "   SurrealDB: ws://localhost:8001/rpc"

parallel-down:
	@echo "🛑 Stopping Lumiton·Omax v2..."
	docker compose -f docker-compose.parallel.yml --env-file .env.parallel down

parallel-status:
	docker compose -f docker-compose.parallel.yml --env-file .env.parallel ps
