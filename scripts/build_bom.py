"""Write build/bom.html from bom/parts.toml.

Stdlib only, so it runs on the plain mise-managed Python.
"""

import html
import json
import tomllib
from collections import OrderedDict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BUILD = ROOT / "build"
SOURCE = ROOT / "bom" / "parts.toml"

CHANGES = [
    (
        "Power supplies: Mean Well RSP-320 instead of LRS-350.",
        "EU shops only sell the LRS-350 to business customers (it has no power-factor "
        "correction). The RSP-320 has the same 215 × 115 × 30 mm footprint, PFC and a "
        "universal input with no 115/230 V selector. The 12 V model gives 26.7 A instead "
        "of 29 A, still well above the planned load.",
    ),
    (
        "PSU → fuse block feeds: 3 × 2.5 mm² per pole.",
        "Each RSP has three +V and three −V screws, one wire per screw. The 12 V and 24 V "
        "negative buses are bonded with 2.5 mm² so both BUNNY boards share one toy ground.",
    ),
    (
        "Inlet earth: one wire per PE tab.",
        "The inlet's PE tab takes only the feed to the earth bar, and the coupler's PE "
        "wire starts at the bar.",
    ),
    (
        "Real mechs on the Tukkari real-mech add-on.",
        "Two BUNNY boards replace the Walter + MiniMOS 4; a 24 V RSP-500 joins the 12 V supply; "
        "one RSP-320-5 now feeds every addressable LED; each Mean Well has its own switched outlet "
        "and a moulded cord, so the mains distribution box and its WAGO terminals are gone.",
    ),
    (
        "Master/slave strip: Brennenstuhl Secure-Tec 19.500A.",
        "1 master, 5 switched and 2 always-on outlets, an adjustable 8–80 W threshold and "
        "surge protection. Switched: 5 V, 12 V and 24 V supplies, amp, DMD; always-on: OLED, "
        "backglass.",
    ),
]

NOT_INCLUDED = [
    "The PC",
    "Parts you already own: HDMI and DisplayPort cables, USB-A → USB-C cable",
    "Other tools: wire stripper, soldering iron (for the XT60s), multimeter with a low-ohm range, step drill (arcade button holes)",
    "Filament for the 3D prints (they have their own list, without prices)",
]

PHASES = OrderedDict(
    [
        (
            1,
            (
                "Must have",
                "Playable and safe: cabinet and legs, the playfield OLED, the Dude's Cab with the "
                "flipper, Start, Launch Ball and Exit buttons, the inlet, strip and earth loop, "
                "cooling, the cable trays, and the coin door and playfield glass that keep the cats out.",
            ),
        ),
        (
            2,
            (
                "Should have",
                "The full experience: backglass and DMD screens, SSF sound, "
                "plunger, tilt, coin switches with The BRAIN, and the Return button.",
            ),
        ),
        (
            3,
            (
                "Later",
                "The light show and the real mechs: Mean Well supplies, fuse blocks and BUNNY boards, "
                "all addressable LEDs, button lamps, flippers, slings, pop bumpers, chimes, bells, "
                "knocker and motors. Adding it doesn't mean rewiring phases 1–2.",
            ),
        ),
    ]
)


def esc(value) -> str:
    return html.escape(str(value), quote=True)


def lines(count: int) -> str:
    return f"{count} line" if count == 1 else f"{count} lines"


def eur(value: float) -> str:
    return f"€{value:,.2f}"


def dkk(value: float) -> str:
    return f"{value:,.0f} kr"


def main() -> None:
    data = tomllib.loads(SOURCE.read_text(encoding="utf-8"))
    dk_vat = data["dk_vat"]
    rate = data["eur_dkk"]
    vendors = OrderedDict((v["id"], v) for v in data["vendors"])
    by_vendor = OrderedDict((vid, []) for vid in vendors)

    for item in data["items"]:
        vendor = vendors[item["vendor"]]
        if "price" in item:
            unit = item["price"] / (1 + vendor["vat"]) * (1 + dk_vat)
        elif "price_asis" in item:
            unit = item["price_asis"]
        elif "price_dkk" in item:
            unit = item["price_dkk"] / rate
        else:
            unit = None
        item["unit_eur"] = unit
        item["total_eur"] = None if unit is None else unit * item["buy"]
        by_vendor[item["vendor"]].append(item)

    def subtotal(items):
        return sum(i["total_eur"] for i in items if i["total_eur"] is not None)

    def unpriced(items):
        return sum(1 for i in items if i["total_eur"] is None)

    subtotals = {vid: subtotal(items) for vid, items in by_vendor.items()}
    grand_total = sum(subtotals.values())
    item_count = sum(len(items) for items in by_vendor.values())
    unpriced_total = sum(unpriced(items) for items in by_vendor.values())
    estimate_total = sum(
        i["total_eur"] for items in by_vendor.values() for i in items if i.get("estimate") and i["total_eur"]
    )

    phase_cards = []
    for number, (label, blurb) in PHASES.items():
        items = [i for i in data["items"] if i["priority"] == number]
        flag = f' · {unpriced(items)} not priced' if unpriced(items) else ""
        phase_cards.append(
            f"""
        <button type="button" class="phase-card p{number}" data-phase-filter="{number}" aria-pressed="false">
          <span class="pill p{number}">{number} · {esc(label)}</span>
          <span class="card-total">{dkk(subtotal(items) * rate)}</span>
          <span class="card-meta">{eur(subtotal(items))} · {lines(len(items))}{flag} · <span data-phase-left="{number}"></span></span>
          <span class="phase-blurb">{esc(blurb)}</span>
        </button>"""
        )

    cards = []
    for vid, vendor in vendors.items():
        items = by_vendor[vid]
        if not items:
            continue
        flag = f' · {unpriced(items)} not priced' if unpriced(items) else ""
        cards.append(
            f"""
      <a class="card" href="#{esc(vid)}" data-card="{esc(vid)}">
        <span class="card-country">{esc(vendor["country"])}</span>
        <strong>{esc(vendor["name"])}</strong>
        <span class="card-total" data-card-kr>{dkk(subtotals[vid] * rate)}</span>
        <span class="card-meta"><span data-card-eur>{eur(subtotals[vid])}</span> · <span data-card-lines>{lines(len(items))}{flag}</span> · <span data-remaining="{esc(vid)}"></span></span>
      </a>"""
        )

    sections = []
    for vid, vendor in vendors.items():
        items = by_vendor[vid]
        if not items:
            continue
        rows = []
        current_group = None
        for index, item in enumerate(items):
            if item["group"] != current_group:
                current_group = item["group"]
                rows.append(f'<tr class="group"><th colspan="9">{esc(current_group)}</th></tr>')
            key = f"{vid}-{index}-{item['part']}"
            phase = item["priority"]
            purchased = bool(item.get("purchased"))
            purchased_pill = '<span class="pill purchased">Purchased</span>' if purchased else ""
            flags = ""
            if item.get("note"):
                flags += f'<p class="flag">{esc(item["note"])}</p>'
            if item.get("priority_note"):
                flags += f'<p class="flag phase-note">{esc(item["priority_note"])}</p>'
            name = esc(item["name"])
            link = f'<a href="{esc(item["url"])}" target="_blank" rel="noopener">{name}</a>' if item["url"] else f"<span class=\"nolink\">{name}</span>"
            if item["unit_eur"] is None:
                price_cells = f'<td class="num muted">not priced</td><td class="num muted">—</td><td class="num muted">—</td>'
                total_attr = "0"
            else:
                est = ' <span class="est">est.</span>' if item.get("estimate") else ""
                price_cells = (
                    f'<td class="num">{eur(item["unit_eur"])}{est}</td>'
                    f'<td class="num total">{eur(item["total_eur"])}</td>'
                    f'<td class="num total">{dkk(item["total_eur"] * rate)}</td>'
                )
                total_attr = f'{item["total_eur"]:.2f}'
            rows.append(
                f"""
          <tr data-key="{esc(key)}" data-vendor="{esc(vid)}" data-total="{total_attr}" data-phase="{phase}" data-unpriced="{int(item["total_eur"] is None)}" data-purchased="{int(purchased)}">
            <td class="check"><input type="checkbox" aria-label="Bought: {name}"{" checked disabled" if purchased else ""}></td>
            <td class="prio"><span class="pill p{phase}">{phase} · {esc(PHASES[phase][0])}</span>{purchased_pill}</td>
            <td class="part">
              {link}
              <span class="pn">{esc(item["part"])}</span>
              {flags}
            </td>
            <td class="used">{esc(item["used_on"])}</td>
            <td class="num">{esc(item["need"])}</td>
            <td class="num buy">{item["buy"]}</td>
            {price_cells}
          </tr>"""
            )

        vat_note = (
            f'prices converted from the shop\'s {int(vendor["vat"] * 100)} % VAT to Danish 25 % moms'
            if "vat" in vendor
            else "prices used as written"
        )
        site = (
            f'<a href="{esc(vendor["site"])}" target="_blank" rel="noopener">{esc(vendor["name"])}</a>'
            if vendor["site"]
            else esc(vendor["name"])
        )
        sections.append(
            f"""
    <section class="vendor" id="{esc(vid)}">
      <header class="vendor-head">
        <div>
          <h2>{site}</h2>
          <p class="vendor-country">{esc(vendor["country"])} · {vat_note}</p>
        </div>
        <div class="vendor-sum">
          <span>Subtotal</span>
          <strong data-sub-kr>{dkk(subtotals[vid] * rate)}</strong>
          <em data-sub-eur>{eur(subtotals[vid])}</em>
        </div>
      </header>
      <p class="why">{esc(vendor["why"])}</p>
      <p class="ship"><strong>Shipping:</strong> {esc(vendor["shipping"])}</p>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th class="check"><span class="sr">Bought</span></th>
              <th>Priority</th>
              <th>Part</th>
              <th>Used for (sheet)</th>
              <th class="num">Need</th>
              <th class="num">Buy</th>
              <th class="num">Each</th>
              <th class="num">Line €</th>
              <th class="num">Line kr</th>
            </tr>
          </thead>
          <tbody>{"".join(rows)}
          </tbody>
        </table>
      </div>
    </section>"""
        )

    prints = data.get("prints", [])
    print_rows = []
    for item in prints:
        phase = item["priority"]
        name = esc(item["name"])
        link = f'<a href="{esc(item["url"])}" target="_blank" rel="noopener">{name}</a>' if item.get("url") else f'<span class="nolink">{name}</span>'
        flags = f'<p class="flag">{esc(item["note"])}</p>' if item.get("note") else ""
        print_rows.append(
            f"""
          <tr data-print="{esc(item["name"])}" data-phase="{phase}">
            <td class="check"><input type="checkbox" aria-label="Printed: {name}"></td>
            <td class="prio"><span class="pill p{phase}">{phase} · {esc(PHASES[phase][0])}</span></td>
            <td class="part">
              {link}
              <span class="pn">{esc(item["source"])}</span>
              {flags}
            </td>
            <td class="used">{esc(item["used_on"])}</td>
            <td class="num buy">{esc(item["need"])}</td>
          </tr>"""
        )
    prints_section = (
        f"""
    <section class="vendor prints" id="prints">
      <header class="vendor-head">
        <div>
          <h2>3D prints</h2>
          <p class="vendor-country">Printed yourself · not in the totals</p>
        </div>
      </header>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th class="check"><span class="sr">Printed</span></th>
              <th>Priority</th>
              <th>Part</th>
              <th>Used for (sheet)</th>
              <th class="num">Qty</th>
            </tr>
          </thead>
          <tbody>{"".join(print_rows)}
          </tbody>
        </table>
      </div>
    </section>"""
        if prints
        else ""
    )
    prints_card = (
        f"""
      <a class="card" href="#prints">
        <span class="card-country">Print yourself</span>
        <strong>3D prints</strong>
        <span class="card-total">{len(prints)} parts</span>
        <span class="card-meta">no shop, not in the totals</span>
      </a>"""
        if prints
        else ""
    )

    changes = "".join(f"<li><strong>{title}</strong> {body}</li>" for title, body in CHANGES)
    not_included = "".join(f"<li>{esc(entry)}</li>" for entry in NOT_INCLUDED)

    page = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Virtual Pinball BOM</title>
  <style>
    :root {{
      --bg: #f6f5f1; --panel: #ffffff; --ink: #1d1f23; --muted: #5d636b; --line: #dedbd2;
      --accent: #b3261e; --accent-soft: #fbe9e7; --info-soft: #e8f0fe; --info: #1a56b8;
      --link: #0b57d0; --done: #8a8f96; --group: #f1efe8;
      --p1: #17603a; --p1-soft: #dcefe2; --p2: #8a5a00; --p2-soft: #fbecc8; --p3: #555b63; --p3-soft: #e9e7e1;
    }}
    @media (prefers-color-scheme: dark) {{
      :root {{
        --bg: #16181c; --panel: #1f2227; --ink: #e8e6e1; --muted: #a3a8af; --line: #33373e;
        --accent: #ff8a80; --accent-soft: #3a2422; --info-soft: #1d2a3f; --info: #8ab4f8;
        --link: #8ab4f8; --done: #6b7078; --group: #262a30;
        --p1: #8fd6a8; --p1-soft: #1d3326; --p2: #f0c46a; --p2-soft: #3a2f17; --p3: #b4b9c0; --p3-soft: #2c3036;
      }}
    }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; background: var(--bg); color: var(--ink);
      font: 15px/1.5 -apple-system, "Segoe UI", Roboto, Arial, sans-serif; }}
    .page {{ max-width: 1240px; margin: 0 auto; padding: 32px 16px 64px; }}
    a {{ color: var(--link); }}
    h1 {{ font-size: 1.9rem; margin: 0 0 4px; letter-spacing: -0.01em; }}
    .lede {{ color: var(--muted); margin: 0 0 24px; max-width: 78ch; }}
    .totals {{ display: flex; flex-wrap: wrap; gap: 12px 40px; align-items: baseline; margin-bottom: 16px; }}
    .totals .big {{ font-size: 2.2rem; font-weight: 700; letter-spacing: -0.02em; }}
    .totals .muted {{ color: var(--muted); }}
    .cards {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); gap: 12px; margin: 16px 0 32px; }}
    .card {{ background: var(--panel); border: 1px solid var(--line); border-radius: 10px; padding: 14px 16px;
      text-decoration: none; color: var(--ink); display: flex; flex-direction: column; gap: 2px; }}
    .card:hover {{ border-color: var(--muted); }}
    .card-country {{ font-size: .75rem; text-transform: uppercase; letter-spacing: .06em; color: var(--muted); }}
    .card-total {{ font-size: 1.35rem; font-weight: 700; margin-top: 4px; }}
    .card-meta {{ font-size: .82rem; color: var(--muted); }}
    .callout {{ border-radius: 8px; padding: 14px 18px; margin: 0 0 20px; }}
    .callout.info {{ background: var(--info-soft); border-left: 4px solid var(--info); }}
    .callout.warn {{ background: var(--accent-soft); border-left: 4px solid var(--accent); }}
    .callout h2 {{ margin: 0 0 6px; font-size: 1.05rem; }}
    .callout p {{ margin: 0 0 8px; }}
    .callout ul {{ margin: 0; padding-left: 20px; }}
    .callout li {{ margin: 6px 0; }}
    .vendor {{ background: var(--panel); border: 1px solid var(--line); border-radius: 12px; padding: 20px; margin: 0 0 24px; }}
    .vendor-head {{ display: flex; flex-wrap: wrap; justify-content: space-between; gap: 12px; align-items: flex-start; }}
    .vendor-head h2 {{ margin: 0; font-size: 1.3rem; }}
    .vendor-head h2 a {{ color: var(--ink); }}
    .vendor-country {{ margin: 2px 0 0; color: var(--muted); font-size: .88rem; }}
    .vendor-sum {{ text-align: right; }}
    .vendor-sum span {{ display: block; font-size: .78rem; text-transform: uppercase; letter-spacing: .06em; color: var(--muted); }}
    .vendor-sum strong {{ font-size: 1.4rem; display: block; }}
    .vendor-sum em {{ font-style: normal; color: var(--muted); font-size: .9rem; }}
    .why {{ margin: 12px 0 4px; max-width: 85ch; }}
    .ship {{ margin: 0 0 12px; color: var(--muted); font-size: .92rem; }}
    .table-wrap {{ overflow-x: auto; }}
    .phases {{ margin: 8px 0 28px; }}
    .phases-head {{ display: flex; flex-wrap: wrap; gap: 8px 16px; align-items: baseline; justify-content: space-between; }}
    .phases-head h2 {{ margin: 0; font-size: 1.2rem; }}
    .phases-head p {{ margin: 0; color: var(--muted); font-size: .9rem; }}
    .show-all {{ font: inherit; font-size: .88rem; padding: 4px 12px; border-radius: 999px; border: 1px solid var(--line);
      background: var(--panel); color: var(--ink); cursor: pointer; }}
    .show-all[aria-pressed="true"] {{ border-color: var(--ink); font-weight: 600; }}
    .phase-cards {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 12px; margin-top: 12px; }}
    .phase-card {{ font: inherit; text-align: left; cursor: pointer; background: var(--panel); color: var(--ink);
      border: 1px solid var(--line); border-top: 4px solid var(--line); border-radius: 10px; padding: 14px 16px;
      display: flex; flex-direction: column; gap: 4px; }}
    .phase-card.p1 {{ border-top-color: var(--p1); }}
    .phase-card.p2 {{ border-top-color: var(--p2); }}
    .phase-card.p3 {{ border-top-color: var(--p3); }}
    .phase-card:hover {{ border-color: var(--muted); }}
    .phase-card[aria-pressed="true"] {{ outline: 2px solid var(--ink); outline-offset: -1px; }}
    .phase-card .pill {{ align-self: flex-start; }}
    .phase-blurb {{ font-size: .86rem; color: var(--muted); }}
    .pill {{ display: inline-block; padding: 2px 9px; border-radius: 999px; font-size: .74rem; font-weight: 700;
      white-space: nowrap; letter-spacing: .01em; }}
    .pill.p1 {{ color: var(--p1); background: var(--p1-soft); }}
    .pill.p2 {{ color: var(--p2); background: var(--p2-soft); }}
    .pill.p3 {{ color: var(--p3); background: var(--p3-soft); }}
    .pill.purchased {{ display: block; margin-top: 4px; width: max-content; color: var(--info); background: var(--info-soft); }}
    .prio {{ width: 1%; }}
    .flag.phase-note {{ font-style: italic; }}
    [hidden] {{ display: none !important; }}
    table {{ width: 100%; border-collapse: collapse; min-width: 960px; }}
    .prints table {{ min-width: 640px; }}
    th, td {{ padding: 8px 10px; border-bottom: 1px solid var(--line); vertical-align: top; text-align: left; }}
    thead th {{ font-size: .75rem; text-transform: uppercase; letter-spacing: .05em; color: var(--muted); font-weight: 600; }}
    tr.group th {{ background: var(--group); font-size: .82rem; color: var(--ink); padding: 6px 10px; }}
    .num {{ text-align: right; white-space: nowrap; font-variant-numeric: tabular-nums; }}
    .muted {{ color: var(--muted); }}
    .buy {{ font-weight: 700; }}
    .total {{ font-weight: 600; }}
    .est {{ font-size: .72rem; text-transform: uppercase; letter-spacing: .04em; color: var(--accent); font-weight: 700; }}
    .check {{ width: 32px; }}
    .check input {{ width: 18px; height: 18px; margin-top: 2px; }}
    .part a, .part .nolink {{ font-weight: 600; text-decoration: none; }}
    .part a:hover {{ text-decoration: underline; }}
    .pn {{ display: block; font-family: ui-monospace, "SF Mono", Menlo, monospace; font-size: .8rem; color: var(--muted); }}
    .used {{ color: var(--muted); font-size: .88rem; min-width: 160px; }}
    .flag {{ margin: 4px 0 0; font-size: .84rem; color: var(--muted); }}
    tr.done td {{ color: var(--done); }}
    tr.done .part a {{ color: var(--done); text-decoration: line-through; }}
    .sr {{ position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); }}
    .notes {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 16px; }}
    .notes section {{ background: var(--panel); border: 1px solid var(--line); border-radius: 12px; padding: 16px 20px; }}
    .notes h2 {{ font-size: 1.05rem; margin: 0 0 8px; }}
    .notes ul {{ margin: 0; padding-left: 20px; }}
    .notes p {{ margin: 0 0 8px; }}
    footer {{ color: var(--muted); font-size: .85rem; margin-top: 24px; }}
    @media print {{
      body {{ background: #fff; color: #000; }}
      .card, .check, .phase-cards, .show-all {{ display: none; }}
      .vendor {{ break-inside: avoid-page; border: 0; padding: 0; }}
      a {{ color: #000; text-decoration: none; }}
    }}
  </style>
</head>
<body>
  <div class="page">
    <h1>Virtual Pinball BOM</h1>
    <p class="lede">Everything for the cabinet except the PC, grouped by shop so each vendor is one order.
    Shop prices are converted to <strong>incl. Danish 25 % moms</strong> (Arnoz shows French 20 %; PU-Parts and Reichelt's German store show 19 %);
    quotes, DKK prices and estimates are used as written. Kroner use a rate of {rate} kr/€. Prices checked up to {esc(data["checked"])}; treat them as a snapshot.</p>

    <div class="totals">
      <div><div class="big" id="grand">{dkk(grand_total * rate)}</div><div class="muted" id="grand-meta">{eur(grand_total)} · {item_count} lines · before shipping</div></div>
      <div><div class="big" id="remaining">{dkk(grand_total * rate)}</div><div class="muted">still to buy (tick rows as you order)</div></div>
    </div>
    <p class="lede">Includes {dkk(estimate_total * rate)} of estimates (backglass, real mechs, toys). <strong>{unpriced_total} lines are not priced yet</strong> (the Amazon LED parts), so the real total is somewhat higher.</p>

    <section class="phases" aria-labelledby="phases-title">
      <div class="phases-head">
        <div>
          <h2 id="phases-title">Priority</h2>
          <p>Every line is tagged with the earliest phase that needs it. Pick a phase to see only its lines, per shop.</p>
        </div>
        <button type="button" class="show-all" data-phase-filter="all" aria-pressed="true">Show all phases</button>
      </div>
      <div class="phase-cards">{"".join(phase_cards)}
      </div>
    </section>

    <nav class="cards" aria-label="Shops">{"".join(cards)}{prints_card}
    </nav>

    <aside class="callout warn">
      <h2>Part choices behind this list</h2>
      <p>Decisions made while sourcing. The wiring sheets have been updated to match.</p>
      <ul>{changes}</ul>
    </aside>
    {"".join(sections)}
    {prints_section}

    <div class="notes">
      <section>
        <h2>How quantities work</h2>
        <p><strong>Need</strong> is what the wiring sheets use; wire lengths are routed estimates through the cable trays.
        <strong>Buy</strong> is the number of shop units (pack, reel or single part) to order, rounded up with sensible spares.</p>
        <p>Your own ticks are saved in this browser only. Rows marked <strong>Purchased</strong> come from
        <code>parts.toml</code> (<code>purchased = true</code>, with the price you paid), so they stay ticked everywhere.</p>
        <p><strong>Priority</strong> is the earliest phase a line is needed in. Wire, terminals and splices shared
        between phases are tagged with the earliest one, so buying phase by phase never leaves you short.</p>
      </section>
      <section>
        <h2>Not in this list</h2>
        <ul>{not_included}</ul>
      </section>
    </div>

    <footer>Generated from <code>bom/parts.toml</code> by <code>scripts/build_bom.py</code>. Rebuild with <code>mise run build</code>.</footer>
  </div>
  <script>
    (function () {{
      var STORE = "wiring-bom-bought";
      var PRINT_STORE = "wiring-bom-printed";
      var PHASE_STORE = "wiring-bom-phase";
      var RATE = {rate};
      var LABELS = {json.dumps({str(n): label for n, (label, _) in PHASES.items()})};
      var fmtKr = new Intl.NumberFormat("en-US", {{ maximumFractionDigits: 0 }});
      var fmtEur = new Intl.NumberFormat("en-US", {{ minimumFractionDigits: 2, maximumFractionDigits: 2 }});
      function kr(value) {{ return fmtKr.format(value * RATE) + " kr"; }}
      function eur(value) {{ return "€" + fmtEur.format(value); }}
      function plural(count) {{ return count + (count === 1 ? " line" : " lines"); }}
      function all(selector) {{ return Array.prototype.slice.call(document.querySelectorAll(selector)); }}

      var saved = {{}};
      try {{ saved = JSON.parse(localStorage.getItem(STORE) || "{{}}"); }} catch (e) {{ saved = {{}}; }}
      var phase = "all";
      try {{ phase = localStorage.getItem(PHASE_STORE) || "all"; }} catch (e) {{}}
      if (phase !== "all" && !LABELS[phase]) phase = "all";
      var rows = all("tr[data-key]");
      var printRows = all("tr[data-print]");
      var printed = {{}};
      try {{ printed = JSON.parse(localStorage.getItem(PRINT_STORE) || "{{}}"); }} catch (e) {{ printed = {{}}; }}

      function update() {{
        var total = 0, remaining = 0, lines = 0, perVendor = {{}}, phaseLeft = {{}};
        rows.forEach(function (row) {{
          var box = row.querySelector("input");
          var vendor = row.dataset.vendor;
          var amount = parseFloat(row.dataset.total);
          var shown = phase === "all" || phase === row.dataset.phase;
          var v = perVendor[vendor] = perVendor[vendor] || {{ total: 0, lines: 0, left: 0, unpriced: 0 }};
          row.classList.toggle("done", box.checked);
          row.hidden = !shown;
          if (!box.checked) phaseLeft[row.dataset.phase] = (phaseLeft[row.dataset.phase] || 0) + 1;
          if (!shown) return;
          total += amount; lines += 1;
          v.total += amount; v.lines += 1; v.unpriced += parseInt(row.dataset.unpriced, 10);
          if (!box.checked) {{ remaining += amount; v.left += 1; }}
        }});

        var printsShown = 0;
        printRows.forEach(function (row) {{
          row.hidden = !(phase === "all" || phase === row.dataset.phase);
          row.classList.toggle("done", row.querySelector("input").checked);
          if (!row.hidden) printsShown += 1;
        }});
        all("section.prints").forEach(function (section) {{ section.hidden = printsShown === 0; }});

        all("tr.group").forEach(function (header) {{
          var next = header.nextElementSibling, any = false;
          while (next && !next.classList.contains("group")) {{
            if (!next.hidden) any = true;
            next = next.nextElementSibling;
          }}
          header.hidden = !any;
        }});
        all("section.vendor:not(.prints)").forEach(function (section) {{
          var v = perVendor[section.id] || {{ total: 0, lines: 0 }};
          section.hidden = v.lines === 0;
          section.querySelector("[data-sub-kr]").textContent = kr(v.total);
          section.querySelector("[data-sub-eur]").textContent = eur(v.total);
        }});
        all("[data-card]").forEach(function (card) {{
          var v = perVendor[card.dataset.card] || {{ total: 0, lines: 0, left: 0, unpriced: 0 }};
          card.hidden = v.lines === 0;
          card.querySelector("[data-card-kr]").textContent = kr(v.total);
          card.querySelector("[data-card-eur]").textContent = eur(v.total);
          card.querySelector("[data-card-lines]").textContent =
            plural(v.lines) + (v.unpriced ? " · " + v.unpriced + " not priced" : "");
        }});
        all("[data-remaining]").forEach(function (el) {{
          var left = (perVendor[el.dataset.remaining] || {{ left: 0 }}).left;
          el.textContent = left === 0 ? "all bought" : left + " to buy";
        }});
        all("[data-phase-left]").forEach(function (el) {{
          var left = phaseLeft[el.dataset.phaseLeft] || 0;
          el.textContent = left === 0 ? "all bought" : left + " to buy";
        }});
        all("[data-phase-filter]").forEach(function (button) {{
          button.setAttribute("aria-pressed", String(button.dataset.phaseFilter === phase));
        }});

        var scope = phase === "all" ? "" : "Phase " + phase + " (" + LABELS[phase] + ") · ";
        document.getElementById("grand").textContent = kr(total);
        document.getElementById("grand-meta").textContent = scope + eur(total) + " · " + plural(lines) + " · before shipping";
        document.getElementById("remaining").textContent = kr(remaining);
      }}

      rows.forEach(function (row) {{
        var box = row.querySelector("input");
        if (row.dataset.purchased === "1") {{ box.checked = true; return; }}
        box.checked = !!saved[row.dataset.key];
        box.addEventListener("change", function () {{
          saved[row.dataset.key] = box.checked;
          try {{ localStorage.setItem(STORE, JSON.stringify(saved)); }} catch (e) {{}}
          update();
        }});
      }});
      printRows.forEach(function (row) {{
        var box = row.querySelector("input");
        box.checked = !!printed[row.dataset.print];
        box.addEventListener("change", function () {{
          printed[row.dataset.print] = box.checked;
          try {{ localStorage.setItem(PRINT_STORE, JSON.stringify(printed)); }} catch (e) {{}}
          update();
        }});
      }});
      all("[data-phase-filter]").forEach(function (button) {{
        button.addEventListener("click", function () {{
          var chosen = button.dataset.phaseFilter;
          phase = chosen === phase ? "all" : chosen;
          try {{ localStorage.setItem(PHASE_STORE, phase); }} catch (e) {{}}
          update();
        }});
      }});
      update();
    }})();
  </script>
</body>
</html>
"""
    BUILD.mkdir(exist_ok=True)
    (BUILD / "bom.html").write_text(page, encoding="utf-8")
    print(
        f"Wrote {BUILD / 'bom.html'} ({item_count} lines, {eur(grand_total)} = {dkk(grand_total * rate)}, "
        f"{unpriced_total} not priced)"
    )


if __name__ == "__main__":
    main()
