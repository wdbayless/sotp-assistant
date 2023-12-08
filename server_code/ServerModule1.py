# Import required Anvil libraries
import anvil.tables as tables
import anvil.tables.query as q
from anvil.tables import app_tables
import anvil.secrets
import anvil.server
import anvil.media
import anvil.http

# Import necessary external libraries
import time
import json
from openai import OpenAI
from tavily import TavilyClient
import markdown2
import convertapi
from io import BytesIO

# Configure API keys and OpenAI Assistant ID
OPENAI_API_KEY = anvil.secrets.get_secret('openai_api_key')
TAVILY_API_KEY = anvil.secrets.get_secret('tavily_api_key')
ASSISTANT_ID = anvil.secrets.get_secret('sotp_assistant_id')
convertapi.api_secret = anvil.secrets.get_secret('convertapi_secret')

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

def markdown_to_html(markdown_text):
    # Convert markdown to HTML
    html = markdown2.markdown(markdown_text)

    # Add the DOCTYPE declaration if it's missing
    if not html.strip().lower().startswith('<!doctype html>'):
        html = f'<!DOCTYPE html>\n{html}'

    html_filename = "conversation.html"

    # Create a BlobMedia object from the HTML content
    html_bytes = html.encode('utf-8')
    media_object = anvil.BlobMedia('text/html', html_bytes, name=html_filename)

    # Save the BlobMedia object to the 'html_file' field in the 'files' table
    row = app_tables.files.add_row(html_file=media_object)

    # Get the record_id of the saved media object
    record_id = row.get_id()

    print(f"Markdown text converted to HTML and saved as {html_filename} in the Anvil app.")
    return record_id

def convert_html_to_docx(record_id):
    # Retrieve the record from the 'files' table using the provided record_id
    record = app_tables.files.get_by_id(record_id)
    if record is None:
        raise ValueError ("Record not found in the 'files' table.")

    # Get a publicly accessible URL for the HTML file to pass to ConvertAPI
    public_file_url = f"{anvil.server.get_api_origin()}/file-url/{record_id}"

    # Convert the HTML document to DOCX format using ConvertAPI
    result = convertapi.convert('docx', {'File': public_file_url}, from_format='html')
    docx_file_url = result.file.url
    print(f"The docx_file_url is: {docx_file_url}")

    # Retrieve the DOCX File from ConvertAPI as bytes
    docx_file = anvil.http.request(docx_file_url)
    docx_bytes = docx_file.get_bytes()

    # Save the DOCX file as a media object and store it in the 'docx_file' field
    docx_media = anvil.BlobMedia(content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                                 content=docx_bytes,
                                 name='conversation.docx')
    record['docx_file'] = docx_media

    print("HTML document converted to DOCX and saved in the 'files' table.")
    return docx_media

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
def launch_send_message_task(message):
    thread_id = anvil.server.session.get("thread_id")
    if not thread_id:
        raise Exception("Thread ID not found in session.")
    task = anvil.server.launch_background_task('send_message_task', message, thread_id)
    return task.get_id()
  
@anvil.server.background_task
def send_message_task(user_msg, thread_id):
    try:
        # Log the start of the task
        print(f"Starting send_message_task with message: '{user_msg}' and thread_id: '{thread_id}'")

        # Update the task state to indicate it's processing
        anvil.server.task_state['status'] = 'processing'

        # Send the message and handle the OpenAI interaction
        if not thread_id:
            raise Exception("Thread ID not found in task state.")
        # conversation = get_conversation()
        message = openai_client.send_message(thread_id, user_msg)

        run = openai_client.initiate_run(thread_id, ASSISTANT_ID)
        run = wait_for_run_completion(openai_client, thread_id, run.id)

        if run.status == "requires_action":
            run = submit_tool_outputs(openai_client, thread_id, run.id, run.required_action.submit_tool_outputs.tool_calls)
            run = wait_for_run_completion(openai_client, thread_id, run.id)

        thread_messages = openai_client.get_thread_messages(thread_id)
        messages = [{"role": m.role, "value": m.content[0].text.value if m.content else None} for m in thread_messages.data]

        # Update the task state to store the result and indicate completion
        anvil.server.task_state['result'] = messages
        anvil.server.task_state['status'] = 'completed'

        # Log the completion of the task
        print("send_message_task completed successfully.")

    except Exception as e:
        # Log the error and update the task state
        print(f"Error in send_message_task: {e}")
        anvil.server.task_state['status'] = 'error'
        anvil.server.task_state['error_message'] = str(e)

@anvil.server.callable
def get_task_status(task_id):
    print(f"get_task_status called with task_id: {task_id}")
    task = anvil.server.get_background_task(task_id)

    if task is None:
        print(f"No task found for task_id: {task_id}")
        return None

    task_state = task.get_state()
    print(f"Task state for task_id {task_id}: {task_state}")
    return task_state

@anvil.server.callable
def get_background_task_result(task_id):
    print(f"Retrieving result for task {task_id}")
    task = anvil.server.get_background_task(task_id)
    if task is None or not task.is_completed:
        return None
    try:
        # Retrieve the 'result' from the task's state
        return task.get_state()['result']
    except Exception as e:
        print(f"Error retrieving task result: {e}")
        return None

@anvil.server.callable
def convert_markdown_to_docx(markdown_text):
    record_id = markdown_to_html(markdown_text)
    docx_file = convert_html_to_docx(record_id)
    return docx_file

@anvil.server.http_endpoint('/file-url/:record_id')
# To make the URL of a file stored in an Anvil table publicly accessible
# it must be exposed via an endpoint.
def get_public_url(record_id):
    row = app_tables.files.get_by_id(record_id)
    if row is not None:
        # Returning a media object from an endpoint serves it as an HTTP response
        return row['html_file']
    else:
        return anvil.server.HttpResponse(status='404')