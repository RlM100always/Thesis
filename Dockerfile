FROM node:22-alpine AS ui
WORKDIR /frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.render.txt ./
RUN pip install --no-cache-dir -r requirements.render.txt
COPY . .
COPY --from=ui /frontend/dist /app/frontend/dist
EXPOSE 10000
CMD ["sh", "-c", "uvicorn api.main:app --host 0.0.0.0 --port ${PORT:-10000}"]
