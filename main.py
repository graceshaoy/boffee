from http.client import NotConnected
# from os import fdatasync
import datetime
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
        # if len(whos_working[person["name"]]["shifts"]) > 1: *!
        #     simple_shifts = []
        #     for i, s in enumerate(whos_working[person["name"]]["shifts"]):
        #         if (whos_working[person["name"]]["shifts"][-1][1] - s[0]).total_seconds()/60 <= 60: # if previous shift ends less than an hr before start of current shift,
        #             simple_shifts.append((whos_working[person["name"]]["shifts"][-1][0], s[1])) # simplify to one shift
        #     whos_working[person["name"]]["shifts"] = simple_shifts

#### BUILDING TWEET ############################################################################
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

def shift_nonspecific(whos_working, person, start, end):
    """turns shift hours into words."""
    opening, closing = cafe_hours[str(whos_working[person]['worksat'])]
    start, end = start.hour, end.hour
    # opening closing
    if start <= opening and end >= closing:
        res = "all day"
    elif  start <= opening and end <= 12:
        res = "opening"
    elif end >= closing and start >=12:
        res = "closing"
    # morning to afternoon to evening
    else:
        if start <= opening:
            start_block, start_period = 0, "opening"
        elif end >= closing:
            end_block, end_period = 5, "closing"
        else:
            start_block, start_period = time_periods[start]
            end_block, end_period = time_periods[end]
        # simplifying
        if start_block == end_block:
            res = start_period
        elif start_block - end_block == 0.25:
            if start_block == 1:
                res = "morning"
            elif start_block == 2:
                res = "afternoon"
            elif start_block == 4:
                res = "night"
        else:
            res = start_period + " to the " + end_period
    return res

def shift_to_sentence(person, start, end, specific = False):
    """turns datetime into text"""
    if specific:
        start, end = start.strftime("%#I:%M%p"), end.strftime("%#I:%M%p")
        res = start + " to " + end
    if not specific:
        res = shift_nonspecific(whos_working, person, start, end)
    return res

if total_working == 0:
    res = "no friends are working today."
else:
    res = "today, "
    for person in whos_working:
        cafe = whos_working[person]['worksat']
        person_res = person + " is "
        shift_words = []
        for i,s in enumerate(whos_working[person]["shifts"]):
            start, end = s
            shift_res = shift_to_sentence(person, start, end, specific = False)
            if i == 0 and (shift_res in {"opening","closing","all day"}):
                person_res = person_res + shift_res + " at " + cafe
            elif len(whos_working[person]["shifts"]) == 1:
                person_res = person_res + "working in the " + shift_res + " at " + cafe
            elif i == 0:
                person_res = person_res + "working in the " + shift_res
            elif len(whos_working[person]["shifts"]) == 2:
                if i == 1:
                    person_res = person_res + " and " + shift_res + " at " + cafe
            elif len(whos_working[person]["shifts"]) > 2:
                if i == len(whos_working[person]["shifts"]) - 1:
                    person_res = person_res + ", and " + shift_res + " at " + cafe
                else:
                    person_res = person_res + ", " + shift_res
        # print(person_res)
        if len(whos_working) == 1: # one person working
            res = res + person_res + "."
        elif person == list(whos_working)[0]: # first person working (today, \ngrace is working in the morning at gob,)
            res = res + "\n" + person_res + ","
        elif person != list(whos_working)[-1]: # not the first or the last person (\nsam is closing at ex,)
            res = res + "\n" + person_res +","
        else:
            res = res + "\n" + "and " + person_res + "." # last person (\nand kevin is working at night at harper.)
#### TWEET ####################################################################################
# res = "test -- tweeting a thread\none the quick brown fox jumped over the lazy dog\ntwo the quick brown fox jumped over the lazy dog\nthree the quick brown fox jumped over the lazy dog\nfour the quick brown fox jumped over the lazy dog\nfive the quick brown fox jumped over the lazy dog\nsix the quick brown fox jumped over the lazy dog"
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