FROM node:20-alpine AS front
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./
RUN npm install
COPY frontend/ ./
RUN npm run build

FROM python:3.11-slim
WORKDIR /srv
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ ./
COPY --from=front /build/dist ./static
ENV STATIC_DIR=/srv/static UPLOAD_DIR=/srv/uploads
EXPOSE 13000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "13000"]
