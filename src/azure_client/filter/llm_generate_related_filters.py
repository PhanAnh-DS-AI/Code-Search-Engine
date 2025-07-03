from groq import Groq
import os
import sys
from dotenv import load_dotenv

# Load environment variables
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
load_dotenv()

Groq_key = os.getenv('GROQ_KEY')
if not Groq_key:
    raise ValueError("GROQ_KEY environment variable not set")

# Initialize Groq client
client = Groq(api_key=Groq_key)

def filter_categories(user_query):
    response = client.chat.completions.create(
        model="llama3-8b-8192",
        messages=[
            {
                "role": "system",
                "content": '''You are an expert AI assistant helping to improve search relevance. 
When given a user query, generate a list of relevant search filter terms. 
These terms can include related topics, keywords, sections, tags, or synonyms that match the user's intent. 
Do not repeat the original query. Return 5 concise phrases in a Python list format like ["term1", "term2", ...] with no additional text.'''
            },
            {
                "role": "user",
                "content": f'User query: {user_query}'
            }
        ],
        temperature=0.7,
        max_tokens=256,
        top_p=0.95,
        stream=True,
    )

    # Accumulate full output text from streamed chunks
    full_text = ""
    for chunk in response:
        content_piece = chunk.choices[0].delta.content
        if content_piece:
            full_text += content_piece

    # Evaluate the output string into a Python list
    try:
        filters = eval(full_text.strip())
        return filters if isinstance(filters, list) else []
    except Exception as e:
        print("⚠️ Failed to parse LLM output:", full_text)
        return []

# Run test
if __name__ == "__main__":
    user_input = input("Enter your query: ")
    filters = filter_categories(user_input)
    print(filters)
    print("\nSuggested filters:")
    for f in filters:
        print("•", f)
