FROM python:3.12-slim

WORKDIR /app

COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt

COPY backend /app/backend
COPY frontend /app/frontend
COPY render_app.py /app/render_app.py

# For Render, the UI and API share one origin. Keep localhost behavior unchanged in source.
RUN sed -i "s#const API='http://localhost:8000';#const API=location.origin + '/api';#" /app/frontend/index.html

ENV PORT=10000
EXPOSE 10000

CMD ["sh", "-c", "uvicorn render_app:app --host 0.0.0.0 --port ${PORT:-10000}"]
