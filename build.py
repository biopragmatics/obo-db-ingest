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
    cgnc, dictybase_gene, hgnc, hgncgenefamily, mgi,
    pombase, rgd, sgd, zfin,
)

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
    # flybase
    zfin,
    cgnc,
    # Chemistry examples
    # drugcentral,
    # drugbank,
    # drugbank_salt,
]


@click.command()
@verbose_option
def main():
    """Build the PyOBO examples."""
    it = tqdm(MODULES, desc="Making OBO examples")
    for module in it:
        name = module.__name__.split(".")[-1]
        it.set_postfix(name=name)
        with logging_redirect_tqdm():
            obo = module.get_obo(force=True)
            obo.write_obo(os.path.join(HERE, f'{name}.obo'))


if __name__ == '__main__':
    main()
