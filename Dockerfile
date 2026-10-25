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
# Rebuild seven reproducible, explicitly synthetic research datasets.
# The normalized_data/ folder is gitignored and does not exist in GitHub.
RUN python 00b_generate_multi_vertical_datasets.py --vertical all \
 && python 00c_generate_additional_datasets.py --vertical all \
 && python -c "from pathlib import Path; names=['pharmacy','grocery','clothing','restaurant','electronics','auto_parts','stationery']; missing=[n for n in names if not (Path('normalized_data/verticals') / n / (n+'_dataset.csv')).is_file()]; assert not missing, 'Missing generated datasets: '+','.join(missing); print('Verified seven bundled research datasets')"
COPY --from=ui /frontend/dist /app/frontend/dist
EXPOSE 10000
CMD ["sh", "-c", "uvicorn api.main:app --host 0.0.0.0 --port ${PORT:-10000}"]
