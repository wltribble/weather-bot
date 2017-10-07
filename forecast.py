from flask import Flask, request, redirect
from twilio.twiml.messaging_response import MessagingResponse
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut

import requests, json

app = Flask(__name__)

# This is from api.darksky.net, and the weather gathering in this app is powered by their API
# I would prefer to have mine stored as an environment variable for safety, but can't get it to work right...
WEATHER_API_KEY = '9a97b0b77b9f03cdd16698d7489ce6e5'

# Converting conversational specifiers to match the JSON file's weather breakdown
# -- these are just some that I came up with based on my conversational style --
known_timeframe_specifiers = {
    "now": "currently",
    "hourly": "hourly",
    "minutely": "minutely",
    "daily": "daily",
    "week": "daily",
    "currently": "currently",
    "current": "currently",
    "today": "hourly",
    "tonight": "hourly",
}

# Converting conversational specifiers to match the JSON file's data types
# -- these are just some that I came up with based on my conversational style --
known_weather_details = {
    "weather": "summary",
    "conditions": "summary",
    "rain": "precipProbability",
    "snow": "precipProbability",
    "precipitation": "precipProbability",
    "temperature": "temperature",
    "temp": "temperature",
    "humidity": "humidity",
    "humid": "humidity",
    "wind": "windSpeed",
    "windy": "windSpeed",
}


known_phone_numbers = {
    "+16013171177": "Oxford, MS",
}

# prevent geocoder timeout!
def do_geocode(address):
    try:
        geolocator = Nominatim()
        return geolocator.geocode(address)
    except GeocoderTimedOut:
        return do_geocode(address)

@app.route('/sms_weather', methods=['POST'])
def sms():
    # Gathering location data (hardcoded per registered Twilio phone number because I don't know how to find a phone's current location in Python :( )
    from_number = request.values.get('From', None)
    if from_number in known_phone_numbers:
        location_string = known_phone_numbers[from_number]
    else:
        location_string = "San Francisco, CA"

    location = do_geocode(location_string)
    latitude = str(location.latitude)
    longitude = str(location.longitude)

    # Getting the weather data
    raw_weather_data = requests.get('https://api.darksky.net/forecast/'+WEATHER_API_KEY+'/'+latitude+','+longitude)
    raw_weather_data = raw_weather_data.text
    json_weather_data = json.loads(raw_weather_data)

    # Getting the text request information
    body = request.values.get("Body")

    body = body.translate({ord(c): " " for c in "1234567890.,?!'-:;"}).translate({ord(c): " " for c in '"'})
    body = body.lower()
    body = body.split()

    is_valid_request = False
    json_weather_specifier = None;

    # Get the timeframe specifier from the text request or default to current
    for item in body:
        if item in known_timeframe_specifiers:
            json_weather_specifier = known_timeframe_specifiers[item]
        if json_weather_specifier == None:
            json_weather_specifier = "currently"

    # Find out what the texter wants to know
    for item in body:
        if item in known_weather_details:
            requested_info = known_weather_details[item]
            readable_info_request = item
            is_valid_request = True

    # Make sure we know how to return that info
    if not is_valid_request:
        unkown_request_error_message = "I\'m sorry, I don\'t know how to find that for you. Try asking for something else!"
        resp = MessagingResponse().message(unkown_request_error_message)
        return str(resp)
    else:
        # Get the requested info
        json_specific_weather = json_weather_data[json_weather_specifier]
        actual_desired_info = json_specific_weather.get(requested_info)

        # Determine how to contextualize the weather data based on user input
        if readable_info_request == 'rain':
            if not actual_desired_info == None:
                actual_desired_info = actual_desired_info * 100
            else:
                actual_desired_info = 0
            message = 'The chance of rain in ' + location_string + ' is currently ' + str(actual_desired_info) + '%'
        elif readable_info_request == 'wind' or readable_info_request == 'windy':
            message = 'The wind speed in ' + location_string + ' is currently ' + str(actual_desired_info) + ' mph'
        elif requested_info == 'temperature':
            message = 'The temperature is currently ' + str(actual_desired_info) + '°F right now in ' + location_string
        elif json_weather_specifier == "hourly":
            message = 'The forecast calls for ' + str(actual_desired_info).lower().replace('.', "") + ' in ' + location_string
        else:
            message = 'It is currently ' + str(actual_desired_info).lower() + ' in ' + location_string

        # Send the actual text message
        resp = MessagingResponse().message(str(message + " \n\n- Data provided by the wonderful DarkSky API"))
        return str(resp)

if __name__ == "__main__":
    app.run(debug=False)
