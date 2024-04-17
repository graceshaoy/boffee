from http.client import NotConnected
# from os import fdatasync
import datetime
from operator import truediv
import os.path
import pickle

import tweepy
from config import bearer_token, api_key, api_key_secret, access_token, access_token_secret, cals, cafe_hours, path_prefix

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

client = tweepy.Client(bearer_token, api_key, api_key_secret, access_token, access_token_secret)
auth = tweepy.OAuth1UserHandler(api_key, api_key_secret, access_token, access_token_secret)
twitter_api = tweepy.API(auth)

SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']

#### GETTING INFO FROM GCAL #############################################################################
creds = None
path = 'C:\\Users\\grace\\Desktop\\for_me\\APIs\\boffee\\'
os.chdir(path)

# The file token.json stores the user's access and refresh tokens, and is created automatically when the authorization flow completes for the first time.
if os.path.exists('token.json'):
    creds = Credentials.from_authorized_user_file('token.json', SCOPES)
# If there are no (valid) credentials available, let the user log in.
if not creds or not creds.valid:
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    else:
        flow = InstalledAppFlow.from_client_secrets_file(
            'credentials.json', SCOPES)
        creds = flow.run_local_server(port=0)
    # Save the credentials for the next run
    with open('token.json', 'w') as token:
        token.write(creds.to_json())

def tweeted_last_night(): # actually checking if im tweeting current day or next day
    last_tweet_time = pickle.load(open("C:\\Users\\grace\\Desktop\\for_me\\APIs\\boffee\\last_tweet_time.pickle", "rb"))
    last_hour, last_day = last_tweet_time.hour, last_tweet_time.day
    now_hour, now_day = datetime.datetime.now().hour, datetime.datetime.now().day

    if last_hour < 20 and now_hour <20 and last_day != now_day: # both before 8pm
        return False
    if last_hour >= 20 and now_hour >= 20 and last_day != now_day: # both after 8pm
        return True
    if last_day == now_day: # same day
        if last_hour < 20 and now_hour >= 20: # last tweet before 8pm, now after 8pm
            return True
    return False

boffee_ontime = tweeted_last_night()

def check_day(cal_id, tomorrow = boffee_ontime, verbose = False):
    """checks if there is an event in the specified calender id. 
    if there is, it gets the start and end times of the event."""
    workingday = False
    shifts = []
    try:
        service = build('calendar', 'v3', credentials=creds)

        # Call the Calendar API
        if tomorrow:
            day = datetime.datetime.combine(datetime.date.today(), datetime.time(0,0)) + datetime.timedelta(days=1)
        else:
            day = datetime.datetime.combine(datetime.date.today(), datetime.time(0,0))
        daystring = (day).isoformat() + 'Z'
                
        events_result = service.events().list(calendarId=cal_id, timeMin=daystring,
                                                maxResults=3, singleEvents=True,
                                                orderBy='startTime').execute()

        events = events_result.get('items', [])
        if verbose:
            print('cal id:', cal_id)
        for event in events:
            start = event['start'].get('dateTime', event['start'].get('date'))
            date = start[:10]
            if date == str(day.date()):
                workingday = True
                ## get the shift time
                end = event['end'].get('dateTime', event['start'].get('date'))
                start_hour = datetime.datetime.strptime(start, "%Y-%m-%dT%H:%M:%S%z")
                end_hour = datetime.datetime.strptime(end, "%Y-%m-%dT%H:%M:%S%z")
                shifts.append((start_hour, end_hour))
                if verbose:
                    print(event['start'],'(today)', event['summary'])
            else:
                if verbose:
                    print(event['start'], event['summary'])
    except HttpError as error:
        print('An error occurred: %s' % error)
    return workingday, shifts

# build dictionary of everyone's shifts today
time_periods = {}
for i in range(0,9):
    time_periods[i] = (1,"early morning")
for i in range(9,12):
    time_periods[i] = (1.25,"late morning")
for i in range(12,15):
    time_periods[i] = (2,"afternoon")
time_periods[15] = (2.25,"late afternoon")
for i in range(16,20):
    time_periods[i] = (3,"evening")
for i in range(20,22):
    time_periods[i] = (4,"night")
for i in range(21,25):
    time_periods[i] = (4.25,"late night")
weekday = (datetime.datetime.today() + datetime.timedelta(days=1)).weekday()
if weekday == 0: weekday = "M"
if weekday == 1: weekday = "T"
if weekday == 2: weekday = "W"
if weekday == 3: weekday = "H"
if weekday == 4: weekday = "F"
if weekday == 5: weekday = "S"
if weekday == 6: weekday = "U"
total_working = 0
whos_working = {}
for person in cals:
    workingday, shifts = check_day(person['id'])
    person['workingday'] = workingday
    total_working += person['workingday']
    if person['workingday']:
        whos_working[person["name"]] = {"shifts":shifts, 'worksat':person['worksat']}
        # print(person["name"], "is working today.")
        if len(whos_working[person["name"]]["shifts"]) > 1:
            simple_shifts = []
            for i, current in enumerate(whos_working[person["name"]]["shifts"][:-1]):
                next = whos_working[person["name"]]["shifts"][i+1]
                if time_periods[current[1].hour] == time_periods[next[0].hour]:
                    simple_shifts.append((current[0],next[1]))
                    whos_working[person["name"]]["shifts"] = simple_shifts
#### BUILDING TWEET ############################################################################
def shift_nonspecific(whos_working, person, start, end):
    """turns shift hours into words."""
    opening, closing = cafe_hours[str(whos_working[person]['worksat'])][weekday]
    start, end = start.hour, end.hour
    # opening closing
    if start <= opening and end >= closing:
        res = "all day"
    elif  start <= opening and end <= opening + 2:
        res = "opening"
    elif end >= closing and start >= closing - 2:
        res = "closing"
    # morning to afternoon to evening
    else:
        if start <= opening:
            start_block, start_period = 0, "opening"
        else:
            start_block, start_period = time_periods[start]
        if end >= closing:
            end_block, end_period = 5, "closing"
        else:
            end_block, end_period = time_periods[end]
        # simplifying
        if start_block == end_block:
            res = start_period
        elif start_block - end_block == -0.25:
            if start_block == 1:
                res = "morning"
            elif start_block == 2:
                res = "afternoon"
            elif start_block == 4:
                res = "night"
        else:
            res = start_period + " to the " + end_period
    return res

def write_shift(person, start, end, specific = False):
    """turns datetime into text"""
    if specific:
        start, end = start.strftime("%#I:%M%p"), end.strftime("%#I:%M%p")
        res = start + " to " + end
    if not specific:
        res = shift_nonspecific(whos_working, person, start, end)
    return res

def write_pres(name, shifts, cafe, specific = False):
    for i,s in enumerate(shifts):
        if i == 0:
            person_res = name + " is "
        start, end = s
        shift_res = write_shift(name, start, end, specific = specific)
        # grammar for opening / closing / all day
        if (shift_res.find("all day") != -1 or shift_res.find("opening") != -1 or shift_res.find("closing") != -1):
            if shift_res.find("to") != -1:
                if shift_res.find("opening") != -1:
                    person_res = person_res + "working open " + shift_res[shift_res.find("to"):]
                if shift_res.find("closing") != -1 and i==0:
                    person_res = person_res + "working " + shift_res[:shift_res.find("to")] + "to close"
                if shift_res.find("closing") != -1 and i!=0:
                    person_res = person_res + " and " + shift_res[:shift_res.find("to")] + "to close"
            elif shift_res.find("opening") != -1 and len(shifts) != 1:
                person_res = person_res + "working open"
            elif shift_res == "all day":
                person_res = person_res + "working " + shift_res
            else:
                person_res = person_res + shift_res
        # grammar for first / only shift
        elif len(shifts) == 1 or i == 0:
            person_res = person_res + "working "
            if not specific:
                person_res = person_res + "in the "
            person_res = person_res + shift_res
        # grammar for second shift
        elif len(shifts) == 2:
            if i == 1:
                person_res = person_res + " and " + shift_res
        # grammar for following shifts
        elif len(shifts) > 2:
            if i == len(shifts) - 1:
                person_res = person_res + ", and " + shift_res
            else:
                person_res = person_res + ", " + shift_res
        # at cafe
        if i == len(shifts) - 1:
            person_res = person_res + " at " + cafe
    return person_res

def check_together(pres_list): #*! use bigrams
    simple_pres_list = []
    for i,pres in enumerate(pres_list[:-1]):
        name, next_name = pres.split(" ")[0], pres_list[i+1].split(" ")[0]
        pres_shift, next_pres_shift = pres.split("working")[1], pres_list[i+1].split("working")[1]
        pres_shift, next_pres_shift = pres_shift.replace(" late","").replace(" early",""), next_pres_shift.replace(" late","").replace(" early","")
        if pres_shift == next_pres_shift:
            pres_shift = name + " and " + next_name + " are working" + pres_shift
            next_pres_shift = ""
            simple_pres_list.append(pres_shift)
        else:
            simple_pres_list.append(pres)
    simple_pres_list = [x for x in simple_pres_list if x]
    return simple_pres_list

def write_tweet(pres_list):
    # if len(pres_list) > 1:
    #     pres_list = check_together(pres_list)
    for i,pres in enumerate(pres_list):
        if i == 0:
            if boffee_ontime:
                res = "tomorrow, "
            else:
                res = "today (boffee slept early last night), "
        if len(pres_list) == 1: # only person
            res = res + pres + "."
        elif i == 0: # first person
            res = res + pres + ","
        elif i != len(pres_list) - 1: # inbtwn people
            res = res + "\n" + pres +","
        else:
            res = res + "\n" + "and " + pres + "." # last people
    return res

def sort_helper(x):
    return x['first_hour']

if total_working == 0:
    if boffee_ontime:
        res = "no friends are working tomorrow."
    else:
        res = "today (boffee slept early last night), no friends are working."
else:
    pres_dicts = []
    for name in whos_working:
        shifts = whos_working[name]['shifts']
        cafe = whos_working[name]['worksat']
        first_hour = shifts[0][0].hour
        pres_dicts.append({'pres':write_pres(name, shifts, cafe), 'first_hour':first_hour})
    pres_dicts.sort(key=sort_helper)
    pres_list = [d['pres'] for d in pres_dicts]
    res = write_tweet(pres_list)

#### TWEET ####################################################################################
# res = "Today, one is working in the evening and closing at gob, \ntwo is working in the evening and closing at gob, \nthree is working in the evening and closing at gob, \nfour is working in the evening and closing at gob, \nfive is working in the evening and closing at gob, \nand six is working in the evening and closing at gob."
if len(res) > 280:
    check = res[:272].splitlines(True)
    separator = len(check[-1])
    tweet1 = res[:272-separator] + "(cont...)"
    tweet2 = res[272-separator:]
    sendtweet = client.create_tweet(text=tweet1)
    client.create_tweet(text=tweet2, in_reply_to_status_id = sendtweet.id, auto_populate_reply_metadata = True)
    pickle.dump(datetime.datetime.now(), open("C:\\Users\\grace\\Desktop\\for_me\\APIs\\boffee\\last_tweet_time.pickle", "wb"))
    print(f"tweeted \"{tweet1}\n....\n{tweet2}\" at ".format(tweet1, tweet2) + str(datetime.datetime.now()))
else:
    # sendtweet = client.create_tweet(text=res)
    # pickle.dump(datetime.datetime.now(), open("C:\\Users\\grace\\Desktop\\for_me\\APIs\\boffee\\last_tweet_time.pickle", "wb"))
    print(f"tweeted \"{res}\" at ".format(res) + str(datetime.datetime.now()))