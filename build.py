# -*- coding: utf-8 -*-

"""Build OBO dumps of database.

This script requires ``pip install pyobo``.
"""

import datetime
import gzip
import os
import shutil
from pathlib import Path
from typing import Optional, TypedDict

import bioontologies.version
import bioregistry
import bioregistry.version
import click
import pyobo.version
import pystow.utils
import yaml
from bioontologies.robot import convert, convert_to_obograph
from more_click import verbose_option
from pyobo import Obo
from pyobo.sources import ontology_resolver
from tqdm import tqdm
from tqdm.contrib.logging import logging_redirect_tqdm
from typing_extensions import NotRequired


BASE_PURL = "https://w3id.org/biopragmatics/resources"
HERE = Path(__file__).parent.resolve()
DATA = HERE.joinpath("docs", "_data")
MANIFEST_PATH = DATA.joinpath("manifest.yml")
EXPORT = HERE.joinpath("export")
pystow.utils.GLOBAL_PROGRESS_BAR = False
#: This is the maximum file size (100MB, rounded down to
#: be conservative) to put on GitHub
MAX_SIZE = 100_000_000
PREFIXES = [
    "eccode",
    "uniprot",  # this one is used for basically everything after
    "rgd",
    "sgd",
    "mirbase",
    "mgi",
    "hgnc",
    "hgnc.genegroup",
    "pombase",  # after hgnc
    "rhea",
    "flybase",
    "zfin",  # after flybase
    "dictybase.gene",
    "cgnc",
    # "drugcentral", # stalling on something
    "complexportal",
    "interpro",
    "mesh",
    "mirbase.family",
    "mirbase.mature",
    "reactome",
    "wikipathways",
    "pathbank",
    #  "msigdb",
    "pfam",
    "pfam.clan",
    "npass",
    "kegg.genome",
    "slm",
]

for _prefix in PREFIXES:
    if _prefix != bioregistry.normalize_prefix(_prefix):
        raise ValueError(f"invalid prefix: {_prefix}")

NO_FORCE = {"drugbank", "drugbank.salt"}
GZIP_OBO = {"mgi", "uniprot", "slm", "reactome", "pathbank", "mesh"}


def _gzip(path: Path, suffix: str):
    output_path = path.with_suffix(suffix)
    with path.open("rb") as src, gzip.open(output_path, "wb") as dst:
        dst.writelines(src)
    path.unlink()
    return output_path


class Artifact(TypedDict):
    gzipped: bool
    iri: str
    path: str
    version_iri: NotRequired[str]
    version_path: NotRequired[str]


def _prepare_art(prefix: str, path: Path, has_version: bool, suffix: str) -> Artifact:
    gzipped = os.path.getsize(path) > MAX_SIZE
    if gzipped:
        tqdm.write(f"[{prefix}] gzipping {path}")
        output_path = _gzip(path, suffix)
    else:
        output_path = path

    if has_version:
        unversioned_path = EXPORT.joinpath(prefix, output_path.name)
        unversioned_relative = unversioned_path.relative_to(EXPORT)
        shutil.copy(output_path, unversioned_path)

        version_relative = output_path.relative_to(EXPORT)
        versioned_iri = f"{BASE_PURL}/{version_relative}"
    else:
        unversioned_path = output_path
        unversioned_relative = unversioned_path.relative_to(EXPORT)

        version_relative = None
        versioned_iri = None

    rv = Artifact(
        gzipped=gzipped,
        iri=f"{BASE_PURL}/{unversioned_relative}",
        path=unversioned_relative.as_posix(),
    )
    if versioned_iri:
        rv.update(
            version_iri=versioned_iri,
            version_path=version_relative.as_posix(),
        )
    return rv


def _get_summary(obo: Obo) -> dict:
    terms = [t for t in obo if t.prefix == obo.ontology]
    rv = {
        "terms": sum(term.prefix == obo.ontology for term in obo),
        "relations": sum(
            len(values) for term in terms for values in term.relationships.values()
        ),
        "properties": sum(
            len(values) for term in terms for values in term.properties.values()
        ),
        "synonyms": sum(len(term.synonyms) for term in terms),
        "xrefs": sum(len(term.xrefs) for term in terms),
        "alts": sum(len(term.alt_ids) for term in terms),
        "parents": sum(len(term.parents) for term in terms),
        "references": sum(len(term.provenance) for term in terms),
        "definitions": sum(term.definition is not None for term in terms),
        "version": obo.data_version,
    }
    return rv


def _make(prefix: str, module: type[Obo], do_convert: bool = False) -> dict:
    rv = {}
    obo = module(force=prefix not in NO_FORCE)

    directory = EXPORT.joinpath(prefix)
    has_version = bool(obo.data_version)
    if has_version:
        directory = directory.joinpath(obo.data_version)
    else:
        tqdm.write(click.style(f"[{prefix}] has no version info", fg="red"))
    directory.mkdir(exist_ok=True, parents=True)
    obo_path = directory.joinpath(f"{prefix}.obo")
    names_path = directory.joinpath(f"{prefix}.tsv")
    sssom_path = directory.joinpath(f"{prefix}.sssom.tsv")
    obo_graph_json_path = directory.joinpath(f"{prefix}.json")
    owl_path = directory.joinpath(f"{prefix}.owl")
    log_path = directory.joinpath(f"{prefix}.log.txt")
    log_path.unlink(missing_ok=True)

    try:
        obo.write_obo(obo_path)
    except Exception as e:
        tqdm.write(click.style(f"[{prefix}] failed to write OBO: {e}", fg="red"))
        log_path.write_text(str(e))
        obo_path.unlink()
        return rv
    rv["obo"] = _prepare_art(prefix, obo_path, has_version, ".obo.gz")

    rv["summary"] = _get_summary(obo)

    with names_path.open("w") as file:
        print(
            "identifier",
            "name",
            "definition",
            "synonyms",
            "alts",
            "parents",
            "species",
            sep="\t",
            file=file,
        )
        for term in obo:
            if term.prefix != prefix:
                continue
            species = term.get_species()
            print(
                term.identifier,
                term.name or "",
                term.definition or "",
                "|".join(s.name for s in term.synonyms),
                "|".join(p.curie for p in term.alt_ids),
                "|".join(p.curie for p in term.parents),
                species.curie if species else "",
                sep="\t",
                file=file,
            )
    rv["nodes"] = _prepare_art(prefix, names_path, has_version, ".tsv.gz")

    sssom_df = pyobo.get_sssom_df(obo)
    sssom_df.to_csv(sssom_path, sep="\t", index=False)
    rv["sssom"] = _prepare_art(prefix, sssom_path, has_version, ".sssom.tsv.gz")

    if not do_convert:
        return rv

    try:
        tqdm.write(f"[{prefix}] converting to OBO Graph JSON")
        convert_to_obograph(input_path=obo_path, json_path=obo_graph_json_path)
        rv["obograph"] = _prepare_art(
            prefix, obo_graph_json_path, has_version, ".json.gz"
        )
    except Exception:
        tqdm.write(
            click.style(f"[{prefix}] ROBOT failed to convert to OBO Graph", fg="red")
        )
    else:
        tqdm.write(f"[{prefix}] done converting to OBO Graph JSON")

    try:
        tqdm.write(f"[{prefix}] converting to OWL")
        convert(obo_path, owl_path)
        rv["owl"] = _prepare_art(prefix, owl_path, has_version, ".owl.gz")
    except Exception:
        tqdm.write(click.style(f"[{prefix}] ROBOT failed to convert to OWL", fg="red"))
    else:
        tqdm.write(f"[{prefix}] done converting to OWL")

    return rv


@click.command()
@verbose_option
@click.option("-m", "--minimum")
@click.option("--no-convert", is_flag=True)
@click.option("-x", "--xvalue", help="Select a specific ontology", multiple=True)
def main(minimum: Optional[str], xvalue: list[str], no_convert: bool):
    """Build the PyOBO examples."""
    if xvalue:
        for prefix in xvalue:
            if prefix != bioregistry.normalize_prefix(prefix):
                raise ValueError(f"invalid prefix: {prefix}")
        prefixes = xvalue
    elif minimum:
        prefixes = [
            prefix for prefix in PREFIXES if not (minimum and prefix < minimum.lower())
        ]
    else:
        prefixes = PREFIXES

    it = [(prefix, ontology_resolver.lookup(prefix)) for prefix in prefixes]
    it = tqdm(it, desc="Making OBO examples")

    manifest = {}

    for prefix, cls in it:
        tqdm.write(click.style(prefix, fg="green", bold=True))
        it.set_postfix(prefix=prefix)
        with logging_redirect_tqdm():
            manifest[prefix] = _make(
                prefix=prefix, module=cls, do_convert=not no_convert
            )

    versions = {
        "pyobo": pyobo.version.get_version(with_git_hash=True),
        "bioontologies": bioontologies.version.get_version(with_git_hash=True),
        "bioregistry": bioregistry.version.get_version(with_git_hash=True),
    }
    MANIFEST_PATH.write_text(
        yaml.safe_dump(
            {
                "date": datetime.date.today().strftime("%Y-%m-%d"),
                "versions": versions,
                "resources": manifest,
            },
        )
    )


if __name__ == "__main__":
    main()
