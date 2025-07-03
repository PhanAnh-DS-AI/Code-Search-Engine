from sentence_transformers import SentenceTransformer
model = SentenceTransformer("BAAI/bge-large-en-v1.5")
print("Encoding is " + str(model.encode("test")))

