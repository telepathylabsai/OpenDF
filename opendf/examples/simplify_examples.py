"""
Simplify dialog examples.

The user can select the example by its index, from the command line. The example 0 is for debug.
"""


dialogs = [
    [
'(Yield :output (CreateCommitEventWrapper :event (CreatePreflightEventWrapper :constraint (Constraint[Event] \
  :start (?= (TimeAfterDateTime :dateTime (:end (Execute :intension (refer (extensionConstraint (Constraint[Event])))))\
   :time (NumberPM :number #(Number 4)))) :subject (?= #(String "family time"))))))',

    # '(let (x0 (DateAtTimeWithDefaults :date (Tomorrow) :time (NumberPM :number #(Number 2)))) (Yield :output (CreateCommitEventWrapper :event \
    # (CreatePreflightEventWrapper :constraint (Constraint[Event] :end (?= (TimeAfterDateTime :dateTime x0 :time \
    # (NumberPM :number #(Number 5)))) :showAs (?= #(ShowAsStatus "Busy")) :start (?= x0))))))'

    #'(Yield :output (FindEventWrapperWithDefaults :constraint (EventOnDate :date (Today) :event (Constraint[Event]))))',

        # '(Yield\
        #   :output (CreateCommitEventWrapper\
        #     :event (CreatePreflightEventWrapper\
        #       :constraint (Constraint[Event]\
        #         :subject (?= #(String "date date"))))))'
        #'(Yield :output (> (size (:results (FindEventWrapperWithDefaults :constraint (EventOnDate :date (Tomorrow) :event (Constraint[Event] :attendees (AttendeeListHasRecipientConstraint :recipientConstraint (RecipientWithNameLike :constraint (Constraint[Recipient]) :name # (PersonName "Pikachu"))) :subject (?~= # (String "fly in"))))))) #(Number 0)))'
        #'(Yield :output (Execute :intension (ReviseConstraint :rootLocation (roleConstraint #(Path "output")) :oldLocation (Constraint[Constraint[Event]]) :new (Constraint[Event] :start (Constraint[DateTime] :time (?< (Execute :intension (refer (andConstraint (roleConstraint (append #(List[Path] []) #(Path "start"))) (extensionConstraint (Constraint[Time])))))))))))'
        #'(let (x0 (DateAtTimeWithDefaults :date (NextDOW :dow #(DayOfWeek "SUNDAY")) :time (NumberAM :number #(Number 10.0))) x1 (singleton (:results (FindEventWrapperWithDefaults :constraint (Constraint[Event] :end (?= (TimeAfterDateTime :dateTime x0 :time (HourMinuteAm :hours #(Number 10.0) :minutes #(Number 30.0)))) :location (?= #(LocationKeyphrase "jeffs")) :start (?= x0))))) x2 (DateAtTimeWithDefaults :date (:date (:start x1)) :time (NumberAM :number #(Number 10.0)))) (Yield :output (UpdateCommitEventWrapper :event (UpdatePreflightEventWrapper :id (:id x1) :update (Constraint[Event] :end (?= (TimeAfterDateTime :dateTime x2 :time (NumberPM :number #(Number 2)))) :start (?= x2))))))'
        #'(Yield :output (PersonFromRecipient :recipient (Execute :intension (refer (extensionConstraint (RecipientWithNameLike :constraint (Constraint[Recipient]) :name #(PersonName "Barack Obama")))))))'
        #'(Yield :output (DeleteCommitEventWrapper :event (DeletePreflightEventWrapper :id (:id (singleton (:results (FindEventWrapperWithDefaults :constraint (EventOnDate :date (Tomorrow) :event (Constraint[Event] :attendees (AttendeeListHasRecipient :recipient (FindManager :recipient (Execute :intension (refer (extensionConstraint (RecipientWithNameLike :constraint (Constraint[Recipient]) :name #(PersonName "John"))))))))))))))))'


    ],

    # 1  Can you add an appointment with Jerri Skinner at 9 am?
    [
        '(Yield \
          :output (CreateCommitEventWrapper \
            :event (CreatePreflightEventWrapper \
              :constraint (Constraint[Event] \
                :attendees (AttendeeListHasRecipient \
                  :recipient (Execute \
                    :intension (refer \
                      (extensionConstraint \
                        (RecipientWithNameLike \
                          :constraint (Constraint[Recipient]) \
                          :name #(PersonName "Jerri Skinner")))))) \
                :start (?= (NextTime :time (NumberAM :number #(Number 9))))))))',

    ],
    # 2
    [
        '(Yield \
           :output (:start \
              (singleton \
                 (:results \
                    (FindEventWrapperWithDefaults \
                       :constraint (Constraint[Event] \
                          :attendees (andConstraint \
                             (andConstraint \
                                (andConstraint \
                                   (AttendeeListHasRecipientConstraint \
                                      :recipientConstraint (RecipientWithNameLike \
                                         :constraint (Constraint[Recipient]) \
                                         :name #(PersonName "Ryan"))) \
                                   (AttendeeListHasRecipientConstraint \
                                      :recipientConstraint (RecipientWithNameLike \
                                         :constraint (Constraint[Recipient]) \
                                         :name #(PersonName "Jane")))) \
                                   (AttendeeListHasRecipientConstraint \
                                      :recipientConstraint (RecipientWithNameLike \
                                         :constraint (Constraint[Recipient]) \
                                         :name #(PersonName "Chad")))) \
                                   (AttendeeListHasRecipientConstraint \
                                      :recipientConstraint (RecipientWithNameLike \
                                         :constraint (Constraint[Recipient]) \
                                         :name #(PersonName "Melissa")))) \
                          :subject (?~= #(String "trivia night"))))))))'

    ],
    # 3.  Change on Sunday at jeffs from 10:00 to 10:30 AM to 10:00 am to 2:00 pm.
    [
        '(let (x0 (DateAtTimeWithDefaults :date (NextDOW :dow #(DayOfWeek "SUNDAY")) :time (NumberAM :number #(Number 10.0))) x1 (singleton (:results (FindEventWrapperWithDefaults :constraint (Constraint[Event] :end (?= (TimeAfterDateTime :dateTime x0 :time (HourMinuteAm :hours #(Number 10.0) :minutes #(Number 30.0)))) :location (?= #(LocationKeyphrase "jeffs")) :start (?= x0))))) x2 (DateAtTimeWithDefaults :date (:date (:start x1)) :time (NumberAM :number #(Number 10.0)))) (Yield :output (UpdateCommitEventWrapper :event (UpdatePreflightEventWrapper :id (:id x1) :update (Constraint[Event] :end (?= (TimeAfterDateTime :dateTime x2 :time (NumberPM :number #(Number 2)))) :start (?= x2))))))'
    ],
    # 4  clear simplification example
    [
        '(Yield :output (DeleteCommitEventWrapper :event (DeletePreflightEventWrapper :id (:id (singleton (:results (FindEventWrapperWithDefaults :constraint (EventOnDate :date (Tomorrow) :event (Constraint[Event] :attendees (AttendeeListHasRecipient :recipient (FindManager :recipient (Execute :intension (refer (extensionConstraint (RecipientWithNameLike :constraint (Constraint[Recipient]) :name #(PersonName "John"))))))))))))))))',
    ]

]
