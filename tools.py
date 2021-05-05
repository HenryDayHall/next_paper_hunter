import urllib
import ratelimit
import datetime
import unicodedata
import logging
import ratelimit

# make it possible to just see meessages from this module
LOGLEVEL = logging.INFO + 1

# 20 seconds is a bit over cautious
# arxiv.org/robots.txt calls for 15
# then again, getting stfc servers banned
# from making arXiv api calls would be embarising for NExT
@ratelimit.sleep_and_retry
@ratelimit.limits(calls=1, period=20)
def request_url(url):
    """To ratelimit requests """
    # need to remove and extended ascii
    url = unicodedata.normalize("NFKD", url).encode("ascii", "ignore").decode()
    logging.log(LOGLEVEL, f"Fetching {url}")
    data = urllib.request.urlopen(url).read()
    return data


def alpha_only(text):
    """Given a string return a
    string with only alphabetical charicters and spaces"""
    text = [c if c.isalpha() else " " for c in text]
    text = ''.join(text)
    return text


def strip_formating(string, brackets=True, quotes=True,
                    whitespace=False, whitespace_to_space=False,
                    comma=False, dot=False):
    if quotes:
        string = string.replace('"', '')
    if brackets:
        string = string.replace('{', '').replace('}', '')
    if whitespace or whitespace_to_space:
        replace_with = ' ' if whitespace_to_space else ''
        string = string.replace('\n', replace_with).replace('\t', replace_with)
        string = string.replace('\r', replace_with)
        string = string.replace(' ', replace_with)
    if comma:
        string = string.replace(',', '')
    if dot:
        string = string.replace('.', '')
    return string


def locate_closing_brace(string, opening_location, closing_brace="}"):
    opening_brace = string[opening_location]
    nesting = opening_brace != closing_brace
    num_open = 1
    for i, charicter in enumerate(string[opening_location+1:]):
        if charicter == opening_brace and nesting:
            num_open += 1
        elif charicter == closing_brace:
            num_open -= 1
            if num_open == 0:
                return opening_location + i + 1
    return -1


def month_to_numeric(month):
    if isinstance(month, int):
        return str(month)
    if isinstance(month, str):
        # remove brackets
        month = strip_formating(month, whitespace=True)
        if month.isnumeric():
            return month
        try:
            month = datetime.datetime.strptime(month, "%b").month
        except ValueError:
            try:
                month = datetime.datetime.strptime(month, "%B").month
            except ValueError:
                raise ValueError(f"Cannot parse {month} as a month")
        return str(month)
    # if we reach here it's dificult to know what the formt has done
    raise TypeError(f"Month {month} is not a str or an int, don't know how to parse")


def check_braces_match(latex_str):
    opening = latex_str.count("{") - latex_str.count("\\{")
    closing = latex_str.count("}") - latex_str.count("\\}")
    return opening - closing

