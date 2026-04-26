.PHONY: help install dev web server build clean

help:
	@echo "TechEurope — Big Berlin Hack 2026 (Qontext track)"
	@echo ""
	@echo "Targets:"
	@echo "  make install     Install web + server dependencies"
	@echo "  make dev         Run web (Vite) + server (FastAPI) concurrently"
	@echo "  make web         Run only the Vite dev server (port 5173)"
	@echo "  make server      Run only the FastAPI dev server (port 8000)"
	@echo "  make build       Production build of the frontend"
	@echo "  make clean       Remove build artifacts and caches"

install:
	cd web && npm install
	cd server && uv sync

dev:
	@echo "Starting via ./dev.sh (kills occupied ports first)."
	@./dev.sh

web:
	cd web && npm run dev

server:
	cd server && uv run server

build:
	cd web && npm run build

clean:
	rm -rf web/dist web/node_modules/.vite
	rm -rf server/.venv server/dist server/.pytest_cache server/.ruff_cache
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
