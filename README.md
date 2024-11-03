This script recieves data from the Tiltify Webhook, processes it, then outputs it to a Google Sheet which keeps track of the donations. I'll be using this `README` to explain the process in more depth.

## Tiltify Webhook
The first stage of the process is having Tiltify connect to an endpoint to send data to. This is set up relatively simply as an application on Tiltify's website, which makes it very easy to subscribe to the data you want to subscribe to. The tricky part then was the endpoint, I wanted the endpoint to be my local device, without the ability to expose said device to the internet for obvious reasons. On top of that, Tiltify understandably would only allow endpoints which implement https, not http as `localhost` would be.

The solution to this was to use a webhook tunnelling service to get the data to my device. Luckily for me, my website https://lordimass.net (Critically *https*) uses CloudFlare as its primary DNS provider already, I was able to implement a webhook tunnel from a subdomain of lordimass.net to a port on my computer.

## Python
Now came the code part, receiving the data by listening to the socket, catching the data, processing it, then forwarding it to Google Sheets. That code is in this repository (and is the main focus of the repo).

I used the class `DataHandler` as a middleman between the `FlaskApplication` and the `GSheetApplication`. The `FlaskApplication` here runs its own internal thread using Flask to receive the network requests as necessary, when it gets them, it pushes them to the stack and notifies the `DataHandler` that it has new data to process. The `DataHandler` then pops the data from the stack, confirms that the data received is of the right type, extracts the donation quantity, donor name, and donor comment from the data, and forwards that information on to the `GSheetApplication`

Now, relatively simply, the `GSheetApplication` interacts with the Google Sheets API in order to append the data to the sheet which logs donations. And that's it! The donation has been logged to the Google sheet successfully!
