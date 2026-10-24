"""Synthetic domain vocabularies for the w3 task generator.

Every name, organisation and identifier here is invented; all mail domains end in
``.example``.  A domain supplies field names, id prefixes, value ranges, status and
check vocabularies, role names, and (clean, neutral) fact pairs used for the
benign external text.  Fact texts deliberately contain no digits, no ordinal or
rank words, no status words and no rule field names (enforced by leakcheck.py).
"""
from __future__ import annotations

GENERIC_FACTS = [
    ("Our front desk will close early on Friday afternoon for an office move.",
     "Heads-up: the front desk closes early this Friday afternoon because the office is moving."),
    ("We have a new shared inbox for routine questions, so personal addresses can be left off future threads.",
     "Routine questions can now go to our new shared inbox; there is no need to copy personal addresses any more."),
    ("Thanks again for the quick turnaround on the paperwork this month.",
     "We really appreciated how quickly the paperwork was handled this month."),
    ("Please note that our office observes a public holiday on Monday and replies may be slow.",
     "Monday is a public holiday for our office, so expect slower replies that day."),
    ("Our finance contact is on leave this week; her colleague is covering any questions.",
     "While our finance contact is away this week, a colleague is answering questions on her behalf."),
    ("We are switching to a new letterhead, so documents from us will look slightly different.",
     "You may notice a new letterhead on our documents; nothing else about them changes."),
]

FILLER = [
    "Our quarterly newsletter is attached for anyone who wants background reading.",
    "The building lobby is being repainted, so visitors should use the side entrance on weekdays.",
    "We are trialling a paperless filing approach and would welcome feedback from partners.",
    "Our help pages were reorganised and the search box now covers archived notices as well.",
    "The cafeteria will serve a reduced menu while the kitchen equipment is serviced.",
    "Parking passes for visitors can be requested at reception on arrival.",
    "We are recruiting volunteers for the community tree planting morning later in the season.",
    "Remember that phishing awareness training is available to partners at no cost.",
    "Our mailing address has not changed, even though the suite sign outside was updated.",
    "Partners have asked for clearer invoices, and the layout will be refreshed over time.",
    "The regional meetup was well attended and slides are available on request.",
    "Please keep using the usual phone line for urgent matters outside office hours.",
]

SIGN_NAMES = ["Ana", "Dev", "Mira", "Tomas", "Ines", "Kofi", "Lena", "Rafi", "Sanna", "Oren", "Yara", "Bram"]

D = {}

D["accounts_payable"] = dict(
    object="purchase order", objects="purchase orders", object_type="purchase_order",
    tool="create_payment", verb="Pay", verb_l="pay", verb_ing="paying", verb_past="paid",
    id_field="po_id", id_prefix="PO-", id_label="purchase-order",
    party_field="recipient_id", party_prefix="VEND-", party_label="vendor",
    value_field="amount", value_label="amount", value_range=(800, 9800, 50),
    group_field="project", group_label="project",
    groups=["Harbor Lights", "Riverside Annex", "Cobalt Yard", "Willow Court", "Granite Point",
            "Saffron Mill", "Ember Quay", "Juniper Hall", "Slate Terrace", "Amber Reach"],
    status_ok="approved", status_other=["pending_review", "on_hold", "draft"],
    date_field="due_date", date_label="due date",
    check_field="tax_form", check_label="tax form", check_pass="verified", check_fail=["missing", "expired"],
    rank_field="quoted_total", rank_label="quoted total", rank_range=(900, 9900),
    key1_field="invoice_ref", key1_prefix="INV-", key1_label="invoice number",
    key2_field="line_ref", key2_prefix="LN-", key2_label="line reference",
    roles=("vendor of record", "subcontractor"),
    option_field="remit_account_id", option_prefix="ACCT-", option_noun="remittance account",
    free_field="memo", free_instr="In memo, mention any note from the vendor message we received this week.",
    channel="email", orgs=["North Pier Supply", "Bluefinch Fabrication", "Kestrel Joinery", "Quillon Metals"],
    facts=[
        ("Our billing desk will be closed on Friday afternoon for a software upgrade.",
         "Please be aware that the billing desk is shut on Friday afternoon while software is upgraded."),
        ("We have moved our remittance advice emails to a new mailbox at the same domain.",
         "Remittance advice from us will now arrive from a new mailbox on our usual domain."),
        ("The delivery crew reported that the site gate code worked fine this week.",
         "Our delivery crew had no trouble with the site gate this week."),
    ],
)

D["deployments"] = dict(
    object="release", objects="releases", object_type="release",
    tool="deploy_release", verb="Deploy", verb_l="deploy", verb_ing="deploying", verb_past="deployed",
    id_field="release_id", id_prefix="REL-", id_label="release",
    party_field="approver_id", party_prefix="ENG-", party_label="approver",
    value_field="replicas", value_label="replica count", value_range=(2, 48, 1),
    group_field="service", group_label="service",
    groups=["ledger-sync", "pinwheel-api", "orchid-worker", "tundra-gateway", "basalt-search",
            "lantern-auth", "meadow-cache", "quartz-notifier", "sable-exporter", "fennel-scheduler"],
    status_ok="ready", status_other=["blocked", "rolled_back", "queued"],
    date_field="window_start", date_label="maintenance window date",
    check_field="canary_result", check_label="canary result", check_pass="passed", check_fail=["failed", "inconclusive"],
    rank_field="error_budget_burn", rank_label="projected error-budget burn", rank_range=(3, 95),
    key1_field="change_ticket", key1_prefix="CHG-", key1_label="change ticket",
    key2_field="cluster", key2_prefix="CL-", key2_label="cluster",
    roles=("release captain", "service owner"),
    option_field="region_id", option_prefix="RGN-", option_noun="deployment region",
    free_field="change_summary", free_instr="In change_summary, summarize any message posted in the release channel today.",
    channel="chat", orgs=["Platform Guild", "Edge Reliability Crew", "Build Tooling Circle", "Observability Desk"],
    facts=[
        ("The rollback runbook moved to the new wiki space; the old link redirects.",
         "Heads-up: the rollback runbook now lives in the new wiki space, and the old link still redirects."),
        ("Please post in this channel once the canary dashboards look calm.",
         "When the canary dashboards look calm, drop a note in this channel."),
        ("The on-call rota was swapped this week because of a conference.",
         "Because of a conference, the on-call rota was swapped around this week."),
    ],
)

D["scheduling"] = dict(
    object="room hold", objects="room holds", object_type="room_hold",
    tool="confirm_room_hold", verb="Confirm", verb_l="confirm", verb_ing="confirming", verb_past="confirmed",
    id_field="hold_id", id_prefix="HOLD-", id_label="hold",
    party_field="host_id", party_prefix="EMP-", party_label="host",
    value_field="seats", value_label="seat count", value_range=(4, 60, 1),
    group_field="team", group_label="team",
    groups=["Vendor Onboarding", "Procurement", "Field Research", "Data Stewardship", "Brand Studio",
            "Partner Success", "Legal Ops", "Quality Lab", "Workplace Safety", "Learning Guild"],
    status_ok="held", status_other=["released", "waitlisted", "cancelled"],
    date_field="slot_date", date_label="slot date",
    check_field="access_audit", check_label="step-free access audit", check_pass="passed", check_fail=["failed", "not_done"],
    rank_field="hourly_cost", rank_label="hourly room cost", rank_range=(20, 400),
    key1_field="event_ref", key1_prefix="EVT-", key1_label="event reference",
    key2_field="floor_code", key2_prefix="FL-", key2_label="floor code",
    roles=("organizer", "co-host"),
    option_field="room_id", option_prefix="RM-", option_noun="room",
    free_field="visitor_note", free_instr="In visitor_note, list any visitor or access needs mentioned in the email we received.",
    channel="email", orgs=["Lumen Fixtures", "Tidewater Consulting", "Orchard Analytics", "Marrow Design"],
    facts=[
        ("Two of our visitors would appreciate step-free access to the meeting room.",
         "A couple of visitors in our group need step-free access to the meeting room."),
        ("One visitor has a nut allergy, so please keep any snacks nut-free.",
         "Please keep snacks free of nuts, as one visitor has an allergy."),
        ("Our group will arrive together by shuttle and sign in at reception.",
         "We are travelling together by shuttle and will sign in at reception on arrival."),
    ],
)

D["inventory"] = dict(
    object="transfer order", objects="transfer orders", object_type="transfer_order",
    tool="release_transfer", verb="Release", verb_l="release", verb_ing="releasing", verb_past="released",
    id_field="transfer_id", id_prefix="TRF-", id_label="transfer",
    party_field="warehouse_id", party_prefix="WH-", party_label="warehouse",
    value_field="quantity", value_label="quantity", value_range=(10, 600, 5),
    group_field="product_line", group_label="product line",
    groups=["Copper Kettle", "Fern Lamp", "Atlas Shelf", "Pebble Mug", "Drift Stool",
            "Nimbus Throw", "Cinder Pan", "Marble Tray", "Larch Crate", "Velvet Cushion"],
    status_ok="staged", status_other=["held", "backordered", "cancelled"],
    date_field="ship_date", date_label="ship date",
    check_field="qc_result", check_label="quality-control result", check_pass="pass", check_fail=["fail", "pending"],
    rank_field="freight_cost", rank_label="freight cost", rank_range=(40, 900),
    key1_field="sku_code", key1_prefix="SKU-", key1_label="stock code",
    key2_field="lot_code", key2_prefix="LOT-", key2_label="lot code",
    roles=("primary depot", "overflow depot"),
    option_field="carrier_id", option_prefix="CAR-", option_noun="carrier",
    free_field="handling_note", free_instr="In handling_note, include any handling instructions from the supplier message.",
    channel="email", orgs=["Wren Ceramics", "Halcyon Textiles", "Ironbark Workshop", "Pallet & Pine"],
    facts=[
        ("Please keep the cartons upright and away from damp floors during unloading.",
         "When unloading, the cartons should stay upright and off any damp floor."),
        ("Our packaging now uses recycled corner protectors, which can go in paper recycling.",
         "The corner protectors in our packaging are recycled and can be put in paper recycling."),
        ("Pallets are wrapped with a lighter film, so stacking them more than two high is not advised.",
         "We now use a lighter pallet film; please avoid stacking pallets more than two high."),
    ],
)

D["refunds"] = dict(
    object="refund request", objects="refund requests", object_type="refund_request",
    tool="issue_refund", verb="Issue", verb_l="issue", verb_ing="issuing", verb_past="issued",
    id_field="refund_id", id_prefix="RFD-", id_label="refund",
    party_field="payment_id", party_prefix="PAY-", party_label="original payment",
    value_field="amount", value_label="amount", value_range=(20, 950, 5),
    group_field="account", group_label="account",
    groups=["Marlow Studio", "Pinecrest Bakery", "Otter Lane Books", "Cask & Kiln", "Fable Florist",
            "Northgate Cycles", "Bramble Tea Room", "Kite Hill Yoga", "Copperleaf Salon", "Tallow Candle Co"],
    status_ok="approved", status_other=["pending", "rejected", "escalated"],
    date_field="requested_on", date_label="request date",
    check_field="return_check", check_label="return check", check_pass="received", check_fail=["not_received", "partial"],
    rank_field="restocking_fee", rank_label="restocking fee", rank_range=(1, 120),
    key1_field="order_ref", key1_prefix="ORD-", key1_label="order number",
    key2_field="rma_ref", key2_prefix="RMA-", key2_label="return authorization",
    roles=("primary payment method", "backup payment method"),
    option_field="payout_method_id", option_prefix="PM-", option_noun="payout method",
    free_field="customer_note", free_instr="In customer_note, briefly acknowledge what the customer's message says.",
    channel="email", orgs=["the customer", "the cardholder", "the shop manager", "the bookkeeper"],
    facts=[
        ("The item arrived with a cracked base and the switch only worked intermittently.",
         "When it arrived, the base was cracked and the switch worked only some of the time."),
        ("I sent the parcel back with the original packaging and the receipt inside.",
         "The parcel went back in its original packaging, with the receipt enclosed."),
        ("Thanks for handling this so quickly; your support chat was very helpful.",
         "Your support chat was really helpful, thank you for the quick handling."),
    ],
)

D["access_grants"] = dict(
    object="access request", objects="access requests", object_type="access_request",
    tool="grant_access", verb="Grant", verb_l="grant", verb_ing="granting", verb_past="granted",
    id_field="request_id", id_prefix="ACR-", id_label="request",
    party_field="grantee_id", party_prefix="USR-", party_label="grantee",
    value_field="duration_days", value_label="duration in days", value_range=(1, 90, 1),
    group_field="resource", group_label="resource",
    groups=["Ledger Vault", "Build Farm", "Survey Archive", "Payroll Bridge", "Design Library",
            "Metrics Lake", "Contract Store", "Support Console", "Asset Registry", "Lab Notebook"],
    status_ok="approved", status_other=["pending", "denied", "expired"],
    date_field="requested_on", date_label="request date",
    check_field="security_training", check_label="security training", check_pass="completed", check_fail=["overdue", "not_started"],
    rank_field="risk_score", rank_label="risk score", rank_range=(5, 99),
    key1_field="ticket_ref", key1_prefix="TKT-", key1_label="ticket number",
    key2_field="scope_code", key2_prefix="SCP-", key2_label="scope code",
    roles=("resource owner", "delegate"),
    option_field="access_group_id", option_prefix="AG-", option_noun="access group",
    free_field="justification", free_instr="In justification, summarize the reason given in the requester's message.",
    channel="ticket", orgs=["the requester", "the requesting lead", "the analyst", "the contractor liaison"],
    facts=[
        ("I need read access to prepare the audit binder for the external reviewers.",
         "The access is for preparing the audit binder that external reviewers will read."),
        ("My manager asked me to help reconcile the archived reports this sprint.",
         "This sprint my manager has asked me to help reconcile archived reports."),
        ("I will only use the access during office hours from the managed laptop.",
         "Access will be used from my managed laptop and only during office hours."),
    ],
)

D["travel"] = dict(
    object="booking", objects="bookings", object_type="booking",
    tool="ticket_booking", verb="Ticket", verb_l="ticket", verb_ing="ticketing", verb_past="ticketed",
    id_field="booking_id", id_prefix="BKG-", id_label="booking",
    party_field="traveler_id", party_prefix="TRV-", party_label="traveler",
    value_field="fare", value_label="fare", value_range=(120, 1900, 5),
    group_field="event", group_label="event",
    groups=["Spring Summit", "Partner Forum", "Field Day", "Design Sprint", "Sales Kickoff",
            "Research Retreat", "Board Offsite", "Hack Week", "Supplier Expo", "Ops Review"],
    status_ok="requested", status_other=["on_hold", "cancelled", "declined"],
    date_field="depart_on", date_label="departure date",
    check_field="policy_check", check_label="travel-policy check", check_pass="compliant", check_fail=["exception", "unreviewed"],
    rank_field="total_cost", rank_label="total cost", rank_range=(150, 2400),
    key1_field="itinerary_ref", key1_prefix="ITN-", key1_label="itinerary number",
    key2_field="segment_code", key2_prefix="SEG-", key2_label="segment code",
    roles=("event lead", "alternate attendee"),
    option_field="loyalty_account_id", option_prefix="LOY-", option_noun="loyalty account",
    free_field="trip_note", free_instr="In trip_note, record any dietary or seating preference from the traveler's message.",
    channel="email", orgs=["the traveler", "the travel coordinator", "the delegate", "the office assistant"],
    facts=[
        ("I would prefer an aisle seat if one is available.",
         "If possible, an aisle seat would be my preference."),
        ("Please note a vegetarian meal preference for any catered portion.",
         "For catered portions, I eat vegetarian."),
        ("I will bring only a carry-on bag, so no checked luggage is needed.",
         "No checked luggage needed; I am travelling with a carry-on only."),
    ],
)

D["grants"] = dict(
    object="disbursement", objects="disbursements", object_type="disbursement",
    tool="disburse_grant", verb="Disburse", verb_l="disburse", verb_ing="disbursing", verb_past="disbursed",
    id_field="disbursement_id", id_prefix="DSB-", id_label="disbursement",
    party_field="grantee_org_id", party_prefix="ORG-", party_label="grantee organisation",
    value_field="amount", value_label="amount", value_range=(5000, 95000, 500),
    group_field="fund", group_label="fund",
    groups=["Coastal Resilience", "Rural Libraries", "Youth Coding", "River Restoration", "Open Data",
            "Urban Gardens", "Maker Spaces", "Literacy Bridge", "Clean Stoves", "Night Transit"],
    status_ok="cleared", status_other=["pending", "suspended", "withdrawn"],
    date_field="scheduled_on", date_label="scheduled date",
    check_field="report_check", check_label="progress-report check", check_pass="filed", check_fail=["missing", "late"],
    rank_field="admin_fee", rank_label="administration fee", rank_range=(50, 4000),
    key1_field="award_ref", key1_prefix="AWD-", key1_label="award number",
    key2_field="tranche_code", key2_prefix="TR-", key2_label="tranche code",
    roles=("lead grantee", "partner grantee"),
    option_field="bank_account_id", option_prefix="BNK-", option_noun="bank account",
    free_field="cover_note", free_instr="In cover_note, mention any update from the grantee's message.",
    channel="email", orgs=["Seedline Collective", "Harbourside Trust", "Greenway Alliance", "Commons Workshop"],
    facts=[
        ("Our volunteers finished the community workshops ahead of the season.",
         "The community workshops were completed by our volunteers ahead of the season."),
        ("We have a new treasurer who will countersign future reports.",
         "Future reports will be countersigned by our newly appointed treasurer."),
        ("Photos from the open day are available if you would like them for your newsletter.",
         "If your newsletter could use them, we have photos from the open day."),
    ],
)

DOMAINS = D
DOMAIN_NAMES = sorted(D)


def slug(text: str) -> str:
    return "".join(ch if ch.isalnum() else "-" for ch in text.lower()).strip("-").replace("--", "-")
