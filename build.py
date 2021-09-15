# -*- coding: utf-8 -*-

"""Build for Drugbank examples.

This script requires ``pip install pyobo``.
"""

import os

import click
from more_click import verbose_option

from pyobo.sources import cgnc, drugbank, drugbank_salt, drugcentral, hgnc, hgncgenefamily, mgi, rgd, sgd

HERE = os.path.abspath(os.path.dirname(__file__))


@click.command()
@verbose_option
def main():
    """Build the PyOBO examples."""
    hgnc.get_obo(force=True).write_obo(os.path.join(HERE, 'hgnc.obo'))
    hgncgenefamily.get_obo(force=True).write_obo(os.path.join(HERE, 'hgnc_genegroup.obo'))
    mgi.get_obo(force=True).write_obo(os.path.join(HERE, 'mgi.obo'))
    rgd.get_obo(force=True).write_obo(os.path.join(HERE, 'rgd.obo'))
    sgd.get_obo(force=True).write_obo(os.path.join(HERE, 'sgd.obo'))
    drugbank.get_obo(force=True).write_obo(os.path.join(HERE, 'drugbank.obo'))
    # FIXME cgnc export is broken
    cgnc.get_obo(force=True).write_obo(os.path.join(HERE, 'cgnc.obo'))
    drugbank_salt.get_obo(force=True).write_obo(os.path.join(HERE, 'drugbank_salt.obo'))
    drugcentral.get_obo(force=True).write_obo(os.path.join(HERE, 'drugcentral.obo'))


if __name__ == '__main__':
    main()
