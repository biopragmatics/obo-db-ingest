# -*- coding: utf-8 -*-

"""Build for Drugbank examples.

This script requires ``pip install pyobo``.
"""

from pathlib import Path

import click
from more_click import verbose_option
from tqdm import tqdm
from tqdm.contrib.logging import logging_redirect_tqdm

from pyobo.sources import (
    cgnc, dictybase_gene, drugbank, drugbank_salt, drugcentral, flybase, hgnc, hgncgenefamily, mgi, mirbase, pombase,
    rgd, sgd, zfin,
)
from pyobo.sources.uniprot import uniprot
from pyobo.utils.misc import obo_to_obograph

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


@click.command()
@verbose_option
def main():
    """Build the PyOBO examples."""
    it = tqdm(MODULES, desc="Making OBO examples")
    with logging_redirect_tqdm():
        for module in it:
            prefix = module.PREFIX
            it.set_postfix(prefix=prefix)

            obo = module.get_obo(force=True)

            directory = HERE.joinpath("export", prefix)
            if obo.data_version:
                directory = HERE.joinpath(directory, obo.data_version)
            else:
                tqdm.write(click.style(f"{prefix} has no version info", fg="red"))
            directory.mkdir(exist_ok=True, parents=True)
            obo_path = directory.joinpath(f'{prefix}.obo')
            obograph_path = directory.joinpath(f'{prefix}.json.gz')

            obo.write_obo(obo_path)

            try:
                it.write(f"converting {prefix} to OBO graph")
                obo_to_obograph(obo_path, obograph_path)
            except Exception as e:
                it.write(click.style(f"{prefix} failed to convert to OBO Graph", fg="red"))
                it.write(click.style(str(e), fg="red"))


if __name__ == '__main__':
    main()
