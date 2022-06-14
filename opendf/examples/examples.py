"""
Main dialog examples.

The user can select the example by its index, from the command line. The example 0 is for debug.
"""

dialogs = [
    # 0
    [
        # 'UpdateEvent(event=Event(start=Today()), update=Event(attendees=AND(#Lindsay, FindManager(#Lindsay))))',
        # 'UpdateEvent(event=Event?(), update=Event?())',
        'FindEvents(with_attendee(jane))',

        #'Yield(output=Date(year=2021))',
        # 'revise(hasParam=year, new=#2020, newMode=extend)',
        # 'revise(hasParam=output, new=#2020, newMode=extend)',

        # 'Yield(FindEventWrapperWithDefaults( \
        #     constraint=eventDuringRange(\
        #         range=FullMonthofMonth(sep), \
        #         event=Event?(attendees=ANY(Recipient?(name=LIKE(PersonName(John_Smith))))))))',

        # # ':start( singleton(FindEventWrapperWithDefaults( constraint=eventOnDate( date=NextDOW(dow=Wednesday), \
        #       event=Event?(attendees=ANY(Recipient?(name=LIKE(PersonName(John_Smith))) ) ) ) ) ))',

        # 'ANDf(#True, #False)',
        # 'GTf(size(SET(Time(hour=1),Time(hour=1),SET(Time(hour=2), Time(hour=2)))), #1)',
        # 'size(SET(Time(hour=1),Time(hour=1),SET(Time(hour=2), Time(hour=2))), unroll=True)',
        # 'size(Time(hour=1))',
        # 'CreateEvent(Event?(\
        #     attendees=OR(Recipient?(name=Jane),Recipient?(name=Jane)),\
        #     start=DateTime?(date=NextDOW(dow=Sunday), time=NumberPM(3))))',

        # 'Yield(output=:dow(DateTime(date=Tomorrow())))',
        # 'Yield(output=WillSnow(place=#zurich, time=DateTime?(date=Today(), time=Morning())))',

        # ':output(Yield(output=Date(year=2021)))',
        # 'revise(hasParam=year, new=#2020, newMode=extend)',
        # 'revise(hasParam=output, new=#2020, newMode=extend)',

        # 'DateTime(date=Tomorrow())',
        # 'DateTime(dow=sat)',
        # ':dow(DateTime(date=Tomorrow()))',
        # 'Yield(output=:start(Event(subject=party, start=DateTime(date=Tomorrow(), time=Time(hour=8)))))',
        # 'Yield(output=:end(Event(subject=party, end=Tomorrow(), start=DateTime(date=Today(), time=Time(hour=8)))))',

        # 'Yield(output=:end(Event(subject=party, end=Tomorrow(), start=DateTime(date=Today(), time=Time(hour=8)))))',

        # 'Recipient(name=john)',

        # 'revise(hasParam=index, new=#1, newMode=extend)',

        # 'Yield(output=:day(Today()))',
        # 'Yield(output=:start(Event(start=Now())))',

        # 'CreateEvent(Event?(\
        #     attendees=Recipient?(name=Jane),\
        #     start=DateTime?(date=NextDOW(dow=Sunday), time=NumberPM(3))))',

        # 'Yield(output=CreateEvent(Event?(\
        #     attendees=Recipient?(name=Jane),\
        #     start=DateTime?(date=NextDOW(dow=Sunday), time=NumberPM(3)))))',

        # 'CreateCommitEventWrapper(event=CreatePreflightEventWrapper(constraint=Event?(\
        #     attendees=Recipient?(name=Jane),\
        #     start=DateTime?(date=GT(NextDOW(dow=Sunday)), time=GT(NumberPM(3))))))',

        # 'CreateCommitEventWrapper(event=CreatePreflightEventWrapper(constraint=Event?(\
        #     attendees=Recipient?(name=Jane),\
        #     start=DateAtTimeWithDefaults(date=NextDOW(dow=Sunday), time=NumberPM(3)))))',

        # 'CreateCommitEventWrapper(event=CreatePreflightEventWrapper(constraint=Event?(\
        #     attendees=Recipient?(name=LIKE(PersonName(Jane))),\
        #     start=DateAtTimeWithDefaults(date=NextDOW(dow=Sunday), time=NumberPM(3)))))',

        # 'revise(hasParam=index, new=#2, newMode=extend)',
        # 'AcceptSuggestion(index=1)',

        # 'refer(Recipient?())',
        # 'refer(type=Recipient?)',
        # 'refer(Recipient?(name=LIKE(john)))',
        # 'refer(Recipient?(name=LIKE(john)), cond=ANY(Recipient?(lastName=Smith), Recipient?(firstName=dan)))',
        # 'refer(type=Recipient, cond=AND(Recipient?(lastName=Smith), Recipient?(firstName=john)))',
        # 'refer(Recipient?(firstName=john), cond=AND(Recipient?(name=LIKE(Doe)), Recipient?(name=LIKE(john))))',
        # 'refer(Recipient?(), cond=AND(Recipient?(name=LIKE(Doe)), Recipient?(name=LIKE(john))))',
        # 'refer(AND(Recipient?(name=LIKE(Doe)), Recipient?(name=LIKE(john))))',
        # 'refer(AND(Recipient?(lastName=Doe), Recipient?(firstName=john)))',

        # 'DateAtTimeWithDefaults(date=NextDOW(dow=Sunday), time=NumberPM(3))',
        # ':start( singleton(FindEventWrapperWithDefaults( constraint=eventOnDate( date=NextDOW(dow=Wednesday), \
        #      event=Event?(attendees=ANY(Recipient?(name=LIKE(PersonName(John_Smith))) ) ) ) ) ))',
        # 'CreateCommitEventWrapper(event=CreatePreflightEventWrapper(constraint=Event?(\
        #     subject=golf, start=DateTime?(date=NextDOW(dow=sat), time=NumberAM(10)), end=NumberPM(3))))',

        # 'CreateCommitEventWrapper(event=CreatePreflightEventWrapper(constraint=Event?(\
        #   attendees=Recipient?(name=LIKE(PersonName(John))),\
        #    start=DateAtTimeWithDefaults(date=NextDOW(dow=Sunday), time=NumberPM(3)))))',

        # 'Yield(output=WillSnow(place=#zurich, time=DateTime?(date=Today(), time=Morning())))',

        # 'revise(oldNode=refer(role=day),  inp_nm=pos1, new=#29, newMode=overwrite)',

        # 'DateTime?(time=Morning())'

        # 'WeatherQueryApi(place=AtPlace(FindPlace(keyphrase=#zurich)), time=DateTime?(date=Today(), time=Morning()))',
        # 'IsCold(table=WeatherQueryApi(place=#zurich, time=DateTime?(date=Today(), time=Morning())))',
        # 'Yield(output=WillSnow(table=WeatherQueryApi(place=#zurich, time=DateTime?(date=Today(), time=Morning()))))',
        # '',
        # 'revise(oldNode=refer(role=day), inp_nm=day, new=#29, newMode=extend)',
        # 'DateTime(date=Date(day=28))',
        # 'refer(Date?())',
        # 'refer(role=day)',
        # 'revise(old=Date?(),  new=Date(day=29), newMode=auto)',

        # 'revise(hasParam=day, new=#29, newMode=extend)',

        # 'DateTime?(date=Today())',
        # 'DateTime?(date=Today(), time=Evening())',

        # 'AtPlace(FindPlace(keyphrase=LocationKeyphrase(zurich)))',
        # 'AtPlace(FindPlace(keyphrase=#zurich))',

        # 'ThisWeekEnd()',
        # 'DateRange_to_Date(ThisWeekEnd())',
        # 'DateTime(date=ThisWeekEnd())',
        # 'CreateCommitEventWrapper(event=CreatePreflightEventWrapper(constraint=Event?(\
        #     subject=date, start=DateTime?(date=ThisWeekEnd()))))',
        # 'revise(hasParam=start, new=DateTime?(date=Date?(dow=NOT(ANY(WeekEndDays())))), newMode=extend)'
        # 'revise(old=Event??(), new=Event?(start=DateTime?(date=Date?(dow=ANY(WeekDays())))), newMode=auto)'
        # 'revise(old=Event??(), new=Event?(start=DateTime?(date=Date?(dow=WeekDays()))), newMode=auto)',
        # 'AcceptSuggestion()',
        # 'AcceptSuggestion()',

        # 'revise(old=Event??(), new=Event?(end=Time(hour=15, minute=30)), newMode=auto)',
        # 'revise(old=Event??(), new=Event?(start=Time(hour=10, minute=30)), newMode=auto)',
        # 'RejectSuggestion()',
        # 'revise(old=Event??(), new=Event?(subject=GolfDay), newMode=auto)',
        # 'revise(hasParam=confirm, new=#true, newMode=extend)',
        # 'RejectSuggestion()',
        # 'AcceptSuggestion()',

        # 'ClosestDayOfWeek(dow=tue, date=Date(year=2021, month=8, day=18))',
        # 'NextDOW(dow=sat)',

        # 'DateTime(date=NextDOW(dow=sat), time=NumberAM(10))',
        # 'DateTime(date=NextDOW(dow=sat))',
        # 'DateAtTimeWithDefaults(date=NextDOW(dow=sat))',
        # 'DateAtTimeWithDefaults()',

        # 'let(x0, DateAtTimeWithDefaults(date=NextDOW(dow=sat), time=NumberAM(10)))',

        # ':start( singleton(FindEventWrapperWithDefaults( constraint=eventOnDate( date=NextDOW(dow=Wednesday), \
        #        event=Event?(attendees=ANY(Recipient?(name=LIKE(PersonName(John_Smith))) ) ) ) ) ))',
        # 'CreateCommitEventWrapper(event=CreatePreflightEventWrapper(constraint=Event?(\
        #  attendees=refer(Recipient?(name=LIKE(PersonName(John)))),\
        #  start=NextTime(time=NumberAM(9)))))',

        # 'let(pers, singleton(refer(Recipient?(name=LIKE(PersonName(John))))), res)',
        # 'revise(hasParam=index, new=#1, newMode=extend)',
        # # '{pers~}refer(Recipient?(name=LIKE(PersonName(Dan))))',
        #
        # 'CreateCommitEventWrapper(event=CreatePreflightEventWrapper(constraint=Event?(\
        #      attendees=SET($pers, FindManager($pers) ), subject=lunch, start=DateTime?(time=Time(hour=12)))))',
        #
        # 'revise(old=Event??(), new=Event?(attendees=NEQ($pers), subject=managers_lunch), newMode=auto)',
        #
        # 'RejectSuggestion()',
        # 'AcceptSuggestion(index=1)',
        # #'revise(hasParam=confirm, new=#true, newMode=extend)',

        # 'refer(Node?())',

        # 'revise(old=Event??(), new=Event?(attendees=excludeRecipient($pers)), newMode=auto)',

        # '{pers~}refer(Recipient?(name=LIKE(PersonName(Dan))))',
        # 'includeRecipient($pers)',
        # 'excludeRecipient($pers)',

        # 'FindManager($pers)',

        # ':start( singleton(index=1, FindEventWrapperWithDefaults( constraint=eventOnDate( date=NextDOW(dow=Wednesday), \
        #      event=Event?(attendees=ANY(AttendeeListHasRecipientConstraint( recipientConstraint=RecipientWithNameLike( \
        #      constraint=Recipient, name=John ) ) ) ) )) ))',

        # 'refer(Recipient?(name=LIKE(PersonName(John_Smith))))',

        # ':start( singleton(FindEventWrapperWithDefaults( constraint=eventOnDate( date=NextDOW(dow=Wednesday), \
        #      event=Event?(attendees=ANY(Recipient?(name=LIKE(PersonName(John_Smith))) ) ) ) ) ))',
        #
        # 'CreateCommitEventWrapper(event=CreatePreflightEventWrapper(constraint=Event?(\
        #  attendees=refer(Recipient?(name=LIKE(PersonName(John)))),\
        #  start=NextTime(time=NumberAM(number=9)))))',
        #
        # 'revise(old=Event??(), new=Event?(duration=PeriodDuration(toHours(2))), newMode=overwrite)',
        # # 'revise(mid=Event??(), hasParam=duration, new=Period(hour=2), newMode=extend)',
        # 'revise(hasParam=confirm, new=#true, newMode=extend)',

        # 'CreateCommitEventWrapper(event=CreatePreflightEventWrapper(constraint=Event?(attendees=ANY( \
        #     RecipientWithNameLike(constraint=Recipient, name=John)),\
        #     start=NextTime(time=NumberAM(number=9)))))',

        # ':start( singleton(FindEventWrapperWithDefaults( constraint=eventOnDate( date=NextDOW(dow=Wednesday), \
        #      event=Event?(attendees=ANY(RecipientWithNameLike(constraint=Recipient, name=John ) ) ) ) ) ))',
        # ':dayOfWeek(Today())',

        # ':start( singleton(FindEventWrapperWithDefaults( constraint=eventOnDate( date=NextDOW(dow=Wednesday), \
        #      event=Event?(attendees=ANY(AttendeeListHasRecipientConstraint( recipientConstraint=RecipientWithNameLike( \
        #      constraint=Recipient, name=John ) ) ) ) )) ))',
        # ':dayOfWeek(Today())',

        # 'Tomorrow()',
        # 'CreateCommitEventWrapper(event=CreatePreflightEventWrapper(constraint=Event?(attendees=AttendeeListHasRecipient( \
        #    recipient=refer(RecipientWithNameLike(constraint=Recipient, name=John))),\
        #    start=NextTime(time=NumberAM(number=9)))))',
        # 'revise(mid=Event??(), hasParam=duration, new=Period(hour=2), newMode=extend)',
        # 'revise(hasParam=confirm, new=#true, newMode=extend)',

        # 'SET(Int(1), Int(2))',
        # 'SET[Int](1,2)',
        # 'SET(#1,#2)',

        # 'Div(d1=Mult(m1=Add(a1=1, a2=2), m2=4), d2=!Sub(s1=9, s2=6))',
        # 'refer(Int?(3))',
        # 'refer(Int?(3))',
        # 'refer(<Int?(3))',
        # 'refer(<Add(a1=1, a2=2))',

        # 'refer(Recipient?(name=AND(LIKE[PersonName](John),NOT(LIKE[PersonName](Doe)))))',
        # 'refer(Recipient?(name=AND(LIKE(PersonName(John)),NOT(LIKE(PersonName(Doe))))))',
    ],

    ['Int()'],  # 1
    ['Int(10)'],  # 2

    # 3
    [
        # 'Bool(yes)',
        'Bool(Yes)',
        # 'Bool(True)',
    ],

    # 4 - dialog #5 - weather, yield
    [
        # 'IsCold(table=WeatherQueryApi(place=#zurich, time=DateTime?(date=Today(), time=Morning())))',
        # 'Yield(output=WillSnow(table=WeatherQueryApi(place=#zurich, time=DateTime?(date=Today(), time=Morning()))))',
        'Yield(output=WillSnow(place=zurich, time=DateTime?(date=Today(), time=Morning())))',
    ],
    # 5 - yield getattr / property
    [
        # 'Yield(output=:day(Today()))',
        # 'Yield(output=:start(Event(start=DateTime(date=Tomorrow(), time=Time(hour=8)))))',
        'Yield(output=:start(Event(subject=party, start=DateTime(date=Tomorrow(), time=Time(hour=8)))))',
        # 'Yield(output=:end(Event(subject=party, end=Tomorrow(), start=DateTime(date=Today(), time=Time(hour=8)))))',
    ],
    # 6 - alias
    [
        'Yield(output=Date(year=2021))',
        'revise(hasParam=output, new=2020, newMode=extend)',
    ],
    # 7 - size (unroll), operator-function
    [
        'size(SET(Time(hour=1),Time(hour=1),SET(Time(hour=2), Time(hour=2))))',
        'size(SET(Time(hour=1),Time(hour=1),SET(Time(hour=2), Time(hour=2))), unroll=True)',
        'size(Time(hour=1))',
        'GTf(size(SET(Time(hour=1),Time(hour=1),SET(Time(hour=2), Time(hour=2)))), 1)',
    ]

]
