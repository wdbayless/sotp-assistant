import anvil.secrets
import anvil.tables as tables
import anvil.tables.query as q
from anvil.tables import app_tables
import anvil.server
import requests

API_URL = "https://api-inference.huggingface.co/models/microsoft/DialoGPT-large"
headers = {"Authorization": f"Bearer {anvil.secrets.get_secret('api_token')}"}

def query(payload):
	response = requests.post(API_URL, headers=headers, json=payload)
	return response.json()

@anvil.server.callable
def get_conversation():
  if "conversation" not in anvil.server.session:
      anvil.server.session["conversation"] = {
          "past_user_inputs": ["Merry Christmas!"],
          "generated_responses": ["And a Merry Christmas to you!"]
      }
  return anvil.server.session["conversation"]


@anvil.server.callable
def send_message(message):
  conversation = get_conversation()
  model_output = query({
    "inputs": {
      "text": message,
      **conversation
    }
  })
  anvil.server.session["conversation"] = model_output["conversation"]
  return model_output["conversation"]
