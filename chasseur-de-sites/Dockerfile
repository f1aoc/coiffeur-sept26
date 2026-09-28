# Chasseur de sites – image Docker (alternative à l'exécutable).
#   docker compose up -d        puis ouvrir http://localhost:8765
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright \
    CHASSEUR_DONNEES=/donnees \
    CHASSEUR_SANDBOX=0

# Bibliothèques de WeasyPrint (PDF) et polices
RUN apt-get update \
 && apt-get install -y --no-install-recommends libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz-subset0 \
      fonts-dejavu-core fonts-liberation \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY pyproject.toml README.md config.yaml signatures.yaml ./
COPY chasseur ./chasseur
RUN pip install --no-cache-dir ".[weasyprint]" \
 && playwright install --with-deps chromium \
 && chmod -R a+rX /ms-playwright

# L'application ne tourne pas en root
RUN useradd --create-home --uid 1000 chasseur && mkdir -p /donnees && chown chasseur /donnees
USER chasseur
VOLUME ["/donnees"]
EXPOSE 8765

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8765/static/icone.svg', timeout=4)"

# Écoute sur toutes les interfaces DU CONTENEUR ; docker-compose ne publie le port que sur 127.0.0.1.
CMD ["chasseur", "web", "--hote", "0.0.0.0", "--port", "8765", "--sans-navigateur"]
