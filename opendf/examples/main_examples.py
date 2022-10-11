"""
Main dialog examples.

The user can select the example by its index, from the command line. The example 0 is for debug.
"""

# noinspection SpellCheckingInspection
dialogs = [
    # 0 - Debug
    [
    # to run multiwoz expressions - add this to the command line call to main.py:  -c resources/multiwoz_2_2_config.yaml
        #'revise_restaurant()',
        'revise_restaurant(food=european, bookpeople=4)',

    ],
    # 1
    [
        'DeleteEvent(AND(starts_at(Tomorrow()), with_attendee(FindManager(John))))'
    ],
    # 2
    [
        # 'CreateEvent(starts_at(Morning()))',
        'CreateEvent(starts_at(NumberAM(9)))',
        'ModifyEventRequest(with_attendee(dan))',
        # 'AcceptSuggestion(2)',
        # 'AcceptSuggestion()',
    ],
    # 3
    [
        'UpdateEvent(AND(ends_at(HourMinuteAm(hours=10,minutes=30)), at_location(jeffs),\
                    starts_at(NextDOW(SUNDAY)),starts_at(NumberAM(10))), \
                    constraint=AND(ends_at(NumberPM(2)),starts_at(NumberAM(11))))',
    ],
    # 4
    [
        'UpdateEvent(event=has_id(4), constraint=starts_at(Time(hour=19)))',
    ],
    # 5
    [
        'FindEvents(starts_at(Morning()))',
        'ModifyEventRequest(starts_at(GT(Time(hour=9, minute=0))))',
    ],
    # 6
    [
        'FindEvents(AND(avoid_start(Morning()), at_location(room3)))',
    ],
    # 7
    [
        'WeatherQueryApi(place=AtPlace(place=FindPlace(Zurich)), time=Today())',
        'WillSnow(table=refer(WeatherTable?()))',
    ],
    # 8
    [
        'FindEvents(Event?(slot=TimeSlot(bound=DateTimeRange('
        'start=DateTime(date=Date(year=2022, month=1, day=5), time=Time(hour=10, minute=0)), '
        'end=DateTime(date=Date(year=2022, month=1, day=6), time=Time(hour=13, minute=0))'
        '))))',
    ],
    # 9
    [
        'FindEvents(Event?(slot=TimeSlot(inter=DateTimeRange('
        'start=DateTime(date=Date(year=2022, month=1, day=5), time=Time(hour=10, minute=0)), '
        'end=DateTime(date=Date(year=2022, month=1, day=6), time=Time(hour=13, minute=0))'
        '))))',
    ],
    # 10
    [
        'GTf(size(FindEvents(with_attendee(jack))), Int(1))'
    ],
    # 11
    [
        'GTf(size(FindEvents(starts_at(GT(singleton(FindEvents(with_attendee(jack))))))), Int(1))',
    ],
]
