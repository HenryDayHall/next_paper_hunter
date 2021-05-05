import json
import tools
import latex_bib

# functions for reading latex files ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

def get_ordered_citations(aux_path):
    with open(aux_path, 'r') as aux_file:
        text = aux_file.read()
    cite_start = "\\abx@aux@cite"
    cites = []
    untrimmed_cites = text.split(cite_start)[1:]
    for untrimmed in untrimmed_cites:
        end = tools.locate_closing_brace(untrimmed, 0)
        if end == -1:
            raise ValueError(f"No end to citation key {untrimmed} found")
        cite = untrimmed[1: end]
        if cite not in cites:
            cites.append(cite)
    return cites


# functions for talking to inspires ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

def get_inspire_key(bib_item, other_fields=None):
    errors = {}
    if isinstance(bib_item, dict):
        bib_fields = bib_item
    else:
        bib_fields = bib_item.fields
    if "doi" in bib_fields:
        # can have more than 1 doi
        string = bib_fields["doi"].split(',', 1)[0]
        string = tools.strip_formating(string, whitespace=True)
        search = f'find doi "{string}"'
        try:
            return _get_inspire_key(search, other_fields)
        except ValueError as e:
            errors["doi"] = e
        # sometimes this is actually an arXiv number
        search = f'find eprint arxiv:{string}'
        try:
            return _get_inspire_key(search, other_fields)
        except ValueError as e:
            errors["arxiv"] = e
    if "eprint" in bib_fields:
        string = bib_fields["eprint"].split(',', 1)[0]
        string = tools.strip_formating(string, whitespace=True)
        search = f'find eprint "{string}"'
        try:
            return _get_inspire_key(search, other_fields)
        except ValueError as e:
            errors["eprint"] = e
    if "title" in bib_fields:
        string = bib_fields["title"]
        string = tools.strip_formating(string, whitespace_to_space=True)
        search = f'find title "{string}"'
        try:
            return _get_inspire_key(search, other_fields)
        except ValueError as e:
            errors["title"] = e
    if "author" in bib_fields:
        string = bib_fields["author"]
        string = tools.strip_formating(string, whitespace_to_space=True,
                                       comma=True, dot=True)
        string = string.replace('and', '')
        search = f'find author "{string}"'
        try:
            return _get_inspire_key(search, other_fields)
        except ValueError as e:
            errors["author"] = e
    raise ValueError(str(errors))


def _get_inspire_key(search, other_fields=None):
    if other_fields is None:
        other_fields = []
    key_tag = "system_control_number"
    out_tags = [key_tag, *other_fields]
    data = query_inspire(search, out_tags)
    if len(data) > 1:
        raise ValueError("Not enough unique info")
    if len(data) == 0:
        raise ValueError(f"No match found for {search}")
    key_list = data[0][key_tag]
    if isinstance(key_list, dict):
        key_list = [key_list]
    try:
        key = next(k['value'] for k in key_list
                   if k['institute'] == 'SPIRESTeX'
                   or k['institute'] == 'INSPIRETeX')
    except StopIteration:
        raise ValueError(f"No Inspires key in {key_list}")
    other = {field: data[0][field] for field in other_fields}
    return key, other


def query_inspire(search_pattern, out_tags=None):
    search_pattern = search_pattern.replace(' ', '+').replace("/", "%2F")
    url = "http://old.inspirehep.net/search?p=" + search_pattern
    url += "&of=recjson"
    if out_tags is not None:
        if isinstance(out_tags, str):
            out_tags = [out_tags]
        url += "&ot=" + ','.join(out_tags)
    data = tools.request_url(url)
    data = json.loads(data)
    return data


# functions for writing latex files ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

def update_entries_in_bib(biblography, cite_order):
    updated_key_dict = {}
    for key, entry in biblography.items():
        month = entry.fields["month"]
        entry.fields["month"] = tools.month_to_numeric(month)
        try:
            new_key, _ = get_inspire_key(entry)
        except ValueError:
            print(f"Didn't find {entry.fields['title']} in INSPIRES")
            new_key = latex_bib.make_bib_key(entry)
        updated_key_dict[key] = new_key
    for old_key, new_key in updated_key_dict.items():
        biblography.change_key(old_key, new_key)
    # make sure there are no duplicates in the new cite order
    new_cite_order = []
    for key in cite_order:
        new_key = updated_key_dict[key]
        if new_key not in new_cite_order:
            new_cite_order.append(new_key)
    return biblography, new_cite_order, updated_key_dict


def update_bib_keys_in_tex(tex_file_name, updated_dict):
    with open(tex_file_name, 'r') as tex_file:
        text = tex_file.read()
    cite_str = "\\cite{"
    cite_len = len(cite_str)
    cite_end = 0
    cite_start = text.find(cite_str)
    new_text = ""
    while cite_start > -1:
        # add the previous segment
        new_text += text[cite_end: cite_start + cite_len]
        # get the new cites
        cite_end = text.find('}', cite_start)
        cites = text[cite_start + cite_len:cite_end].split(',')
        new_cites = [updated_dict.get(c.strip(), c) for c in cites]
        # add the new cites
        new_text += ','.join(new_cites)
        cite_start = text.find(cite_str, cite_end)
    # add the last segment
    new_text += text[cite_end:]
    new_name = tex_file_name + ".sorted"
    with open(new_name, 'w') as new_file:
        new_file.write(new_text)

