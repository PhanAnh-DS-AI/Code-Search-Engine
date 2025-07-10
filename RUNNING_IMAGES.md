# Running Backend (BE) and Frontend (FE) Docker Images

This guide explains how to **build** and run your backend (Azure Functions/FastAPI) and frontend (Streamlit) Docker images together, both **locally** and in **Azure**.

---

## 0. Building the Docker Images

Before running the containers, you need to build the Docker images from your project source code.

### **Step 0.1: Build the Backend (BE) Image**

From your project root, run:

```
docker build -f azure-app-functions/function_image.dockerfile -t my-azure-func-app:latest ./azure-app-functions
```
- This uses the Dockerfile at `azure-app-functions/function_image.dockerfile` to build the backend image.

### **Step 0.2: Build the Frontend (FE) Image**

From your project root, run:

```
docker build -t my-streamlit-app:latest ./src/streamlit_client
```
- This uses the Dockerfile at `src/streamlit_client/Dockerfile` to build the frontend image.

---

## 1. Running Locally with Docker

### **Step 1: Run the Backend (BE) Image**

```
docker run -d --name my-backend -p 8080:80 my-azure-func-app:latest
```
- Maps container port 80 to host port 8080.

### **Step 2: Run the Frontend (FE) Image**

```
docker run -d --name my-frontend -p 8501:8501 -e BACKEND_URL="http://localhost:8080" my-streamlit-app:latest
```
- Maps container port 8501 to host port 8501.
- Sets the `BACKEND_URL` environment variable so the frontend can reach the backend.

### **Step 3: Access the Apps**
- **Frontend:** [http://localhost:8501](http://localhost:8501)
- **Backend:** [http://localhost:8080](http://localhost:8080)

---

## 2. Running in Azure (Azure Container Apps)

### **Step 1: Deploy Backend (BE) to Azure Container Apps**
- Deploy your backend image to Azure Container Apps, exposing port 80.
- Note the FQDN (URL) Azure provides (e.g., `https://my-backend-app.<random>.<region>.azurecontainerapps.io`).

### **Step 2: Deploy Frontend (FE) to Azure Container Apps**
- Deploy your frontend image to Azure Container Apps, exposing port 8501.
- Set the environment variable `BACKEND_URL` to the backend's public URL:
  - Example: `https://my-backend-app.<random>.<region>.azurecontainerapps.io`

### **Step 3: Access the Apps**
- **Frontend:** Use the FQDN provided by Azure for your frontend app.
- **Backend:** The frontend will communicate with the backend using the `BACKEND_URL` you set.

---

## 3. Notes
- Make sure your backend allows CORS requests from your frontend domain if needed.
- You can use Azure Portal or Azure CLI to set environment variables and manage deployments.
- For local testing, both containers must be running and accessible on the mapped ports.

---

**Let us know if you need deployment scripts or help with Azure CLI commands!** 