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

        # Any code you write here will run when the form opens.
        self.conversation = anvil.server.call('get_conversation')
        self.refresh_conversation()

    def refresh_conversation(self):
        messages = []
        user_inputs = self.conversation["past_user_inputs"]
        responses = self.conversation["generated_responses"]
        for idx in range(len(user_inputs)):
            messages.append({"from": "user", "text": user_inputs[idx]})
            messages.append({"from": "bot", "text": responses[idx]})
        self.repeating_panel_1.items = messages

    def send_btn_click(self, **event_args):
        """This method is called when the button is clicked"""
        self.conversation = anvil.server.call('send_message', self.new_message_box.text)
        self.new_message_box.text = ""
        self.refresh_conversation()
        self.send_btn.scroll_into_view()
        

    def new_message_box_pressed_enter(self, **event_args):
        """This method is called when the user presses Enter in this text box"""
        self.send_btn_click()



