"""
Database Test.
"""
import logging
import time

import sqlalchemy
from sqlalchemy import select

from opendf.applications.smcalflow.database import Database, populate_stub_database
from opendf.utils.database_utils import DATABASE_SYSTEM

# init type info
from opendf.applications.smcalflow.stub_data import dFri, dThu
from opendf.applications.smcalflow.fill_type_info import fill_type_info
from opendf.graph.node_factory import NodeFactory
from opendf.defs import use_database, database_connection, config_log

node_fact = NodeFactory.get_instance()
fill_type_info(node_fact)

logger = logging.getLogger(__name__)


def main():
    database = None
    try:
        logger.info(f"Hello SQLAlchemy {sqlalchemy.__version__}!")

        # connection_string = "sqlite+pysqlite:///:memory:"
        # connection_string = "sqlite+pysqlite:///test.db"
        # connection_string = "postgresql://postgres:root@localhost:5432/test"
        if use_database:
            database = Database.get_instance()
        else:
            database = Database(database_connection)
        populate_stub_database()

        logger.info(database_connection)
        logger.info(DATABASE_SYSTEM)

        with database.engine.connect() as connection:
            const = sqlalchemy.sql.expression.bindparam("zero", 2).label("const")
            selection = select(Database.EVENT_TABLE.columns.id, const).where(const == 2)
            logger.info(" ".join(str(selection.compile(compile_kwargs={"literal_binds": True})).split()))
            for row in connection.execute(selection):
                logger.info(row)

        # print(database.get_current_recipient_entry())
        # print(database.get_recipient_entry(1004))
        # print(database.get_recipient_graph(1004))
        # print(database.get_manager(1002))
        # print(database.get_friends(1007))
        # print(database.find_recipients_that_match(None))
        # print(database.find_events_that_match(None))
        # print(database._get_attendees_from_event(5))
        # print(database.get_event_entry(1))
        # print(database._get_event_entries([1, 2]))
        # print(database.get_event_graph(5))
        # print(database._get_maximum_event_id())
        # print(database.add_event("meeting", datetime(2022, 2, 24, 10, 0), datetime(2022, 2, 24, 11, 0), "Telepathy",
        #                          [1003, 1004]))
        # print(database.update_event(6, "meeting", datetime(2022, 2, 24, 10, 0), datetime(2022, 2, 24, 11, 0), \
        #                             "Telepathy", [1003, 1004]))
        # print(database.get_events(avoid_id=2, subject="meeting", location="room"))
        logger.info("\n".join(map(lambda x: str(x), database.get_events(attendees=[1001, 1004, 1006, 1005]))))
        # print("\n".join(map(lambda x: str(x), database.get_events(attendees=[1004, 1007],
        #                                                           with_current_recipient=False))))
        # print(database.delete_event(5, None, None, None, None, None))
        # print("\n".join(map(lambda x: str(x),
        #                     database.get_time_overlap_events(dThu + "9/00", dFri + "23/00", [1001, 1006, 1007]))))
        # print("\n".join(map(lambda x: str(x),
        #                     database.get_location_overlap_events("room3", dThu + "9/00", dFri + "20/00"))))
        logger.info(database.is_recipient_free(1001, dThu + "9/00", dFri + "20/00", 6))
        logger.info(database.is_location_free("room3", dFri + "9/00", dFri + "20/00", 7))
        logger.info('')

        # earliest = datetime.strptime("2022-01-01 00:00", "%Y-%m-%d %H:%M")
        # latest = datetime.strptime("2022-01-02 00:00", "%Y-%m-%d %H:%M")
        # current = earliest
        # delta = timedelta(minutes=5)
        # values = []
        # while current < latest:
        #     values.append({"x": current})
        #     current += delta
        #
        # with engine.begin() as conn:
        #     conn.execute(text("CREATE TABLE timeslot (slot timestamp)"))
        #     conn.execute(text("INSERT INTO timeslot (slot) VALUES (:x)"), values)
        #
        #     # result = conn.execute(text("SELECT slot FROM timeslot"))
        #     duration = 30.0
        #     result = conn.execute(text(
        #         "SELECT s.slot, e.slot, "
        #         # "timediff(e.slot, s.slot) as duration "
        #         "ROUND((JULIANDAY(e.slot) - JULIANDAY(s.slot)) * 1440) as duration "
        #         "FROM timeslot s, timeslot e "
        #         "WHERE s.slot < e.slot "
        #         "and duration = :x "
        #         "ORDER BY s.slot, e.slot"
        #     ), {"x": duration})
        #     for row in result:
        #         # print(f"Slot: {row.slot}")
        #         print(f"Slot: {row}")
        #
        #     conn.execute(text("DROP TABLE timeslot"))
    except Exception as e:
        raise e
    finally:
        if database is not None:
            database.erase_database()


if __name__ == '__main__':
    try:
        config_log('DEBUG')
        start = time.time()
        main()
        end = time.time()
        logger.info(f"{end - start:.3f}s")
    except:
        pass
    finally:
        logging.shutdown()
