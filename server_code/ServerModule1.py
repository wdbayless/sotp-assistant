# Configuration and Initialization
import anvil.secrets
import anvil.server

OPENAI_API_KEY = anvil.secrets.get_secret('openai_api_key')
TAVILY_API_KEY = anvil.secrets.get_secret('tavily_api_key')
ASSISTANT_ID = anvil.secrets.get_secret('sotp_assistant_id')

# Import necessary libraries
import time
import json
from openai import OpenAI
from tavily import TavilyClient

# Define OpenAIClient class
class OpenAIClient:
    def __init__(self, api_key):
        self.client = OpenAI(api_key=api_key)

    def create_thread(self):
        return self.client.beta.threads.create()

    def send_message(self, thread_id, user_msg):
        return self.client.beta.threads.messages.create(thread_id=thread_id, role="user", content=user_msg)

    def initiate_run(self, thread_id, assistant_id):
        return self.client.beta.threads.runs.create(thread_id=thread_id, assistant_id=assistant_id)

    def get_thread_messages(self, thread_id):
        return self.client.beta.threads.messages.list(thread_id=thread_id, order="asc")

# Define TavilyClientWrapper class
class TavilyClientWrapper:
    def __init__(self, api_key):
        self.client = TavilyClient(api_key)

    def search(self, query):
        return self.client.get_search_context(query, search_depth="advanced", max_tokens=8000)

# Instantiate clients
openai_client = OpenAIClient(OPENAI_API_KEY)
tavily_client = TavilyClientWrapper(TAVILY_API_KEY)

# Utility functions
def wait_for_run_completion(client, thread_id, run_id):
    while True:
        time.sleep(3)
        run = client.client.beta.threads.runs.retrieve(thread_id=thread_id, run_id=run_id)
        if run.status in ['completed', 'failed', 'requires_action']:
            return run

def submit_tool_outputs(client, thread_id, run_id, tools_to_call):
    tool_output_array = []
    for tool in tools_to_call:
        output = None
        if tool.function.name == "tavily_search":
            output = tavily_client.search(json.loads(tool.function.arguments)["query"])
        if output:
            tool_output_array.append({"tool_call_id": tool.id, "output": output})

    return client.client.beta.threads.runs.submit_tool_outputs(thread_id=thread_id, run_id=run_id, tool_outputs=tool_output_array)

# Anvil server callable functions
@anvil.server.callable
def create_new_thread():
    thread = openai_client.create_thread()
    anvil.server.session["thread_id"] = thread.id

@anvil.server.callable
def reset_conversation():
    anvil.server.session["conversation"] = [
        {"role": "user", "value": "What is the core assumption of the Science of the Positive?"},
        {"role": "assistant", "value": "The Positive exists."}
    ]
    return anvil.server.session["conversation"]

@anvil.server.callable
def get_conversation():
    if "conversation" not in anvil.server.session:
        anvil.server.session["conversation"] = []
    return anvil.server.session["conversation"]

@anvil.server.callable
def launch_send_message_task(message):
    thread_id = anvil.server.session.get("thread_id")
    if not thread_id:
        raise Exception("Thread ID not found in session.")
    task = anvil.server.launch_background_task('send_message_task', message, thread_id)
    return task.get_id()
  
@anvil.server.background_task
def send_message_task(user_msg, thread_id):
    if not thread_id:
        raise Exception("Thread ID not found in task state.")
    conversation = get_conversation()
    message = openai_client.send_message(thread_id, user_msg)

    run = openai_client.initiate_run(thread_id, ASSISTANT_ID)
    run = wait_for_run_completion(openai_client, thread_id, run.id)

    if run.status == "requires_action":
        run = submit_tool_outputs(openai_client, thread_id, run.id, run.required_action.submit_tool_outputs.tool_calls)
        run = wait_for_run_completion(openai_client, thread_id, run.id)

    thread_messages = openai_client.get_thread_messages(thread_id)
    messages = [{"role": m.role, "value": m.content[0].text.value if m.content else None} for m in thread_messages.data]

    anvil.server.session["conversation"] = messages
    return messages

@anvil.server.callable
def check_task_status(task_id):
    task = anvil.server.get_background_task(task_id)
    return task.get_termination_status()