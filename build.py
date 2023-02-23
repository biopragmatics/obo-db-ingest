# -*- coding: utf-8 -*-

"""Build for Drugbank examples.

This script requires ``pip install pyobo``.
"""

import gzip
from pathlib import Path
from typing import Optional

import click
from bioontologies.robot import convert, convert_to_obograph
from more_click import verbose_option
import pyobo.sources.uniprot
import pyobo.sources
from tqdm import tqdm
from tqdm.contrib.logging import logging_redirect_tqdm
from pyobo.sources import ontology_resolver
from pyobo import Obo

HERE = Path(__file__).parent.resolve()
PREFIXES = [
    "eccode",
    "rgd",
    "sgd",
    "mirbase",
    "mgi",
    "uniprot",
    "hgnc",
    "hgnc.genegroup",
    "pombase",
    "rhea",
    "flybase",
    # "drugcentral",
    # # wormbase
    # pyobo.sources.dictybase_gene,
    # # ecogene
    # pyobo.sources.flybase,
    # pyobo.sources.zfin,
    # pyobo.sources.cgnc,
    # pyobo.sources.mirbase,
    # # Chemistry examples
    # pyobo.sources.drugcentral,
    # pyobo.sources.drugbank,
    # pyobo.sources.drugbank_salt,
    # # Famplexes
    # pyobo.sources.complexportal,
    # pyobo.sources.expasy,
    # # Big!
    # pyobo.sources.uniprot.uniprot,
    # pyobo.sources.mgi,
    # pyobo.sources.slm,
]

NO_FORCE = {pyobo.sources.drugbank, pyobo.sources.drugbank_salt}
GZIP_OBO = {"mgi", "uniprot", "swisslipid"}


def _gzip(path: Path, suffix: str):
    output_path = path.with_suffix(suffix)
    with path.open("rb") as src, gzip.open(output_path, "wb") as dst:
        dst.writelines(src)
    path.unlink()


def _make(prefix, module: type[Obo]):
    obo = module(force=module not in NO_FORCE)

    directory = HERE.joinpath("export", prefix)
    if obo.data_version:
        directory = directory.joinpath(obo.data_version)
    else:
        tqdm.write(click.style(f"[{prefix}] has no version info", fg="red"))
    directory.mkdir(exist_ok=True, parents=True)
    obo_path = directory.joinpath(f"{prefix}.obo")
    obo_graph_json_path = directory.joinpath(f"{prefix}.json")
    owl_path = directory.joinpath(f"{prefix}.owl")

    try:
        obo.write_obo(obo_path)
    except Exception as e:
        tqdm.write(click.style(f"[{prefix}] failed to write OBO: {e}", fg="red"))
        return
    if prefix in GZIP_OBO:
        _gzip(obo_path, ".obo.gz")

    try:
        tqdm.write(f"[{prefix}] converting to OBO Graph JSON")
        convert_to_obograph(input_path=obo_path, json_path=obo_graph_json_path)
        _gzip(obo_graph_json_path, ".json.gz")
    except Exception:
        tqdm.write(
            click.style(f"[{prefix}] ROBOT failed to convert to OBO Graph", fg="red")
        )
    else:
        click.echo(f"[{prefix}] done converting to OBO Graph JSON")

    try:
        tqdm.write(f"[{prefix}] converting to OWL")
        convert(obo_path, owl_path)
        _gzip(owl_path, ".owl.gz")
    except Exception:
        tqdm.write(click.style(f"[{prefix}] ROBOT failed to convert to OWL", fg="red"))
    else:
        click.echo(f"[{prefix}] done converting to OWL")


@click.command()
@verbose_option
@click.option("-m", "--minimum")
@click.option("-x", "--xvalue", help="Select a specific ontology")
def main(minimum: Optional[str], xvalue: Optional[str]):
    """Build the PyOBO examples."""
    if xvalue:
        prefixes = [xvalue]
    elif minimum:
        prefixes = [
            prefix
            for prefix in PREFIXES
            if not (minimum and prefix < minimum.lower())
        ]
    else:
        prefixes = PREFIXES

    it = [
        (prefix, ontology_resolver.lookup(prefix))
        for prefix in prefixes
    ]
    it = tqdm(it, desc="Making OBO examples")
    with logging_redirect_tqdm():
        for prefix, cls in it:
            tqdm.write(click.style(prefix, fg="green", bold=True))
            it.set_postfix(prefix=prefix)
            _make(prefix=prefix, module=cls)


if __name__ == "__main__":
    main()
