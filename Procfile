# Start command for Railway / Render / Heroku.
#
# Runs from backend/ because the API modules import each other by bare name
# (`import core`, `from schemas.optimize import ...`), which requires that
# directory on sys.path. --proxy-headers lets uvicorn resolve the real client
# address behind the platform's proxy; backend/settings.py's TRUST_PROXY_HEADERS
# controls whether the app itself believes X-Forwarded-For.
web: cd backend && uvicorn main_backend:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips='*'
