import anvil.tables as tables
import anvil.tables.query as q
from anvil.tables import app_tables
import anvil.secrets
import anvil.server
import anvil.http
import anvil.media

OPENAI_API_KEY = anvil.secrets.get_secret('openai_api_key')
TAVILY_API_KEY = anvil.secrets.get_secret('tavily_api_key')
ASSISTANT_ID = anvil.secrets.get_secret('sotp_assistant_id')

# Import necessary libraries
import time
import json
from openai import OpenAI
from tavily import TavilyClient
import cloudconvert
import base64

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
    # Convert markdown text to byte string
    markdown_bytes = markdown_text.encode('utf-8')

    # Encode bytes to base64 sstring
    base64_encoded_str = base64.b64encode(markdown_bytes).decode('utf-8')

    # Instantiate CloudConvert client
    cloudconvert.configure(api_key=anvil.secrets.get_secret('cloudconvert_api_key'), sandbox=False)

    # Create a CloudConvert job for direct upload
    job = cloudconvert.Job.create(payload={
        "tasks": {
            "upload-file": {
                "operation": "import/upload"
            },
            "convert-to-docx": {
                "operation": "convert",
                "input": "upload-file",
                "output_format": "docx",
                "engine": "pandoc"
            },
            "export-my-file": {
                "operation": "export/url",
                "input": "convert-to-docx"
            }
        }
    })

    # Get the upload URL from the created job
    # assuming the upload task is the first task in the job
    upload_task = job['tasks'][0]
    upload_url = upload_task['result']['form']['url']

    # Upload the file to CloudConvert
    response = anvil.http.request(upload_url,
                                  method="POST",
                                  data=base64_encoded_str,
                                  headers={"Content-Type": "application/octet-stream"}
                                 )

    # Assuming the export task is the final task in the job
    export_task_id = job['tasks'][-1]['id']
  
    # Polling for the conversion job to finish
    timeout = 120  # seconds
    poll_interval = 5  # seconds
    start_time = time.time()
    while time.time() - start_time < timeout:
        export_task = cloudconvert.Task.find(id=export_task_id)
        if export_task['status'] == 'finished':
            print("Export task completed successfully.")
            break
        elif export_task['status'] == 'error':
            raise Exception("Export task encountered an error.")
        time.sleep(poll_interval)
    else:
        raise TimeoutError("Conversion job timed out.")

  # Diagnostic print statement
    print(f"Completed CloudConvert job object: {job}")

    # Retrieve the DOCX file URL
    export_task = job['tasks'][-1]
    download_url = export_task['result']['files'][0]['url']

    # Download the DOCX file using Anvil's HTTP request
    response = anvil.http.request(download_url, method="GET")
    docx_file_content = response.get_bytes()

    # Convert to an Anvil Media Object
    docx_media = anvil.media.from_bytes(docx_file_content, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")

    # Delete the temporary .md file from the Anvil data table
    stored_file.delete()

    return docx_media  
    