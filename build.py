# -*- coding: utf-8 -*-

"""Build for Drugbank examples.

This script requires ``pip install pyobo``.
"""

import gzip
from operator import attrgetter
from pathlib import Path
from typing import Optional

import click
from bioontologies.robot import convert, convert_to_obograph
from more_click import verbose_option
from pyobo.sources import (
    cgnc,
    complexportal,
    dictybase_gene,
    drugbank,
    drugbank_salt,
    drugcentral,
    expasy,
    flybase,
    hgnc,
    hgncgenefamily,
    mgi,
    mirbase,
    pombase,
    rgd,
    rhea,
    sgd,
    zfin,
)
from pyobo.sources.uniprot import uniprot
from tqdm import tqdm
from tqdm.contrib.logging import logging_redirect_tqdm

HERE = Path(__file__).parent.resolve()
MODULES = [
    hgncgenefamily,
    # Organism-specific gene nomenclature examples
    hgnc,
    mgi,
    # araport
    sgd,
    pombase,
    # wormbase
    dictybase_gene,
    # ecogene
    flybase,
    zfin,
    cgnc,
    mirbase,
    uniprot,
    # Chemistry examples
    drugcentral,
    drugbank,
    drugbank_salt,
    rhea,
    #
    complexportal,
    expasy,
    rgd,
]

NO_FORCE = {drugbank, drugbank_salt}
GZIP_OBO = {"mgi", "uniprot"}


def _gzip(path: Path, suffix: str):
    output_path = path.with_suffix(suffix)
    with path.open("rb") as src, gzip.open(output_path, "wb") as dst:
        dst.writelines(src)
    path.unlink()


@click.command()
@verbose_option
@click.option("-m", "--minimum")
@click.option("-x", "--xvalue")
def main(minimum: Optional[str], xvalue: Optional[str]):
    """Build the PyOBO examples."""
    it = tqdm(sorted(MODULES, key=attrgetter("PREFIX")), desc="Making OBO examples")
    with logging_redirect_tqdm():
        for module in it:
            prefix = module.PREFIX
            if minimum and prefix.lower() < minimum.lower():
                continue
            if xvalue and xvalue.lower() != prefix.lower():
                continue
            it.set_postfix(prefix=prefix)

            obo = module.get_obo(force=module not in NO_FORCE)

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
                if prefix in GZIP_OBO:
                    _gzip(obo_path, ".obo.gz")
            except ValueError as e:
                it.write(click.style(f"[{prefix}] failed to write OBO: {e}", fg="red"))
                continue

            try:
                it.write(f"[{prefix}] converting to OBO Graph JSON")
                convert_to_obograph(input_path=obo_path, json_path=obo_graph_json_path)
                _gzip(obo_graph_json_path, ".json.gz")
            except Exception:
                it.write(
                    click.style(
                        f"[{prefix}] ROBOT failed to convert to OBO Graph", fg="red"
                    )
                )

            try:
                it.write(f"[{prefix}] converting to OWL")
                convert(obo_path, owl_path)
                _gzip(owl_path, ".owl.gz")
            except Exception:
                it.write(
                    click.style(f"[{prefix}] ROBOT failed to convert to OWL", fg="red")
                )


if __name__ == "__main__":
    main()
