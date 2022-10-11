import re
import sys
from collections import defaultdict

add_delim = None  # '..'

template_words = set([
    "%", "Busy", "Can", "Could", "DAY", "Day", "DayOfWeek", "Does", "Hello", "Here", "Holiday", "How",
    "I", "I'm", "I've", "If", "Is", "It", "I’ve", "Let", "LocationKeyphrase", "Looks", "MERID", "MONTH",
    "NUM", "NUM:NUM", "NUMth", "No", "None", "Out", "PersonName", "PlaceFeature", "Please", "Possible", "QUOTE",
    "ShowAsStatus", "Sorry", "The", "There", "Unfortunately, ", "WeatherProp", "What", "Where", "Which", "Yes",
    "You", "You'll", "You're", "Your", "__BREAK",
    "a", "able", "about", "accepted", "access", "action", "address", "after", "afternoon", "again", "agenda",
    "all", "also", "am", "an", "and", "answer", "any", "anyone", "anything", "are", "aren't", "as", "ask",
    "at", "attendees", "be", "been", "before", "being", "between", "book", "businesses", "calculations",
    "calendar", "can", "can't", "cancel", "capability", "chance", "change", "changed", "clear", "conference",
    "contact", "could", "create", "criteria", "current", "currently", "date", "day", "decline", "declined", "delete",
    "deleted", "describe", "did", "didn't", "different", "dining", "do", "doesn't", "don't", "else", "encountered", "end",
    "error", "event", "events", "everyone", "find", "first", "for", "forwarded", "found", "free", "from", "full", "give",
    "good", "groups", "half", "handle", "has", "have", "haven't", "haven’t", "help", "high", "hour", "hours", "if",
    "in", "information", "internal", "is", "it", "kind", "know", "later", "like", "list", "listed", "located",
    "location", "locations", "logged", "look", "looking", "low", "lunch", "make", "manager", "matching", "maximum",
    "me", "mean", "meeting", "mentioned", "minimum", "minutes", "month", "more", "morning", "multiple",
    "name", "named", "names", "next", "no", "not", "now", "of", "on", "one", "only", "or", "organizer", "outdoor",
    "people", "process", "put", "query", "questions", "rain", "recurring", "referring", "reminders",
    "request", "requests", "rest", "result", "right", "rooms", "say", "schedule", "separate", "set", "shared",
    "snow", "some", "something", "sorry", "specific", "speed", "starts", "status", "subject", "support", "sure",
    "temperature", "that", "the", "them", "there's", "these", "this", "those", "time", "times", "to", "toHours",
    "trained", "transit", "try", "unable", "understand", "until", "up", "update", "updated", "use",
    "want", "was", "way?", "weather", "week", "weekend", "what", "when", "whether", "will", "wind", "with", "without",
    "work?", "would", "yet", "you", "you're", "your", "°C", "°F"
])

# needed??
keep_case = [
"DAY", "Day", "DayOfWeek", "PersonName", "NUM", "MONTH", "NUMth"
]

# some special strings in the dataset, which can also be "normal" strings, depending on capitalization and punctuation
def mark_special(s):
    ss = re.sub('[.,:;?!]', '', s)
    ss = re.sub("'s$", '', ss)
    if ss=='AM':
        return '[AM]'
    if ss in ['Lax']:
        return '['+ss+']'
    return s


def align_quotes(l):
    align = []
    in_quote = False
    s = []
    for i in l.split():
        if '"' in i:
            if in_quote:
                s.append(i)
                align.append(('QUOTE', ' '.join(s)))
                in_quote = False
            elif i.count('"')>1:
                align.append(('QUOTE', i))
            else:
                s = [i]
                in_quote = True
        elif in_quote:
            s.append(i)
        else:
            ii = mark_special(i)
            align.append((ii, i))
    if in_quote:
        align.append(('QUOTE', ' '.join(s)))
    return align


# special words to map to categories. words should be LOWERCASED
maplist = {
    'sunday': 'DayOfWeek',
    'monday': 'DayOfWeek',
    'tuesday': 'DayOfWeek',
    'wednesday': 'DayOfWeek',
    'thursday': 'DayOfWeek',
    'friday': 'DayOfWeek',
    'saturday': 'DayOfWeek',

    'january': 'MONTH',
    'february': 'MONTH',
    'march': 'MONTH',
    'april': 'MONTH',
    'may': 'MONTH',  # ambig?
    'june': 'MONTH',
    'july': 'MONTH',
    'august': 'MONTH',
    'september': 'MONTH',
    'october': 'MONTH',
    'november': 'MONTH',
    'december': 'MONTH',

    'today': 'DAY',
    'yesterday': 'DAY',
    'tomorrow': 'DAY',

    'pm': 'MERID',
    '[am]': 'MERID',

    # some very frequent names
    'dan': 'PersonName',
    'schoffel': 'PersonName',
    'abby': 'PersonName',
    'gonano': 'PersonName',
    'damon': 'PersonName',
    'straeter': 'PersonName',
    'david': 'PersonName',
    'megan': 'PersonName',
    'bowen': 'PersonName',
    '[lax]': 'PersonName',

}


def norm_num(s):
    t = re.sub('\d+\.?\d*', 'NUM', s)
    numth = 'NUMth'  # 'NUM'
    if 'NUM' in t:
        t = re.sub('NUMst', numth, re.sub('NUMnd', numth, re.sub('NUMrd', numth, t)))
    return t


def norm_text(l):
    l = l.strip()
    g = l.split('//')
    l = g[0]
    vals = None
    if len(g) > 1:
        vals = []
        for i in g[1].split():
            j = i.split('=')
            if len(j) == 2:
                vals.append([j[0], j[1].lower().split('__')])
    if add_delim:
        l = add_delim + ' ' + l + ' ' + add_delim
    align = align_quotes(l)
    L = len(align)
    if vals:
        words = [re.sub('[.,:;?!]', '', i[0].lower()) for i in align]
        for v in vals:
            k = 0
            while k<len(v[1]):
                i = v[1][k]
                if i not in template_words and words.count(i) == 1:
                    j = words.index(i)
                    m=1
                    while k+m<len(v[1]) and j+m<len(words) and v[1][k+m]==words[j+m]:
                        m += 1
                    if m==1:
                        words[j] = v[0]
                        align[j] = (v[0], align[j][1])
                    else:
                        tail = align[j+m:]
                        align = align[:j] + [(v[0], ' '.join([j for (i,j) in align[j:j+m]]))]
                        words = [re.sub('[.,:;?!]', '', i[0].lower()) for i in align]
                    k += m
                else:
                    k += 1
    align = [(norm_num(i[0]), i[1]) for i in align]

    align = [(maplist.get(re.sub("'s$", '', re.sub('[.,:;?!]', '', i.lower())),i), j) for (i,j) in align]
    s = ' '.join([i[0] for i in align])
    return s, align




def norm2(l):
    s, align = norm_text(l)
    ss, aa = [], []
    for i,j in align:
        has_comma = i[-1] == ','
        ii = re.sub('[.,:;\?!]$', '', re.sub('[.,:;\?!]$', '', i))
        iis = re.sub("'s$", '', ii)
        if iis in template_words:
            if iis not in keep_case:
                iis = iis.lower()
            aa.append((iis, j))
        else:
            aa.append(('tok', j))
        if ii.lower()!=iis.lower():
            aa.append(("'s", ''))
        if has_comma:
            aa.append((",", ''))
    s = ' '.join([i[0] for i in aa])
    return s, aa




def match_templates(l, templates):
    used = []
    s, align = norm_text(l)
    s2 = s.split()
    # need to align orig and normalized...
    L = len(s2)
    i = 0
    words = []
    vals = []
    templ = []
    while i < L:
        j = i + 1
        k = i
        while j <= L:
            r = s2[i:j]
            if ' '.join(r) in templates:
                k = j
            j += 1
        if k > i + 1:
            t = templates.index(' '.join(s2[i:k]))
            for m in range(i,k):
                words.append(s2[m])
                templ.append(t)
                vals.append(align[m][1] if align[m][1]!=align[m][0] else '')
        else:
            words.append(s2[i])
            templ.append(-2)
            vals.append(align[i][1] if align[i][1]!=align[i][0] else '')
        i = k if k > i else i + 1
    return words, templ, vals
