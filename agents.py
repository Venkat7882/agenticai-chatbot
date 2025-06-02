import requests
import os
import fitz  # PyMuPDF
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
MODEL = "anthropic/claude-3-haiku"
API_URL = "https://openrouter.ai/api/v1/chat/completions"

# Global storage for chunks and embeddings
pdf_chunks = []
chunk_embeddings = []
vectorizer = None

def call_openrouter(prompt):
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://your-app.com",
        "X-Title": "AgenticAI-Demo"
    }
    data = {
        "model": MODEL,
        "messages": [
            {"role": "user", "content": prompt}
        ]
    }
    response = requests.post(API_URL, headers=headers, json=data)

    try:
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]
    except requests.exceptions.HTTPError:
        print("❌ Response Error:", response.text)
        raise


class Agent:
    def __init__(self, name):
        self.name = name
        self.history = []

    def say(self, message):
        self.history.append((self.name, message))
        return message

    def ask(self, prompt):
        # Use RAG by appending relevant chunks
        context = retrieve_relevant_chunks(prompt)
        full_prompt = f"""
Use the following context to answer the question.

Context:
{context}

Question:
{prompt}
"""
        message = call_openrouter(full_prompt)
        self.history.append((self.name, message))
        return message


# Instantiate agents
agent_a = Agent("Agent A")
agent_b = Agent("Agent B")

def generate_followups(topic, previous_query, agent_b_response):
    prompt = f"""
You are helping Agent A continue an intelligent and insightful conversation with Agent B.

The conversation so far:

Agent A asked:
"{previous_query}"

Agent B responded:
"{agent_b_response}"

The overall topic of discussion is:
"{topic}"

Now, suggest 3 smart and contextually relevant follow-up questions that Agent A could ask to keep the conversation flowing meaningfully.

Please provide only the 3 questions as a numbered list like this:
1. ...
2. ...
3. ...
"""
    response = call_openrouter(prompt)
    followups = [line.strip("1234567890. ").strip() for line in response.split("\n") if line.strip()]
    return followups

def generate_summary(history):
    conversation_text = "\n".join([f"{speaker}: {message}" for speaker, message in history])

    short_prompt = f"""
Summarize the following conversation between Agent A and Agent B in 3 bullet points:

{conversation_text}
"""

    long_prompt = f"""
Convert the following conversation between Agent A and Agent B into a detailed FAQ format. Each question should be asked by Agent A and the corresponding answer should be from Agent B.

{conversation_text}
"""

    short_summary = call_openrouter(short_prompt)
    long_summary = call_openrouter(long_prompt)
    return short_summary, long_summary


def embed_and_chunk_pdf(file):
    global pdf_chunks, chunk_embeddings, vectorizer

    doc = fitz.open(stream=file.read(), filetype="pdf")
    text = " ".join(page.get_text() for page in doc)
    chunks = [text[i:i+1000] for i in range(0, len(text), 1000)]
    pdf_chunks = chunks

    vectorizer = TfidfVectorizer().fit(chunks)
    chunk_embeddings = vectorizer.transform(chunks)
    return "PDF processed with embeddings ready."

def retrieve_relevant_chunks(query, top_k=3):
    if chunk_embeddings is None or chunk_embeddings.shape[0] == 0 or vectorizer is None:
        return ""
    query_vec = vectorizer.transform([query])
    scores = cosine_similarity(query_vec, chunk_embeddings).flatten()
    top_indices = scores.argsort()[-top_k:][::-1]
    return "\n\n".join([pdf_chunks[i] for i in top_indices])
