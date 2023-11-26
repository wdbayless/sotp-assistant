from ._anvil_designer import Form1Template
from anvil import *
import anvil.server

class Form1(Form1Template):
    def __init__(self, **properties):
        # Initialize form properties and components
        self.init_components(**properties)

        # Set up conversation
        self.initialize_conversation()

        # Refresh the conversation display
        self.refresh_conversation()

    def initialize_conversation(self):
        """Initialize a new OpenAI thread and reset the conversation."""
        anvil.server.call('create_new_thread')
        self.conversation = anvil.server.call('reset_conversation')

    def refresh_conversation(self):
        """Fetches the updated conversation and updated the UI."""
        self.conversation = anvil.server.call('get_conversation')
        messages = self.format_conversation(self.conversation)
        self.repeating_panel_1.items = messages

    def format_conversation(self, conversation):
        """Formats the conversation messages for display."""
        return [{"from": message["role"], "text": message["value"]} for message in conversation]
       
    def send_btn_click(self, **event_args):
        """Handles the event when the send button is clicked"""
        task_id = anvil.server.call('launch_send_message_task', self.new_message_box.text)
        self.task_id = task_id # Store the task ID
        self.clear_message_box()
        self.check_task_status()

    def check_task_status(self):
        """Checks the status of the background task and updates UI accordingly."""
        task_status = anvil.server.call('check_task_status', self.task_id)

        if task_status == "completed":
           self.update_conversation_from_task()
        elif task_status == "running":
           # Re-check after some delay if the task is still running
            anvil.js.call_js('setTimeout', self.check_task_status, 1000)

    def update_conversation_from_task(self):
        """Updates the conversation with the result from the background task."""
        updated_conversation = anvil.server.call('get_background_task_result', self.task_id)
        if updated_conversation is not None:
            self.conversation = updated_conversation
            self.refresh_conversation()
            self.scroll_to_bottom()

    def send_message(self, message):
        """Sends a message to the server."""
        self.conversation = anvil.server.call('send_message', message)

    def clear_message_box(self):
        """Clears the new message input box."""
        self.new_message_box.text = ""

    def scroll_to_bottom(self):
        """Scrolls the view to the bottom."""
        self.send_btn.scroll_into_view()

    def new_message_box_pressed_enter(self, **event_args):
        """Triggered when Enter is pressed in the message box."""
        self.send_btn_click()