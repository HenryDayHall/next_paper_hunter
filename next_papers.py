import numpy as np
from ipdb import set_trace as st
import time
import logging
from datetime import datetime
import pybtex.database
import os
import io
import pdfplumber
import urllib
import xml
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
    logging.log(LOGLEVEL, f"Fetching {url}")
    data = urllib.request.urlopen(url).read()
    return data


def get_paper_pdf(arxiv_id):
    url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"
    data = request_url(url)
    io_bytes = io.BytesIO(data)
    pdf_object = pdfplumber.open(io_bytes)
    return pdf_object


def check_pdf_for_next(pdf_object):
    # acknowldgments are normally at the end so work backwards
    text = ""
    for page in pdf_object.pages[::-1]:
        previous_page = page.extract_text()
        if previous_page is None:
            continue
        previous_page = alpha_only(page.extract_text())
        text = previous_page + " " + text
        if check_text_is_next(text):
            return True
    if len(text.strip()) == 0:
        logging.warning("PDF appears empty")
    return False


def alpha_only(text):
    """Given a string return a
    string with only alphabetical charicters and spaces"""
    text = [c if c.isalpha() else " " for c in text]
    text = ''.join(text)
    return text


def check_text_is_next(clean_text):
    """Check if a given string represents
    the text of a NExT collaboration paper"""
    next_string = "NExT"
    if next_string not in clean_text:
        return False
    start_acknowldgments = clean_text.find("cknowledgement")
    if start_acknowldgments == -1:
        start_acknowldgments = clean_text.find("cknowledgment")
    if start_acknowldgments == -1:
        start_acknowldgments = clean_text.find("thank")
    if start_acknowldgments == -1:
        start_acknowldgments = clean_text.find("Thank")
    if start_acknowldgments == -1:
        # no idea where the acknowldgments start,
        # require full string
        # but ignore spacing
        institute_string = "NExTInstitute"
        clean_text = clean_text.replace(" ", "")
        next_string = institute_string
        start_acknowldgments = 0
    is_next = next_string in clean_text[start_acknowldgments:]
    if is_next:
        location = clean_text.find(next_string)
        context = clean_text[max(location - 20, 0): location + 30]
        logging.log(LOGLEVEL, f'Classified as NExT due to; "{context}"')
    return is_next


def check_is_next(arxiv_id):
    """Check if an arXiv id refers to a paper from NExT"""
    pdf_object = get_paper_pdf(arxiv_id)
    return check_pdf_for_next(pdf_object)


class KnownAuthors:
    """Keep track of authors we have seen"""
    field_sep = "#"

    def __init__(self, file_path):
        self.file_path = file_path
        self.is_next = set()
        self.not_next = set()
        self.maybe_next = set()
        if os.path.exists(file_path):
            self.__parse_file()

    def __parse_file(self):
        """Read the existing authors from disk"""
        with open(self.file_path, 'r') as file_obj:
            for line in file_obj.readlines():
                line = line.strip()
                if len(line) == 0:
                    continue  # ignore empty lines
                if line.count(self.field_sep) != 1:
                    msg = f"line\n{line}\npoorly formatted\n" +\
                          f"expected exactly one '{self.field_sep}'\n" +\
                          "fix {self.file_path} and run again"
                    raise ValueError(msg)
                name, membership = line.split(self.field_sep)
                try:
                    self.add_author(name, membership)
                except ValueError as e:
                    msg = str(e) + \
                          f"found in line\n{line}\n" + \
                          "fix {self.file_path} and run again"
                    raise ValueError(msg)
        logging.log(LOGLEVEL, f"In file {self.file_path} found " +
                     f"{len(self.is_next)} confirmed NExT authors, " +
                     f"{len(self.maybe_next)} possible NExT authors, " +
                     f"{len(self.not_next)} non-NExT authors, ")

    def save(self):
        """Write the authors to disk """
        text = ""
        yes_suffix = f" {self.field_sep} yes\n"
        for name in self.is_next:
            text += name + yes_suffix
        no_suffix = f" {self.field_sep} no\n"
        for name in self.not_next:
            text += name + no_suffix
        maybe_suffix = f" {self.field_sep} maybe\n"
        for name in self.maybe_next:
            text += name + maybe_suffix
        with open(self.file_path, 'w') as file_obj:
            file_obj.write(text)
        logging.log(LOGLEVEL, f"Written authors to {self.file_path}")

    def add_author(self, name, membership="maybe"):
        """We only use a name becuase no other field is garenteed to be consistant
        Overscanning shouldn't be too much of an issue"""
        membership = membership.lower()
        initial, last = get_initial_last(name)
        name = f"{initial}. {last}" if initial is not None else last
        # remove it from maybe
        self.maybe_next.discard(name)
        if "no" in membership:
            self.not_next.add(name)
            self.is_next.discard(name)
        elif "yes" in membership or "is" in membership:
            self.is_next.add(name)
            self.not_next.discard(name)
        elif "maybe" in membership:
            # only maybe if we don't have better info
            if name not in self.is_next and name not in self.not_next:
                self.maybe_next.add(name)
        else:
            msg = f"Cant understand membership status {membership}\n" +\
                   " expected 'yes', 'no' or 'maybe'"
            raise ValueError(msg)


class KnownPapers:
    """Keep track of papers we have found """
    def __init__(self, file_is_next, file_not_next):
        self.file_is_next, self.is_next, self.ids_is_next = \
                self.__setup(file_is_next)
        logging.log(LOGLEVEL, f"In {file_is_next} found {len(self.is_next.entries)} items")
        self.file_not_next, self.not_next, self.ids_not_next = \
                self.__setup(file_not_next)
        logging.log(LOGLEVEL, f"In {file_not_next} found {len(self.not_next.entries)} items")

    def __setup(self, file_path):
        assert file_path.endswith(".bib"),\
                f"Expected a '.bib' file, found {file_path}"
        ids = {}  # key is arxiv id, value is bib key
        if os.path.exists(file_path):
            bib_data = pybtex.database.parse_file(file_path)
            for key, entry in bib_data.entries.items():
                arxiv_id = entry.fields['eprint'].split('v')[0]
                ids[arxiv_id] = key
        else:
            bib_data = pybtex.database.BibliographyData()
        return file_path, bib_data, ids

    def save(self):
        self.is_next.to_file(self.file_is_next)
        self.not_next.to_file(self.file_not_next)

    def update_paper(self, arxiv_id, new_entry, in_next):
        logging.log(LOGLEVEL, f"{arxiv_id} recognised")
        if in_next:
            bib_object = self.is_next
            key = self.ids_is_next[arxiv_id]
        else:
            bib_object = self.not_next
            key = self.ids_not_next[arxiv_id]
        existing_date = bib_object.entries[key].fields["last_update"]
        existing_date = datetime.fromisoformat(existing_date)
        new_date = new_entry.fields["last_update"]
        new_date = datetime.fromisoformat(new_date)
        if new_date > existing_date:
            logging.log(LOGLEVEL, f"Found update for {arxiv_id}")
            bib_object.entries[key] = new_entry

    def add_paper(self, bib_entry):
        arxiv_id = bib_entry.fields['eprint'].split('v')[0]
        # check if we have it
        if arxiv_id in self.ids_is_next:
            next_paper = True
            self.update_paper(arxiv_id, bib_entry, next_paper)
        elif arxiv_id in self.ids_not_next:
            next_paper = False
            self.update_paper(arxiv_id, bib_entry, next_paper)
        else:  # new entry
            try:
                next_paper = check_is_next(arxiv_id)
            except pdfplumber.pdfminer.pdfparser.PDFSyntaxError:
                logging.warning(f"Failed to get PDF for {arxiv_id}")
                return False
            key = make_bib_key(bib_entry)
            if next_paper:
                logging.log(LOGLEVEL, f"Added {arxiv_id} as NExT")
                self.ids_is_next[arxiv_id] = key
                self.is_next.add_entry(key, bib_entry)
            else:
                logging.log(LOGLEVEL, f"{arxiv_id} is not NExT")
                self.ids_not_next[arxiv_id] = key
                self.not_next.add_entry(key, bib_entry)
        return next_paper


def get_initial_last(name):
    name = name.replace('.', ' ')
    *first, last = name.split()
    if len(first):
        initial = first[0][0]
    else:
        initial = None
    return initial, last


def check_for_papers(prefix="./"):
    log_file = prefix + str(datetime.today().date()) + ".log"
    logging.basicConfig(filename=log_file, level=LOGLEVEL)
    print("To follow progress do \n" + 
          f" >> tail -f {log_file}")

    date_file = prefix + "last_run.txt"
    if os.path.exists(date_file):
        with open(date_file, 'r') as date_f:
            start_date = date_f.read().strip()
    else:
        start_date = "2021-04-01"
    logging.log(LOGLEVEL, f"Checking back to date={start_date}")
    start_date = datetime.fromisoformat(start_date)

    authors_file = prefix + "authors.txt"
    known_authors = KnownAuthors(authors_file)
    if len(known_authors.is_next) == 0:
        raise ValueError(f"No NExT authors in {authors_file}")

    is_next_bib_file = prefix + "is_NExT.bib"
    not_next_bib_file = prefix + "not_NExT.bib"
    known_papers = KnownPapers(is_next_bib_file, not_next_bib_file)

    for author in known_authors.is_next:
        logging.log(LOGLEVEL, f"Checking author {author}")
        check_author_name(known_papers, known_authors, author, start_date)

    with open(date_file, 'w') as date_f:
        date_f.write(str(datetime.today().date()))
    known_papers.save()
    known_authors.save()
    logging.log(LOGLEVEL, f"Done")


def check_author_name(known_papers, known_authors, author, start_date):
    # author names tend to be given "first last"
    # for a search string we need last,&first
    initial, last = get_initial_last(author)
    author = f"{last},&{initial}" if initial is not None else last
    query = f"http://export.arxiv.org/api/query?search_query=au:{author}&sortBy=lastUpdatedDate&sortOrder=descending&start="
    page = 0
    while True:
        xml_string = request_url(query + str(page))
        xml_tree = xml.etree.ElementTree.fromstring(xml_string)
        for part in xml_tree:
            if part.tag.endswith("entry"):
                bib_entry, last_update, paper_authors = xml_entry_to_bib(part)
                known_papers.add_paper(bib_entry)
                for paper_author in paper_authors:
                    known_authors.add_author(paper_author)
        if last_update < start_date:
            return
        page += 1


def xml_entry_to_bib(xml_entry):
    bib_fields = {"archivePrefix": "arXiv"}
    authors = []
    for part in xml_entry:
        tag = part.tag.split("}")[-1]
        if tag == "id":
            url = part.text
            bib_fields["url"] = url
            bib_fields["eprint"] = url.split("/abs/")[-1]
        elif tag == "title":
            logging.log(LOGLEVEL, f'Paper title "{part.text}"')
            bib_fields["title"] = part.text
        elif tag == "author":
            for subpart in part:
                if subpart.tag.endswith("name"):
                    authors.append(subpart.text)
        elif tag == "updated":
            last_update = datetime.fromisoformat(part.text[:-1])
            # this isn't really a field but adding it should break anything
            bib_fields["last_update"] = part.text[:-1]
        elif tag == "published":  # this is the date we care about
            date = part.text
            year, month, _ = date.split('-')
            bib_fields["year"] = year
            bib_fields["month"] = month
        elif tag == "summary":
            bib_fields["abstract"] = part.text
        elif tag == "doi":
            bib_fields["doi"] = part.text
        elif tag == "journal_ref":
            # this information appears to be a mix of
            # journal, pages and volume
            bib_fields["journal"] = part.text
    bib_persons = {'author': [pybtex.database.Person(author)
                              for author in authors]}
    bib_entry = pybtex.database.Entry("paper", bib_fields, bib_persons)
    return bib_entry, last_update, authors


def make_bib_key(bib_entry):
    fields = bib_entry.fields
    author = bib_entry.persons['author'][0].last()[-1]
    author = ''.join(list(filter(lambda c: c.isalpha(), author)))
    title = ''.join(list(filter(lambda c: c.isalpha(), fields['title'])))
    key = f'{author}:{fields["year"]}+{title[:5]}'
    return key

## don't use these..... arXiv robot.txt forbits downloading e-prints.
#import gzip
#import tarfile
#import zipfile
#
#def unpack_tex_from_tar(byte_tar):
#    """Given a bytestring representing a tar containing tex files,
#    return the texfiles as bytestring"""
#    io_bytes = io.BytesIO(byte_tar)
#    tar_file = tarfile.open(fileobj=io_bytes, mode='r')
#    members = tar_file.getmembers()
#    data = b""
#    for member in members:
#        if member.name.endswith(".tex"):
#            with tar_file.extractfile(member) as file_obj:
#                if file_obj is not None:
#                    data += file_obj.read()
#    return data
#
#
#def unpack_tex_from_zip(byte_zip):
#    """Given a bytestring representing a zip containing tex files,
#    return the texfiles as bytestring"""
#    io_bytes = io.BytesIO(byte_zip)
#    zip_file = zipfile.ZipFile(io_bytes, mode='r')
#    members = zip_file.namelist()
#    data = b""
#    for member in members:
#        if member.endswith(".tex"):
#            with zip_file.open(member) as file_obj:
#                data += file_obj.read()
#    return data
#
#
#def get_paper_tex(arxiv_id):
#    """Get the tex files in a paper"""
#    url = "http://arxiv.org/e-print/" + arxiv_id
#    data = urllib.request.urlopen(url).read()
#    try:
#        data = gzip.decompress(data)
#        print("Was gzipped")
#    except OSError:
#        pass  # not a gzip
#    try:
#        data = unpack_tex_from_tar(data)
#        print("Was tar")
#    except tarfile.ReadError:
#        pass  # not a tar
#    try:
#        data = unpack_tex_from_zip(data)
#        print("Was zip")
#    except zipfile.BadZipFile:
#        pass  # not a zip
#    return data
#
