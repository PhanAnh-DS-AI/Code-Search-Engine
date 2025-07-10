FROM mcr.microsoft.com/azure-functions/python:4-python3.11

# Set the working directory to where Azure Functions expects code
WORKDIR /home/site/wwwroot

# Copy all function app files into the container
COPY . /home/site/wwwroot

RUN if [ -f requirements.txt ]; then pip install -r requirements.txt; fi

# Expose the port Azure Functions runtime listens on
EXPOSE 80
