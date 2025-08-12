"""Generate an OLS sheet."""

import json
from pathlib import Path

import click
import pandas as pd
import requests
import yaml
from bioregistry import manager
from tabulate import tabulate

HERE = Path(__file__).parent.resolve()
MANIFEST = HERE.joinpath("docs", "_data", "manifest.yml")

REQUESTS = HERE.joinpath("ols-requests")
REQUESTS.mkdir(exist_ok=True)

REQUEST_FORM_URL = (
    "https://github.com/EBISPOT/ols4/raw/refs/heads/dev/New%20OLS%20ontology%20request.xlsx"
)
REMOTE_CONFIG = "https://github.com/EBISPOT/ols4/raw/refs/heads/dev/ebi_ontologies.json"

NEVER = {
    "clinicaltrials",
    "kegg.genome",
    "omim.ps",
    "nihreporter.project",
}


@click.command()
@click.option("--write-excel", is_flag=True)
@click.option(
    "--regenerate-old",
    is_flag=True,
    help="if true, regenerates JSON for already-integrated resources",
)
def main(write_excel: bool, regenerate_old: bool) -> None:
    """Generate OLS request documents."""
    pre_indexed = {
        record["id"] for record in requests.get(REMOTE_CONFIG, timeout=5).json()["ontologies"]
    }

    manifest = yaml.safe_load(MANIFEST.read_text())

    df = pd.read_excel(REQUEST_FORM_URL)

    rows = sorted(
        (prefix in pre_indexed, prefix, manager.get_name(prefix))
        for prefix, data in manifest["resources"].items()
        if prefix not in NEVER
    )
    click.echo(tabulate(rows))

    for prefix, data in manifest["resources"].items():
        if prefix in NEVER:
            continue
        if prefix in pre_indexed and not regenerate_old:
            continue
        if "owl" not in data:
            click.echo(f"no OWL for {prefix}")
            continue

        owl_purl = data["owl"]["iri"]

        resource = manager.get_resource(prefix)
        if resource is None:
            raise ValueError

        if contact := resource.get_contact():
            creator = contact.name
        else:
            creator = (
                "Converted to OWL by Charles Tapley Hoyt (cthoyt@gmail.com), "
                "no primary contact information is available."
            )

        description = resource.get_description()
        if license := resource.get_license():
            description += f" Licensed under {license}."

        values = {
            # as per https://github.com/EBISPOT/ols4/pull/896#discussion_r2126144218
            "id": prefix,
            "creator": [
                creator,
            ],
            "is_foundary": resource.get_obofoundry_prefix() is not None,
            "preferredPrefix": resource.get_preferred_prefix() or resource.prefix,
            "title": resource.get_name(),
            "uri": owl_purl,
            "description": description,
            "homepage": resource.get_homepage(),
            "mailing_list": resource.get_mailing_list() or resource.get_contact_email(),
            "label_property": "https://www.w3.org/2000/01/rdf-schema#label",
            "definition_property": [
                "http://purl.org/dc/terms/description",
            ],
            "synonym_property": [
                "http://www.geneontology.org/formats/oboInOwl#hasExactSynonym",
                "http://www.geneontology.org/formats/oboInOwl#hasNarrowSynonym",
                "http://www.geneontology.org/formats/oboInOwl#hasBroadSynonym",
                "http://www.geneontology.org/formats/oboInOwl#hasCloseSynonym",
            ],
            "hierarchical_property": [
                "https://www.w3.org/2000/01/rdf-schema#subclassOf",
            ],
            "hidden_property": [],
            "base_uri": [
                resource.get_rdf_uri_prefix() or resource.get_uri_prefix(),
            ],
            "reasoner": "none",
            "oboSlims": False,
            "ontology_purl": owl_purl,
        }

        if write_excel:
            specific_df: pd.DataFrame = df.copy()
            specific_df["Value"] = [values[f] for f in df["Field"]]
            excel_path = REQUESTS.joinpath(f"{prefix}-request.xlsx")
            specific_df.to_excel(excel_path, index=False)

        # should match https://github.com/EBISPOT/ols4/blob/dev/dataload/configs/ols.json
        json_path = REQUESTS.joinpath(f"{prefix}-request.json")
        json_path.write_text(json.dumps(values, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
