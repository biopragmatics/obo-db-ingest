# OBO Database Ingestion

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.10829095.svg)](https://doi.org/10.5281/zenodo.10829095)

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
- [Simple Standard for Sharing Ontological Mappings (SSSOM)](https://w3id.org/sssom)

A manifest of all resources is available at [manifest.yml](docs/_data/manifest.yml).

## Build

To generate OBO files, run the following shell commands (Python 3.8+):

```console
$ pip install tox
$ tox
```

## PURLs

See PURL configuration at https://github.com/perma-id/w3id.org/tree/master/biopragmatics. 
This W3ID entry makes ontology artifacts in the "export" folder (https://github.com/biopragmatics/obo-db-ingest/tree/main/export) resolvable.
Here are a few examples:

| Resource | Version Type | Example PURL                                                                   |
|----------|--------------|--------------------------------------------------------------------------------|
| Reactome | Sequential   | https://w3id.org/biopragmatics/resources/reactome/83/reactome.obo              |
| Interpro | Major/Minor  | https://w3id.org/biopragmatics/resources/interpro/92.0/interpro.obo            |
| Interpro | Semantic     | https://w3id.org/biopragmatics/resources/drugbank.salt/5.1.9/drugbank.salt.obo |
| MeSH     | Year         | https://w3id.org/biopragmatics/resources/mesh/2003/mesh.obo.gz                 |
| UniProt  | Year/Month   | https://w3id.org/biopragmatics/resources/uniprot/2022_05/uniprot.obo.gz        |
| HGNC     | Date         | https://w3id.org/biopragmatics/resources/hgnc/2023-02-01/hgnc.obo              |
| CGNC     | unversioned  | https://w3id.org/biopragmatics/resources/cgnc/cgnc.obo                         |
