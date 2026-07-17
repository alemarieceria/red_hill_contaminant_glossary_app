# Canonical Data Schema 1.0.0

This document defines the normalized fields produced from the two incoming
workbooks. "Owner" identifies where a value's meaning originates: Registry,
Glossary, References, Footnotes, or Pipeline. Public fields form the explicit
website-export allowlist; private fields may appear in validation or audit
outputs but never in public JSON.

## Shared type rules

- `text` is Unicode text with no leading or trailing whitespace.
- `text[]` is an ordered list with blank entries and duplicates removed only
  when the source-specific parsing rule explicitly permits that operation.
- `integer` and `decimal` are numbers, not formatted strings.
- `boolean` is `true` or `false`; blank remains null.
- `integer range` is a closed inclusive pair such as `1 - 3`.
- `regulatory value` is a decimal in the stated unit, a documented numeric
  range, or a documented action-level value. Raw text is retained in reports.
- "Unknown" means a blank source cell becomes null.
- "N/A" means an explicit not-applicable state is allowed.

## Contaminant identity and classification

| Source header | Canonical field | Type | Owner | Null | Units | Public |
| --- | --- | --- | --- | --- | --- | --- |
| Derived from registry | `contaminant_id` | `RHC-NNN` text | Registry | No | — | Yes |
| Compound name given in datasets | `compound_name` | text | Glossary | No | — | Yes |
| Compound name for sorting | `sort_name` | text | Glossary | No | — | Yes |
| CG ID # | `legacy_cg_id` | positive integer | Glossary | No | — | No |
| Chemical formula | `chemical_formula` | text | Glossary | No | — | Yes |
| a.k.a.s | `aliases` | text[] split on ` | ` | Glossary | Unknown | — | Yes |
| CASRN | `casrns` | text[] split on ` | ` | Glossary | Unknown | — | Yes |
| InChIKey | `inchikeys` | text[] split on ` | ` | Glossary | Unknown | — | Yes |
| Primary | `primary_class` | primary enum | Glossary | No | — | Yes |
| Secondary | `secondary_class` | secondary enum | Glossary | Unknown | — | Yes |
| Tertiary | `tertiary_class` | tertiary enum | Glossary | Unknown | — | Yes |
| Aromatic | `is_aromatic` | boolean | Glossary | Unknown | — | Yes |
| BTEXMN | `is_btexmn` | boolean | Glossary | Unknown | — | Yes |
| DBP | `is_disinfection_byproduct` | boolean | Glossary | Unknown | — | Yes |
| Known JP-5 component | `is_known_jp5_component` | boolean | Glossary | Unknown | — | Yes |
| PAH | `is_pah` | boolean | Glossary | Unknown | — | Yes |
| Pesticide | `pesticide_status` (also uses footnote D) | pesticide enum | Glossary | No | — | Yes |

Allowed primary values are `Aliphatic`, `Aromatic`, `Glycol ether`, `Inorganic
compound`, `Mixture`, `Non-compound measurement`, and `Pure element`.

Allowed secondary values are `Alkane`, `Alkene`, `Benzene`, `Metal`,
`Metalloid`, `Method-defined analytical mixture`, `Mixture of pure compounds`,
`Nonmetal`, `PAH`, and `Triazine`.

Allowed tertiary values for schema 1.0.0 are `Alkali earth metal`, `Alkaline
earth metal`, `Alkenylated`, `Alkylated`, `Anthracene`, `Branched`, `Chalcogen
(oxygen group)`, `Cyclic`, `Derivatized`, `Halogen`, `Halogenated`, `Linear`,
`Naphthalene`, `Naphthalene, alkylated`, `Pnictogen (nitrogen group)`,
`Post-transition metal, group 13`, `Post-transition metal, group 14`, and
`Transition metal (group 6)`, `Transition metal (group 7)`, `Transition metal
(group 8)`, `Transition metal (group 10)`, `Transition metal (group 11)`, or
`Transition metal (group 12)`. Both current earth-metal spellings are
preserved in 1.0.0; consolidating them is a data change, not silent
normalization.

The pesticide enum is `pesticide`, `pesticide_product_contaminant`,
`not_pesticide`, `unknown`, or `not_applicable`.

## Composition and functional groups

| Source header | Canonical field | Type | Owner | Null | Units | Public |
| --- | --- | --- | --- | --- | --- | --- |
| C | `carbon_count` | nonnegative integer, integer range, or N/A | Glossary | No | atoms | Yes |
| N | `nitrogen_count` | nonnegative integer, integer range, or N/A | Glossary | No | atoms | Yes |
| F | `fluorine_count` | nonnegative integer, integer range, or N/A | Glossary | No | atoms | Yes |
| Cl | `chlorine_count` | nonnegative integer, integer range, or N/A | Glossary | No | atoms | Yes |
| Br | `bromine_count` | nonnegative integer, integer range, or N/A | Glossary | No | atoms | Yes |
| 1° alcohols | `primary_alcohol_count` | nonnegative integer | Glossary | Unknown | groups | Yes |
| 2° alcohols | `secondary_alcohol_count` | nonnegative integer | Glossary | Unknown | groups | Yes |
| 3° alcohols | `tertiary_alcohol_count` | nonnegative integer | Glossary | Unknown | groups | Yes |
| Ethers | `ether_count` | nonnegative integer | Glossary | Unknown | groups | Yes |
| Ketones | `ketone_count` | nonnegative integer | Glossary | Unknown | groups | Yes |
| Aldehydes | `aldehyde_count` | nonnegative integer | Glossary | Unknown | groups | Yes |
| Esters | `ester_count` | nonnegative integer | Glossary | Unknown | groups | Yes |
| Epoxides | `epoxide_count` | nonnegative integer | Glossary | Unknown | groups | Yes |
| Amines | `amine_count` | nonnegative integer | Glossary | Unknown | groups | Yes |
| Halogenated | `is_halogenated` | boolean or N/A | Glossary | Unknown | — | Yes |
| Saturated | `is_saturated` | boolean or N/A | Glossary | Unknown | — | Yes |

`NA` is the only legacy spelling accepted for not applicable in the five atom
columns. Range text must contain two nonnegative integers separated by a
hyphen, with the lower value first. Formula-derived workbook cells are checked
against independently parsed canonical values later; formulas do not override
the documented type.

## Regulatory and convention fields

| Source header | Canonical field | Type | Owner | Null | Units | Public |
| --- | --- | --- | --- | --- | --- | --- |
| NPDWR MCLG (mg/L) | `npdwr_mclg` | nonnegative decimal | Glossary | Unknown | mg/L | Yes |
| NPDWR MCL (mg/L) | `npdwr_mcl` | nonnegative decimal | Glossary | Unknown | mg/L | Yes |
| NPDWR notes | `npdwr_notes` | text | Glossary | Unknown | — | Yes |
| SMCL (mg/L) | `smcl` | regulatory value | Glossary | Unknown | mg/L, or pH for `6.5-8.5` | Yes |
| CCL5 | `is_ccl5` | boolean | Glossary | Unknown | — | Yes |
| HDOH MCL (mg/L) | `hdoh_mcl` | regulatory value | Glossary | Unknown | mg/L | Yes |
| HDOH more stringent | `is_hdoh_more_stringent` | boolean | Glossary | Unknown | — | Yes |
| Montreal Protocol | `is_montreal_protocol` | boolean | Glossary | Unknown | — | Yes |
| Stockholm Convention | `stockholm_listing` | Stockholm enum | Glossary | Unknown | — | Yes |

Numeric regulatory values must be finite and nonnegative. Schema 1.0.0 also
allows the SMCL pH range `6.5-8.5` and HDOH action-level text `AL = 0.015` or
`AL = 1.3`; these normalize to typed range or action-level values rather than
ordinary strings. Stockholm values are `A` or `A (as industrial chemical), C
(as unintentional production)`.

## Narrative, footnote, and dataset fields

| Source header | Canonical field | Type | Owner | Null | Units | Public |
| --- | --- | --- | --- | --- | --- | --- |
| Sources | `source_description` | text | Glossary | Unknown | — | Yes |
| Notes | `internal_notes` | text | Glossary | Unknown | — | No |
| Footnotes | `footnote_ids` | ordered text[] | Glossary | Unknown | — | Yes |
| Immediate | `in_immediate_dataset` | boolean | Glossary | Unknown | — | Yes |
| Flushing reports | `in_flushing_reports` | boolean | Glossary | Unknown | — | Yes |
| LTM plan | `in_ltm_plan` | boolean | Glossary | Unknown | — | Yes |
| EDWM plan | `in_edwm_plan` | boolean | Glossary | Unknown | — | Yes |
| SafeWaters data (old scrape) | `in_safewaters_legacy` | boolean | Glossary | Unknown | — | No |
| SafeWaters data (checking 2026-06-22) | `safewaters_review_state` | boolean or `!!!!` review marker | Glossary | Unknown | — | No |

The `!!!!` value is preserved only in private validation output as an unresolved
legacy review marker. It is never converted to a boolean or published.

## References and footnotes

| Source | Canonical field | Type | Owner | Null | Units | Public |
| --- | --- | --- | --- | --- | --- | --- |
| Registry/crosswalk | `references.contaminant_id` | `RHC-NNN` text | Registry | No | — | Yes |
| references `compound_name` | `references.compound_name` | text review label | References | No | — | Yes |
| references `source` | `references.source` | text | References | No | — | Yes |
| references `link` | `references.link` | absolute HTTP(S) URL | References | No | — | Yes |
| Footnotes `id` | `footnotes.footnote_id` | footnote-ID text | Footnotes | No | — | Yes |
| Footnotes `text` | `footnotes.text` | text | Footnotes | No | — | Yes |

Metadata keys and source file hashes are private release-manifest fields. They
may appear in `release.json` only as release provenance, not as contaminant
attributes.

## Source-header policy

Schema 1.0.0 expects the 50 named glossary headers listed above, the Footnotes
headers `id` and `text`, and reference headers `compound_name`, `source`, and
`link` before a derived ID is attached. Column order is not semantic, but names
must match exactly. Empty formatted columns outside the declared data range are
ignored. Unknown named columns default to private and block publication until a
supported schema version documents them.
