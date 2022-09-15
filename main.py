from http.client import NotConnected
# from os import fdatasync
import time
import requests
import datetime
import pytz
import os.path
import pandas as pd

import tweepy
from config import bearer_token, api_key, api_key_secret, access_token, access_token_secret, cals, cafe_hours

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
            'C:/Users/grace/Desktop/knowledge/tutorials/APIs/boffee/credentials.json', SCOPES)
        creds = flow.run_local_server(port=0)
    # Save the credentials for the next run
    with open('token.json', 'w') as token:
        token.write(creds.to_json())

def check_today(cal_id, verbose = False):
    """checks if there is an event today in the specified calender id. 
    if there is, it gets the start and end times of the event."""
    workingtoday = False
    shift = None
    try:
        service = build('calendar', 'v3', credentials=creds)

        # Call the Calendar API
        now = datetime.datetime.utcnow().isoformat() + 'Z'  # 'Z' indicates UTC time
        events_result = service.events().list(calendarId=cal_id, timeMin=now,
                                                maxResults=3, singleEvents=True,
                                                orderBy='startTime').execute()

        events = events_result.get('items', [])
        if verbose:
            print('cal id:', cal_id)
        for event in events:
            start = event['start'].get('dateTime', event['start'].get('date'))
            date = start[:10]
            if str(datetime.date.today()) == date:
                workingtoday = True
                ## get the shift time
                end = event['end'].get('dateTime', event['start'].get('date'))
                start_hour = datetime.datetime.strptime(start, "%Y-%m-%dT%H:%M:%S%z")
                end_hour = datetime.datetime.strptime(end, "%Y-%m-%dT%H:%M:%S%z")
                shift = (start_hour, end_hour)
                if verbose:
                    print(event['start'],'(today)', event['summary'])
            else:
                if verbose:
                    print(event['start'], event['summary'])
    except HttpError as error:
        print('An error occurred: %s' % error)
    return workingtoday, shift

# build dictionary of everyone's shifts today
total_working = 0
whos_working = {}
specific = False
for person in cals:
    workingtoday, shift = check_today(person['id'])
    person['workingtoday'] = workingtoday
    total_working += person['workingtoday']
    if person['workingtoday']:
        whos_working[person["name"]] = {"shift":shift, 'worksat':person['worksat']}
        # print(person["name"], "is working today.")

#### BUILDING TWEET ############################################################################
def shift_nonspecific(whos_working, person, start, end):
    """turns shift hours into a sentence."""
    opening, closing = cafe_hours[str(whos_working[person]['worksat'])]
    start, end = start.hour, end.hour
    cafe = whos_working[person]['worksat']
    # opening closing
    if start <= opening and end >= closing:
        person_res = person + " is working all day at " + cafe
    elif  start <= opening:
        person_res = person + " is opening at " + cafe
    elif end >= closing:
        person_res = person + " is closing at " + cafe
    # morning afternoon evening
    elif start <= 10 and end < 13:
        person_res = person + " is working in the morning at " + cafe
    elif start >= 12 and end <= 4:
        person_res = person + " is working in the afternoon at " + cafe
    elif start >= 5 and end <= 7:
        person_res = person + " is working in the evening at " + cafe
    elif start >= 7:
        person_res = person + " is working at night at " + cafe
    # morning to afternoon to evening *!
    else:
        time_periods = {{0,1,2,3,4,5,6,7,8}:"early morning", {9,10,11}:"late morning", {12,13,14}:"afternoon",{15}:"late afternoon",{16,17,18,19}:"evening",{20,21}:"night",{22,23,23}:"late night"}
        for period in time_periods:
            if start in period:
                start_period = time_periods[period]
            if end in period:
                end_period = time_periods[period]
        person_res = person + " is working " + start_period + " to " + end_period + " at " + cafe
    return person_res

def shift_to_sentence(person, specific = False):
    """takes a person's shift and turns it into a sentence"""
    start, end = whos_working[person]['shift'][0], whos_working[person]['shift'][1]
    cafe = whos_working[person]['worksat']
    res = ""
    if specific:
        start, end = start.strftime("%#I:%M%p"), end.strftime("%#I:%M%p")
        res = person + " is working from " + start + " to " + end + " at " + cafe
    if not specific:
        res = shift_nonspecific(whos_working, person, start, end)
    return res

if total_working == 0:
    res = "no friends are working today."
else:
    res = "Today, "
    for person in whos_working:
        person_res = shift_to_sentence(person, specific = False)
        if len(whos_working) == 1: # one person working
            res = res + person_res + "."
        elif person == list(whos_working)[0]: # first person working (Today, \ngrace is working in the morning at gob,)
            res = res + "\n" + person_res + ","
        elif person != list(whos_working)[-1]: # not the first or the last person (\nsahar is closing at ex,)
            res = res + "\n" + person_res +","
        else:
            res = res + "\n" + "and " + person_res + "." # last person (\nand kevin is working at night at harper.)
#### TWEET ####################################################################################

# twitter_api.update_status(res)
print(f"tweeted \"{res}\" at ".format(res) + str(datetime.datetime.now()))