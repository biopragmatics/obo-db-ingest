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
    dictybase_gene,
    drugbank,
    drugbank_salt,
    drugcentral,
    flybase,
    hgnc,
    hgncgenefamily,
    mgi,
    mirbase,
    pombase,
    rgd,
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
    rgd,
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
]

NO_FORCE = {drugbank, drugbank_salt}


@click.command()
@verbose_option
@click.option("-m", "--minimum")
def main(minimum: Optional[str]):
    """Build the PyOBO examples."""
    it = tqdm(sorted(MODULES, key=attrgetter("PREFIX")), desc="Making OBO examples")
    with logging_redirect_tqdm():
        for module in it:
            prefix = module.PREFIX
            if minimum and prefix.lower() < minimum.lower():
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
            except ValueError as e:
                it.write(click.style(f"[{prefix}] failed to write OBO: {e}", fg="red"))
                continue

            try:
                it.write(f"[{prefix}] converting to OBO Graph JSON")
                convert_to_obograph(input_path=obo_path, json_path=obo_graph_json_path)
                with obo_graph_json_path.open("rb") as src, gzip.open(
                    obo_graph_json_path.with_suffix(".json.gz"), "wb"
                ) as dst:
                    dst.writelines(src)
            except Exception:
                it.write(
                    click.style(
                        f"[{prefix}] ROBOT failed to convert to OBO Graph", fg="red"
                    )
                )
            else:
                obo_graph_json_path.unlink()

            try:
                it.write(f"[{prefix}] converting to OWL")
                convert(obo_path, owl_path)
                with owl_path.open("rb") as src, gzip.open(
                    owl_path.with_suffix(".owl.gz"), "wb"
                ) as dst:
                    dst.writelines(src)
            except Exception:
                it.write(
                    click.style(f"[{prefix}] ROBOT failed to convert to OWL", fg="red")
                )
            else:
                owl_path.unlink()


if __name__ == "__main__":
    main()
