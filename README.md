![Travis (.org)](https://img.shields.io/travis/HenryDayHall/next_paper_hunter)
![Codecov](https://img.shields.io/codecov/c/gh/HenryDayHall/next_paper_hunter)
# NExT paper finder

A package to find papers by the NExT institute.
Also contains some other LaTeX utility functions.

### Setting up
Download the package directly from github, 
or install with pip;
```
pip install git+https://github.com/HenryDayHall/next_paper_hunter
```

Make a folder for the output to go in, and add a file with the date to scan to.
```
mkdir /path/to/NExT_papers
echo "2010-01-01" > /path/to/NExT_papers/my_prefix_last_run.txt
```
This would cause the finder to check from the present day to the start of 2010.
The prefix `my_prefix_` can be anything or nothing.

Then call the function `check_for_papers` in `next_papers.py`;
```
ipython3
In [1]: from next_paper_hunter import next_papers
In [2]: next_papers.check_for_papers("/path/to/NExT_papers/my_prefix_")
To follow progress do
 >> tail -f /path/to/NExT_papers/my_prefix_<current_date>.log
```

The command takes a long time, because the api requests to arXiv are time delayed,
as required in `https://export.arxiv.org/robots.txt`.
It will create `my_prefix_is_NExT.bib`, a bibLaTeX bibliography containing all the papers
found to be NExT, `my_prefix_not_NExT.bib` a bibliography for all other papers,
which prevents it from checking if a paper is a NExT paper more than once,
and `my_prefix_authors.txt`, a list of all possible NExT authors found.
