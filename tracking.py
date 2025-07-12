import os
from phoenix.otel import register
from google import genai

os.environ["GEMINI_API_KEY"] = "AIzaSyBwJ01S77JrCYZGlcLVShjfo90sUMVxlxg"
register(project_name="my-llm-app", auto_instrument=True)

def send_message_multi_turn():
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    chat = client.chats.create(model="gemini-1.5-flash-latest")
    response1 = chat.send_message("What is the capital of France?")
    response2 = chat.send_message("Why is the sky blue?")
    return response1.text or "", response2.text or ""

if __name__ == "__main__":
    print(send_message_multi_turn())