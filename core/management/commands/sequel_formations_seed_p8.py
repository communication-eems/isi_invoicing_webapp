# core/management/commands/sequel_formations_seed_p6.py
"""
Sequel seed — Part 6: extraction, plastics & hospitality invoices (2026), gap 060-072

Loads:
  • 6 new Clients (Lakrache Toufik, SNC Kebiche Abdelhalim et Cie, SNC
    Kebiche et Cie, SARL Kebiche Invest, SPA H.B.A.G, SARL Louai Catring
    Service)
  • Reuses existing clients: SARL LAMSAT KABIR (P0), SARL SETIF CITERNES
    (P0), SARL HOTEL TEDJ EL MAOUADA (P5), SPA BIOREAL PHARM ETS ELEULMA
    (P4)
  • Formations (reuses HSE / COM / RH categories, adds new titles: gestion
    d'équipe, RH et paie, gestion administrative, management RH, gestion
    trésorerie, agents de sécurité, communication, veille réglementaire)
  • 11 finalised FORMATION invoices for year 2026 (060, 061, 062, 063,
    064, 065, 066, 067, 069, 070, 072)

Hardening vs. P5
──────────────────────────
* Each invoice is now created inside its own nested atomic block
  (savepoint). If one invoice fails, only that savepoint rolls back —
  the rest of the batch (and everything already committed to the outer
  transaction) is unaffected. Previously the whole command ran inside a
  single top-level @transaction.atomic, so one bad invoice silently
  rolled back the entire run, which is what caused "055 not found" in P5.
* A verification pass at the end of _seed_invoices checks every target
  number/year against the DB and prints any that are still missing, so a
  silent gap is visible immediately instead of discovered later.

Source invoices:
  - FACTURE_060 / 30-06-2026 → SARL LAMSAT KABIR (Qualification Conduite Transport)
  - FACTURE_061 / 30-06-2026 → SARL HOTEL TEDJ EL MAOUADA (CPHS)
  - FACTURE_062 / 30-06-2026 → SARL LAMSAT KABIR (Qualification Conduite Transport, 2e session)
  - FACTURE_063 / 30-06-2026 → LAKRACHE TOUFIK (Gestion d'équipe)
  - FACTURE_064 / 30-06-2026 → SNC KEBICHE ABDELHALIM ET CIE (RH et paie)
  - FACTURE_065 / 30-06-2026 → SNC KEBICHE ET CIE (Gestion d'équipe)
  - FACTURE_066 / 30-06-2026 → SARL KEBICHE INVEST (Gestion administrative)
  - FACTURE_067 / 30-06-2026 → SPA H.B.A.G (Gestion d'équipe)
  - FACTURE_069 / 30-06-2026 → SARL LOUAI CATRING SERVICE (Communication, HSE, Excel)
  - FACTURE_070 / 17-08-2026 → SPA BIOREAL PHARM ETS ELEULMA (4 formations)
  - FACTURE_072 / 23-08-2026 → SARL SETIF CITERNES (Veille réglementaire RH)

Run:
    python manage.py sequel_formations_seed_p6
    python manage.py sequel_formations_seed_p6 --clear
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
    "LAKRACHE TOUFIK",
    "SNC KEBICHE ABDELHALIM ET CIE",
    "SNC KEBICHE ET CIE",
    "SARL KEBICHE INVEST",
    "SPA H.B.A.G",
    "SARL LOUAI CATRING SERVICE",
]

# Existing clients reused from earlier sequel parts (looked up, not created).
REUSED_CLIENT_NAMES = {
    "lamsat_kabir": "SARL LAMSAT KABIR",
    "setif_citernes": "SARL SETIF CITERNES",
    "hotel_tedj": "SARL HOTEL TEDJ EL MAOUADA",
    "bioreal_pharm": "SPA BIOREAL PHARM ETS ELEULMA",
}


class Command(BaseCommand):
    help = "Sequel seed P6 — extraction, plastics & hospitality invoices (2026), gap 060-072."

    def add_arguments(self, parser):
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Delete the P6 invoices and the clients created solely for this part before re-seeding.",
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
            self.style.SUCCESS("\n✓ Sequel seed P6 terminé avec succès.\n")
        )

    # ------------------------------------------------------------------ #
    # Clear
    # ------------------------------------------------------------------ #
    def _clear_data(self):
        # Only the 6 brand-new clients are wiped here; reused clients
        # (lamsat_kabir, setif_citernes, hotel_tedj, bioreal_pharm) keep
        # their other invoices from earlier parts and are cleaned up by
        # the per-invoice self-healing delete in _seed_invoices instead.
        client_qs = Client.objects.filter(name__in=NEW_CLIENT_NAMES)
        InvoiceItem.objects.filter(invoice__client__in=client_qs).delete()
        Invoice.objects.filter(client__in=client_qs).delete()
        client_qs.delete()
        self.stdout.write("  ✓ Données P6 supprimées (nouveaux clients).")

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
        cat_rh, _ = FormationCategory.objects.get_or_create(
            code="RH",
            defaults={"name": "Management des Ressources Humaines", "color": "#6366F1"},
        )

        # (title, category, duration_days, duration_hours, base_price)
        formations = [
            ("Formation de Gestion d'Équipe", cat_com, 2, 16, Decimal("29816.52")),
            ("Formations RH et Paie", cat_rh, 2, 16, Decimal("27981.65")),
            ("Formations en Gestion Administrative", cat_com, 2, 16, Decimal("29357.80")),
            ("Formation Management RH", cat_rh, 5, 40, Decimal("50000.00")),
            ("Formation Gestion Trésorerie", cat_com, 4, 32, Decimal("45779.80")),
            ("Formation des Agents de Sécurité", cat_hse, 3, 24, Decimal("55000.00")),
            ("Formation Communication Interpersonnelle", cat_com, 3, 24, Decimal("55000.00")),
            ("Formation Communication", cat_com, 5, 40, Decimal("20000.00")),
            ("Formation Superviseur HSE", cat_hse, 5, 40, Decimal("20000.00")),
            ("Formation Excel Avancée", cat_com, 4, 32, Decimal("50000.00")),
            ("Formation CPHS", cat_hse, 5, 40, Decimal("60000.00")),
            ("Formation Veille Réglementaire RH", cat_rh, 3, 24, Decimal("25000.00")),
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
            f"  ✓ Catalogue P6 — {created} formations créées, "
            f"{len(formations) - created} déjà existantes."
        )

    # ------------------------------------------------------------------ #
    # Clients
    # ------------------------------------------------------------------ #
    def _seed_clients(self):
        fj_sarl, _ = FormeJuridique.objects.get_or_create(
            name="SARL",
            defaults={"description": "Société à Responsabilité Limitée"},
        )
        fj_snc, _ = FormeJuridique.objects.get_or_create(
            name="SNC",
            defaults={"description": "Société en Nom Collectif"},
        )
        fj_spa, _ = FormeJuridique.objects.get_or_create(
            name="SPA",
            defaults={"description": "Société par Actions"},
        )
        E = Client.ClientType.ENTREPRISE

        specs = [
            (
                "lakrache_toufik",
                dict(
                    # Individual commerçant (no company suffix in the RC) —
                    # still holds a full RC/NIF/NIS/AI and is TVA-liable
                    # (9% charged), so modelled as ENTREPRISE with no
                    # forme_juridique rather than as auto-entrepreneur.
                    name="LAKRACHE TOUFIK",
                    client_type=E,
                    forme_juridique=None,
                    address="Zone d'Activité, Ouled Saber, Sétif",
                    city="Ouled Saber",
                    activity_sector="Production Industrielle des Éléments en Béton Non Assemblés",
                    rc="99A0430872-19/02",
                    nif="169190101459111",
                    nis="196919010145923",
                    article_imposition="19470020730",
                ),
            ),
            (
                "kebiche_abdelhalim",
                dict(
                    name="SNC KEBICHE ABDELHALIM ET CIE",
                    client_type=E,
                    forme_juridique=fj_snc,
                    address="Kef Lahmar, Djebel Youcef, Bir Haddada, Sétif",
                    city="Sétif",
                    activity_sector="Extraction et Préparation de Sables, Extraction de Matériaux Alluvionnaires",
                    rc="04B0085710-00/19",
                    nif="000419008571081",
                    nis="000419340810946",
                    article_imposition="19343224094",
                ),
            ),
            (
                "kebiche_et_cie",
                dict(
                    name="SNC KEBICHE ET CIE",
                    client_type=E,
                    forme_juridique=fj_snc,
                    address="Djebel Youcef, Bir Haddada, Sétif",
                    city="Sétif",
                    activity_sector="Extraction et Préparation de Sables, Extraction de Matériaux Alluvionnaires",
                    rc="98B0082728-00/19",
                    nif="09981900827284500000",
                    nis="099819340642419",
                    article_imposition="19343378005",
                ),
            ),
            (
                "kebiche_invest",
                dict(
                    name="SARL KEBICHE INVEST",
                    client_type=E,
                    forme_juridique=fj_sarl,
                    address=(
                        "Cité Gaoua, 50 Logements Sociaux Participatifs, "
                        "Lot N°3, Bloc C, Rez-de-Chaussée, Sétif"
                    ),
                    city="Sétif",
                    activity_sector="Fabrication de Matières Plastiques de Base et d'Articles en Matières Plastiques",
                    rc="18B0093165-00/19",
                    nif="001819009316569",
                    nis="001819010017068",
                    article_imposition="19017010053",
                ),
            ),
            (
                "hbag",
                dict(
                    name="SPA H.B.A.G",
                    client_type=E,
                    forme_juridique=fj_spa,
                    address="Djenane Tebib, Ain Naadja, N°09, Bâtiment S, RDC, Bir Khadem",
                    city="Bir Khadem",
                    activity_sector="Fabrication de Produits pour l'Alimentation des Animaux",
                    rc="11 B 0089243-00/16",
                    nif="001119008924389",
                    nis="001119010024370",
                    article_imposition="19016742029",
                ),
            ),
            (
                "louai_catring",
                dict(
                    name="SARL LOUAI CATRING SERVICE",
                    client_type=E,
                    forme_juridique=fj_sarl,
                    address="Cité Bouchama, Projet 04 Logements, Lot 4, Détachement Touskoz, Lot 06, RDC",
                    city="",
                    activity_sector="Entreprise de Services Hôteliers et de Restauration (Catering)",
                    rc="11B0143735-00/21",
                    nif="001121014373517",
                    nis="197319010305541",
                    article_imposition="20117304389",
                ),
            ),
        ]

        clients = {}
        for key, defaults in specs:
            client, _ = Client.objects.get_or_create(
                name=defaults["name"], defaults=defaults
            )
            clients[key] = client

        for key, name in REUSED_CLIENT_NAMES.items():
            clients[key] = Client.objects.get(name=name)

        self.stdout.write(
            f"  ✓ {len(specs)} nouveaux clients + {len(REUSED_CLIENT_NAMES)} clients réutilisés"
        )
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
            target_number/year slot — matched on either the finale
            reference (…-NNN-YEAR) or the proforma reference (…-NNN-YEAR),
            regardless of prefix. Makes the seed self-healing across
            re-runs. Returns the number of invoices deleted.
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
            # ── 060 / LAMSAT KABIR — Qualification Transport (2026) ─────
            dict(
                target_number=60,
                year=YEAR,
                date=datetime.date(2026, 6, 30),
                client=C["lamsat_kabir"],
                bc="",
                mode="",
                amount_ht=D("32000.00"),
                amount_tva=D("2880.00"),
                amount_ttc=D("34880.00"),
                items=[
                    (
                        1,
                        "Formation de Qualification de Conduite de Transport Personnel",
                        PP, D("1"), D("1"), D("32000.00"), D("0"),
                    ),
                ],
            ),
            # ── 061 / HOTEL TEDJ EL MAOUADA — Formations CPHS (2026) ────
            dict(
                target_number=61,
                year=YEAR,
                date=datetime.date(2026, 6, 30),
                client=C["hotel_tedj"],
                bc="",
                mode="",
                amount_ht=D("300000.00"),
                amount_tva=D("27000.00"),
                amount_ttc=D("327000.00"),
                items=[
                    (1, "Formations CPHS", PD, D("1"), D("5"), D("60000.00"), D("0")),
                ],
            ),
            # ── 062 / LAMSAT KABIR — Qualification Transport, 2e session ─
            dict(
                target_number=62,
                year=YEAR,
                date=datetime.date(2026, 6, 30),
                client=C["lamsat_kabir"],
                bc="",
                mode="",
                amount_ht=D("32000.00"),
                amount_tva=D("2880.00"),
                amount_ttc=D("34880.00"),
                items=[
                    (
                        1,
                        "Formation de Qualification de Conduite de Transport Personnel",
                        PP, D("1"), D("1"), D("32000.00"), D("0"),
                    ),
                ],
            ),
            # ── 063 / LAKRACHE TOUFIK — Gestion d'équipe (2026) ─────────
            dict(
                target_number=63,
                year=YEAR,
                date=datetime.date(2026, 6, 30),
                client=C["lakrache_toufik"],
                bc="",
                mode="",
                amount_ht=D("59633.03"),
                amount_tva=D("5366.97"),
                amount_ttc=D("65000.00"),
                items=[
                    # Source shows 02J × 29 816.515 HT/j = 59 633.03 — the
                    # per-day rate has 3 decimals (unrepresentable on the
                    # 2-decimal unit_price_ht field), so the exact invoiced
                    # total is captured directly as a forfait line.
                    (1, "Formation de gestion d'équipe", FF, D("1"), D("1"), D("59633.03"), D("0")),
                ],
            ),
            # ── 064 / SNC KEBICHE ABDELHALIM ET CIE — RH et paie (2026) ─
            dict(
                target_number=64,
                year=YEAR,
                date=datetime.date(2026, 6, 30),
                client=C["kebiche_abdelhalim"],
                bc="",
                mode="",
                amount_ht=D("55963.30"),
                amount_tva=D("5036.70"),
                amount_ttc=D("61000.00"),
                items=[
                    (1, "Formations RH et paie", PD, D("1"), D("2"), D("27981.65"), D("0")),
                ],
            ),
            # ── 065 / SNC KEBICHE ET CIE — Gestion d'équipe (2026) ──────
            dict(
                target_number=65,
                year=YEAR,
                date=datetime.date(2026, 6, 30),
                client=C["kebiche_et_cie"],
                bc="",
                mode="",
                amount_ht=D("25688.07"),
                amount_tva=D("2311.93"),
                amount_ttc=D("28000.00"),
                items=[
                    (1, "Formation de gestion d'équipe", PD, D("1"), D("1"), D("25688.07"), D("0")),
                ],
            ),
            # ── 066 / SARL KEBICHE INVEST — Gestion administrative ──────
            dict(
                target_number=66,
                year=YEAR,
                date=datetime.date(2026, 6, 30),
                client=C["kebiche_invest"],
                bc="",
                mode="",
                amount_ht=D("58715.60"),
                amount_tva=D("5284.40"),
                amount_ttc=D("64000.00"),
                items=[
                    (1, "Formations en gestion administrative", PD, D("1"), D("2"), D("29357.80"), D("0")),
                ],
            ),
            # ── 067 / SPA H.B.A.G — Gestion d'équipe (2026) ─────────────
            dict(
                target_number=67,
                year=YEAR,
                date=datetime.date(2026, 6, 30),
                client=C["hbag"],
                bc="",
                mode="",
                amount_ht=D("520000.00"),
                amount_tva=D("46800.00"),
                amount_ttc=D("566800.00"),
                items=[
                    # Printed Prix U/J (10 400.00 × 5j = 52 000.00) doesn't
                    # reconcile with the printed MONTANT HT (520 000.00) —
                    # likely a missing digit or an unstated multiplier on
                    # the source document. Captured as forfait matching the
                    # printed total exactly rather than guessing.
                    (1, "Formation de gestion d'équipe", FF, D("1"), D("1"), D("520000.00"), D("0")),
                ],
            ),
            # ── 069 / LOUAI CATRING SERVICE — 3 formations (2026) ───────
            dict(
                target_number=69,
                year=YEAR,
                date=datetime.date(2026, 6, 30),
                client=C["louai_catring"],
                bc="",
                mode="",
                amount_ht=D("400000.00"),
                amount_tva=D("36000.00"),
                amount_ttc=D("436000.00"),
                items=[
                    (1, "Formation Communication", PD, D("1"), D("5"), D("20000.00"), D("0")),
                    (2, "Formation superviseur HSE", PD, D("1"), D("5"), D("20000.00"), D("0")),
                    (3, "Formation Excel Avancée", PD, D("1"), D("4"), D("50000.00"), D("0")),
                ],
            ),
            # ── 070 / BIOREAL PHARM ETS ELEULMA — 4 formations (2026) ───
            dict(
                target_number=70,
                year=YEAR,
                date=datetime.date(2026, 8, 17),
                client=C["bioreal_pharm"],
                bc="",
                mode="Cheque",
                amount_ht=D("471559.60"),
                amount_tva=D("42440.36"),
                amount_ttc=D("513999.96"),
                items=[
                    # Item 1 & 2 montants don't reconcile with the printed
                    # "Jours" label (05-P / 04-J) — captured as forfait
                    # matching the printed montant exactly. Item 3 & 4 do
                    # reconcile cleanly (3j × price) and use per-day pricing.
                    (1, "Formation management RH", FF, D("1"), D("1"), D("50000.00"), D("0")),
                    (2, "Formation gestion trésorerie", FF, D("1"), D("1"), D("91559.60"), D("0")),
                    (3, "Formation des agents de sécurité", PD, D("1"), D("3"), D("55000.00"), D("0")),
                    (4, "Formation communication interpersonnel", PD, D("1"), D("3"), D("55000.00"), D("0")),
                ],
            ),
            # ── 072 / SETIF CITERNES — Veille réglementaire RH (2026) ───
            dict(
                target_number=72,
                year=YEAR,
                date=datetime.date(2026, 8, 23),
                client=C["setif_citernes"],
                bc="",
                mode="",
                amount_ht=D("75000.00"),
                amount_tva=D("6750.00"),
                amount_ttc=D("81750.00"),
                items=[
                    (1, "Formation veille réglementaire RH", PD, D("1"), D("3"), D("25000.00"), D("0")),
                ],
            ),
        ]

        created = 0
        for spec in specs:
            client = spec["client"]
            final_ref = None
            try:
                with transaction.atomic():
                    # Self-healing: delete anything already occupying this
                    # slot, re-prime ("configure") the counter, then create
                    # fresh. Runs inside its own savepoint so a failure on
                    # one invoice can't silently roll back the rest of the
                    # batch (see module docstring — this is what caused
                    # "055 not found" in P5).
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
            except Exception as exc:  # noqa: BLE001 — surface & continue the batch
                self.stdout.write(
                    self.style.ERROR(
                        f"    ✗ ÉCHEC n° {spec['target_number']:03d}/{spec['year']} "
                        f"({client.name[:40]}) : {exc}"
                    )
                )
                continue

            created += 1
            self.stdout.write(f"    + {final_ref}  {client.name[:50]}")

        self.stdout.write(f"  ✓ {created} factures FORMATION finalisées")

        # ── Verification pass ───────────────────────────────────────────
        missing = []
        for spec in specs:
            suffix = f"-{spec['target_number']:03d}-{spec['year']}"
            if not Invoice.objects.filter(
                invoice_type=Invoice.InvoiceType.FORMATION, reference__endswith=suffix
            ).exists():
                missing.append(f"{spec['target_number']:03d}/{spec['year']}")
        if missing:
            self.stdout.write(
                self.style.WARNING(f"  ⚠ Introuvables après le seed : {', '.join(missing)}")
            )
        else:
            self.stdout.write("  ✓ Vérification — toutes les factures ciblées sont présentes.")

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
