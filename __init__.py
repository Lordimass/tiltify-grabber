from flask import Flask, request
import threading

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

    def _push(self, data) -> None:
        self.__donationStack.append(data)
        print(type(data))


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


