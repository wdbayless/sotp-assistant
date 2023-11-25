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

        # Initialize the conversation
        self.conversation = anvil.server.call('get_conversation')

        # Update the interface with the current state of the conversation
        self.refresh_conversation()

    def refresh_conversation(self):
        # Construct a list of messages
        messages = []
        user_inputs = self.conversation["past_user_msgs"]
        responses = self.conversation["past_asst_msgs"]
        for idx in range(len(user_inputs)):
            messages.append({"from": "user", "text": user_inputs[idx]})
            messages.append({"from": "assistant", "text": responses[idx]})

        # Update the interface
        self.repeating_panel_1.items = messages

    def send_btn_click(self, **event_args):
        """This method is called when the button is clicked"""
        # Send the contents of the new message box to the server
        self.conversation = anvil.server.call('send_message', self.new_message_box.text)

        # Clear the contents of the new message box
        self.new_message_box.text = ""

        # Refresh the conversation display
        self.refresh_conversation()

        # Scroll down to ensure the send message button is in view
        self.send_btn.scroll_into_view()
        

    def new_message_box_pressed_enter(self, **event_args):
        """This method is called when the user presses Enter in this text box"""
        self.send_btn_click()



