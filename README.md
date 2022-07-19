# OBO Database Ingestion

This repository shows how databases can be formalized as an OBO Ontology in the OBO flat file format,
OWL format, and OBO Graph JSON format. A list of the databases whose controlled vocabularies and related
content can be readily converted to OBO can be in found in the [PyOBO](https://github.com/pyobo/pyobo)
source code's `sources/` folder [here](https://github.com/pyobo/pyobo/tree/master/src/pyobo/sources).

Further discussion:

- [Limits of ontologies: How should databases be represented in OBO?](https://docs.google.com/presentation/d/1aySEHTgkags7UPJYHyvQ9frYvAIqr1G5A3u7dGF26Y4) presented by Chris Mungall
- https://github.com/OBOFoundry/OBOFoundry.github.io/discussions/1981

## Contents

Each resource gets a subdirectory in the [export/](export/) directory
containing the following exports:

- [OWL (functional syntax)](http://www.w3.org/TR/owl2-syntax/)
- [OBO](http://purl.obolibrary.org/obo/oboformat)
- [OBO Graph JSON](https://github.com/geneontology/obographs/)

## Build

To generate OBO files, run the following shell commands (Python 3.6+):

```shell
$ pip install tox
$ tox
```
