import tools
from ipdb import set_trace as st
import numpy as np
import os
from tools import LOGLEVEL
import logging


def get_initial_last(name):
    name = name.replace('.', ' ')
    *first, last = name.split()
    if len(first):
        initial = first[0][0]
    else:
        initial = None
    return initial, last


def make_bib_key(bib_entry):
    fields = bib_entry.fields
    author_strings = tools.alpha_only(fields["author"]).split()
    author = next((auth for auth in author_strings
                   if len(auth) > 1 and
                   "collaboration" not in auth.lower()),
                  author_strings[0])
    key = f'{author}:{fields["year"]}:{fields["eprint"]}'
    return key


def split_bib(bib_string):
    bib_entries = []
    start_key = "@"
    next_start = bib_string.find(start_key)
    while next_start > -1:
        entry_type, entry_key, fields, end =\
            read_bib_entry(bib_string[next_start:])
        next_start = bib_string.find(start_key, next_start + end)
        bib_entries.append(BibEntry(fields, key=entry_key,
                                    entry_type=entry_type))
    return bib_entries


def get_bib_entry_key(bib_string):
    try:
        key_string = bib_string.split('{', 1)[1].split(',', 1)[0]
    except IndexError:
        message = "Problem in bib string;\n" + bib_string
        raise IndexError(message)
    return key_string.strip()


def read_bib_entry(entry_string):
    # this may contain more than just the entry
    # but it wills tart with the entry
    last_char = len(entry_string) - 1
    entry_string = entry_string.strip()
    # the entry type should be capitalised for neatness
    try:
        entry_type = entry_string.split('@', 1)[1].split('{', 1)[0]
    except IndexError as err:
        msg = f"Problems finding entry type in entry;\n{entry_string}"
        raise ValueError(msg) from err
    entry_type = entry_type.capitalize()
    # can use existing function to get the key
    entry_key = get_bib_entry_key(entry_string)

    fields = {}
    # there can be = insie titles
    # the first entry has no comma, the key starts at char 0
    key_starts = entry_string.find(',') + 1
    brackets = {'"': '"', '{': '}'}
    while key_starts:
        key_ends = entry_string.find('=', key_starts)
        key = entry_string[key_starts:key_ends].strip().lower()
        char_reached = key_ends
        while char_reached < last_char:
            char_reached += 1
            char = entry_string[char_reached]
            if char in brackets:
                field_end = tools.locate_closing_brace(entry_string,
                                                       char_reached,
                                                       brackets[char])
                content = entry_string[char_reached+1:field_end]
                # only white space is single space
                content = ' '.join(content.split())
                fields[key] = content
                break
        else:
            err_msg = (f"Problem in entry with key {entry_key}\n" +
                       f" couldn't find end of field {key}")
            raise ValueError(err_msg)

        char_reached = field_end
        # now see if there is another field
        while char_reached < last_char:
            char_reached += 1
            if entry_string[char_reached] == '=':
                key_starts = entry_string.find(',', field_end) + 1
                break
            if entry_string[char_reached] == "}":
                key_starts = False
                entry_ends = char_reached + 1
                break
        else:
            err_msg = (f"Problem in entry with key {entry_key}\n" +
                       f" couldn't find field after {key}, or closing brace")
            raise ValueError(err_msg)
    return entry_type, entry_key, fields, entry_ends


class Bibliography:
    def __init__(self, bib_file=None):
        # key = bibkey, value = BibEntry
        self._entries = {}
        if bib_file is not None:
            self.add_file(bib_file)

    def __getitem__(self, key):
        return self._entries[key]

    def __setitem__(self, key, entry):
        assert isinstance(key, str), \
            f"Bib keys should be strings, not type({key}) = {type(key)}"
        assert isinstance(entry, BibEntry), \
            f"Bib entrys should be BibEntry, not type({entry}) = {type(entry)}"
        assert key == entry.key, \
            f"Bib key should be same as entry.key, {key} != {entry.key}"
        self._entries[key] = entry

    def __delitem__(self, key):
        del self._entries[key]

    def keys(self):
        return self._entries.keys()

    def values(self):
        return self._entries.values()

    def items(self):
        return self._entries.items()

    def __len__(self):
        return len(self._entries)

    def __iter__(self):
        return iter(self._entries)

    def change_key(self, old_key, new_key):
        entry = self[old_key]
        entry.key = new_key
        del self[old_key]
        self[new_key] = entry

    def add_file(self, file_path):
        with open(file_path, 'r') as bib_file:
            bib_string = bib_file.read()
        self.add_file_string(bib_string)

    def add_file_string(self, file_string):
        for entry in split_bib(file_string):
            self.add_entry(entry)

    def add_entry_string(self, entry_string):
        entry = BibEntry(entry_string)
        self.add_entry(entry)

    def add_entry(self, entry):
        self[entry.key] = entry

    def to_string(self, cite_order=None):
        if cite_order is None:
            cite_order = sorted(self.keys())
        else:
            # check for dups
            no_dups = []
            for key in cite_order:
                if key not in no_dups:
                    no_dups.append(key)
            cite_order = no_dups
        ordered_cites = [str(self[key]) for key in cite_order]
        cite_sep = os.linesep + os.linesep
        text = cite_sep.join(ordered_cites)
        return text

    def save(self, file_path, cite_order=None):
        text = self.to_string(cite_order)
        with open(file_path, 'w') as bib_file:
            bib_file.write(text)


class BibEntry:
    def __init__(self, content, key=None, entry_type=None):
        self.key = key
        self.entry_type = entry_type
        if isinstance(content, dict):
            self.fields = content
        elif isinstance(content, str):
            read_type, read_key, self.fields, _ = read_bib_entry(content)
            if self.key is None:
                self.key = read_key
            if self.entry_type is None:
                self.entry_type = read_type
        else:
            raise TypeError("content must be dict of fields, " +
                            "or string containing bibLaTeX entry.\n" +
                            f"Given type {type(content)}")
        if self.key is None:
            self.key = make_bib_key(self)
        if self.entry_type is None:
            self.entry_type = "Article"

    def __str__(self):
        text = "@" + self.entry_type.capitalize() + "{"
        text += " " + self.key + ",\n"
        longest_field_key = np.max([len(key) for key in self.fields])
        for key in self.fields:
            text += "    " + key.ljust(longest_field_key) + " = "
            field = self.fields[key]
            missmatch = tools.check_braces_match(field)
            # stick braces on the end or beginning to force a match
            if missmatch > 0:
                # space prevents escaping the new braces
                field += " " + "}"*missmatch
                message = f"In bib entry {self.key}, field {key} " +\
                          f"was missing {missmatch} closing braces"
                logging.log(LOGLEVEL, message)
            elif missmatch < 0:
                field = "{"*abs(missmatch) + field
                message = f"In bib entry {self.key}, field {key} " +\
                          f"was missing {missmatch} opening braces"
                logging.log(LOGLEVEL, message)
            text += "{" + self.fields[key] + "},\n"
        text += "}"
        return text
            
# functions to check a bib entry ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~


def bib_missing_fields(entry_type, fields):
    required_fields = ["author", "title", "year"]
    if entry_type == "Article":
        required_fields += ["journal", "volume", "pages", "eprint"]
    elif entry_type == "Book":
        required_fields += ["publisher"]
    elif entry_type == "Inproceedings":
        required_fields += ["booktitle"]
    not_found = [field for field in required_fields if field not in fields]
    return not_found

