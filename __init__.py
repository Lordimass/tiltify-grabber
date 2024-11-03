from flask import Flask, request
import threading
from currency_converter import CurrencyConverter # Used to convert inbound donations to GBP
import os.path
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

if not(os.path.exists("config.py")):
    raise Exception('''You are missing config.py, this file is excluded from the GitHub repository
           as it contains client secrets.''')
import config
    
class DataHandler():
    """
    This class is used as a middleman between `FlaskApplication` and `GSheetsApplication`.
    When it recieves data from the `FlaskApplication` it will process it as necessary before
    forwarding it to the `GSheetsApplication` for POSTing to GSheets.

    Attributes:
        __donationStack (list) : A stack of unhandled donations, updated for each update to donations
    Methods:
        _push: Pushes items onto the `__donationStack`
    """
    def __init__(self, port:int) -> None:
        """
        Constructor function

        Arguments:
            port (int) : The port on which to open the `FlaskApplication` on.
        """
        # This will start the application and start listening for donations.
        # We don't assign an identifier due to the direction of flow of data
        # FlaskApplication -> DataHandler -> GSheetsApplication
        FlaskApplication(port, self) 

        # This time we do want to assign an identifier since we need to run
        # its functions at a later point.
        self.__gSheets = GSheetsApplication()
        
        self.__donationStack = []

    def _push(self, data:dict) -> None:
        """
        Pushes data to the `__donationStack`

        Arguments:
            data (dict) : The data to push
        """
        self.__donationStack.append(data)
        donationHandler = threading.Thread(target=self.handleDonation)
        donationHandler.start()

    def handleDonation(self):
        """
        Processes the top donation, removing unnecessary data then sending it to `GSheetsApplication`
        Designed to be run in a separate thread.
        """
        # First, we need to get the piece of data we'll be processing
        # since we're on a thread, we need to double check that there actually
        # is something to process, then if there is, we pop it and begin processing
        if self.__donationStack == []:
            return
        data = self.__donationStack.pop(0)

        # We'll start by double checking that we have recieved a donation update, not anything else.
        eventType = data["meta"]["event_type"]
        if not(eventType == "private:direct:donation_updated" or eventType == "public:direct:donation_updated"):
            return
        
        # Now we've confirmed that, we need to get:
        # - The name of the donor
        # - The comment
        # - The amount in GBP
        datadata = data["data"]
        name = datadata["donor_name"]
        comment = datadata["donor_comment"]

        # To get the amount, we must convert to GBP to keep currency consistent
        c = CurrencyConverter()
        amount = c.convert(
            datadata["amount"]["value"],
            datadata["amount"]["currency"],
            "GBP"
        )
        amount = round(amount, 2)

        # Now we have all the data we need, we can move to putting the data in GSheets!
        self.__gSheets.recordDonation(amount, name, comment)

class FlaskApplication(DataHandler):
    """
    Class to store the Tiltify Listener
    
    Attributes:
    Methods:
    """

    def __init__(self, port:int, dataHandler:DataHandler) -> None:
        """
        Constructor function. Starts the Flask Application and updates the `donationStack`

        Arguments:
            port (int) : The port on which Cloudflared forwards content from tiltify.lordimass.net to.
            dataHandler (DataHandler) : The parent object.
        """
        assert 0 <= port <= 65535, "Port out of range"
        self.__port = port
        self.__dataHandler = dataHandler
        self.__app = Flask(__name__) # Creates the actual flask application

        @self.__app.route("/", methods=["POST"]) # Only accept POST requests, these will come from Cloudflared
        def __webhook() -> tuple:
            """
            This function is called whenever a `POST` request is made to 127.0.0.1:`port`.
            It will push new donations onto the `donationStack` of the `DataHandler`.
            """
            data = request.get_json()
            self.__dataHandler._push(data)
            return "OK", 200 # Return OK code 200, signifying to the sender the POST request was successful 
        
        # We'll run the application on a separate thread so as to not interrupt the the rest of the program
        self.__appThread = threading.Thread(target=self.__app.run, args=(None,self.__port))
        self.__appThread.start()

class GSheetsApplication(DataHandler):
    """
    Interfaces with the Google Sheets API in order to write data obtained from the `DataHandler`
    """
    
    def __init__(self):
        # Authorise and return the GSheet
        self.__sheet = self.__authorize()

    def __authorize(self) -> any:
        """
        Performs Google authorisation process

        The file token.json stores the user's access and refresh tokens, and is
        created automatically when the authorization flow completes for the first
        time.
        """

        creds = None
        # The file token.json stores the user's access and refresh tokens, and is
        # created automatically when the authorization flow completes for the first
        # time.
        if os.path.exists("token.json"):
            creds = Credentials.from_authorized_user_file("token.json", config.SCOPES)
        # If there are no (valid) credentials available, let the user log in.
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    "credentials.json", config.SCOPES
                )
                creds = flow.run_local_server(port=0)
            # Save the credentials for the next run
            with open("token.json", "w") as token:
                token.write(creds.to_json())#
        
        try:
            service = build("sheets", "v4", credentials=creds)
            # Call the Sheets API
            return service.spreadsheets()
        except HttpError as e:
            print(e)
    
    def recordDonation(self, amount:int, name:str, comment:str = None) -> None:
        """
        Records a donation to the sheet

        Arguments:
            amount (int) : The amount of money donated, in GBP
            name (str) : The name of the donor
            comment (str) : The comment attached to the donation, if there was one
        """

        # The body of the request to the Google Sheet to append
        body = {
            "values": [[amount, name, comment]]
        }

        # Send 
        self.__sheet.values().append(
            spreadsheetId = config.SPREADSHEET_ID,
            range = "Donation List!A2:C2",
            valueInputOption = "USER_ENTERED",
            body = body,
        ).execute()


if __name__ == "__main__":
    DataHandler(port=config.PORT) # Instantiate the DataHandler, beginning webhook receiving and processing