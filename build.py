# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "bioregistry>=0.11.23",
#     "bioversions>=0.5.533",
#     "bioontologies>=0.5.1",
# ]
# ///

"""Build OBO dumps of database.

This script requires ``pip install pyobo``.
"""

from __future__ import annotations

import datetime
import gzip
import os
import shutil
import subprocess
import traceback
from pathlib import Path
from textwrap import dedent
from typing import TypedDict

import bioontologies.version
import bioregistry
import bioregistry.version
import click
import pyobo.constants
import pyobo.version
import pystow.utils
import yaml
from bioontologies.robot import convert
from more_click import verbose_option
from pyobo import Obo
from pyobo.sources import ontology_resolver
from tabulate import tabulate
from tqdm import tqdm
from tqdm.contrib.logging import logging_redirect_tqdm
from typing_extensions import NotRequired

BASE_PURL = "https://w3id.org/biopragmatics/resources"
HERE = Path(__file__).parent.resolve()
DATA = HERE.joinpath("docs", "_data")
MANIFEST_PATH = DATA.joinpath("manifest.yml")
EXPORT = HERE.joinpath("export")
pystow.utils.GLOBAL_PROGRESS_BAR = False
pyobo.constants.GLOBAL_CHECK_IDS = True
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
    "drugcentral",
    "complexportal",
    "interpro",
    "mesh",
    "mirbase.family",
    "mirbase.mature",
    "reactome",
    "wikipathways",
    "pathbank",
    "pfam",
    "pfam.clan",
    "npass",
    "kegg.genome",
    "slm",
    "gtdb",
    "msigdb",
    "uniprot.ptm",
    "credit",
    "cvx",
    "cpt",
    "gard",
    "bigg.metabolite",
    "bigg.model",
    "bigg.reaction",
]

for _prefix in PREFIXES:
    if _prefix != bioregistry.normalize_prefix(_prefix):
        raise ValueError(f"invalid prefix: {_prefix}")

NO_FORCE = {"drugbank", "drugbank.salt"}
GZIP_OBO = {"mgi", "uniprot", "slm", "reactome", "pathbank", "mesh"}
ARTIFACT_LABELS = {
    "obo": "OBO",
    "owl": "OWL",
    "sssom": "SSSOM",
    "nodes": "Nodes",
    "obograph": "OBO Graph JSON",
}


def _gzip(path: Path, suffix: str) -> Path:
    output_path = path.with_suffix(suffix)
    with path.open("rb") as src, gzip.open(output_path, "wb") as dst:
        dst.writelines(src)
    path.unlink()
    return output_path


class Artifact(TypedDict):
    """Describes an artifact that was produced."""

    gzipped: bool
    iri: str
    path: str
    version_iri: NotRequired[str]
    version_path: NotRequired[str]


def _prepare_artifact(
    prefix: str, path: Path, has_version: bool, suffix: str
) -> tuple[Path, Artifact]:
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
    return output_path, rv


def _get_summary(obo: Obo) -> dict:
    terms = [t for t in obo if t.prefix == obo.ontology]
    rv = {
        "terms": sum(term.prefix == obo.ontology for term in obo),
        "relations": sum(len(values) for term in terms for values in term.relationships.values()),
        "properties": sum(
            len(values)
            for term in terms
            for dd in [term.annotations_literal, term.annotations_object]
            for values in dd.values()
        ),
        "synonyms": sum(len(term.synonyms) for term in terms),
        "mappings": sum(len(term.get_mappings(include_xrefs=True)) for term in terms),
        "alts": sum(len(term.alt_ids) for term in terms),
        "parents": sum(len(term.parents) for term in terms),
        "references": sum(len(term.provenance) for term in terms),
        "definitions": sum(term.definition is not None for term in terms),
        "version": obo.data_version,
        "license": bioregistry.get_license(obo.ontology),
    }
    return rv


def _write_nodes(path: Path, obo: Obo, prefix: str) -> None:
    with path.open("w") as file:
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
                "|".join(sorted(s.name for s in term.synonyms)),
                "|".join(sorted(p.curie for p in term.alt_ids)),
                "|".join(sorted(p.curie for p in term.parents)),
                species.curie if species else "",
                sep="\t",
                file=file,
            )


def _make(prefix: str, module: type[Obo], do_convert: bool = False, no_force: bool = False) -> dict:
    rv = {}
    if no_force:
        force = False
    else:
        force = prefix not in NO_FORCE
    obo = module(force=force)

    directory = EXPORT.joinpath(prefix)
    readme_path = directory.joinpath("README.md")

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
        tqdm.write(
            click.style(
                f"[{prefix}] failed to write OBO: {e}\n\tWriting to {log_path.as_posix()}",
                fg="red",
            )
        )
        with log_path.open("w") as file:
            traceback.print_exc(file=file)
        obo_path.unlink()
        return rv
    obo_path, rv["obo"] = _prepare_artifact(prefix, obo_path, has_version, ".obo.gz")

    rv["summary"] = _get_summary(obo)

    _write_nodes(names_path, obo, prefix)
    _, rv["nodes"] = _prepare_artifact(prefix, names_path, has_version, ".tsv.gz")

    sssom_df = pyobo.get_mappings_df(obo, names=False)
    sssom_df.to_csv(sssom_path, sep="\t", index=False)
    _, rv["sssom"] = _prepare_artifact(prefix, sssom_path, has_version, ".sssom.tsv.gz")

    if do_convert:
        # add -vvv and search for org.semanticweb.owlapi.oboformat.OBOFormatOWLAPIParser on errors
        try:
            tqdm.write(f"[{prefix}] converting to OWL")
            convert(obo_path, owl_path, merge=False, reason=False, debug=True)
            _, rv["owl"] = _prepare_artifact(prefix, owl_path, has_version, ".owl.gz")
        except subprocess.CalledProcessError as e:
            tqdm.write(
                click.style(
                    f"[{prefix}] {type(e)} - ROBOT failed to convert to OWL\n\t{e}\n\t{' '.join(e.cmd)}",
                    fg="red",
                )
            )
            with log_path.open("a") as file:
                traceback.print_exc(file=file)
                file.write(str(e.stderr))
        else:
            tqdm.write(f"[{prefix}] done converting to OWL")

        try:
            tqdm.write(f"[{prefix}] converting to OBO Graph JSON")
            convert(obo_path, obo_graph_json_path, merge=False, reason=False, debug=True)
            _, rv["obograph"] = _prepare_artifact(
                prefix, obo_graph_json_path, has_version, ".json.gz"
            )
        except subprocess.CalledProcessError as e:
            tqdm.write(
                click.style(
                    f"[{prefix}] {type(e)} - ROBOT failed to convert to OBO Graph JSON"
                    f"\n\t{e}\n\t{' '.join(e.cmd)}",
                    fg="red",
                )
            )
            with log_path.open("a") as file:
                traceback.print_exc(file=file)
                file.write(str(e.stderr))
        else:
            tqdm.write(f"[{prefix}] done converting to OBO Graph JSON")

    purls_table_rows = [
        (ARTIFACT_LABELS[key], data["iri"], data.get("version_iri"))
        for key, data in rv.items()
        if "iri" in data
    ]

    # Write a README file, so anyone who navigates there can see what's going on.
    # skip any entries that have 0 values
    summary = sorted(
        (k, v) for k, v in rv["summary"].items() if k not in {"version", "license"} and v
    )
    text = (
        dedent(f"""\
# {bioregistry.get_name(prefix)}

{bioregistry.get_description(prefix)}

**License**: {bioregistry.get_license(prefix) or '_unlicensed_'}

## PURLs

{tabulate(purls_table_rows, headers=['Artifact', 'Download PURL', 'Latest Versioned Download PURL'], tablefmt="github")}

## Summary

{tabulate(summary, headers=['field', 'count'], tablefmt='github')}

""").strip()
        + "\n"
    )
    readme_path.write_text(text)

    return rv


@click.command()
@verbose_option
@click.option("-m", "--minimum")
@click.option("--no-convert", is_flag=True)
@click.option("-x", "--xvalue", help="Select a specific ontology", multiple=True)
@click.option("--force/--no-force")
def main(minimum: str | None, xvalue: list[str], no_convert: bool, force: bool):
    """Build the PyOBO examples."""
    if xvalue:
        for prefix in xvalue:
            if prefix != bioregistry.normalize_prefix(prefix):
                raise ValueError(f"invalid prefix: {prefix}")
        prefixes = xvalue
    elif minimum:
        prefixes = [prefix for prefix in PREFIXES if not (minimum and prefix < minimum.lower())]
    else:
        prefixes = PREFIXES

        all_classes = {ontology_resolver.lookup(prefix) for prefix in PREFIXES}
        missing = sorted(
            o.ontology for o in set(ontology_resolver.lookup_dict.values()).difference(all_classes)
        )
        for cls in missing:
            click.secho(f"Skipping: {cls}", fg="yellow")

    for prefix in prefixes:
        if not bioregistry.get_license(prefix):
            click.secho(f"missing license for `{prefix}`", fg="yellow")

    it = [(prefix, ontology_resolver.lookup(prefix)) for prefix in prefixes]
    it = tqdm(it, desc="Making OBO examples")

    manifest = {}

    for prefix, cls in it:
        tqdm.write(click.style(prefix, fg="green", bold=True))
        it.set_postfix(prefix=prefix)
        with logging_redirect_tqdm():
            try:
                manifest[prefix] = _make(
                    prefix=prefix,
                    module=cls,
                    do_convert=not no_convert,
                    no_force=not force,
                )
            except Exception as e:
                tqdm.write(click.style(f"[{prefix}] {e}", fg="red"))
                continue

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
