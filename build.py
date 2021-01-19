# -*- coding: utf-8 -*-

"""Build for Drugbank examples.

This script requires ``pip install pyobo``.
"""

import os

import pyobo

HERE = os.path.abspath(os.path.dirname(__file__))


def main():
    """Build the PyOBO examples."""
    for prefix in ('drugbank', 'drugcentral', 'hgnc'):
        path = os.path.join(HERE, f'{prefix}.obo')
        if os.path.exists(path):
            continue
        obo = pyobo.get(prefix)
        obo.write_obo(path)


if __name__ == '__main__':
    main()
