# api.py
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import os

# Import your chatbot module – adjust the import path as needed
from application.modules.agent_collection import AgentCollection

app = FastAPI(title="Chatbot API")

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # or specify a list of allowed origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize your agent.
# Make sure to set the correct config path or adjust the initialization accordingly.
config_path = os.path.join(os.getcwd(), "application", "json", "config.json")
agent = AgentCollection(config_path=config_path)

# Define the request and response models
class ChatRequest(BaseModel):
    message: str

class ChatResponse(BaseModel):
    response: str

@app.post("/chat", response_model=ChatResponse)
def chat_endpoint(request: ChatRequest):
    try:
        # Process the message through your existing agent
        result, _ = agent.process_message(request.message)
        # If result is a list, you might want to join or format it; here we convert it to a string.
        response_text = result if isinstance(result, str) else "\n".join(result)
        return ChatResponse(response=response_text)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

