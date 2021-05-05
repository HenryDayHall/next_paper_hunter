import latex_bib, tools
import os


def test_get_initial_last():
    name = "Samwise Gamgee"
    initial, last = latex_bib.get_initial_last(name)
    assert initial == "S"
    assert last == "Gamgee"
    name = "S. Gamgee"
    initial, last = latex_bib.get_initial_last(name)
    assert initial == "S"
    assert last == "Gamgee"
    name = "S.Gamgee"
    initial, last = latex_bib.get_initial_last(name)
    assert initial == "S"
    assert last == "Gamgee"


def test_make_bib_key():
    bib_entry = latex_bib.BibEntry({'author': "Collaboration Hobbit",
                                    'year': "1341",
                                    'eprint': "1111.1111"},
                                   key="LOTR:1341ring",
                                   entry_type="Book")
    expected = "Hobbit:1341:1111.1111"
    assert latex_bib.make_bib_key(bib_entry) == expected


def read_sample():
    bib_sample = "test/sample.bib"
    with open(bib_sample, 'r') as bib:
        bib_string = bib.read()
    return bib_string


def test_split_bib():
    bib_string = read_sample()
    bib_entries = latex_bib.split_bib(bib_string)
    assert len(bib_entries) == 2
    for bib_entry in bib_entries:
        assert isinstance(bib_entry, latex_bib.BibEntry)
        assert len(bib_entry.fields) > 1


def test_get_bib_entry_key():
    bib_strings = [str(e) for e in latex_bib.split_bib(read_sample())]
    key = "Gallicchio_2010"
    assert latex_bib.get_bib_entry_key(bib_strings[0]) == key
    key = "chakraborty2020revisiting"
    assert latex_bib.get_bib_entry_key(bib_strings[1]) == key


def test_read_bib_entry():
    bib_entries = read_sample()
    
    entry_type, entry_key, fields, end = latex_bib.read_bib_entry(bib_entries)
    assert entry_key == "Gallicchio_2010"
    assert entry_type == "Article"
    
    expected_fields = dict(title="Seeing in Color: Jet Superstructure",
                           volume="105",
                           issn="1079-7114",
                           url="http://dx.doi.org/10.1103/PhysRevLett.105.022001",
                           doi="10.1103/physrevlett.105.022001",
                           number="2",
                           journal="Physical Review Letters",
                           publisher="American Physical Society (APS)",
                           author="Gallicchio, Jason and Schwartz, Matthew D.",
                           year="2010",
                           month="Jul")
    assert len(expected_fields) == len(fields)
    for key in expected_fields:
        assert fields[key] == expected_fields[key], \
            f"fields[{key}]={fields[key]} but expected {expected_fields[key]}"

    entry_type, entry_key, fields, end = latex_bib.read_bib_entry(bib_entries[end:])
    assert entry_key == "chakraborty2020revisiting"
    assert entry_type == "Misc"

    expected_fields = dict(title="Revisiting Jet Clustering Algorithms for New Higgs Boson Searches in Hadronic Final States",
                           author="Amit Chakraborty and Srinandan Dasmahapatra and Henry Day-Hall and Billy Ford and Shubhani Jain and Stefano Moretti and Emmanuel Olaiya and Claire Shepherd-Themistocleous",
                           year="2020",
                           eprint="2008.02499",
                           archiveprefix="arXiv",
                           primaryclass="hep-ph")
    assert len(expected_fields) == len(fields)
    for key in expected_fields:
        assert fields[key] == expected_fields[key], \
            f"fields[{key}]={fields[key]} but expected {expected_fields[key]}"



def test_Bibliography():
    # make an empty one
    empty = latex_bib.Bibliography()
    assert len(empty) == 0
    bib_entry1 = latex_bib.BibEntry({'author': "Collaboration Hobbit",
                                     'year': "1341",
                                     'eprint': "1111.1111"},
                                    key="LOTR:1341ring",
                                    entry_type="Book")
    empty.add_entry(bib_entry1)
    assert len(empty) == 1
    # replace an entry
    bib_entry1.fields['author'] = "J.R.R. Tolkien"
    empty["LOTR:1341ring"] = bib_entry1
    assert len(empty) == 1
    
    # new entry
    bib_entry2 = latex_bib.BibEntry({'author': "Collaboration Sauron",
                                     'year': "1341",
                                     'eprint': "1111.1112"},
                                    key="Evil:1341doom",
                                    entry_type="Book")
    empty.add_entry(bib_entry2)
    assert len(empty) == 2

    assert empty["LOTR:1341ring"] == bib_entry1
    assert empty["Evil:1341doom"] == bib_entry2
    
    keys = ["LOTR:1341ring", "Evil:1341doom"]
    for key in empty:
        keys.remove(key)
    assert len(keys) == 0

    entries = [bib_entry1, bib_entry2]
    for entry in empty.values():
        entries.remove(entry)
    assert len(entries) == 0

    keys = ["LOTR:1341ring", "Evil:1341doom"]
    entries = [bib_entry1, bib_entry2]
    for key, entry in empty.items():
        entries.remove(entry)
        keys.remove(key)
    assert len(keys) == 0
    assert len(entries) == 0

    # change a key
    empty.change_key("Evil:1341doom", "Missunderstood:1341doom")
    found_keys = [key for key in empty.keys()]
    assert len(found_keys) == 2
    assert "LOTR:1341ring" in found_keys
    assert "Missunderstood:1341doom" in found_keys
    assert "Evil:1341doom" not in found_keys
    
    lotr_string = empty.to_string()
    assert "LOTR:1341ring" in lotr_string
    assert "Missunderstood:1341doom" in lotr_string
    assert "Evil:1341doom" not in lotr_string
    
    # we can read files we write
    file_name = "temp.bib"
    empty.save(file_name)
    lotr_bib = latex_bib.Bibliography(file_name)
    keys = ["LOTR:1341ring", "Missunderstood:1341doom"]
    for key in lotr_bib:
        keys.remove(key)
    assert len(keys) == 0
    os.remove(file_name)  # clean up
    
    # we can read standard files
    bib_sample = "test/sample.bib"
    sample = latex_bib.Bibliography(bib_sample)
    keys = ["chakraborty2020revisiting", "Gallicchio_2010"]
    for key in sample:
        keys.remove(key)
    assert len(keys) == 0



def test_BibEntry():
    bib_string = read_sample()

    keys = ["chakraborty2020revisiting", "Gallicchio_2010"]
    for entry in latex_bib.split_bib(bib_string):
        assert entry.key in keys
        alt = latex_bib.BibEntry(str(entry), key="Frodo",
                                 entry_type="Hobbit")
        assert alt.key == "Frodo"
        assert alt.entry_type == "Hobbit"
        alt_string = str(alt)
        assert "Frodo" in alt_string
        assert "Hobbit" in alt_string

