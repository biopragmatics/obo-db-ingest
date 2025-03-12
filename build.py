# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "bioregistry",
#     "bioversions",
#     "bioontologies",
#     "pyobo",
# ]
#
# [tool.uv.sources]
# bioversions = { path = "../bioversions", editable = true }
# bioregistry = { path = "../bioregistry", editable = true }
# bioontologies = { path = "../bioontologies", editable = true }
# gilda = { git = "https://github.com/cthoyt/gilda", branch = "slim" }
# pyobo = { path = "../pyobo", editable = true }
# ///

"""Build OBO dumps of database.

Run with ``UV_PREVIEW=1 uv run --script build.py``
"""

from __future__ import annotations

import datetime
import functools
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
from tqdm.contrib.concurrent import process_map
from tqdm.contrib.logging import logging_redirect_tqdm
from typing_extensions import NotRequired

MULTIPROCESSING = False
PYOBO_VERSION = pyobo.version.get_version(with_git_hash=True)
BASE_PURL = "https://w3id.org/biopragmatics/resources"
HERE = Path(__file__).parent.resolve()
DATA = HERE.joinpath("docs", "_data")
MANIFEST_PATH = DATA.joinpath("manifest.yml")
SKEY = "manifest"
TODAY = datetime.date.today().strftime("%Y-%m-%d")
EXPORT = HERE.joinpath("export")
pystow.utils.GLOBAL_PROGRESS_BAR = False
pyobo.constants.GLOBAL_CHECK_IDS = True
#: This is the maximum file size (100MB, rounded down to
#: be conservative) to put on GitHub
MAX_SIZE = 100_000_000
PREFIXES = [
    "pharmgkb.drug",
    "pharmgkb.gene",
    "pharmgkb.variant",
    "pharmgkb.disease",
    "pharmgkb.pathways",
    "nihreporter.project",
    "chembl.compound",
    "chembl.target",
    "pid.pathway",
    "ncbi.gc",
    "civic.gid",
    "itis",
    "depmap",
    "clinicaltrials",
    "signor",
    "sty",
    "omim.ps",
    "nlm.publisher",
    "geonames.feature",
    "geonames",  # has instances
    "ror",  # has instances
    "icd10",
    "bigg.compartment",
    "ccle",
    "icd11",
    "ec",
    "sgd",
    "mirbase",
    "mirbase.family",
    "mirbase.mature",
    "mgi",
    "hgnc",
    "hgnc.genegroup",
    "rgd",
    "pombase",
    "flybase",
    "zfin",
    "dictybase.gene",
    "cgnc",
    "drugcentral",
    "nlm",
    "complexportal",
    "interpro",
    "mesh",
    "reactome",
    "wikipathways",
    "pathbank",
    "pfam",
    "pfam.clan",
    "npass",
    "kegg.genome",
    "slm",
    "rhea",
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
    "uniprot",
]

for _prefix in PREFIXES:
    if _prefix != bioregistry.normalize_prefix(_prefix):
        raise ValueError(f"invalid prefix: {_prefix}")

NO_FORCE = {"drugbank", "drugbank.salt"}
GZIP_OBO = {"mgi", "uniprot", "slm", "reactome", "pathbank", "mesh"}
ARTIFACT_LABELS = {
    "obo": "OBO",
    "owl": "OWL",
    "ofn": "OFN",
    "sssom": "SSSOM",
    "synonyms": "Synonyms",
    "nodes": "Nodes",
    "obograph": "OBO Graph JSON",
}


def secho(s: str, *args, **kwargs) -> None:
    """Write to the standard output stream with appropriate locking for tqdm."""
    tqdm.write(click.style(s, *args, **kwargs))


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
    terms = list(obo._iter_stanzas(desc=f"[{obo.ontology}]"))
    rv = {
        "terms": sum(term.prefix == obo.ontology for term in obo),
        "relations": sum(len(values) for term in terms for values in term.relationships.values()),
        "properties": sum(len(values) for term in terms for values in term.properties.values()),
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


def _make_safe(
    cls: type[Obo], *, do_convert: bool = False, no_force: bool = False
) -> tuple[str, dict, bool]:
    prefix = cls.ontology
    secho(prefix, fg="green", bold=True)
    with logging_redirect_tqdm():
        try:
            rv, errored = _make(cls, do_convert=do_convert, no_force=no_force)
        except Exception as e:
            secho(f"[{prefix}] got exception in _make: {e}", fg="red")
            traceback.print_exc()
            return prefix, {}, True
        else:
            return prefix, rv, errored


def _make(  # noqa:C901
    module: type[Obo], *, do_convert: bool = False, no_force: bool = False
) -> tuple[dict, bool]:
    prefix = module.ontology
    errored = False
    if no_force:
        force = False
    else:
        force = prefix not in NO_FORCE
    obo = module(force=force)

    directory = EXPORT.joinpath(prefix)
    readme_path = directory.joinpath("README.md")
    manifest_path = directory.joinpath("manifest.yaml")

    has_version = bool(obo.data_version)
    if has_version:
        directory = directory.joinpath(obo.data_version)
    else:
        secho(f"[{prefix}] has no version info", fg="red")
    directory.mkdir(exist_ok=True, parents=True)

    if manifest_path.exists():
        manifest_full = yaml.safe_load(manifest_path.read_text())
        cached_pyobo_version = manifest_full.pop("dependencies", {}).get("pyobo")
        manifest = manifest_full[SKEY]
        cached_data_version = manifest["summary"].get("version")
        if not manifest_full["errored"] and cached_pyobo_version == PYOBO_VERSION:
            if has_version and cached_data_version == obo.data_version:
                secho(f"[{prefix}] using cache data v{cached_data_version}")
                return manifest, False
            elif (cached_data_date := manifest_full["date"]) == TODAY:
                secho(f"[{prefix}] using cached data from {cached_data_date}")
                return manifest, False

    tqdm.write(f"[{prefix}] getting summary")
    rv = {"summary": _get_summary(obo)}

    # can't use the stub path because if the
    # prefix has a dot in it, gets overridden
    obo_path = directory.joinpath(f"{prefix}.obo")
    names_path = directory.joinpath(f"{prefix}.tsv")
    sssom_path = directory.joinpath(f"{prefix}.sssom.tsv")
    literal_mappings_path = directory.joinpath(f"{prefix}.synonyms.tsv")
    obo_graph_json_path = directory.joinpath(f"{prefix}.json")
    ofn_path = directory.joinpath(f"{prefix}.ofn")
    owl_path = directory.joinpath(f"{prefix}.owl")
    log_path = directory.joinpath(f"{prefix}.log.txt")
    log_path.unlink(missing_ok=True)

    try:
        obo.write_obo(obo_path)
    except Exception as e:
        errored = True
        msg = f"[{prefix}] failed to write OBO: {e}\n\tWriting to {log_path.as_posix()}"
        secho(msg, fg="red")
        with log_path.open("a") as file:
            file.write(f"\n\n{msg}\n\n")
            traceback.print_exc(file=file)
        obo_path.unlink()

    else:
        obo_path, rv["obo"] = _prepare_artifact(prefix, obo_path, has_version, ".obo.gz")

    try:
        obo.write_ofn(ofn_path)
    except Exception as e:
        errored = True
        msg = f"[{prefix}] failed to write OFN: {e}\n\tWriting to {log_path.as_posix()}"
        secho(msg, fg="red")
        with log_path.open("a") as file:
            file.write(f"\n\n{msg}\n\n")
            traceback.print_exc(file=file)
        obo_path.unlink()
    else:
        ofn_path, rv["ofn"] = _prepare_artifact(prefix, ofn_path, has_version, ".ofn.gz")

    _write_nodes(names_path, obo, prefix)
    _, rv["nodes"] = _prepare_artifact(prefix, names_path, has_version, ".tsv.gz")

    tqdm.write(f"[{prefix}] writing SSSOM")
    sssom_df = obo.get_mappings_df(use_tqdm=False)
    sssom_df.to_csv(sssom_path, sep="\t", index=False)
    _, rv["sssom"] = _prepare_artifact(prefix, sssom_path, has_version, ".sssom.tsv.gz")

    tqdm.write(f"[{prefix}] writing synonyms")
    try:
        literal_mappings_df = obo.get_literal_mappings_df()
    except Exception as e:
        errored = True
        msg = f"[{prefix}] failed to write synonyms: {e}\n\tWriting to {log_path.as_posix()}"
        secho(msg, fg="red")
        with log_path.open("a") as file:
            file.write(f"\n\n{msg}\n\n")
            traceback.print_exc(file=file)
    else:
        literal_mappings_df.to_csv(literal_mappings_path, sep="\t", index=False)
        _, rv["synonyms"] = _prepare_artifact(
            prefix, literal_mappings_path, has_version, ".synonyms.tsv.gz"
        )

    if do_convert:
        # add -vvv and search for org.semanticweb.owlapi.oboformat.OBOFormatOWLAPIParser on errors
        try:
            tqdm.write(f"[{prefix}] converting OFN to OWL ({ofn_path})")
            # FIXME add a way to update the ontology IRI and version IRI
            convert(ofn_path, owl_path, merge=False, reason=False, debug=True)
            _, rv["owl"] = _prepare_artifact(prefix, owl_path, has_version, ".owl.gz")
        except subprocess.CalledProcessError as e:
            errored = True
            msg = (
                f"[{prefix}] {type(e)} - ROBOT failed to convert to OWL\n\t{e}\n\t{' '.join(e.cmd)}"
            )
            secho(msg, fg="red")
            with log_path.open("a") as file:
                file.write(f"\n\n{msg}\n\n")
                traceback.print_exc(file=file)
                file.write(str(e.stderr))
        else:
            tqdm.write(f"[{prefix}] done converting to OWL")

        try:
            tqdm.write(f"[{prefix}] converting OFN to OBO Graph JSON")
            convert(ofn_path, obo_graph_json_path, merge=False, reason=False, debug=True)
            _, rv["obograph"] = _prepare_artifact(
                prefix, obo_graph_json_path, has_version, ".json.gz"
            )
        except subprocess.CalledProcessError as e:
            errored = True
            msg = click.style(
                f"[{prefix}] {type(e)} - ROBOT failed to convert to OBO Graph JSON"
                f"\n\t{e}\n\t{' '.join(e.cmd)}",
                fg="red",
            )
            tqdm.write(msg)
            with log_path.open("a") as file:
                file.write(f"\n\n{msg}\n\n")
                traceback.print_exc(file=file)
                file.write(str(e.stderr))
        else:
            tqdm.write(f"[{prefix}] done converting to OBO Graph JSON")

    purls_table_rows = [
        (ARTIFACT_LABELS[key], data["iri"], data.get("version_iri"))
        for key, data in rv.items()
        if "iri" in data
    ]

    tqdm.write(f"[{prefix}] writing README")
    # Write a README file, so anyone who navigates there can see what's going on.
    # skip any entries that have 0 values
    summary = sorted(
        (k, v) for k, v in rv["summary"].items() if k not in {"version", "license"} and v
    )
    purls_table_text = tabulate(
        purls_table_rows,
        headers=["Artifact", "Download PURL", "Latest Versioned Download PURL"],
        tablefmt="github",
    )
    text = (
        dedent(f"""\
# {bioregistry.get_name(prefix)}

{bioregistry.get_description(prefix)}

**License**: {bioregistry.get_license(prefix) or "_unlicensed_"}

## PURLs

{purls_table_text}

## Summary

{tabulate(summary, headers=["field", "count"], tablefmt="github")}

""").strip()
        + "\n"
    )
    readme_path.write_text(text)

    manifest_dict = {
        SKEY: rv,
        "dependencies": _get_build_dependency_versions(),
        "errored": errored,
        "prefix_map": {str(k): v for k, v in obo._get_clean_idspaces().items()},
        "date": TODAY,
    }
    manifest_path.write_text(yaml.safe_dump(manifest_dict))

    del obo

    tqdm.write(f"[{prefix}] done")
    return rv, errored


@click.command()
@verbose_option
@click.option("-m", "--minimum")
@click.option("--no-convert", is_flag=True)
@click.option("-x", "--xvalue", help="Select a specific ontology", multiple=True)
@click.option("--force/--no-force")
def main(minimum: str | None, xvalue: list[str], no_convert: bool, force: bool):  # noqa:C901
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
            secho(f"Skipping: {cls}", fg="yellow")

    for prefix in prefixes:
        if not bioregistry.get_license(prefix):
            if contact := bioregistry.get_contact(prefix):
                secho(
                    f"missing license for `{prefix}`, contact {contact.name} ({contact.email})",
                    fg="yellow",
                )
            else:
                secho(f"missing license for `{prefix}`", fg="yellow")

    it = [ontology_resolver.lookup(prefix) for prefix in prefixes]

    make_wrapped = functools.partial(
        _make_safe,
        do_convert=not no_convert,
        no_force=not force,
    )

    rv = {
        "date": TODAY,
        "versions": _get_build_dependency_versions(),
        "resources": {},
        "errors": [],
    }

    _tqdm_kwargs = {"unit": "ontology", "total": len(it), "desc": "obo-db-ingest"}
    if MULTIPROCESSING:
        mm = process_map(make_wrapped, it, max_workers=4, **_tqdm_kwargs)
    else:
        mm = tqdm(map(make_wrapped, it), **_tqdm_kwargs)

    for prefix, result, errored in mm:
        rv["resources"][prefix] = result
        if errored:
            rv["errors"].append(prefix)

        MANIFEST_PATH.write_text(yaml.safe_dump(rv))

    secho("obo-db-ingest is complete")


@functools.lru_cache(1)
def _get_build_dependency_versions() -> dict[str, str]:
    return {
        "pyobo": PYOBO_VERSION,
        "bioontologies": bioontologies.version.get_version(with_git_hash=True),
        "bioregistry": bioregistry.version.get_version(with_git_hash=True),
    }


if __name__ == "__main__":
    main()
