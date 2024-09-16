import re
from datetime import datetime
import pytz
import tkinter as tk
from tkinter import filedialog, scrolledtext
import webbrowser
from requests_oauthlib import OAuth1Session
import os
import json
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Get Twitter API credentials from .env
CONSUMER_KEY = os.getenv("CONSUMER_KEY")
CONSUMER_SECRET = os.getenv("CONSUMER_SECRET")

# Global variables for access tokens
access_token = None
access_token_secret = None
authorization_url = None  # Store the authorization URL

# Function to open the authorization URL in a browser
def open_authorization_url(event):
    if authorization_url:
        webbrowser.open_new(authorization_url)

# Function to handle OAuth1 authorization flow
def oauth_authorization():
    global access_token, access_token_secret, authorization_url

    # Get request token
    request_token_url = "https://api.twitter.com/oauth/request_token?oauth_callback=oob&x_auth_access_type=write"
    oauth = OAuth1Session(CONSUMER_KEY, client_secret=CONSUMER_SECRET)

    try:
        fetch_response = oauth.fetch_request_token(request_token_url)
    except ValueError:
        status_label.config(text="Invalid consumer key or secret.")
        return

    resource_owner_key = fetch_response.get("oauth_token")
    resource_owner_secret = fetch_response.get("oauth_token_secret")
    print("Got OAuth token: %s" % resource_owner_key)

    # Get authorization
    base_authorization_url = "https://api.twitter.com/oauth/authorize"
    authorization_url = oauth.authorization_url(base_authorization_url)
    
    # Display authorization URL for user to visit
    auth_label.config(text=f"Please go here and authorize:")
    auth_link_label.config(text=authorization_url, fg="blue", cursor="hand2")
    auth_link_label.bind("<Button-1>", open_authorization_url)

    # Show the PIN entry and submit button
    pin_entry_label.pack(pady=5)
    pin_entry.pack(pady=5)
    submit_pin_button.pack(pady=5)

    # Function to process PIN submission and get access tokens
    def get_pin_and_authorize():
        verifier = pin_entry.get()

        # Get the access token
        access_token_url = "https://api.twitter.com/oauth/access_token"
        oauth = OAuth1Session(
            CONSUMER_KEY,
            client_secret=CONSUMER_SECRET,
            resource_owner_key=resource_owner_key,
            resource_owner_secret=resource_owner_secret,
            verifier=verifier,
        )
        oauth_tokens = oauth.fetch_access_token(access_token_url)

        global access_token, access_token_secret
        access_token = oauth_tokens["oauth_token"]
        access_token_secret = oauth_tokens["oauth_token_secret"]

        status_label.config(text="OAuth Authorization Successful!")

    # Configure the submit button command
    submit_pin_button.config(command=get_pin_and_authorize)

# Function to post tweet after authorization
def post_to_twitter(text):
    global access_token, access_token_secret

    if access_token and access_token_secret:
        oauth = OAuth1Session(
            CONSUMER_KEY,
            client_secret=CONSUMER_SECRET,
            resource_owner_key=access_token,
            resource_owner_secret=access_token_secret,
        )

        payload = {"text": text}
        response = oauth.post("https://api.twitter.com/2/tweets", json=payload)

        if response.status_code != 201:
            status_label.config(text=f"Failed to post tweet: {response.status_code} {response.text}")
        else:
            status_label.config(text="Successfully posted to Twitter!")
    else:
        status_label.config(text="Please authorize first!")

# Function to convert from UTC +8 to UTC +0
def convert_to_utc(datetime_str):
    date_format = "%Y/%m/%d %H:%M:%S"
    local_time = datetime.strptime(datetime_str, date_format)
    timezone = pytz.timezone('Asia/Manila')
    local_time = timezone.localize(local_time)
    utc_time = local_time.astimezone(pytz.utc)
    return utc_time

# Function to process the schedule file
def process_schedule(file_path):
    on_off_schedule = []
    header_pattern = re.compile(r"##### ARU (ON|OFF)")
    datetime_pattern = re.compile(r"#SC_DATE=(\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2})")

    with open(file_path, 'r') as file:
        lines = file.readlines()
        status = None
        datetime_str = None

        for line in lines:
            header_match = header_pattern.search(line)
            if header_match:
                status = header_match.group(1)
            
            datetime_match = datetime_pattern.search(line)
            if datetime_match and status:
                datetime_str = datetime_match.group(1)
                utc_datetime = convert_to_utc(datetime_str)
                on_off_schedule.append({
                    "status": status,
                    "UTC8": datetime_str,
                    "UTC0": utc_datetime
                })
                status = None
                datetime_str = None
    return on_off_schedule

# Function to format the schedule into chunks of 280 characters
def format_schedule(schedule):
    output_chunks = []
    current_chunk = "PO-101 will be active for the following schedules in UTC + 0:\n\n"
    
    for i in range(0, len(schedule), 2):
        if i + 1 < len(schedule):
            on_event = schedule[i]
            off_event = schedule[i + 1]
            on_date = on_event['UTC0'].strftime("%Y/%m/%d")
            on_time = on_event['UTC0'].strftime("%H:%M")
            off_date = off_event['UTC0'].strftime("%Y/%m/%d")
            off_time = off_event['UTC0'].strftime("%H:%M")
            schedule_entry = f"{on_date} - {off_date}\n{on_time} - {off_time}\n\n"

            # Check if adding the new entry exceeds 280 characters
            if len(current_chunk) + len(schedule_entry) + len("73 de DW4TA\n") > 220:
                # Add the closing and save current chunk
                current_chunk += "73 de DW4TA\n"
                output_chunks.append(current_chunk)
                
                # Start a new chunk
                current_chunk = "PO-101 will be active for the following schedules in UTC + 0:\n\n"
            
            current_chunk += schedule_entry
    
    # Add the final chunk if it contains content
    if current_chunk.strip():
        current_chunk += "73 de DW4TA\n"
        output_chunks.append(current_chunk)

    # Join the chunks with separators
    final_output = "\n----------------------------------------\n".join(output_chunks)
    return final_output

# Function to load the file and process the schedule
def load_file():
    file_path = filedialog.askopenfilename(title="Select Commands Text File")
    if file_path:
        schedule = process_schedule(file_path)
        formatted_schedule = format_schedule(schedule)
        display_schedule(formatted_schedule)

# Function to display the schedule in the text box
def display_schedule(text):
    schedule_textbox.delete(1.0, tk.END)
    schedule_textbox.insert(tk.END, text)

# Function to get the text from the tweet text box and post it to Twitter
def send_tweet():
    tweet_text = tweet_textbox.get("1.0", tk.END).strip()  # Get text from the Tweet Content Text Box
    if len(tweet_text) > 0 and len(tweet_text) <= 280:
        post_to_twitter(tweet_text)
    else:
        status_label.config(text="Error: Tweet exceeds 280 characters or is empty.")

# Create the main window
root = tk.Tk()
root.title("ARU Schedule Processor")

# Create a button to select the file
select_file_button = tk.Button(root, text="Select Schedule File", command=load_file)
select_file_button.pack(pady=10)

# Create a text box to display the schedule (This is for the output from the .txt file)
schedule_textbox = scrolledtext.ScrolledText(root, width=50, height=10)
schedule_textbox.pack(padx=10, pady=10)

# Create a separate text box for typing/pasting content to tweet (This is for the tweet content)
tweet_textbox = scrolledtext.ScrolledText(root, width=50, height=5)
tweet_textbox.pack(padx=10, pady=10)

# Button to authorize Twitter OAuth
authorize_button = tk.Button(root, text="Authorize Twitter", command=oauth_authorization)
authorize_button.pack(pady=5)

# Label to display the authorization message
auth_label = tk.Label(root, text="")
auth_label.pack(pady=5)

# Clickable link for authorization
auth_link_label = tk.Label(root, text="", fg="blue", cursor="hand2")
auth_link_label.pack(pady=5)

# Entry for the PIN and its label (initially hidden)
pin_entry_label = tk.Label(root, text="Enter PIN:")
pin_entry = tk.Entry(root)

# Button to submit the PIN (initially hidden)
submit_pin_button = tk.Button(root, text="Submit PIN")

# Button to post the content of the tweet text box to Twitter
post_button = tk.Button(root, text="Post to Twitter", command=send_tweet)
post_button.pack(pady=5)

# Label to display the status of the tweet posting
status_label = tk.Label(root, text="")
status_label.pack(pady=5)

# Run the GUI application
root.mainloop()
