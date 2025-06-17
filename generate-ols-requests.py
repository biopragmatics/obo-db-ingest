"""Generate an OLS sheet."""

import json
from pathlib import Path

import click
import pandas as pd
import yaml
from bioregistry import manager

HERE = Path(__file__).parent.resolve()
MANIFEST = HERE.joinpath("docs", "_data", "manifest.yml")

REQUESTS = HERE.joinpath("ols-requests")
REQUESTS.mkdir(exist_ok=True)

REQUEST_FORM_URL = "https://github.com/EBISPOT/ols4/raw/refs/heads/dev/New%20OLS%20ontology%20request.xlsx"


@click.command()
def main() -> None:
    """Generate OLS request documents."""
    manifest = yaml.safe_load(MANIFEST.read_text())

    df = pd.read_excel(REQUEST_FORM_URL)

    for prefix, data in manifest["resources"].items():
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
            "description": resource.get_description(),
            "homepage": resource.get_homepage(),
            "mailing_list": resource.contact_group_email,
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
                "http://purl.obolibrary.org/obo/",
                resource.get_rdf_uri_prefix() or resource.get_uri_prefix(),
            ],
            "reasoner": "none",
            "oboSlims": False,
            "ontology_purl": owl_purl,
        }

        specific_df: pd.DataFrame = df.copy()

        specific_df["Value"] = [values[f] for f in df["Field"]]

        path = REQUESTS.joinpath(f"{prefix}-request.xlsx")
        specific_df.to_excel(path, index=False)

        # should match https://github.com/EBISPOT/ols4/blob/dev/dataload/configs/ols.json
        json_path = REQUESTS.joinpath(f"{prefix}-request.json")
        json_path.write_text(json.dumps(values, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
