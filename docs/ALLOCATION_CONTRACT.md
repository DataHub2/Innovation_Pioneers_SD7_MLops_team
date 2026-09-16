# Allokeringskontrakt — algoritmkomponenten (v0.1)

Detta dokument är gränssnittet mellan **algoritmen** och allt annat (dashboard, datapipeline,
hårdvara, pitch). Allt under "Vad som INTE ingår" är andras grenar.

Antaganden som ännu inte bekräftats är markerade `[ANTAGANDE]`.

---

## 1. Ansvar och form

Komponenten svarar på **en enda fråga per tidssteg**:

> Givet den energi som finns tillgänglig just nu, vilka fastigheter ska få hur mycket,
> och varför?

Den är en **ren funktion**:

```python
def allocate(req: AllocRequest, policy: Policy, config: Config) -> AllocResult: ...
```

Krav på formen:

- **Ingen I/O inuti.** Ingen fil, inget nätverk, ingen databas.
- **Ingen klocka.** Tiden kommer in som parameter (`req.t_start`). Aldrig `datetime.now()`.
- **Inget tillstånd inuti.** Credits och historik kommer in, ändringar går ut.
  Vem som helst kan anropa den, i vilken ordning som helst.
- **Deterministisk.** Samma input ger exakt samma output, varje gång.
- **Inga tunga beroenden.** Helst stdlib only — den ska kunna köra offline på en
  Raspberry Pi i en barangay. `numpy` endast om teamet säger att det är ok.

Detta gör komponenten testbar utan en simulator, och det är det som ger
*feasibility*-poängen.

---

## 2. Indata

```python
@dataclass(frozen=True)
class AllocRequest:
    cycle_id: str
    t_start: str                  # ISO 8601 MED tidszon, t.ex. "2026-03-14T18:00:00+08:00"
    duration_s: int               # längd på tidssteget
    available_energy_kwh: float   # vad som finns att fördela denna cykel
    available_power_kw: float     # effekttak just nu
    storage_soc_kwh: float        # batteri, 0.0 om inget batteri [ANTAGANDE: batteri finns]
    is_islanded: bool             # true = ingen import möjlig [ANTAGANDE]
    grid_import_limit_kw: float   # 0.0 om isolerad
    properties: tuple[Property, ...]
    credits: dict[str, float]     # property_id -> saldo
```

```python
@dataclass(frozen=True)
class Property:
    id: str
    category: Category
    occupants: int
    vulnerability_flags: frozenset[str]   # "elderly", "dialysis", "cold_chain", "pwd"
    lifeline_declared_kwh: float          # minimibehov, satt av byn/operatören
    demand_kwh: float                     # vad fastigheten vill ha denna cykel
    registered_productive_kw: float       # deklarerad produktiv användning
    historical_kwh_per_day: float         # för anomalidetektion, kan vara 0.0
```

```python
class Category(Enum):
    CLINIC = "clinic"          # vårdcentral, kylkedja
    WATER = "water"            # vattenpump
    SCHOOL = "school"
    PRODUCTIVE = "productive"  # ismaskin, sari-sari-butik
    HOUSEHOLD = "household"
    COMMUNITY = "community"    # gatlyse, laddstation
```

---

## 3. Utdata

```python
@dataclass(frozen=True)
class Alloc:
    property_id: str
    granted_energy_kwh: float
    granted_power_kw: float
    state: Literal["granted", "partial", "deferred", "denied"]
    reason_code: ReasonCode
    reason_text: str                      # människoläsbar, till dashboarden
    score_breakdown: dict[str, float]     # hur poängen räknades fram
```

```python
@dataclass(frozen=True)
class AllocResult:
    cycle_id: str
    alloc: dict[str, Alloc]
    credits_delta: dict[str, float]
    unserved_critical_kwh: float
    unserved_total_kwh: float
    warnings: tuple[str, ...]      # t.ex. "starvation: prop_14 nekad 6 cykler i rad"
    meta: dict[str, object]        # policy_version, config_hash, compute_ms
```

### Orsakskoder (exakt en primär per beslut)

| Kod | Betyder |
|---|---|
| `LIFELINE_FLOOR` | Fick sin miniminivå, prioriterad före allt annat |
| `CRITICALITY_ORDER` | Fick utdelning enligt kritikalitetsvikt |
| `CREDIT_REDEMPTION` | Löste in intjänade credits i ett överskottsläge |
| `PARTIAL_BUDGET` | Fick delar av sin efterfrågan, budgeten tog slut |
| `BUDGET_EXHAUSTED` | Nekad helt, ingen energi kvar i denna cykel |
| `SUPPLY_UNAVAILABLE` | Nekad, det finns ingen effekt alls att ge |
| `VOLUNTARY_CURTAILMENT` | Fastigheten stängde av frivilligt, tjänade credits |
| `OVER_DECLARED` | Begärd mängd avvisad (över tak / misstänkt felförbrukning) |
| `DEFERRED_TO_STORAGE` | Uppskjuten för att spara batteri till senare kritisk last |

**Poängformel (för `score_breakdown`):**

```
poäng = kategori_vikt
      × (1 + sårbarhetsbonus)
      × tidskänslighetsfaktor(timme, kategori)
      × lagernivåfaktor
```

Vikterna är **konfiguration**, aldrig hårdkodade. Algoritmen har ingen egen åsikt
om vem som är viktigast — byn har det.

---

## 4. Invariants — får aldrig brytas

Detta är listan testsviten ska bevisa. Den är också er *creativity*- och
*feasibility*-evidens: "här är vad som matematiskt inte kan hända".

| # | Invariant |
|---|---|
| I1 | `sum(granted_energy_kwh) <= available_energy_kwh * (1 - safety_margin)` |
| I2 | `sum(granted_power_kw) <= available_power_kw` (+ urladdning endast om batteri tillåts) |
| I3 | Om `sum(lifeline_declared) <= budget` så får **varje** fastighet sin lifeline |
| I4 | `credits >= 0` alltid; credits skapas bara av uttryckliga beslut |
| I5 | Deterministisk: samma input → bitvis samma output, även vid exakt lika poäng |
| I6 | Varje fastighet får exakt en `reason_code` |
| I7 | `granted_energy_kwh <= demand_kwh` (ingen får mer än den bett om) |
| I8 | Ingen fastighet nekas i fler än `starvation_cycles` cykler medan andra får överskott |
| I9 | `sum(credits_delta)` är konsistent med bokföringen (ingen credits ur tomma luften) |
| I10 | Ingen `NaN`, ingen negativ tilldelning, ingen tyst avrundning som bryter I1 |

Tie-break (vid exakt lika poäng) måste vara en **uttalad regel** (t.ex. lägst
`property_id`), inte ett resultat av dict-ordning i Python. Annars faller I5.

---

## 5. Konfiguration

```yaml
# config.yaml — redigeras av byn/operatören, inte av utvecklaren
category_weights:
  clinic: 10.0
  water: 6.0
  school: 3.0
  productive: 2.0
  household: 1.0
  community: 1.5
vulnerability_bonus:
  dialysis: 2.0
  cold_chain: 1.5
  elderly: 1.3
  pwd: 1.3
lifeline_kwh_per_capita: 0.15
credit_earn_per_kwh_curtailed: 1.0
credit_redeem_threshold: 5.0
safety_margin: 0.02
max_share_per_property: 0.25
starvation_cycles: 6
tie_break: "property_id_asc"
```

---

## 6. Stressmatris

Varje rad ska bli ett automatiserat test. Kolumnen "Förväntat" är det som gör
att ni kan säga "det funkar" i stället för "det verkar funka".

| # | Scenario | Vad det provocerar | Förväntat / godkänt |
|---|---|---|---|
| S1 | Tillgång = 0, allt annat normalt | Division med noll, tomma listor | Alla `SUPPLY_UNAVAILABLE`, inga undantag, >= 0 tilldelning |
| S2 | Efterfrågan 3× tillgången | Överteckning | I1 håller, alla får lifeline om I3 gäller, inga negativa tal |
| S3 | 40 % av fastigheterna ansluter mitt i en cykel | State-läckage | Inga undantag, nya fastigheter behandlas som `deferred` |
| S4 | Ett hushåll begär 20× sitt historiska medelvärde | Free-rider / frosseri | `OVER_DECLARED`, hushållet får max sin lifeline + andel |
| S5 | Alla 60 fastigheter får exakt lika poäng | Tie-break | I5 håller, identisk output över 100 körningar |
| S6 | Konfig med vikt 0, negativ vikt, saknad kategori | Skräpindata | Tydligt felmeddelande i `warnings`, ingen krasch |
| S7 | Batteri tomt klockan 18:00 med klinik som behöver kylkedja | Tidsmässig prioritering | Klinikens last går före hushåll, `DEFERRED_TO_STORAGE` används |
| S8 | Fyra dagars molnighet i rad | Uttömning över tid | Ingen fastighet under lifeline i mer än `starvation_cycles` |
| S9 | Tidsstämplar över midnatt och över tidszonsbyte | Tidslogik | Dygnsräkning och credits rullar korrekt |
| S10 | 30 dagar à 15-minuterssteg utan avbrott | Långsam drift i bokföringen | I4 och I9 håller hela vägen, credits varken försvinner eller blåser upp |
| S11 | 500 fastigheter × 1440 steg | Prestanda | p99 < 200 ms per anrop; 60 fastigheter < 50 ms |
| S12 | Fastighet försvinner / dubblerat id | Robusthet | Ingen krasch, varning, dokumenterat beteende |
| S13 | Flyttal: tilldelning 0.0000001 kWh över budgeten | Avrundning | I1 håller exakt, ingen tyst övertrassering |

**Verktyg:** vanliga `pytest`-fall för scenarierna ovan, plus
`hypothesis` (property-based testing) för att slumpa fram inputs och bevisa
I1–I10. Property-based testing är billigt och ser mycket seriöst ut i en
redovisning — det är bokstavligen "vi sökte efter motbevis och hittade inga".

---

## 7. Vad som INTE ingår (andras grenar)

- Datainsamling, fastighetsregister, mätvärden → datagrenen
- Dashboard, visualisering, UI → UI-grenen (konsumerar JSON)
- Hårdvara: reläer, mätare, invertrar → hårdvarugrenen
- Väderprognoser → datagrenen (algoritmen tar emot en färdig siffra)
- Pitch, deck, marknadsanalys, val av land/region → presentationsgrenen

Gränsen är: **algoritmen tar emot siffror och lämnar ifrån sig siffror + orsaker.**

---

## 8. Antaganden att bekräfta

1. Isolerad microgrid eller nätansluten? (styr om export alls är möjlig)
2. Finns batteri? Hur stort?
3. Tidssteg: minut, kvart eller timme?
4. Antal fastigheter i demo:n?
5. Allokeringsfilosofi: kvotering / pris / hybrid? (hybrid är default i utkastet)
6. Är `numpy` tillåtet, eller ska det vara stdlib only?
