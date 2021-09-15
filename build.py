# -*- coding: utf-8 -*-

"""Build for Drugbank examples.

This script requires ``pip install pyobo``.
"""

import os

import click
from more_click import verbose_option

import pyobo
import pyobo.sources.drugbank
import pyobo.sources.drugcentral
import pyobo.sources.hgnc
import pyobo.sources.hgncgenefamily

HERE = os.path.abspath(os.path.dirname(__file__))


@click.command()
@verbose_option
def main():
    """Build the PyOBO examples."""
    hgnc_obo = pyobo.sources.hgnc.get_obo(force=True)
    hgnc_obo.write_obo(os.path.join(HERE, 'hgnc.obo'))

    hgnc_group_obo = pyobo.sources.hgncgenefamily.get_obo(force=True)
    hgnc_group_obo.write_obo(os.path.join(HERE, 'hgnc_genegroup.obo'))

    drugbank_obo = pyobo.sources.drugbank.get_obo(force=True)
    drugbank_obo.write_obo(os.path.join(HERE, 'drugbank.obo'))

    drugcentral_obo = pyobo.sources.drugcentral.get_obo(force=True)
    drugcentral_obo.write_obo(os.path.join(HERE, 'drugcentral.obo'))


if __name__ == '__main__':
    main()
