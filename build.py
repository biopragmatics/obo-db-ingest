# -*- coding: utf-8 -*-

"""Build for Drugbank examples.

This script requires ``pip install pyobo``.
"""

import os

import click
from more_click import verbose_option
from tqdm import tqdm
from tqdm.contrib.logging import logging_redirect_tqdm

from pyobo.sources import (
    cgnc, dictybase_gene, drugbank, drugbank_salt, drugcentral, flybase, hgnc, hgncgenefamily, mgi, pombase, rgd, sgd,
    zfin,
)
from pyobo.utils.misc import obo_to_obograph

HERE = os.path.abspath(os.path.dirname(__file__))
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
    # Chemistry examples
    drugcentral,
    drugbank,
    drugbank_salt,
]


@click.command()
@verbose_option
def main():
    """Build the PyOBO examples."""
    it = tqdm(MODULES, desc="Making OBO examples")
    for module in it:
        name = module.__name__.split(".")[-1]
        obo_path = os.path.join(HERE, f'{name}.obo')
        obograph_path = os.path.join(HERE, f'{name}.json.gz')

        it.set_postfix(name=name)
        with logging_redirect_tqdm():
            obo = module.get_obo(force=True)
            obo.write_obo(obo_path)

        try:
            obo_to_obograph(obo_path, obograph_path)
        except Exception as e:
            it.write(click.style(f"{name} failed to convert to OBO Graph", fg="red"))
            it.write(click.style(str(e), fg="red"))


if __name__ == '__main__':
    main()
