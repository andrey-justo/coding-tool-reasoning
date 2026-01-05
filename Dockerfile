FROM python:3.11-slim

WORKDIR /app

# Copy the rest of the application
COPY . .

RUN pip install poetry

# Install dependencies
RUN poetry install

# Command to run the application
CMD ["python", "src/main.py"]