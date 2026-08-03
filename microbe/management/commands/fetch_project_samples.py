import logging

from django.core.management.base import BaseCommand
from django.db import transaction

from microbe.external_apis.biosamples.api import (
    get_project_samples,
    import_biosample,
)
from microbe.models import Sample, SynComConstituent
from microbe.utils import unnest_attributes


def _attribute_text(value):
    if isinstance(value, dict):
        return value.get("text", "")
    if isinstance(value, list):
        return _attribute_text(value[0]) if value else ""
    return value


def _sample_type(biosample):
    attributes = unnest_attributes(biosample.get("characteristics", {}))
    return str(_attribute_text(attributes.get("sample_type", ""))).lower()


def _import_constituent(biosample):
    attributes = unnest_attributes(biosample.get("characteristics", {}))
    organism = _attribute_text(attributes.get("organism", ""))
    constituent, _ = SynComConstituent.objects.update_or_create(
        accession=biosample["accession"],
        defaults={
            "organism": organism or biosample.get("name") or biosample["accession"],
            "attributes": attributes,
        },
    )
    return constituent


class Command(BaseCommand):
    help = "(Re)fetches the list of MICROBE samples from the BioSamples API."

    def add_arguments(self, parser):
        parser.add_argument(
            "--project_attr",
            type=str,
            help="Value of `project+name` attribute to search for in BioSamples",
            default="MICROBE",
        )
        parser.add_argument(
            "--webin_filter",
            type=str,
            help="Webin submitter accounts to include samples from. Others are filtered out.",
            nargs="+",
            metavar="WEBIN",
            default=["Webin-67954", "Webin-67007"],
        )
        parser.add_argument(
            "--biosamples_page_cursor",
            type=str,
            help="Pagination cursor value for biosamples, useful to continue running from a page other than the first.",
            default=None,
        )
        parser.add_argument(
            "--max_pages",
            type=int,
            help="Maximum page count to retrieve from biomsamples",
            default=None,
        )
        parser.add_argument(
            "--updated_since",
            type=str,
            help="ISO8601 formatted datetime, to limit samples to those updated since a certain date. E.g. 2023-04-31",
            default=None,
        )

    def handle(self, *args, **options):
        biosamples = list(
            get_project_samples(
                options["project_attr"],
                options["webin_filter"],
                options["max_pages"],
                options["biosamples_page_cursor"],
                options["updated_since"],
            )
        )
        constituent_biosamples = {
            biosample["accession"]: biosample
            for biosample in biosamples
            if biosample.get("accession") and _sample_type(biosample) == "isolate"
        }
        imported_accessions = {
            biosample.get("accession")
            for biosample in biosamples
            if biosample.get("accession")
            and biosample.get("accession") not in constituent_biosamples
        }
        relationship_parents = {
            relationship.get("target")
            for biosample in biosamples
            for relationship in biosample.get("relationships", [])
            if str(relationship.get("type", "")).lower() == "derived_from"
            and relationship.get("source") == biosample.get("accession")
            and relationship.get("target")
            and relationship.get("target") not in constituent_biosamples
        }
        samples_added = 0
        samples_updated = 0
        relationships_added = 0

        with transaction.atomic():
            for biosample in biosamples:
                if biosample.get("accession") in constituent_biosamples:
                    continue
                logging.info(f"Importing biosample {biosample.get('accession')}")
                _, created = import_biosample(biosample)
                if created:
                    samples_added += 1
                else:
                    samples_updated += 1

            constituents_by_accession = {
                accession: _import_constituent(biosample)
                for accession, biosample in constituent_biosamples.items()
            }
            Sample.objects.filter(accession__in=constituent_biosamples).delete()
            samples_by_accession = Sample.objects.in_bulk(
                imported_accessions | relationship_parents
            )
            for biosample in biosamples:
                child_accession = biosample.get("accession")
                child = samples_by_accession.get(child_accession)
                if not child:
                    continue

                parent_accessions = set()
                for relationship in biosample.get("relationships", []):
                    if (
                        str(relationship.get("type", "")).lower() != "derived_from"
                        or relationship.get("source") != child_accession
                    ):
                        continue
                    parent_accession = relationship.get("target")
                    if not parent_accession:
                        continue
                    if parent_accession in samples_by_accession:
                        parent_accessions.add(parent_accession)
                    else:
                        logging.warning(
                            "Skipping parent %s for %s because it has not been imported",
                            parent_accession,
                            child_accession,
                        )

                existing_parents = set(
                    child.derived_from.values_list("accession", flat=True)
                )
                new_parent_accessions = parent_accessions - existing_parents
                child.derived_from.set(
                    [samples_by_accession[accession] for accession in parent_accessions]
                )
                relationships_added += len(new_parent_accessions)

                if child.experiment_type == Sample.ExperimentType.SYNCOMS:
                    constituent_accessions = {
                        relationship.get("target")
                        for relationship in biosample.get("relationships", [])
                        if str(relationship.get("type", "")).lower() == "derived_from"
                        and relationship.get("source") == child_accession
                        and relationship.get("target") in constituents_by_accession
                    }
                    child.syncom_constituents.set(
                        [
                            constituents_by_accession[accession]
                            for accession in constituent_accessions
                        ]
                    )

        self.stdout.write(
            self.style.SUCCESS(
                f"Added {samples_added} samples, updated {samples_updated}, "
                f"and added {relationships_added} derivation relationships."
            )
        )
