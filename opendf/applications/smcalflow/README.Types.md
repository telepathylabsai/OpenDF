## Types in SMCalFlow Implementation

Here is a high level description of "object" types use in our implementation of SMCalFlow.

For full detail, please see the code.

### Date and Time

- **Date** is represented as a triple (year, month, day);
- **Time** is represented as a pair (hour, minute); and
- **DateTime** is represented as a date and a time.

For each one of these three times, there is a **Range** type (e.g. DateRange, TimeRange, DateTimeRange) that represents
and range between (inclusive) a start and an end of the given type.

For instance, we can represent *Morning()* as *TimeRange(start=Time(hour=8, minute=0), end=Time(hour=11, minute=30))*.

In `nodes.time_nodes.py`, there are several nodes to extract Date/Time/DateTime representations (and their respective
Range variations) in several ways it might be requested from natural language form.

### People

- PersonName - string representing (part of a) person's name - first name, last name, or first+last name.
- (We don't have a *Person* type)
- Recipient - a specific person, with a unique ID, and contact info
- Attendee - represents the relationship between a Recipient and an Event. It has a Recipient, a response (accept,
  reject...), and a show-as status
  (busy, free...)

### Places

- LocationKeyphrase - string describing a location / place. This could refer to either physical (geographical) or
  virtual (online) venue. This would typically be a (non-unique) "natural language" description, which could be
  disambiguated to a (unique) specific place entity.
- Place - this is the disambiguated (unique) specific entity. It may have geographical coordinates, and if so, it has
  a "Radius" element, to indicate the approximate size (e.g. to distinguish between a point and an area).
- GeoCoords - geographical coordinates (long., lat.)

A common use is:

*AtPlace(FindPlace(LocationKeyphrase(Zurich)))*

Where FindPlace tries to find the unique entity (type=Place), and AtPlace gets the GeoCoords from Place.


