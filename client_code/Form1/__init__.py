from ._anvil_designer import Form1Template
from anvil import *
import anvil.server
import anvil.tables as tables
import anvil.tables.query as q
from anvil.tables import app_tables

class Form1(Form1Template):

    def __init__(self, **properties):
        # Set Form properties and Data Bindings.
        self.init_components(**properties)

        # Initialize a new OpenAI thread
        anvil.server.call('create_new_thread')

        # Reset the conversation when the app starts     
        self.conversation = anvil.server.call('reset_conversation')

        # Update the interface with the current state of the conversation
        self.refresh_conversation()

    def refresh_conversation(self):
        # Construct a list of messages
        messages = []
        for message in self.conversation:
            role = message["role"]
            text = message["value"]
            if role == "user":
                messages.append({"from": "user", "text": text})
            elif role == "assistant":
                messages.append({"from": "assistant", "text": text})

        # Update the interface
        self.repeating_panel_1.items = messages

    def send_btn_click(self, **event_args):
        """This method is called when the button is clicked"""
        # Send the contents of the new message box to the server
        self.conversation = anvil.server.call(
            'send_message',
            self.new_message_box.text,
        )
        
        # Clear the contents of the new message box
        self.new_message_box.text = ""

        # Refresh the conversation display
        self.refresh_conversation()

        # Scroll down to ensure the send message button is in view
        self.send_btn.scroll_into_view()
        

    def new_message_box_pressed_enter(self, **event_args):
        """This method is called when the user presses Enter in this text box"""
        self.send_btn_click()