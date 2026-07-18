FROM python:3.10-slim

# Set Working Directory
WORKDIR /app

# Install Dependencies
# Copying requirements first to leverage Docker cache
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy Application Code
COPY . .

# Set Environment Variables
ENV FLASK_ENV=production
ENV PYTHONUNBUFFERED=1
ENV PORT=5000

# Expose Port
EXPOSE 5000

# Define Startup Command
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "app:app"]
