# -*- coding: utf-8 -*-

"""Build OBO dumps of database.

This script requires ``pip install pyobo``.
"""

import gzip
import os
from pathlib import Path
from typing import Optional

import bioregistry
import click
import pystow.utils
import yaml
from bioontologies.robot import convert, convert_to_obograph
from more_click import verbose_option
from pyobo import Obo
from pyobo.sources import ontology_resolver
from tqdm import tqdm
from tqdm.contrib.logging import logging_redirect_tqdm

BASE_PURL = "https://w3id.org/biopragmatics/resources"
HERE = Path(__file__).parent.resolve()
EXPORT = HERE.joinpath("export")
pystow.utils.GLOBAL_PROGRESS_BAR = False
#: This is the maximum file size (100MB, rounded down to
#: be conservative) to put on GitHub
MAX_SIZE = 100_000_000
PREFIXES = [
    "eccode",
    "rgd",
    "sgd",
    "mirbase",
    "mgi",
    "uniprot",
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
    #  "msigdb",
    "pfam",
    "pfam.clan",
    "npass",
    "kegg.genome",
    "swisslipid",
]

for prefix in PREFIXES:
    if prefix != bioregistry.normalize_prefix(prefix):
        raise ValueError(f"invalid prefix: {prefix}")

NO_FORCE = {"drugbank", "drugbank.salt"}
GZIP_OBO = {"mgi", "uniprot", "swisslipids", "reactome", "pathbank", "mesh"}


def _gzip(path: Path, suffix: str):
    output_path = path.with_suffix(suffix)
    with path.open("rb") as src, gzip.open(output_path, "wb") as dst:
        dst.writelines(src)
    path.unlink()
    return output_path


def _make(prefix: str, module: type[Obo], do_convert: bool = False) -> dict:
    rv = {}

    obo = module(force=prefix not in NO_FORCE)

    directory = EXPORT.joinpath(prefix)
    if obo.data_version:
        directory = directory.joinpath(obo.data_version)
    else:
        tqdm.write(click.style(f"[{prefix}] has no version info", fg="red"))
    directory.mkdir(exist_ok=True, parents=True)
    obo_path = directory.joinpath(f"{prefix}.obo")
    names_path = directory.joinpath(f"{prefix}.tsv")
    obo_graph_json_path = directory.joinpath(f"{prefix}.json")
    owl_path = directory.joinpath(f"{prefix}.owl")

    try:
        obo.write_obo(obo_path)
    except Exception as e:
        tqdm.write(click.style(f"[{prefix}] failed to write OBO: {e}", fg="red"))
        return rv
    if os.path.getsize(obo_path) > MAX_SIZE:
        output_path = _gzip(obo_path, ".obo.gz")
        rv["obo"] = {
            "path": output_path.relative_to(EXPORT).as_posix(),
            "gzipped": True,
            "link": f"{BASE_PURL}/{output_path.relative_to(EXPORT)}",
        }
    else:
        rv["obo"] = {
            "path": obo_path.relative_to(EXPORT).as_posix(),
            "gzipped": False,
            "link": f"{BASE_PURL}/{obo_path.relative_to(EXPORT)}",
        }

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
    if os.path.getsize(names_path) > MAX_SIZE:
        names_gzip_path = _gzip(names_path, ".tsv.gz")
        rv["nodes"] = {
            "path": names_gzip_path.relative_to(EXPORT).as_posix(),
            "gzipped": True,
            "link": f"{BASE_PURL}/{names_gzip_path.relative_to(EXPORT)}",
        }
    else:
        rv["nodes"] = {
            "path": names_path.relative_to(EXPORT).as_posix(),
            "gzipped": False,
            "link": f"{BASE_PURL}/{names_path.relative_to(EXPORT)}",
        }

    if not do_convert:
        return rv

    try:
        tqdm.write(f"[{prefix}] converting to OBO Graph JSON")
        convert_to_obograph(input_path=obo_path, json_path=obo_graph_json_path)
        _gzip(obo_graph_json_path, ".json.gz")
    except Exception:
        tqdm.write(
            click.style(f"[{prefix}] ROBOT failed to convert to OBO Graph", fg="red")
        )
    else:
        tqdm.write(f"[{prefix}] done converting to OBO Graph JSON")

    try:
        tqdm.write(f"[{prefix}] converting to OWL")
        convert(obo_path, owl_path)
        _gzip(owl_path, ".owl.gz")
    except Exception:
        tqdm.write(click.style(f"[{prefix}] ROBOT failed to convert to OWL", fg="red"))
    else:
        tqdm.write(f"[{prefix}] done converting to OWL")

    return rv


@click.command()
@verbose_option
@click.option("-m", "--minimum")
@click.option("-c", "--do-convert")
@click.option("-x", "--xvalue", help="Select a specific ontology", multiple=True)
def main(minimum: Optional[str], xvalue: list[str], do_convert: bool):
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
            manifest[prefix] = _make(prefix=prefix, module=cls, do_convert=do_convert)

    manifest_path = HERE.joinpath("manifest.yml")
    manifest_path.write_text(
        yaml.safe_dump(
            manifest,
        )
    )


if __name__ == "__main__":
    main()
