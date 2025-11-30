# Stage 1: Build Frontend
FROM node:18-alpine AS frontend-builder
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# Stage 2: Runtime Backend
FROM python:3.11-slim
WORKDIR /app/backend

# Install dependencies
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend code
COPY backend/ .

# Copy built frontend assets from Stage 1
# We place it in /app/frontend/dist so the backend logic (../frontend/dist) finds it
COPY --from=frontend-builder /app/frontend/dist /app/frontend/dist

# Environment variables
ENV PYTHONUNBUFFERED=1
ENV PORT=8000

# Expose port
EXPOSE 8000

# Run the application
CMD ["sh", "-c", "python update_db_schema.py && uvicorn main:app --host 0.0.0.0 --port 8000"]
