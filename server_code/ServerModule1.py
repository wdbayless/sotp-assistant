# Import Anvil libraries
import anvil.secrets
import anvil.server

# Standard library imports
import time
import json

# OpenAI library imports
import openai
from openai import OpenAI

# Tavily library import
from tavily import TavilyClient

# Initialize clients with API authorizations
OPENAI_API_KEY = anvil.secrets.get_secret('openai_api_key')
client = OpenAI(api_key=OPENAI_API_KEY)

tavily_api_key = anvil.secrets.get_secret('tavily_api_key')
tavily_client = TavilyClient(tavily_api_key)

# Retrieve OpenAI Assistant ID
assistant_id = anvil.secrets.get_secret('sotp_assistant_id')

def wait_for_run_completion(thread_id, run_id):
  """
  Wait for a specified run to complete.
  
  Continuously checks the status of a run and returns once
  the run is completed.
  
  Args:
  thread_id (str): The ID of the thread.
  run_id (str): The ID of the run.
  
  Returns:
  object: The final status of the run.
  """
  while True:
      # Wait before checking the run status
      time.sleep(5)
      # Retrieve the current status of the run
      run = client.beta.threads.runs.retrieve(
          thread_id=thread_id,
          run_id=run_id
      )
      # Return the status upon completion of the run
      if run.status in ['completed', 'failed', 'requires_action']:
        return run

def submit_tool_outputs(thread_id, run_id, tools_to_call):
    """
    Handle the submission of tool outputs.

    Processes the outputs of specified tools and submits them as part of a run.

    Args:
    thread_id (str): The thread ID associated with the run.
    run_id (str): The run ID for which the outputs are being submitted.
    tools_to_call (list): A list of tools to call and process.

    Returns:
    object: Response from submitting the tool outputs.
    """
    tool_output_array = []
    for tool in tools_to_call:
        output = None
        tool_call_id = tool.id
        function_name = tool.function.name
        function_args = tool.function.arguments

        # Perform tavily_search if the function name matches
        if function_name == "tavily_search":
            output = tavily_search(query=json.loads(function_args)["query"])

        # Append the output to the tool_output_array if it exists
        if output:
            tool_output_array.append({"tool_call_id": tool_call_id, "output": output})

    # Submit the collected tool outputs
    return client.beta.threads.runs.submit_tool_outputs(
        thread_id=thread_id,
        run_id=run_id,
        tool_outputs=tool_output_array
    )

def tavily_search(query):
    """
    Perform a Tavily search with a specified query.

    Args:
    query (str): The search query string.

    Returns:
    object: The search result returned by the tavily_client.
    """
    # Perform a search using tavily_client with specified parameters
    search_result = tavily_client.get_search_context(
        query,
        search_depth="advanced",
        max_tokens=8000
    )
    return search_result

@anvil.server.callable
def create_new_thread():
  # Create a new OpenAI thread
  thread = client.beta.threads.create()
  # Save the thread_id as a session variable
  anvil.server.session["thread_id"] = thread.id

@anvil.server.callable
def get_conversation():
  # Check to see if the conversation is stored in the server session
  if "conversation" not in anvil.server.session:
      # If not, initialize a starter conversation
      anvil.server.session["conversation"] = {
          "past_user_msgs": ["What is the core assumption of the Science of the Positive?"],
          "past_asst_msgs": ["The positive exists."]
      }
  # Return the current state of the conversation
  return anvil.server.session["conversation"]

@anvil.server.callable
def send_message(user_msg):
  # Fetch the thread_id session variable
  thread_id = anvil.server.session.get("thread_id")
  if not thread_id:
    raise Exception("Thread ID not found in session.")
  # Fetches the current conversation state
  conversation = get_conversation()
  # Add the user's message to the current OpenAI thread
  message = client.beta.threads.messages.create(
      thread_id=thread_id,
      role="user",
      content=user_msg,
  )
  # Initiate a run which process the user's message and
  # generates a response
  run = client.beta.threads.runs.create(
      thread_id=thread_id,
      assistant_id=assistant_id,
  )
  # Wait for the run to complete and retrieve the final status
  run = wait_for_run_completion(
      thread_id,
      run.id
  )
  # If the run requires action, submit tool outputs and
  # wait again for the run to complete
  if run.status == "requires_action":
    run = submit_tool_outputs(
        thread_id,
        run.id,
        run.required_action.submit_tool_outputs.tool_calls
    )
    run = wait_for_run_completion(
        thread_id,
        run.id
    )
  # Retrieve the user and assistant messages from the thread
  thread_messages = client.beta.threads.messages.list(
      thread_id=thread_id
  )
  messages = thread_messages.data
  # Update the conversation in the server session with the
  # new state returned by the OpenAI Assistant
  anvil.server.session["conversation"] = messages
  return messages