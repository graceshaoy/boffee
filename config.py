# from twitter
bearer_token = "bearer token"
api_key = "api key"
api_key_secret = "api key secret"
access_token = "access token"
access_token_secret = "access token secret"
client_id = "client id"
client_secret = "client secret"

# specific calendar ids to use
barista1 = {"name":"barista1","id":"barista1 calendar id", "worksat":"cafe1","workingtoday":"false"}
barista2 = {"name":"barista2", "id":"barista2 calendar id", "worksat":"cafe2","workingtoday":"false"} # etc.
cals = [barista1, barista2]

cafe_hours = {"cafe1":(7,16), "cafe2":(9,23)}
for cafe in cafe_hours:
    if cafe_hours[cafe][0] > cafe_hours[cafe][1]:
        raise ValueError ('cafe cannot open after it closes.')
    if cafe_hours[cafe][0] == cafe_hours[cafe][1]:
        raise ValueError('cafe cannot open when it closes.')