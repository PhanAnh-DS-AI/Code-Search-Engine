from elasticsearch import Elasticsearch
from dotenv import load_dotenv
import os

# Load biến môi trường từ file .env
load_dotenv()

# Lấy thông tin từ .env
ES_CLOUD_ID = os.getenv("ES_CLOUD_ID")
ES_USER = os.getenv("ES_USER")
ES_PASSWORD = os.getenv("ES_PASSWORD")


# Tạo client
client = Elasticsearch(
    cloud_id=ES_CLOUD_ID,
    basic_auth=(ES_USER, ES_PASSWORD),

)
client.info()

# print("Cloud ID:", ES_CLOUD_ID)
# print("User:", ES_USER)
# print("Password:", ES_PASSWORD)

# INDEX_NAME = "search-eg5w"
# INDEX_CONFIG = {}
