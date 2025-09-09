import re
from datetime import datetime
import pytz
import os
import json
import requests
from requests_oauthlib import OAuth1Session
import streamlit as st

# ---------- Settings ----------
# Put these in .streamlit/secrets.toml on Streamlit Cloud:
# [twitter]
# CONSUMER_KEY = "xxxx"
# CONSUMER_SECRET = "yyyy"

CONSUMER_KEY = st.secrets["twitter"]["CONSUMER_KEY"]
CONSUMER_SECRET = st.secrets["twitter"]["CONSUMER_SECRET"]

# ---------- Helpers ----------
def convert_to_utc(datetime_str: str):
    date_format = "%Y/%m/%d %H:%M:%S"
    local_time = datetime.strptime(datetime_str, date_format)
    timezone = pytz.timezone('Asia/Manila')
    local_time = timezone.localize(local_time)
    return local_time.astimezone(pytz.utc)

def process_schedule(file_text: str):
    on_off_schedule = []
    header_pattern = re.compile(r"##### ARU (ON|OFF)")
    datetime_pattern = re.compile(r"#SC_DATE=(\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2})")

    status = None
    for line in file_text.splitlines():
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
    return on_off_schedule

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

            # Keep headroom under 280 chars for tweet body, using 220 here (as in your code)
            if len(current_chunk) + len(schedule_entry) + len("73 de DW4TA\n") > 220:
                current_chunk += "73 de DW4TA\n"
                output_chunks.append(current_chunk)
                current_chunk = "PO-101 will be active for the following schedules in UTC + 0:\n\n"

            current_chunk += schedule_entry

    if current_chunk.strip():
        current_chunk += "73 de DW4TA\n"
        output_chunks.append(current_chunk)

    final_output = "\n----------------------------------------\n".join(output_chunks)
    return final_output

# ---------- OAuth1 (PIN/OOB) ----------
def start_oauth():
    # request token (with OOB PIN flow)
    request_token_url = "https://api.twitter.com/oauth/request_token?oauth_callback=oob&x_auth_access_type=write"
    oauth = OAuth1Session(CONSUMER_KEY, client_secret=CONSUMER_SECRET)
    fetch_response = oauth.fetch_request_token(request_token_url)
    st.session_state["resource_owner_key"] = fetch_response.get("oauth_token")
    st.session_state["resource_owner_secret"] = fetch_response.get("oauth_token_secret")

    base_authorization_url = "https://api.twitter.com/oauth/authorize"
    authorization_url = oauth.authorization_url(base_authorization_url)
    st.session_state["authorization_url"] = authorization_url

def exchange_pin_for_tokens(pin: str):
    access_token_url = "https://api.twitter.com/oauth/access_token"
    oauth = OAuth1Session(
        CONSUMER_KEY,
        client_secret=CONSUMER_SECRET,
        resource_owner_key=st.session_state.get("resource_owner_key"),
        resource_owner_secret=st.session_state.get("resource_owner_secret"),
        verifier=pin,
    )
    tokens = oauth.fetch_access_token(access_token_url)
    st.session_state["access_token"] = tokens["oauth_token"]
    st.session_state["access_token_secret"] = tokens["oauth_token_secret"]

def post_tweet(text: str):
    if not st.session_state.get("access_token") or not st.session_state.get("access_token_secret"):
        st.error("Please authorize first.")
        return

    oauth = OAuth1Session(
        CONSUMER_KEY,
        client_secret=CONSUMER_SECRET,
        resource_owner_key=st.session_state["access_token"],
        resource_owner_secret=st.session_state["access_token_secret"],
    )
    payload = {"text": text}
    resp = oauth.post("https://api.twitter.com/2/tweets", json=payload)
    if resp.status_code == 201:
        st.success("Successfully posted to Twitter!")
    else:
        st.error(f"Failed to post tweet: {resp.status_code} {resp.text}")

# ---------- UI ----------
st.set_page_config(page_title="ARU Schedule Processor", page_icon="🛰️")

st.title("🛰️ ARU Schedule Processor (Streamlit)")

# File upload & processing
uploaded = st.file_uploader("Select Commands Text File", type=["txt"])
formatted_output = ""
if uploaded is not None:
    file_text = uploaded.read().decode("utf-8", errors="ignore")
    schedule = process_schedule(file_text)
    formatted_output = format_schedule(schedule)

    st.subheader("Formatted Schedule")
    st.text_area("Output", formatted_output, height=200)

# Tweet compose
st.subheader("Compose Tweet")
tweet_text = st.text_area("Tweet Content (max 280 chars)", value="", height=120)
colA, colB = st.columns([1, 1])

with colA:
    if st.button("Get Authorization URL"):
        try:
            start_oauth()
            st.info("Authorization URL generated below. Open it, authorize, then paste the PIN here.")
        except Exception as e:
            st.error(f"OAuth error: {e}")

if st.session_state.get("authorization_url"):
    st.link_button("Open Twitter to Authorize", st.session_state["authorization_url"])

pin = st.text_input("Enter PIN (from Twitter after authorizing)", value="")
with colB:
    if st.button("Submit PIN"):
        if pin.strip():
            try:
                exchange_pin_for_tokens(pin.strip())
                st.success("OAuth Authorization Successful!")
            except Exception as e:
                st.error(f"PIN exchange failed: {e}")
        else:
            st.warning("Please paste the PIN from Twitter.")

st.divider()
# If you want to quickly tweet the formatted schedule chunk (first chunk)
prefill = formatted_output.split("\n----------------------------------------\n")[0] if formatted_output else ""
use_prefill = st.checkbox("Use first formatted schedule chunk as tweet body")
final_tweet = prefill if use_prefill and prefill else tweet_text

st.write(f"Characters: {len(final_tweet)} / 280")
if st.button("Post to Twitter"):
    if 0 < len(final_tweet) <= 280:
        post_tweet(final_tweet)
    else:
        st.error("Tweet is empty or exceeds 280 characters.")
