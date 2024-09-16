import re
from datetime import datetime
import pytz

# Function to convert from UTC +8 to UTC +0
def convert_to_utc(datetime_str):
    # Define the format of the datetime string in the text
    date_format = "%Y/%m/%d %H:%M:%S"
    
    # Parse the string into a datetime object
    local_time = datetime.strptime(datetime_str, date_format)
    
    # Set the timezone to UTC +8 (Asia/Manila)
    timezone = pytz.timezone('Asia/Manila')
    local_time = timezone.localize(local_time)  # Localize the datetime to UTC+8
    
    # Convert to UTC (UTC +0)
    utc_time = local_time.astimezone(pytz.utc)
    
    # Return the UTC datetime object
    return utc_time

# Function to process the schedule file
def process_schedule(file_path):
    on_off_schedule = []

    # Regular expressions to match ON/OFF headers and datetime
    header_pattern = re.compile(r"##### ARU (ON|OFF)")
    datetime_pattern = re.compile(r"#SC_DATE=(\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2})")

    with open(file_path, 'r') as file:
        lines = file.readlines()  # Read all lines
        
        # Initialize variables to store header and datetime
        status = None
        datetime_str = None

        for line in lines:
            # Check if the line is a header (ON or OFF)
            header_match = header_pattern.search(line)
            if header_match:
                status = header_match.group(1)  # Capture ON or OFF
            
            # Check if the line contains the datetime
            datetime_match = datetime_pattern.search(line)
            if datetime_match and status:
                datetime_str = datetime_match.group(1)  # Capture datetime
                
                # Convert datetime from UTC +8 to UTC +0
                utc_datetime = convert_to_utc(datetime_str)
                
                # Append the event to the schedule list
                on_off_schedule.append({
                    "status": status,
                    "UTC8": datetime_str,
                    "UTC0": utc_datetime
                })
                
                # Reset status and datetime for the next event
                status = None
                datetime_str = None

    return on_off_schedule

# Function to format and print the schedule
def print_schedule(schedule):
    print("PO-101 will be active for the following schedules in UTC + 0:")
    print() # Add an empty line
    
    for i in range(0, len(schedule), 2):  # Iterate in pairs (ON followed by OFF)
        if i + 1 < len(schedule):
            # Extract the ON and OFF events
            on_event = schedule[i]
            off_event = schedule[i + 1]
            
            # Format the dates and times
            on_date = on_event['UTC0'].strftime("%Y/%m/%d")
            on_time = on_event['UTC0'].strftime("%H:%M")
            
            off_date = off_event['UTC0'].strftime("%Y/%m/%d")
            off_time = off_event['UTC0'].strftime("%H:%M")
            
            # Print the formatted schedule
            print(f"{on_date} - {off_date}")
            print(f"{on_time} - {off_time}")
            print()  # Add an empty line between schedule pairs
        
    print("73 de DW4TA")
    
# =============================================================================
# # Example usage
# file_path = 'TU_240908_023843_PHT.txt'  # Replace with the actual file path
# schedule = process_schedule(file_path)
# 
# # Print the schedule in the tweet format
# print_schedule(schedule)
# 
# =============================================================================

# Main script to ask for filename and process the file
if __name__ == "__main__":
    # Ask the user to input the file path
    file_path = input("Enter the commands text filename: ")

    # Process the schedule from the file
    schedule = process_schedule(file_path)

    # Print the schedule in the desired format
    print_schedule(schedule)
