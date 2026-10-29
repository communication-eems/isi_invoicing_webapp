# core/management/commands/sequel_formations_seed_p5.py
"""
Sequel seed — Part 5: hospitality, retail & industrial invoices (2026), gap 049-059

Loads:
  • 7 new Clients (Golden Body Production, SARL Station de Services El
    Farouk — station-service & supermarché branches, EURL Hôtel Ferdi
    Messaoud, SARL Hôtel Tedj El Maouada, SNC Sakhra Urbanisme et
    Construction, SARL Saim Textiles, SARL IAM Pack)
  • Formations (reuses HSE / COM / RH / MET categories, adds a few new
    titles: HACCP, CPHS, Topographie, PHS, Winalco, Lutte Incendie)
  • 8 finalised FORMATION invoices for year 2026 (049, 052, 053, 054,
    055, 057, 058, 059)

Note: FACTURE_037/2026 (HALLIBURTON — Advanced Excel) and FACTURE_046/2026
(EURL SOCIETE ZOUAOUI — ISO 45001) were supplied as source documents too,
but both are already seeded by sequel_formations_seed_p3 / _p4 respectively
— amounts match exactly, so they are intentionally NOT re-seeded here.

Source invoices:
  - FACTURE_049 / 30-06-2026 → GOLDEN BODY PRODUCTION (RH + chariot élévateur)
  - FACTURE_052 / 10-08-2026 → SARL STATION DE SERVICES EL FAROUK (station-service, RH)
  - FACTURE_053 / 10-08-2026 → EURL HOTEL FERDI MESSAOUD (organisation et gestion)
  - FACTURE_054 / 10-08-2026 → SARL STATION DE SERVICES EL FAROUK (supermarché, gestion de stock)
  - FACTURE_055 / 30-06-2026 → SARL HOTEL TEDJ EL MAOUADA (HSE, HACCP, secours, incendie offerte)
  - FACTURE_057 / 30-06-2026 → SNC SAKHRA URBANISME ET CONSTRUCTION (CPHS, HSE, topographie, PHS)
  - FACTURE_058 / 30-06-2026 → SARL SAIM TEXTILES (comptabilité et fiscalité)
  - FACTURE_059 / 30-06-2026 → SARL IAM PACK (premiers secours, comptabilité Winalco)

Run:
    python manage.py sequel_formations_seed_p5
    python manage.py sequel_formations_seed_p5 --clear
"""

import datetime
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from clients.models import Client, FormeJuridique
from financial.models import Invoice, InvoiceItem, InvoiceSequence
from formations.models import Formation, FormationCategory

TVA_9 = Decimal("0.09")
ZERO = Decimal("0.00")
YEAR = 2026

NEW_CLIENT_NAMES = [
    "GOLDEN BODY PRODUCTION",
    "SARL STATION DE SERVICES EL FAROUK",
    "EURL HOTEL FERDI MESSAOUD",
    "SARL HOTEL TEDJ EL MAOUADA",
    "SNC SAKHRA URBANISME ET CONSTRUCTION",
    "SARL SAIM TEXTILES",
    "SARL IAM PACK",
]


class Command(BaseCommand):
    help = "Sequel seed P5 — hospitality, retail & industrial invoices (2026), gap 049-059."

    def add_arguments(self, parser):
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Delete the P5 invoices and the clients created solely for this part before re-seeding.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        if options["clear"]:
            self._clear_data()

        self._seed_formation_catalog()
        clients = self._seed_clients()
        self._seed_invoices(clients)
        self._update_sequences()

        self.stdout.write(
            self.style.SUCCESS("\n✓ Sequel seed P5 terminé avec succès.\n")
        )

    # ------------------------------------------------------------------ #
    # Clear
    # ------------------------------------------------------------------ #
    def _clear_data(self):
        # All 7 clients in this part are new (none are reused from earlier
        # sequels), so cascading through the client set is sufficient.
        client_qs = Client.objects.filter(name__in=NEW_CLIENT_NAMES)
        InvoiceItem.objects.filter(invoice__client__in=client_qs).delete()
        Invoice.objects.filter(client__in=client_qs).delete()
        client_qs.delete()
        self.stdout.write("  ✓ Données P5 supprimées.")

    # ------------------------------------------------------------------ #
    # Formation catalog
    # ------------------------------------------------------------------ #
    def _seed_formation_catalog(self):
        from django.utils.text import slugify

        cat_hse, _ = FormationCategory.objects.get_or_create(
            code="HSE", defaults={"name": "Formation HSE", "color": "#EF4444"}
        )
        cat_com, _ = FormationCategory.objects.get_or_create(
            code="COM", defaults={"name": "Formation Commerce & Gestion", "color": "#2563EB"}
        )
        cat_met, _ = FormationCategory.objects.get_or_create(
            code="MET",
            defaults={"name": "Industrie & Métallurgie", "color": "#78716C"},
        )
        cat_rh, _ = FormationCategory.objects.get_or_create(
            code="RH",
            defaults={"name": "Management des Ressources Humaines", "color": "#6366F1"},
        )

        # (title, category, duration_days, duration_hours, base_price)
        formations = [
            ("Les Fondamentaux RH", cat_rh, 5, 40, Decimal("50000.00")),
            ("Habilitation Conduite des Chariots Élévateurs", cat_met, 2, 16, Decimal("22000.00")),
            ("Formation en Organisation et Gestion", cat_com, 2, 16, Decimal("20000.00")),
            ("Formation en Gestion de Stock", cat_com, 2, 16, Decimal("12000.00")),
            ("Formation en Comptabilité et Fiscalité", cat_com, 2, 16, Decimal("26195.42")),
            ("Formation Comptabilité (Winalco)", cat_com, 2, 16, Decimal("20000.00")),
            ("Formations Superviseur HSE", cat_hse, 5, 40, Decimal("10000.00")),
            ("Formation HACCP (Hazard Analysis Critical Control Point)", cat_hse, 3, 24, Decimal("50000.00")),
            ("Formations Premier Secours", cat_hse, 2, 16, Decimal("40000.00")),
            ("Formation Lutte Contre Incendie", cat_hse, 1, 8, Decimal("0.00")),
            ("Formation CPHS", cat_hse, 5, 40, Decimal("65000.00")),
            ("Formation Topographie (volet CPHS)", cat_hse, 7, 56, Decimal("9000.00")),
            ("Formation PHS", cat_hse, 1, 8, Decimal("80000.00")),
        ]

        created = 0
        for title, cat, days, hours, price in formations:
            _, was_created = Formation.objects.get_or_create(
                slug=slugify(title)[:255],
                defaults={
                    "category": cat,
                    "title": title,
                    "duration_days": days,
                    "duration_hours": hours,
                    "base_price": price,
                    "is_active": True,
                },
            )
            if was_created:
                created += 1

        self.stdout.write(
            f"  ✓ Catalogue P5 — {created} formations créées, "
            f"{len(formations) - created} déjà existantes."
        )

    # ------------------------------------------------------------------ #
    # Clients
    # ------------------------------------------------------------------ #
    def _seed_clients(self):
        fj_eurl, _ = FormeJuridique.objects.get_or_create(
            name="EURL",
            defaults={"description": "Entreprise Unipersonnelle à Responsabilité Limitée"},
        )
        fj_sarl, _ = FormeJuridique.objects.get_or_create(
            name="SARL",
            defaults={"description": "Société à Responsabilité Limitée"},
        )
        fj_snc, _ = FormeJuridique.objects.get_or_create(
            name="SNC",
            defaults={"description": "Société en Nom Collectif"},
        )
        E = Client.ClientType.ENTREPRISE

        specs = [
            (
                "golden_body",
                dict(
                    name="GOLDEN BODY PRODUCTION",
                    client_type=E,
                    forme_juridique=fj_sarl,
                    address="Zone d'Activité Artisanale, Classe 10, Section 282/283/284, Oued Sabor, Sétif",
                    city="Sétif",
                    activity_sector="Production de Produits Diététiques",
                    rc="20B0094127-00/19",
                    nif="002019009412767",
                    nis="",
                    article_imposition="19011162144",
                ),
            ),
            (
                "station_farouk",
                dict(
                    # Same legal entity operates both the station-service
                    # (FACTURE_052, RC suffix 00/19, AI 19470092511) and the
                    # supermarché (FACTURE_054, RC suffix 01/19, AI
                    # 19470092512) as two établissements under one client.
                    name="SARL STATION DE SERVICES EL FAROUK",
                    client_type=E,
                    forme_juridique=fj_sarl,
                    address=(
                        "Section 17, Groupement, Parcelle 05, Pôle Sportif et "
                        "de Loisirs, Commune d'Ouled Sabeur, Sétif"
                    ),
                    city="Ouled Sabeur",
                    activity_sector="Station-service & Supermarché",
                    rc="15B0091948-00/19",
                    nif="001519009194896",
                    nis="001519470048442",
                    article_imposition="19470092511",
                ),
            ),
            (
                "hotel_ferdi",
                dict(
                    name="EURL HOTEL FERDI MESSAOUD",
                    client_type=E,
                    forme_juridique=fj_eurl,
                    address="115, Rue Kamel Houcine, Sétif",
                    city="Sétif",
                    activity_sector="Hôtel - Restaurant",
                    rc="15 B 0091771",
                    nif="001519009177178",
                    nis="001519010027951",
                    article_imposition="19019138011",
                ),
            ),
            (
                "hotel_tedj",
                dict(
                    name="SARL HOTEL TEDJ EL MAOUADA",
                    client_type=E,
                    forme_juridique=fj_sarl,
                    address="15 Rue Haffad Abdelmadjid",
                    city="",
                    activity_sector="Hôtel, Restauration, Cafétéria",
                    rc="10 B 0088836",
                    nif="001019008883689",
                    nis="00109010034369",
                    article_imposition="1900134011",
                ),
            ),
            (
                "sakhra",
                dict(
                    name="SNC SAKHRA URBANISME ET CONSTRUCTION",
                    client_type=E,
                    forme_juridique=fj_snc,
                    address="Cité Bahlouli, El Eulma",
                    city="El Eulma",
                    activity_sector="ETPBH (Entreprise de Travaux Publics et de Bâtiment et Hydraulique)",
                    rc="07 B 0086831-00/19",
                    nif="000719008683119",
                    nis="000719200000371",
                    article_imposition="19206146391",
                ),
            ),
            (
                "saim_textiles",
                dict(
                    name="SARL SAIM TEXTILES",
                    client_type=E,
                    forme_juridique=fj_sarl,
                    address="Zone Industrielle, Îlot N°49, Bordj Bou Arreridj",
                    city="Bordj Bou Arreridj",
                    activity_sector="Fabrication de Couvertures",
                    rc="02B0462740-34/00",
                    nif="000234046274012",
                    nis="000234010043859",
                    article_imposition="34017101580",
                ),
            ),
            (
                "iam_pack",
                dict(
                    name="SARL IAM PACK",
                    client_type=E,
                    forme_juridique=fj_sarl,
                    address=(
                        "Cité 80 Logements Participatifs, Bloc B N°02, "
                        "Ritchoussé, Section 50, GP N°20, Bordj Bou Arreridj"
                    ),
                    city="Bordj Bou Arreridj",
                    activity_sector="Transformation de la Matière Première en Plastique",
                    rc="19B 0466100",
                    nif="001934046610021",
                    nis="001934010010369",
                    article_imposition="34010784934",
                ),
            ),
        ]

        clients = {}
        for key, defaults in specs:
            client, _ = Client.objects.get_or_create(
                name=defaults["name"], defaults=defaults
            )
            clients[key] = client

        self.stdout.write(f"  ✓ {len(specs)} nouveaux clients")
        return clients

    # ------------------------------------------------------------------ #
    # Invoices
    # ------------------------------------------------------------------ #
    def _seed_invoices(self, C: dict):
        PP = InvoiceItem.PricingMode.PER_PERSON
        PD = InvoiceItem.PricingMode.PER_DAY
        FF = InvoiceItem.PricingMode.FORFAIT
        D = Decimal

        def _prime_and_get_ref(target_number: int, year: int) -> str:
            for phase in (InvoiceSequence.Phase.PROFORMA, InvoiceSequence.Phase.FINALE):
                InvoiceSequence.objects.update_or_create(
                    invoice_type=Invoice.InvoiceType.FORMATION,
                    year=year,
                    phase=phase,
                    defaults={"last_number": target_number - 1},
                )
            return Invoice._next_final_reference(Invoice.InvoiceType.FORMATION, year)

        def _delete_conflicting(target_number: int, year: int) -> int:
            """
            Delete any pre-existing FORMATION invoice already occupying this
            target_number/year slot — matched on either the finale reference
            (…-NNN-YEAR) or the proforma reference (…-NNN-YEAR), regardless
            of prefix. Makes the seed self-healing: safe to re-run even if a
            previous run left a stale invoice with different data under the
            same number (which is what raised the UniqueViolation on
            proforma_reference). Returns the number of invoices deleted.
            """
            suffix = f"-{target_number:03d}-{year}"
            qs = Invoice.objects.filter(invoice_type=Invoice.InvoiceType.FORMATION).filter(
                Q(reference__endswith=suffix) | Q(proforma_reference__endswith=suffix)
            )
            count = qs.count()
            if count:
                InvoiceItem.objects.filter(invoice__in=qs).delete()
                qs.delete()
            return count

        specs = [
            # ── 049 / GOLDEN BODY PRODUCTION — RH + chariot (2026) ──────
            dict(
                target_number=49,
                year=YEAR,
                date=datetime.date(2026, 6, 30),
                client=C["golden_body"],
                bc="",
                mode="",
                amount_ht=D("116000.00"),
                amount_tva=D("10440.00"),
                amount_ttc=D("126440.00"),
                items=[
                    (1, "Formation Les Fondamentaux RH", PP, D("1"), D("1"), D("50000.00"), D("0")),
                    (2, "Formation conduite chariot élévateur", PP, D("3"), D("1"), D("22000.00"), D("0")),
                ],
            ),
            # ── 052 / STATION DE SERVICES EL FAROUK — RH (2026) ─────────
            dict(
                target_number=52,
                year=YEAR,
                date=datetime.date(2026, 8, 10),
                client=C["station_farouk"],
                bc="",
                mode="",
                amount_ht=D("28000.00"),
                amount_tva=D("2520.00"),
                amount_ttc=D("30520.00"),
                items=[
                    (1, "Formation les fondamentaux RH", PD, D("1"), D("2"), D("14000.00"), D("0")),
                ],
            ),
            # ── 053 / HOTEL FERDI MESSAOUD — organisation et gestion ────
            dict(
                target_number=53,
                year=YEAR,
                date=datetime.date(2026, 8, 10),
                client=C["hotel_ferdi"],
                bc="",
                mode="",
                amount_ht=D("40000.00"),
                amount_tva=D("3600.00"),
                amount_ttc=D("43600.00"),
                items=[
                    (1, "Formation en organisation et gestion", PD, D("1"), D("2"), D("20000.00"), D("0")),
                ],
            ),
            # ── 054 / STATION DE SERVICES EL FAROUK (supermarché) ───────
            dict(
                target_number=54,
                year=YEAR,
                date=datetime.date(2026, 8, 10),
                client=C["station_farouk"],
                bc="",
                mode="",
                amount_ht=D("24000.00"),
                amount_tva=D("2160.00"),
                amount_ttc=D("26160.00"),
                items=[
                    (1, "Formation en gestion de stock", PD, D("1"), D("2"), D("12000.00"), D("0")),
                ],
            ),
            # ── 055 / HOTEL TEDJ EL MAOUADA — 4 formations (2026) ───────
            dict(
                target_number=55,
                year=YEAR,
                date=datetime.date(2026, 6, 30),
                client=C["hotel_tedj"],
                bc="",
                mode="",
                amount_ht=D("280000.00"),
                amount_tva=D("25200.00"),
                amount_ttc=D("305200.00"),
                items=[
                    (1, "Formations Superviseur HSE", PD, D("1"), D("5"), D("10000.00"), D("0")),
                    (
                        2,
                        "Formations HACCP (Hazard Analysis Critical Control Point)",
                        PD, D("1"), D("3"), D("50000.00"), D("0"),
                    ),
                    (3, "Formations Premier Secours", PD, D("1"), D("2"), D("40000.00"), D("0")),
                    (4, "Formations Lutte Contre Incendie (offerte)", FF, D("1"), D("1"), D("0.00"), D("0")),
                ],
            ),
            # ── 057 / SNC SAKHRA — CPHS, HSE, topographie, PHS (2026) ───
            dict(
                target_number=57,
                year=YEAR,
                date=datetime.date(2026, 6, 30),
                client=C["sakhra"],
                bc="",
                mode="Cheque",
                amount_ht=D("568000.00"),
                amount_tva=D("51120.00"),
                amount_ttc=D("619120.00"),
                items=[
                    (1, "Formation CPHS", PD, D("1"), D("5"), D("65000.00"), D("0")),
                    (2, "Formation superviseur HSE", PD, D("1"), D("2"), D("50000.00"), D("0")),
                    (3, "Formation topographies (cphs)", PD, D("1"), D("7"), D("9000.00"), D("0")),
                    (4, "Formation PHS", PD, D("1"), D("1"), D("80000.00"), D("0")),
                ],
            ),
            # ── 058 / SAIM TEXTILES — comptabilité et fiscalité (2026) ──
            dict(
                target_number=58,
                year=YEAR,
                date=datetime.date(2026, 6, 30),
                client=C["saim_textiles"],
                bc="",
                mode="",
                amount_ht=D("52390.83"),
                amount_tva=D("4715.17"),
                amount_ttc=D("57106.00"),
                items=[
                    # Source shows 02 j × 26 195.415 HT/j = 52 390.83 — the
                    # per-day rate has 3 decimals (unrepresentable on the
                    # 2-decimal unit_price_ht field), so the exact invoiced
                    # total is captured directly as a forfait line instead.
                    (1, "Formations en comptabilité et fiscalité", FF, D("1"), D("1"), D("52390.83"), D("0")),
                ],
            ),
            # ── 059 / IAM PACK — secours + comptabilité Winalco (2026) ──
            dict(
                target_number=59,
                year=YEAR,
                date=datetime.date(2026, 6, 30),
                client=C["iam_pack"],
                bc="",
                mode="",
                amount_ht=D("160000.00"),
                amount_tva=D("14400.00"),
                amount_ttc=D("174400.00"),
                items=[
                    # Source montants (80 000 each) don't reduce to
                    # jours × prix U/J with the columns given (likely an
                    # implicit multi-candidat count not broken out on the
                    # printed invoice) — captured as forfait lines matching
                    # the printed MONTANT HT exactly.
                    (1, "Formations en premier secoure", FF, D("1"), D("1"), D("80000.00"), D("0")),
                    (2, "Formation comptabilité (winalco)", FF, D("1"), D("1"), D("80000.00"), D("0")),
                ],
            ),
        ]

        created = 0
        for spec in specs:
            client = spec["client"]

            # Self-healing: if an invoice already occupies this
            # target_number/year slot (from an earlier run — partial,
            # re-run, or seeded with stale data), delete it and its items
            # first, then re-prime ("configure") the counter and recreate
            # from scratch. Makes the command safe to run repeatedly with
            # no --clear needed.
            deleted = _delete_conflicting(spec["target_number"], spec["year"])
            if deleted:
                self.stdout.write(
                    f"    ↻ {deleted} facture(s) existante(s) pour le n° "
                    f"{spec['target_number']:03d}/{spec['year']} supprimée(s), reconfiguration…"
                )

            final_ref = _prime_and_get_ref(spec["target_number"], spec["year"])

            inv = Invoice.objects.create(
                invoice_type=Invoice.InvoiceType.FORMATION,
                phase=Invoice.Phase.PROFORMA,
                status=Invoice.Status.DRAFT,
                client=client,
                invoice_date=spec["date"],
                tva_rate=TVA_9,
                bon_commande_number=spec["bc"],
                mode_reglement=spec["mode"],
            )

            item_objs = []
            for order, desc, mode, nb_persons, nb_days, unit_price, discount in spec["items"]:
                item = InvoiceItem(
                    invoice=inv,
                    order=order,
                    description=desc,
                    pricing_mode=mode,
                    nb_persons=nb_persons,
                    nb_days=nb_days,
                    unit_price_ht=unit_price,
                    discount_percent=discount,
                    total_ht=ZERO,
                )
                item.total_ht = item._compute_total_ht()
                item_objs.append(item)

            InvoiceItem.objects.bulk_create(item_objs)

            finalized_at = timezone.make_aware(
                datetime.datetime.combine(spec["date"], datetime.time(12, 0))
            )
            Invoice.objects.filter(pk=inv.pk).update(
                phase=Invoice.Phase.FINALE,
                status=Invoice.Status.UNPAID,
                reference=final_ref,
                finalized_at=finalized_at,
                amount_ht=spec["amount_ht"],
                amount_tva=spec["amount_tva"],
                amount_ttc=spec["amount_ttc"],
                amount_remaining=spec["amount_ttc"],
                client_name_snapshot=client.name,
                client_address_snapshot=client.address,
                client_type_snapshot=client.client_type,
                client_nif_snapshot=client.nif,
                client_nis_snapshot=getattr(client, "nis", ""),
                client_rc_snapshot=client.rc,
                client_ai_snapshot=client.article_imposition,
                client_nin_snapshot=getattr(client, "nin", ""),
                client_rib_snapshot=getattr(client, "rib", ""),
                client_tin_snapshot=getattr(client, "tin", ""),
            )
            created += 1
            self.stdout.write(f"    + {final_ref}  {client.name[:50]}")

        self.stdout.write(f"  ✓ {created} factures FORMATION finalisées")

    # ------------------------------------------------------------------ #
    # Sequence counters
    # ------------------------------------------------------------------ #
    def _update_sequences(self):
        seq = InvoiceSequence.objects.filter(
            invoice_type=Invoice.InvoiceType.FORMATION,
            year=YEAR,
            phase=InvoiceSequence.Phase.FINALE,
        ).first()
        last = seq.last_number if seq else "?"
        self.stdout.write(
            f"  ✓ InvoiceSequence {YEAR} → dernier n° {last} (géré automatiquement)"
        )
