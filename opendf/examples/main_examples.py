"""
Main dialog examples.

The user can select the example by its index, from the command line. The example 0 is for debug.
"""

# noinspection SpellCheckingInspection
dialogs = [
    # 0 - Debug
    [

    'AND(TimeSlot?(start=DateTime?(date=Date(year=2022,month=1,day=3))),\
    AND(TimeSlot?(start=GE(DateTime?(time=Time(hour=11,minute=0)))),\
    TimeSlot?(start=LE(DateTime?(time=Time(hour=13,minute=0))))),\
    AND(TimeSlot?(start=DateTime(date=Date(year=2022,month=1,day=3),time=Time(hour=11,minute=0))),\
        TimeSlot?(end=DateTime(date=Date(year=2022,month=1,day=3),time=Time(hour=11,minute=30)))))',


# 'CreateEvent( AND( with_attendee(Dan ) , starts_at(NextDOW(  MONDAY ) ) , starts_at(NumberPM( 4 ) ) ) )' ,
#  'do( Let( x0 , AcceptSuggestion( ) ) ,do(Yield( $ x0 ) ,\
#      DeleteEvent(AND(starts_at(LT(:start( :item( $ x0 ) ) ) ) ,with_attendee(Jerry ) ) ) ) ) ',

        # 'CreateEvent(    AND(       has_duration(          toHours(             2 ) ) ,       has_subject(          dentist appoint ) ,       starts_at(          NextDOW(             TUESDAY ) ) ,       starts_at(          NumberPM(             1 ) ) ) )',
        # #'AcceptSuggestion()',
        # 'do(    Let(       x0 ,       :end(          refer(             Event?(                ) ) ) ) ,    FindEvents(       AND(          starts_at(             :date(                $ x0 ) ) ,          starts_at(             GT(                :time(                   $ x0 ) ) ) ) ) )',
        # 'do(    Let(       x0 ,       :end(          refer(             Event?(                ) ) ) ) ,    FindEvents(       AND(          has_subject(             dinner plans ) ,          starts_at(             :date(                $ x0 ) ) ,          starts_at(             GT(                :time(                   $ x0 ) ) ) ) ) )',
        #

        #':dayOfWeek( :date( :start( FindEvents( has_subject( meeting1 ) ) ) ) ) ',
        #':dayOfWeek(Today())',
        #':day(:date(Now()))',
        #':date(NextDOW( TUESDAY))',
        #':day(:date(NextDOW( TUESDAY)))',
        # 'refer(Node?())'
        #'FindEvents(starts_at(NextDOW( TUESDAY)))',
        #'CreateEvent( AND(starts_at(:end(refer(Event?()))),has_duration(  toHours( 2)) ))',
        #'CreateEvent( AND(starts_at(:end(FindEvents(constraint=Event?() ) ) ),has_duration(  toHours( 2)) ) )',

        #'CreateEvent(AND(has_subject( book a hotel room ), starts_at(LT( :start(FindEvents(starts_at(NextDOW( TUESDAY)))) ) ) ) )'



        # FindEvents( \
        #     AND( \
        #         starts_at( \
        #             NextDOW( \
        #                 TUESDAY)), \
        #         has_subject( \
        #             flight)))) ) ) ) )',


    # 'CreateEvent(\
    #     AND(\
    #        with_attendee(\
    #           Anna ) ,\
    #        starts_at(\
    #           Today(\
    #              ) ) ,\
    #        starts_at(\
    #           NumberPM(\
    #              1 ) ) ) ) ',
    #  'do(\
    #     Let(\
    #        x0 ,\
    #        :end(\
    #           refer(\
    #              Event?(\
    #                 ) ) ) ) ,\
    #     GTf(\
    #        size(\
    #           FindEvents(\
    #              AND(\
    #                 starts_at(\
    #                    :date(\
    #                       $ x0 ) ) ,\
    #                 starts_at(\
    #                    GT(\
    #                       :time(\
    #                          $ x0 ) ) ) ) ) ) ,\
    #        0 ) ) '


#'CreateEvent(AND(has_subject(swimming ) ,starts_at(NextDOW(FRIDAY ) ) ) )',
#'AcceptSuggestion()'

        #'MD(day=10,month=JAN)',

        # 'FindEvents(  AND(   at_time( NextWeekList(  )), has_subject( presentation>xx)))\
        #  do( Let( x0,:end(refer( Event?() ) ) ),GTf(  size( FindEvents( \
        #      AND( starts_at(: date($x0) ),starts_at( GT(: time($x0) ) ) ) ) ),0 ) )'

#'Yield(FindEventWrapperWithDefaults(EventOnDate(date=Tomorrow(), event=Event?(subject=LIKE(train)))))'
#'FindEvents(with_attendee(jane))',

        # 'Mult(2,3)',

        #'refer(Attendee?(recipient=Recipient?(firstName=John)))',
        # '{evs~}FindEvents(with_attendee(jane))',
        # '$evs',
        # 'do(Let(x0, refer(Recipient?(name=John))), FindEvents(AND(with_attendee($x0))))',
        # 'refer(Attendee?(recipient=Recipient?(firstName=John)))',
        # 'FindRecipients(Recipient?(name=john))',

        #'Recipient(name=John)',
        #'do(Let(x0, refer(Recipient?(name=John))), FindEvents(AND(with_attendee($x0))))',
        #'do(Let(x0, refer(Recipient?(John))), FindEvents(AND(with_attendee($x0))))',
         # 'do(Let(x0, refer(Recipient?(#John))), ModifyEventRequest(AND(with_attendee(#Bob), \
         #          with_attendee(FindManager($x0)), with_attendee($x0), with_attendee(#Emily))))',

        #'NumberWeekOfMonth(month=3,num=2)',

        # 'FindManager(refer(Recipient?(name=John)))',
        # 'FindEvents(with_attendee(FindManager(refer(Recipient?(name=John)))))',
        # 'do(Let(x0, refer(Recipient?(name=John))), FindEvents(AND(with_attendee($x0))))',

        # 'GTf(size(FindEvents(with_attendee(vijeta))), Int(1))',
        # 'GTf(size(FindEvents(starts_at(GT(singleton(FindEvents(with_attendee(vijeta))))))), Int(1))',

        #'refer(Recipient?(firstName=John))',
        #'refer(Event?(attendees=ANY(Attendee?(recipient=Recipient?(firstName=John)))))',



        #'refer(Attendee?(recipient=Recipient?(firstName=jane)), multi=True)',
        #'FindAttendees(with_recipient(John))',
        #'FindAttendees(participated_in(FindEvents(with_attendee(John))))',
        #'FindAttendees(participated_in(with_attendee(Jane)))',

        # 'refer(Event?(id=4))',
        # 'refer(Event?(id=5))',
        #'refer(with_attendee(dan), type=Event)'
        # 'refer(clear_attendees())'

        #'FindRecipients(AND(participated_in(with_attendee(John)), participated_in(with_attendee(Jane))))',
        #'FindAttendees(AND(participated_in(with_attendee(John)), participated_in(with_attendee(Jane))))',
        #'refer(Event?(slot=TimeSlot(start=WeekendOfMonth(Jan, 2))), multi=True)',
        # 'inFahrenheit(-50)'
        # 'FindEvents(starts_at(ThisWeekend()))',
        # 'FindEvents(Event?(slot=TimeSlot(bound=DateTimeRange('
        # 'start=DateTime(date=Date(year=2022, month=1, day=6), time=Time(hour=0, minute=0)), '
        # 'end=DateTime(date=Date(year=2022, month=1, day=6), time=Time(hour=13, minute=0))'
        # '))))',
        # 'FindEvents(Event?(slot=TimeSlot(inter=DateTimeRange('
        # 'start=DateTime(date=Date(year=2022, month=1, day=5), time=Time(hour=10, minute=0)), '
        # 'end=DateTime(date=Date(year=2022, month=1, day=6), time=Time(hour=13, minute=0))'
        # '))))',
        # 'UpdateEvent(event=FindEvents(has_id(4)), constraint=shift_start(toHours(1)))',
        # 'UpdateEvent(event=FindEvents(has_id(4)), constraint=shift_end(toHours(1)))',
        # 'FindEvents(AND(starts_at(NumberAM(9))))',
        # 'FindEvents(at_time(DateTime(date=Tomorrow(), time=NumberAM(10))))',
        # 'CreateEvent(AND(starts_at(NumberAM(9)), ends_at(NumberAM(10))))',
        # 'CreateEvent(at_time(DateTime(date=Tomorrow(), time=NumberAM(10))))',
        # 'CreateEvent(AND(at_time(Afternoon()), at_time(NumberPM(4))))',
        # 'FindEvents(AND(at_time(Date(year=2022, month=1, day=6)), at_time(NumberPM(4))))',
        # 'FindEvents(AND(at_time(Date(year=2022, month=1, day=6)), at_time(NumberPM(1))))',
        #'CreateEvent(AND(at_time(Date(year=2022, month=1, day=6)), at_time(Time(hour=1))))',


        # 'CreateEvent(AND(at_time(Date(year=2022, month=1, day=6)), at_time(Time(hour=9))))',
        # 'ModifyEventRequest(AND(with_attendee(dan), with_attendee(john)))',
        # 'FindEvents(AND(with_attendee(dan), with_attendee(john)))',
        # 'ModifyEventRequest(clear_attendees())',
        # 'ModifyEventRequest(with_attendee(Empty()))',
        # 'ModifyEventRequest(Event?(attendees=Empty()))',
        # 'ModifyEventRequest(with_attendee(jane))',
        # 'AcceptSuggestion()',

        # 'CreateEvent(AND(with_attendee(dan), with_attendee(john)))',
        # 'FindEvents(AND(with_attendee(dan), with_attendee(adam)))',

        #'GTf(size(SET(Int(0), Int(1))), Int(1))'

        # 'GTf(size(FindEvents(with_attendee(vijeta))), Int(1))',
        # 'Exists(FindEvents(with_attendee(dan)))',
        # 'GTf(size(FindEvents(starts_at(GT(singleton(FindEvents(with_attendee(jack))))))), Int(1))',

        #'FindEvents(EXACT(with_attendee(dan), with_attendee(adam)))',
        # 'FindEvents(NONE(SET(with_attendee(dan), with_attendee(jane), at_location(room5))))',
        # 'FindEvents(Event?())',
        # 'ModifyEventRequest(NONE(SET(with_attendee(dan), with_attendee(adam))))',
        # 'ModifyEventRequest(at_time(Date(year=2022, month=1, day=6)))',
        # 'ModifyEventRequest(AND(at_time(Date(year=2022, month=1, day=6)), at_time(Time(hour=9))))',
        # 'ModifyEventRequest(empty_event_field(attendees))',
        # 'ModifyEventRequest(at_location(room))',
        # 'ModifyEventRequest(empty_event_field(location))',
        # 'ModifyEventRequest(clear_event_field(subject))',
        # 'ModifyEventRequest(has_subject(party))',
        # 'ModifyEventRequest(clear_event_field(subject))',
        # 'ModifyEventRequest(Event?(attendees=Empty()))',
        # 'ModifyEventRequest(with_attendee(jane))',
        # 'CreateEvent(with_attendee(jane))',
        # 'AcceptSuggestion()',


        # 'refer(Event?(id=4))',
        # 'refer(Event?(id=5))',
        # 'refer(Event?(attendees=Empty()))',
        # 'refer(clear_attendees())',
        # 'refer(execute(clear_attendees()))',
        # 'FindEvents(AND(with_attendee(dan), with_attendee(john), at_location(room3)))',
        # 'FindEvents(at_location(room3))',
        # 'FindEvents(Event?())',
        # 'FindEvents(AND(with_attendee(jane)))',
        # 'ModifyEventRequest(clear_attendees())',
        # 'ModifyEventRequest(with_attendee(jane))',

        # 'FindEvents(has_id(4))',
        # 'Event?(subject=hello)',
        # 'Event?(location=hello)',
        # 'FindEvents(has_id(5))',
        # 'refer(Event?())',
        # 'refer(Event?(subject=Empty()))',
        # 'refer(Event??(subject=Empty()))',

        # 'ModifyEventRequest(clear_attendees())',

        # 'ModifyEventRequest(AND(with_attendee(dan)))',

        # 'ModifyEventRequest(avoid_attendee(jane))',
        # 'ModifyEventRequest(at_location(lisas))',

        # 'FindEvents(AND(at_time(Afternoon()), at_time(Tomorrow())))',
        # 'CreateEvent(AND(at_time(Afternoon())))',
        #'AcceptSuggestion()',
        # 'AcceptSuggestion()',
        # 'CreateEvent(AND(at_time(NumberPM(4))))',
        # 'CreateEvent(AND(at_interval(Tomorrow()), at_interval(Morning())))',
        # 'ModifyEventRequest(shift_end(toHours(1)))',
        # 'ModifyEventRequest(shift_start(toHours(1)))',
        # 'ModifyEventRequest(shift_start(toHours(2)))',
        # 'ModifyEventRequest(shift_end(toHours(3)))',

        # 'refer(TRUE?(), role=attendees)',
        # 'refer(Event?())',
        # 'CreateEvent(starts_at(NumberAM(10)))',
        # 'FindEvents(Event?(slot=TimeSlot(inter='
        # 'DateTime(date=Date(year=2022, month=1, day=6), time=Time(hour=13, minute=0)))))',

        # 'FindEvents(Event?(slot=TimeSlot(bound='
        # 'DateTimeRange('
        # 'start=DateTime(date=Date(year=2022, month=1, day=5)), '
        # 'end=DateTime(date=Date(year=2022, month=1, day=6), time=Time(hour=10)))))'
        # 'inFahrenheit(-40)',
        # 'toFahrenheit(inCelsius(100))',
        # 'inUsMilesPerHour(1.609)',
        # ':hour(NumberAM(#9))',

        # 'Time?(hour=1)'
        # 'CreateEvent(starts_at(NumberAM(9)))',
        # 'FindEvents(AND(starts_at(NumberAM(9)), with_attendee(Dan Smith)))',
        # 'FindEvents(starts_at(NumberAM(9)))',
        # 'FindEvents(with_attendee(jane))',
        # 'ModifyEventRequest(ends_at(NumberAM(10)))',
        # 'ModifyEventRequest(has_duration(Period(hour=2)))',
        # 'ModifyEventRequest(starts_at(NumberAM(10)))',

        # 'CreateEvent(OR(OR(with_attendee(#John), avoid_attendee(#Dan)), AND(starts_at(NumberAM(9)), at_location(#room3))))',

        # 'CreateEvent(with_attendee(#John))',
        # 'ModifyEventRequest(with_attendee(#Dan))',
        # 'ModifyEventRequest(avoid_attendee(#John))',

        # 'GTf(size(SET(#1,#2)), #1)',
        # 'DeleteEvent(AND(starts_at(Tomorrow()), with_attendee(FindManager(#John))))',
        # 'WeatherQueryApi(place=AtPlace(place=FindPlace(keyphrase=#Zurich)))',
        # 'WeatherQueryApi(place=AtPlace(place=FindPlace(keyphrase=#Zurich)), time=DateTime(date=Today(), '
        # 'time=NumberAM(11)))',
        # 'WeatherQueryApi(place=#Zurich)',
        # 'WeatherQueryApi(place=LocationKeyphrase(#Zurich))',
        # 'WeatherQueryApi(place=AtPlace(place=FindPlace(keyphrase=#Zurich)))',
        # 'WeatherQueryApi(place=AtPlace(place=FindPlace(keyphrase=#Zurich)), time=DateTime(date=Today()))',
        # 'WeatherQueryApi(place=AtPlace(place=FindPlace(keyphrase=#Zurich)), time=Now())',
        # 'WeatherQueryApi(place=AtPlace(place=FindPlace(keyphrase=LocationKeyphrase(#Zurich))))',

        # 'WeatherAggregate(property=#temperature, quantifier=#Min, table=#Zurich)',
        # 'WeatherAggregate(property=temperature, quantifier=min, table='
        # 'WeatherQueryApi(place=#Zurich))',
        # 'WeatherForEvent(event=FindEvents(has_id(8)))',
        # 'FindEvents(Event?(slot=TimeSlot?(start=DateTime?(date=MDY(JAN, 5, 2023)))))',
        # 'CurrentUser()',

        # 'WeekendOfDate(Date(year=2022, month=4, day=3))',
        # 'WeekendOfDate(Date(year=2022, month=4, day=4))',
        # 'WeekendOfDate(Date(year=2022, month=4, day=5))',
        # 'WeekendOfDate(Date(year=2022, month=4, day=6))',
        # 'WeekendOfDate(Date(year=2022, month=4, day=7))',
        # 'WeekendOfDate(Date(year=2022, month=4, day=8))',
        # 'WeekendOfDate(Date(year=2022, month=4, day=9))',
        # 'WeekendOfDate(Date(year=2022, month=4, day=10))',

        # 'LateTimeRange(Morning())',

        # 'nextDayOfMonth(Date(year=2020, month=1, day=31), 29)',
        # 'LastDayOfMonth(8)',
        # 'previousDayOfMonth(Date(year=2022, month=1, day=4), 30)',
        # 'NextWeekend()',

        # 'DowOfWeekNew(WED, DateRange(start=Date(year=2022, month=4, day=4), end=Date(year=2022, month=4, day=5)))',

        # 'WillSnow(table=WeatherQueryApi(place=AtPlace(place=FindPlace(keyphrase=#Zurich)), time=Tomorrow()))',

        # 'FindPlaceAtHere(place=room, radiusConstraint=AtPlace(place=FindPlace(bern)))',
        # 'PlaceHasFeature(feature=HappyHour,place=FindPlace(jeffs))',

        # 'FencePlaces()',
        # 'GenericPleasantry()',

        # 'PlaceHasFeature(feature=HappyHour,place=FindPlace(keyphrase=jeffs))',

        # 'PlaceHasFeature(feature=PlaceFeature(HappyHour),place=FindPlace(keyphrase=zurich))',
        # 'PlaceHasFeature(feature=HappyHour,place=FindPlace(keyphrase=jeffs))',
        # 'PlaceHasFeature(feature=HappyHour,place=FindPlace(keyphrase=zurich))',
        # 'FindPlaceMultiResults(keyphrase=room)',
        # 'FindPlaceMultiResults(keyphrase=zurich)',
        # 'PlaceDescribableLocation(place=#zurich)',
        # 'PlaceDescribableLocation(place=#letzipark)',
        # 'FindPlace(keyphrase=room)',

        # ':email(refer(Recipient?(id=1006)))',
        # ':email(refer(Recipient?(John)))',
        # 'FindEvents(AND(ends_at(HourMinuteAm(hours=10,minutes=30)), at_location(#jeffs),starts_at(NextDOW(#SUNDAY)),starts_at(NumberAM(10))))',
        # 'FindEvents(starts_at(has_id(4)))',
        # 'FindEvents(starts_at(DateTime(time=Time(hour=9, minute=30))))',

        # 'FindEvents(starts_at(FindEvents(has_id(4))))',

        # 'UpdateEvent(AND(ends_at(HourMinuteAm(hours=10,minutes=30)), at_location(#jeffs),starts_at(NextDOW(#SUNDAY)),starts_at(NumberAM(10))) \
        #             constraint=AND(ends_at(NumberPM(2)),starts_at(NumberAM(11))))',
        # 'CreateEvent(AND(starts_at(Morning()), ends_at(Morning())))',
        # 'CreateEvent(AND(starts_at(Morning()), ends_at(Morning()), has_duration(Period(minute=40))))',
        # 'UpdateEvent(FindEvents(AND(ends_at(HourMinuteAm(hours=10,minutes=30)), at_location(#jeffs),starts_at(NextDOW(#SUNDAY)),starts_at(NumberAM(10)))) \
        #             constraint=AND(ends_at(NumberPM(2)),starts_at(NumberAM(11))))',

        # 'CreateEvent(AND(has_duration(toHours(#1)),with_attendee(#Je),with_attendee(#Jane),at_location(#Conference_Room_B),has_subject(#discuss_analytics),starts_at(NextDOW(#THURSDAY)),starts_at(NumberPM(4))))'

        # 'CreateEvent(AND(starts_at(DateTime(date=Date(year=2022, month=1, day=5), time=Time(hour=9, minute=0)))))',
        # 'CreateEvent(AND(with_attendee(#Dan), starts_at(Now()), ends_at(NumberPM(3))))',
        # 'CreateEvent(starts_at(Morning()))',
        # 'CreateEvent(AND(starts_at(Morning()), ends_at(Morning())))',
        # 'CreateEvent(AND(with_attendee(#Jane), starts_at(NumberAM(10))))',
        # 'CreateEvent(AND(with_attendee(#Jane), '
        #     'starts_at(DateTime(date=Date(month=1, day=10), time=Time(hour=10, minute=10)))))',
        # 'CreateEvent(AND(with_attendee(#Jane), starts_at(Time(hour=10, minute=10)), at_location(#room2)))',
        # 'CreateEvent(AND(with_attendee(#Dan), at_location(#room2), has_duration(Period(hour=1))))',
        # 'CreateEvent(AND(with_attendee(#Jane), at_location(#room2), starts_at(Time(hour=10, minute=10))))',
        # 'AcceptSuggestion()',
        # 'AcceptSuggestion()',
        # 'CreateEvent(AND(with_attendee(#Jane), at_location(#room2)))',
        # 'AcceptSuggestion()',
        # 'CreateEvent(starts_at(GT(Now())))',
        # 'AcceptSuggestion()',
        # 'CreateEvent(starts_at(GT(Now())))'
        # 'CreateEvent(AND(with_attendee(#Jane), at_location(#room2), '
        # 'starts_at(DateTime(date=Date(month=1, day=10))), has_subject(#breakfast)))',
        # 'AcceptSuggestion()',
        # 'starts_at(Time(hour=9, minute=0)), has_subject(#breakfast)))',
        # 'CreateEvent(AND(with_attendee(#Jane), starts_at(Time(hour=10, minute=0)), ',
        #     'starts_at(DateTime(date=Date(month=1, day=6), time=Time(hour=10, minute=10)))',
        # 'CreateEvent(AND(with_attendee(#Jane), starts_at(Time(hour=10, minute=10))))',
        # 'FindEvents(AND(with_attendee(#Dan), starts_at(NumberAM(9))))',
        # 'AcceptSuggestion(2)',
        # 'MoreSuggestions(#next)',
        # 'AcceptSuggestion()',
        # 'FindEvents(starts_at(Morning()))',
        # 'UpdateEvent(starts_at(Morning()))',
        # 'CreateEvent(AND(starts_at(NumberAM(9)), ends_at(NumberAM(10))))',
        # 'CreateEvent(starts_at(Morning()))',

        # 'CreateEvent(AND(with_attendee(#Dan), starts_at(NumberAM(9))))',
        # 'AcceptSuggestion()',

        # 'SelectEventSuggestion(starts_at(NumberPM(15)))',

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
