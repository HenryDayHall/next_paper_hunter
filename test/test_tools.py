import tools
import os
import datetime
import unittest.mock


class PretendReadable:
    def read(self):
        now = datetime.datetime.now()
        text = f"datetime: {str(now)}+1.00".encode()
        return text


def mock_open(url):
    return PretendReadable()


def test_requesturl():
    # while nice in theory this url is too unrelyable to use in a unti test
    time_url = "http://worldtimeapi.org/api/timezone/Europe/London.txt"
    # the key thing is that if we spam the url link twice it should wait 20s between calls
    with unittest.mock.patch('urllib.request.urlopen', new=mock_open):
        data1 = tools.request_url(time_url).decode()
        data2 = tools.request_url(time_url).decode()
    line_start = "datetime: "
    time1 = next(line.split('+')[0][len(line_start):]
                 for line in data1.split(os.linesep)
                 if line.startswith(line_start))
    time1 = datetime.datetime.fromisoformat(time1)
    time2 = next(line.split('+')[0][len(line_start):]
                 for line in data2.split(os.linesep)
                 if line.startswith(line_start))
    time2 = datetime.datetime.fromisoformat(time2)
    wait = datetime.timedelta(seconds=20)
    assert time2 - time1 >= wait, f"Wait was {time2 - time1}"


def test_alpha_only():
    inp = out = "Good Dog"
    assert tools.alpha_only(inp) == out
    inp = "Good Dog!"
    out = "Good Dog "
    assert tools.alpha_only(inp) == out
    inp = "Good\nDog!"
    out = "Good Dog "
    assert tools.alpha_only(inp) == out
    inp = "57394"
    out = "     "
    assert tools.alpha_only(inp) == out


def test_strip_formating():
    inp = "\"'{} \n\r\t,."
    out = "'{} \n\r\t,."
    assert tools.strip_formating(inp, brackets=False) == out
    out = inp
    assert tools.strip_formating(inp, brackets=False, quotes=False) == out
    out = "\"' \n\r\t,."
    assert tools.strip_formating(inp, quotes=False) == out
    out = "',."
    assert tools.strip_formating(inp, whitespace=True) == out
    out = "'    ,."
    assert tools.strip_formating(inp, whitespace=True,
                                 whitespace_to_space=True) == out
    out = "' \n\r\t."
    assert tools.strip_formating(inp, comma=True) == out
    out = "' \n\r\t,"
    assert tools.strip_formating(inp, dot=True) == out


def test_locate_closing_brace():
    inp = "{}"
    assert tools.locate_closing_brace(inp, 0) == 1
    inp = "{a}b"
    assert tools.locate_closing_brace(inp, 0) == 2
    inp = "{b})"
    assert tools.locate_closing_brace(inp, 0, ")") == 3
    inp = "{{}}}"
    assert tools.locate_closing_brace(inp, 0) == 3
    assert tools.locate_closing_brace(inp, 1) == 2


def test_month_to_numeric():
    inp = 1
    assert tools.month_to_numeric(inp) == "1"
    inp = "Jan"
    assert tools.month_to_numeric(inp) == "1"
    inp = "jan"
    assert tools.month_to_numeric(inp) == "1"
    inp = "January"
    assert tools.month_to_numeric(inp) == "1"
    inp = "1"
    assert tools.month_to_numeric(inp) == "1"
    inp = "December"
    assert tools.month_to_numeric(inp) == "12"
    inp = "dec"
    assert tools.month_to_numeric(inp) == "12"

