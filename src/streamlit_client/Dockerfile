FROM python:3.11-slim

# Set the working directory
WORKDIR /app

# Copy requirements.txt if present
COPY requirements.txt ./

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the app code
COPY . .

# Expose Streamlit's default port
EXPOSE 8501

# Run Streamlit
CMD ["streamlit", "run", "client.py", "--server.port=8501", "--server.address=0.0.0.0"] 