"""
Main dialog examples.

The user can select the example by its index, from the command line. The example 0 is for debug.
"""

dialogs = [
    # 0
    [
        'DeleteEvent(AND(starts_at(Tomorrow()), with_attendee(FindManager(John))))',
        #'set_ctx_mem(xxx, Int(1))',
        #'Yield(get_ctx_mem(xxx))',
        #'Add(get_ctx_mem(xxx), 1)',
        #'set_ctx_mem(xxx, Int(2))',
        #'revise(root=Add?(), hasParam=pos2, new=Int(1), newMode=extend)',
        #"Find(Hotel?(internet=yes, pricerange=cheap, type=hotel))",
        #"revise(old=Hotel??(), newMode=overwrite, new=Hotel?(name=LIKE(Name(cambridge belfry)), parking=refer(role=parking)))",
        # 'UpdateEvent(event=Event(start=Today()), update=Event(attendees=AND(#Lindsay, FindManager(#Lindsay))))',
        # 'UpdateEvent(event=Event?(), update=Event?())',
        #'Date(year=2022)',
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

    # 1 - this is used as part of the automatic tests - do not change!
    [
        'DeleteEvent(AND(starts_at(Tomorrow()), with_attendee(FindManager(John))))'
    ],
    # 2 - this is used as part of the automatic tests - do not change!
    [
        # 'CreateEvent(starts_at(Morning()))',
        'CreateEvent(starts_at(NumberAM(9)))',
        'ModifyEventRequest(with_attendee(dan))',
        # 'AcceptSuggestion(2)',
        # 'AcceptSuggestion()',
    ],
    # 3 - this is used as part of the automatic tests - do not change!
    [
        'UpdateEvent(AND(ends_at(HourMinuteAm(hours=10,minutes=30)), at_location(jeffs),\
                    starts_at(NextDOW(SUNDAY)),starts_at(NumberAM(10))), \
                    constraint=AND(ends_at(NumberPM(2)),starts_at(NumberAM(11))))',
    ],
    # 4 - this is used as part of the automatic tests - do not change!
    [
        'UpdateEvent(event=has_id(4), constraint=starts_at(Time(hour=19)))',
    ],
    # 5 - this is used as part of the automatic tests - do not change!
    [
        'FindEvents(starts_at(Morning()))',
        'ModifyEventRequest(starts_at(GT(Time(hour=9, minute=0))))',
    ],
    # 6 - this is used as part of the automatic tests - do not change!
    [
        'FindEvents(AND(avoid_start(Morning()), at_location(room3)))',
    ],
    # 7 - this is used as part of the automatic tests - do not change!
    [
        'WeatherQueryApi(place=AtPlace(place=FindPlace(Zurich)), time=Today())',
        'WillSnow(table=refer(WeatherTable?()))',
    ],
    # 8 - this is used as part of the automatic tests - do not change!
    [
        'FindEvents(Event?(slot=TimeSlot(bound=DateTimeRange('
        'start=DateTime(date=Date(year=2022, month=1, day=5), time=Time(hour=10, minute=0)), '
        'end=DateTime(date=Date(year=2022, month=1, day=6), time=Time(hour=13, minute=0))'
        '))))',
    ],
    # 9 - this is used as part of the automatic tests - do not change!
    [
        'FindEvents(Event?(slot=TimeSlot(inter=DateTimeRange('
        'start=DateTime(date=Date(year=2022, month=1, day=5), time=Time(hour=10, minute=0)), '
        'end=DateTime(date=Date(year=2022, month=1, day=6), time=Time(hour=13, minute=0))'
        '))))',
    ],
    # 10 - this is used as part of the automatic tests - do not change!
    [
        'GTf(size(FindEvents(with_attendee(jack))), Int(1))'
    ],
    # 11 - this is used as part of the automatic tests - do not change!
    [
        'GTf(size(FindEvents(starts_at(GT(singleton(FindEvents(with_attendee(jack))))))), Int(1))',
    ],
    # 12 create event
    [
        #'FindEvents(at_location(room1))',
        #'CreateEvent(AND(with_attendee(dan), at_location(room3), starts_at(Today())))',
        'CreateEvent(starts_at(Today()))',
        #'CreateEvent(starts_at(NumberAM(10)))',
        #'CreateEvent(starts_at(Time(hour=10)))',
        #'CreateEvent(AND(with_attendee(dan), starts_at(NumberPM(8))))',
        #'CreateEvent(starts_at(DateTime(date=Date(day=1), time=Time(hour=1))))',
    ],
]
