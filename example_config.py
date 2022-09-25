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

cafe_hours = {"cafe1":{"M":(7,21),"T":(7,21),"W":(7,21),"U":(7,21),"F":(7,21)}, "cafe2":{"M":(8,22),"T":(8,22),"W":(8,22),"U":(8,22),"F":(8,17),"S":(12,17)}}
for cafe in cafe_hours:
    for day in cafe_hours[cafe]:
        start, end = cafe_hours[cafe][day]
        if start > end:
            raise ValueError ('cafe cannot open after it closes.')
        if start == end:
            raise ValueError('cafe cannot open when it closes.')

username = "twitter username"