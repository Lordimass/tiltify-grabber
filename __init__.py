from flask import Flask, request
import threading
from currency_converter import CurrencyConverter # Used to convert inbound donations to GBP

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
        # Create the `FlaskApplication`, this will start the application and start listening for donations
        FlaskApplication(port, self) 

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
        
        # Now we've confirmed that, we need to get the name of the donor, the amount in GBP, and the comment.
        datadata = data["data"]
        name = datadata["donor_name"]
        comment = datadata["donor_comment"]

        # To get the amount, we must convert to GBP to keep things consistent
        c = CurrencyConverter()
        amount = c.convert(
            datadata["amount"]["value"],
            datadata["amount"]["currency"],
            "GBP"
        )
        amount = round(amount, 2)

        # Now we have all the data we need, we can overwrite the big block of data, 
        # then move to putting the data in GSheets!
        data = (name, amount, comment)
        print(data)


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



if __name__ == "__main__":
    DataHandler(port=12345) # Instantiate the DataHandler, beginning webhook receiving and processing


