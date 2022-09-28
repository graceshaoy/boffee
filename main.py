from http.client import NotConnected
# from os import fdatasync
import datetime
from operator import truediv
import os.path

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
# The file token.json stores the user's access and refresh tokens, and is created automatically when the authorization flow completes for the first time.
if os.path.exists('token.json'):
    creds = Credentials.from_authorized_user_file('token.json', SCOPES)
# If there are no (valid) credentials available, let the user log in.
if not creds or not creds.valid:
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    else:
        flow = InstalledAppFlow.from_client_secrets_file(
            path_prefix + 'credentials.json', SCOPES)
        creds = flow.run_local_server(port=0)
    # Save the credentials for the next run
    with open('token.json', 'w') as token:
        token.write(creds.to_json())

def check_today(cal_id, verbose = False):
    """checks if there is an event today in the specified calender id. 
    if there is, it gets the start and end times of the event."""
    workingtoday = False
    shifts = []
    try:
        service = build('calendar', 'v3', credentials=creds)

        # Call the Calendar API
        today = datetime.datetime.today().isoformat() + 'Z'  # 'Z' indicates UTC time
        events_result = service.events().list(calendarId=cal_id, timeMin=today,
                                                maxResults=3, singleEvents=True,
                                                orderBy='startTime').execute()

        events = events_result.get('items', [])
        if verbose:
            print('cal id:', cal_id)
        for event in events:
            start = event['start'].get('dateTime', event['start'].get('date'))
            date = start[:10]
            if str(datetime.date.today()) == date and event['summary'] != "chd":
                workingtoday = True
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
    return workingtoday, shifts

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
weekday = datetime.datetime.today().weekday()
if weekday == 0: weekday = "M"
if weekday == 1: weekday = "T"
if weekday == 2: weekday = "W"
if weekday == 3: weekday = "H"
if weekday == 4: weekday = "F"
if weekday == 5: weekday = "S"
if weekday == 6: weekday = "U"
total_working = 0
whos_working = {}
specific = False
for person in cals:
    workingtoday, shifts = check_today(person['id'])
    person['workingtoday'] = workingtoday
    total_working += person['workingtoday']
    if person['workingtoday']:
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

def write_pres(name, shifts, cafe):
    for i,s in enumerate(shifts):
        if i == 0:
            person_res = name + " is "
        start, end = s
        shift_res = write_shift(name, start, end, specific = False)
        # grammar for opening / closing / all day
        if (shift_res.find("all day") != -1 or shift_res.find("opening") != -1 or shift_res.find("closing") != -1):
            if shift_res.find("to") != -1:
                if shift_res.find("opening") != -1:
                    person_res = person_res + "working open " + shift_res[shift_res.find("to"):]
                if shift_res.find("closing") != -1:
                    person_res = person_res + "working " + shift_res[:shift_res.find("to")] + "to close"
            elif shift_res.find("opening") != -1 and len(shifts) != 1:
                person_res = person_res + "working open"
            elif shift_res == "all day":
                person_res = person_res + "working " + shift_res
            else:
                person_res = person_res + shift_res
        # grammar for first / only shift
        elif len(shifts) == 1 or i == 0:
            person_res = person_res + "working in the " + shift_res
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

def write_tweet(pres_list):
    for i,pres in enumerate(pres_list):
        if i == 0:
            res = "today, "
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
    res = "no friends are working today."
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
    sendtweet = twitter_api.update_status(tweet1)
    twitter_api.update_status(tweet2, in_reply_to_status_id = sendtweet.id, auto_populate_reply_metadata = True)
    print(f"tweeted \"{tweet1}\n....\n{tweet2}\" at ".format(tweet1, tweet2) + str(datetime.datetime.now()))
else:
    twitter_api.update_status(res)
    print(f"tweeted \"{res}\" at ".format(res) + str(datetime.datetime.now()))