import numpy as np
import time
from datetime import datetime
import pybtex.database
import os
import io
import pdfplumber
import urllib
import xml


def get_paper_pdf(arxiv_id):
    url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"
    data = urllib.request.urlopen(url).read()
    io_bytes = io.BytesIO(data)
    pdf_object = pdfplumber.open(io_bytes)
    return pdf_object


def check_pdf_for_next(pdf_object):
    # acknowldgments are normally at the end so work backwards
    text = ""
    for page in pdf_object.pages[::-1]:
        previous_page = alpha_only(page.extract_text())
        text = previous_page + " " + text
        if check_text_is_next(text):
            return True
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
        return institute_string in clean_text
    return next_string in clean_text[start_acknowldgments:]


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

    def add_author(self, name, membership="maybe"):
        """We only use a name becuase no other field is garenteed to be consistant
        Overscanning shouldn't be too much of an issue"""
        membership = membership.lower()
        name = name.strip()
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
        self.file_not_next, self.not_next, self.ids_not_next = \
                self.__setup(file_not_next)

    def __setup(self, file_path):
        assert file_path.endswith(".bib"),\
                f"Expected a '.bib' file, found {file_path}"
        ids = {}  # key is arxiv id, value is bib key
        if os.path.exists(file_path):
            bib_data = pybtex.database.parse_file(file_path)
            for key, entry in bib_data.items():
                arxiv_id = entry.fields['eprint'].split('v')[0]
                ids[arxiv_id] = key
        else:
            bib_data = pybtex.database.BibliographyData()
        return file_path, bib_data, ids

    def save(self):
        self.is_next.to_file(self.file_is_next)
        self.not_next.to_file(self.file_not_next)

    def add_paper(self, key, bib_entry):
        arxiv_id = bib_entry.fields['eprint'].split('v')[0]
        # check if we have it
        if arxiv_id in self.ids_is_next:
            # update
            key = self.ids_is_next[arxiv_id]
            self.is_next.entries[key] = bib_entry
            next_paper = True
        elif arxiv_id in self.ids_not_next:
            # update
            key = self.ids_not_next[arxiv_id]
            self.not_next.entries[key] = bib_entry
            next_paper = False
        else:  # new entry
            next_paper = check_is_next(arxiv_id)
            if next_paper:
                self.is_next.add_entry(key, bib_entry)
            else:
                self.not_next.add_entry(key, bib_entry)
        return next_paper


def check_for_papers(known_papers, known_authors, author, start_date):
    author = author.replace(" ", "+")
    query = f"http://export.arxiv.org/api/query?search_query=au:{author}&sortBy=lastUpdatedDate&sortOrder=ascending&start="
    page = 0
    while True:
        xml_string = urllib.request.urlopen(query + str(page)).read()
        xml_tree = xml.etree.ElementTree.fromstring(xml_string)
        for part in xml_tree:
            if part.tag.endswith("entry"):
                key, bib_entry, last_update, authors = xml_entry_to_bib(part)
                known_papers.add_paper(key, bib_entry)
                for author in authors:
                    known_authors.add_author(author)
        if last_update < start_date:
            return
        time.sleep(3)  # wait 3 seconds before next request
        page += 1


def xml_entry_to_bib(xml_entry):
    bib_fields = {"archivePrefix": "arXiv"}
    authors = []
    for part in xml_entry:
        tag = part.tag.split("}")[-1]
        if tag == "id":
            url = part.text
            bib_fields["url"] = url
            bib_fields["eprint"] = url.split("/")[-1]
        elif tag == "title":
            bib_fields["title"] = part.text
        elif tag == "author":
            for subpart in part:
                authors.append(subpart.text)
        elif tag == "updated":
            last_update = datetime.fromisoformat(part.text[:-1])
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
    key = ''.join(list(filter(lambda c: c.isalpha(), authors[0]))) + \
            ":" + bib_fields["year"] + bib_fields["Title"].strip()[:5]
    bib_persons = {'author': authors}
    bib_entry = pybtex.database.Entry("paper", bib_fields, bib_persons)
    return key, bib_entry, last_update, authors
                

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
