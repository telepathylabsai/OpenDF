import datetime

from opendf.defs import get_system_date

# this does not work yet, but gives an example how input may look like
# doesn't really make sense to use this for SMCalFlow... maybe do this for MultiWOZ?

dialogs = [
    # 0 - search and create meeting
    [
        "When is my meeting with John on Wednesday?",
        "create a meeting with John at 9AM",
        "make it 2 hours",
        "that's good.",
    ],
    # 1
    [
        # "I need you to get Conference Room B booked for a meeting to discuss analytics on Thursday at 4PM for one hour"
        # "   - Jeff and John will be in the meeting",
        # "yes",
        # "Schedule a Lunch Meeting with Dennis, Gabriel, and Max at the Chili's on 15th street at 12:15 pm.",
        # "That looks great.",
        # "Thanks, also add Jane to Lunch meeting on Tuesday June 4 at 12:15 pm at Chili's on 15th street.",
        # "Yes, that is right.",
    ],
]

# the calendar start from real 'now', so date preferences should be in future
today = get_system_date()
tue = today + datetime.timedelta(days=1 - today.weekday(), weeks=1)
wed = tue + datetime.timedelta(days=1)
TUE = '%d-%02d-%02d' % (tue.year, tue.month, tue.day)
WED = '%d-%02d-%02d' % (wed.year, wed.month, wed.day)

nlu_results = {
    "When is my meeting with John on Wednesday?":
        {'intent': ['findEvent:findTime'],
         'tree': ['date("WEDNESDAY"[DayOfWeek])', 'event(attendees(name("John"[PersonName])))']},
    "create a meeting with John at 9AM":
        {'intent': 'createEvent',
         'tree': ['event(attendees(name("John"[PersonName])),'
                  'start(date("SATURDAY"[DayOfWeek]), time(NumberPM(number(2[Number])))),'
                  'subject("20th annual chili cook off"[String]))', ]},
    "make it 2 hours": {'tree': ['duration(2[Number])']},
    "that's good.": {'tree': ['confirm(accept)']},
}
