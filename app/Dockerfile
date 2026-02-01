FROM python:3.11-slim
WORKDIR /app

RUN apt-get update && apt-get install -y gcc g++ && rm -rf /var/lib/apt/lists/*

# Copy requirements from ROOT (not app/)
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copy the entire esgbackend folder (which contains app/, api/, etc.)
COPY esgbackend /app/esgbackend

# Create uploads directory
RUN mkdir -p /app/uploads

# Change the CMD to point to the correct location
CMD ["sh", "-c", "cd /app/esgbackend && uvicorn app.main:app --host 0.0.0.0 --port $PORT"]