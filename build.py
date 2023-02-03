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
import pyobo.sources.uniprot
import pyobo.sources
from tqdm import tqdm
from tqdm.contrib.logging import logging_redirect_tqdm

HERE = Path(__file__).parent.resolve()
MODULES = [
    pyobo.sources.hgncgenefamily,
    # Organism-specific gene nomenclature examples
    pyobo.sources.hgnc,
    pyobo.sources.rgd,
    # araport
    pyobo.sources.sgd,
    pyobo.sources.pombase,
    # wormbase
    pyobo.sources.dictybase_gene,
    # ecogene
    pyobo.sources.flybase,
    pyobo.sources.zfin,
    pyobo.sources.cgnc,
    pyobo.sources.mirbase,
    # Chemistry examples
    pyobo.sources.drugcentral,
    pyobo.sources.drugbank,
    pyobo.sources.drugbank_salt,
    pyobo.sources.rhea,
    # Famplexes
    pyobo.sources.complexportal,
    pyobo.sources.expasy,
    # Big!
    pyobo.sources.uniprot.uniprot,
    pyobo.sources.mgi,
    pyobo.sources.slm,
]

NO_FORCE = {pyobo.sources.drugbank, pyobo.sources.drugbank_salt}
GZIP_OBO = {"mgi", "uniprot", "swisslipid"}


def _gzip(path: Path, suffix: str):
    output_path = path.with_suffix(suffix)
    with path.open("rb") as src, gzip.open(output_path, "wb") as dst:
        dst.writelines(src)
    path.unlink()


def _make(prefix, module):
    try:
        obo = module.get_obo(force=module not in NO_FORCE)
    except Exception as e:
        tqdm.write(click.style(f"[] failed: {e}", fg="red"))
        return

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
    modules = sorted(MODULES, key=attrgetter("PREFIX"))
    modules = [
        module
        for module in modules
        if (
            not (minimum and module.PREFIX.lower() < minimum.lower())
            and not (xvalue and xvalue.lower() != module.PREFIX.lower())
        )
    ]
    it = tqdm(modules, desc="Making OBO examples")
    with logging_redirect_tqdm():
        for module in it:
            it.set_postfix(prefix=module.PREFIX)
            _make(prefix=module.PREFIX, module=module)


if __name__ == "__main__":
    main()
