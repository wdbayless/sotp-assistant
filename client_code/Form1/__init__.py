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
        print("Refreshing conversation in UI.")
        print(f"Conversation received for refresh: {self.conversation}")
        messages = self.format_conversation(self.conversation)
        print(f"Formatted messages for UI: {messages}")
        self.repeating_panel_1.items = messages
        print("UI conversation refreshed.")
    
    def format_conversation(self, conversation):
        """Formats the conversation messages for display."""
        print(f"Formatting conversation: {conversation}")
        formatted = [{"from": message["role"], "text": message["value"]} for message in conversation]
        print(f"Formatted conversation: {formatted}")
        return formatted

    def send_btn_click(self, **event_args):
        """Handles the event when the send button is clicked"""
        message_text = self.new_message_text_area.text.strip()
    
        if message_text:
            print("Send button clicked.")
            task_id = anvil.server.call('launch_send_message_task', message_text)
            print(f"Background task launched with task ID: {task_id}")
            self.task_id = task_id  # Store the task ID
            self.clear_message_box()
            self.check_task_status()
        else:
            print("No message to send.")

    def check_task_status(self):
        try:
            # Request the task state from the server
            task_status = anvil.server.call('get_task_status', self.task_id)
            print(f"Received task status: {task_status}")
    
            if task_status.get('status') is None:
                print("Task status is None.")
                   
            elif task_status.get('status') == 'completed':
                print("Task completed. Updating conversation.")
                self.update_conversation_from_task()
    
            elif task_status.get('status') == 'processing':
                print("Task still processing. Will check again.")
                anvil.js.call_js('setTimeout', self.check_task_status, 1000)  # Check again after 1 second
    
            elif task_status.get('status') == 'error':
                error_message = task_status.get('error_message', 'Unknown error')
                print(f"Error in task: {error_message}")

        except Exception as e:
            print(f"Error while checking task status: {e}")
            # Implement error handling for issues in checking the task status

    def update_conversation_from_task(self):
        """Updates the conversation with the result from the background task."""
        print("Updating conversation from background task.")
        updated_conversation = anvil.server.call('get_background_task_result', self.task_id)
        print(f"Updated conversation: {updated_conversation}")
        if updated_conversation is not None:
            self.conversation = updated_conversation
            self.refresh_conversation()
            self.scroll_to_bottom()

    def send_message(self, message):
        """Sends a message to the server."""
        self.conversation = anvil.server.call('send_message', message)

    def clear_message_box(self):
        """Clears the new message input box."""
        self.new_message_text_area.text = ""

    def scroll_to_bottom(self):
        """Scrolls the view to the bottom."""
        self.send_btn.scroll_into_view()