# PyOBO Conversion Examples

This repository shows how databases can be formalized in the same way as OBO. A list of the databases whose controlled
vocabularies can be readily converted to OBO can be in found in the PyOBO source code's `sources/` folder
[here](https://github.com/pyobo/pyobo/tree/master/src/pyobo/sources).

## Contents

Each resource gets a subdirectory in the [export/](export/) directory
containing the following exports:

- [OWL (functional syntax)](http://www.w3.org/TR/owl2-syntax/)
- [OBO](http://purl.obolibrary.org/obo/oboformat)
- [OBO Graph JSON](https://github.com/geneontology/obographs/)

## Build

To generate OBO files, run the following shell commands (Python 3.6+):

```shell
$ pip install pyobo
$ python build.py -v
```

Remove the `-v` for more silent, or add an extra `-v` for debug mode.

