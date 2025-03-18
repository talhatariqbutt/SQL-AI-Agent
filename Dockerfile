# Use an official Python image as base
FROM python:3.10

# Set the working directory inside the container
WORKDIR /app

# Copy only requirements first to leverage Docker caching
COPY requirements.txt /app/

# Install system dependencies for MSSQL
RUN apt-get update && apt-get install -y \
    unixodbc \
    unixodbc-dev \
    gcc \
    g++ \
    libpq-dev \
    freetds-dev \
    freetds-bin \
    tdsodbc \
    && rm -rf /var/lib/apt/lists/*

# Install ODBC Driver 17
RUN apt-get update && apt-get install -y curl apt-transport-https gnupg && \
    curl https://packages.microsoft.com/keys/microsoft.asc | apt-key add - && \
    echo "deb [arch=amd64] https://packages.microsoft.com/debian/10/prod buster main" > /etc/apt/sources.list.d/mssql-release.list && \
    apt-get update && ACCEPT_EULA=Y apt-get install -y msodbcsql17 unixodbc-dev

# Install Python dependencies
RUN pip install --no-cache-dir -v -r requirements.txt

# Copy the rest of the project files
COPY . /app

# Expose port for Django
EXPOSE 8000

# Set environment variables for Django
ENV PYTHONUNBUFFERED=1

# Run migrations and start Gunicorn
ENTRYPOINT ["sh", "-c", "python manage.py migrate && gunicorn agent.wsgi:application --bind 0.0.0.0:8000"]
