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
| Derived from registry | `id_contaminant` | `RHC-NNN` text | Registry | No | — | Yes, technical key |
| Compound name given in datasets | `id_name` | text | Glossary | No | — | Yes |
| Compound name for sorting | `id_sort_name` | text | Glossary | No | — | Yes |
| CG ID # | `id_legacy_cg` | positive integer | Glossary | No | — | No |
| Chemical formula | `id_chem_formula` | text | Glossary | No | — | Yes |
| a.k.a.s | `id_aka` | text[] split on ` | ` | Glossary | Unknown | — | Yes |
| CASRN | `id_casrn` | text[] split on ` | ` | Glossary | Unknown | — | Yes |
| InChIKey | `id_inchikey` | text[] split on ` | ` | Glossary | Unknown | — | Yes |
| Primary | `class_primary` | primary enum | Glossary | No | — | Yes |
| Secondary | `class_secondary` | secondary enum | Glossary | Unknown | — | Yes |
| Tertiary | `class_tertiary` | tertiary enum | Glossary | Unknown | — | Yes |
| Aromatic | `class_aromatic` | boolean | Glossary | Unknown | — | Yes |
| BTEXMN | `class_btexmn` | boolean | Glossary | Unknown | — | Yes |
| DBP | `class_dbp` | boolean | Glossary | Unknown | — | Yes |
| Known JP-5 component | `class_jp5_component` | boolean | Glossary | Unknown | — | Yes |
| PAH | `class_pah` | boolean | Glossary | Unknown | — | Yes |
| Pesticide | `class_pesticide` (also uses footnote D) | pesticide enum | Glossary | No | — | Yes |

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
| C | `chem_info_n_carbon` | nonnegative integer, integer range, or N/A | Glossary | No | atoms | Yes |
| N | `chem_info_n_nitrogen` | nonnegative integer, integer range, or N/A | Glossary | No | atoms | Yes |
| F | `chem_info_n_fluorine` | nonnegative integer, integer range, or N/A | Glossary | No | atoms | Yes |
| Cl | `chem_info_n_chlorine` | nonnegative integer, integer range, or N/A | Glossary | No | atoms | Yes |
| Br | `chem_info_n_bromine` | nonnegative integer, integer range, or N/A | Glossary | No | atoms | Yes |
| 1° alcohols | `chem_info_n_primary_alcohol` | nonnegative integer | Glossary | Unknown | groups | Yes |
| 2° alcohols | `chem_info_n_secondary_alcohol` | nonnegative integer | Glossary | Unknown | groups | Yes |
| 3° alcohols | `chem_info_n_tertiary_alcohol` | nonnegative integer | Glossary | Unknown | groups | Yes |
| Ethers | `chem_info_n_ether` | nonnegative integer | Glossary | Unknown | groups | Yes |
| Ketones | `chem_info_n_ketone` | nonnegative integer | Glossary | Unknown | groups | Yes |
| Aldehydes | `chem_info_n_aldehyde` | nonnegative integer | Glossary | Unknown | groups | Yes |
| Esters | `chem_info_n_ester` | nonnegative integer | Glossary | Unknown | groups | Yes |
| Epoxides | `chem_info_n_epoxide` | nonnegative integer | Glossary | Unknown | groups | Yes |
| Amines | `chem_info_n_amine` | nonnegative integer | Glossary | Unknown | groups | Yes |
| Halogenated | `chem_info_halogenated` | boolean or N/A | Glossary | Unknown | — | Yes |
| Saturated | `chem_info_saturated` | boolean or N/A | Glossary | Unknown | — | Yes |

`NA` is the only legacy spelling accepted for not applicable in the five atom
columns. Range text must contain two nonnegative integers separated by a
hyphen, with the lower value first. Formula-derived workbook cells are checked
against independently parsed canonical values later; formulas do not override
the documented type.

## Regulatory and convention fields

| Source header | Canonical field | Type | Owner | Null | Units | Public |
| --- | --- | --- | --- | --- | --- | --- |
| NPDWR MCLG (mg/L) | `reg_status_npdwr_mclg_mg_l` | nonnegative decimal | Glossary | Unknown | mg/L | Yes |
| NPDWR MCL (mg/L) | `reg_status_npdwr_mcl_mg_l` | nonnegative decimal | Glossary | Unknown | mg/L | Yes |
| NPDWR notes | `source_notes_npdwr_internal` | text | Glossary | Unknown | — | No |
| SMCL (mg/L) | `reg_status_smcl` | regulatory value | Glossary | Unknown | mg/L, or pH for `6.5-8.5` | Yes |
| CCL5 | `reg_status_ccl5` | boolean | Glossary | Unknown | — | Yes |
| HDOH MCL (mg/L) | `reg_status_hdoh_mcl_mg_l` | regulatory value | Glossary | Unknown | mg/L | Yes |
| HDOH more stringent | `reg_status_hdoh_more_stringent` | boolean | Glossary | Unknown | — | No |
| Montreal Protocol | `reg_status_montreal_protocol` | boolean | Glossary | Unknown | — | Yes |
| Stockholm Convention | `reg_status_stockholm_convention` | Stockholm enum | Glossary | Unknown | — | Yes |

Numeric regulatory values must be finite and nonnegative. Schema 1.0.0 also
allows the SMCL pH range `6.5-8.5` and HDOH action-level text `AL = 0.015` or
`AL = 1.3`; these normalize to typed range or action-level values rather than
ordinary strings. Stockholm values are `A` or `A (as industrial chemical), C
(as unintentional production)`.

## Narrative, footnote, and dataset fields

| Source header | Canonical field | Type | Owner | Null | Units | Public |
| --- | --- | --- | --- | --- | --- | --- |
| Sources | `source_notes_sources` | text | Glossary | Unknown | — | Yes |
| Notes | `source_notes_general` | text | Glossary | Unknown | — | Yes |
| Footnotes | `source_notes_footnote_ids` | ordered text[] | Glossary | Unknown | — | Yes |
| Immediate | `source_notes_dataset_immediate` | boolean | Glossary | Unknown | — | No |
| Flushing reports | `source_notes_dataset_flushing` | boolean | Glossary | Unknown | — | No |
| LTM plan | `source_notes_dataset_ltm` | boolean | Glossary | Unknown | — | No |
| EDWM plan | `source_notes_dataset_edwm` | boolean | Glossary | Unknown | — | No |
| SafeWaters data (old scrape) | `source_notes_safewaters_legacy` | boolean | Glossary | Unknown | — | No |
| SafeWaters data (checking 2026-06-22) | `source_notes_safewaters_review` | boolean or `!!!!` review marker | Glossary | Unknown | — | No |

The `!!!!` value is preserved only in private validation output as an unresolved
legacy review marker. It is never converted to a boolean or published.

## References and footnotes

| Source | Canonical field | Type | Owner | Null | Units | Public |
| --- | --- | --- | --- | --- | --- | --- |
| Registry/crosswalk | `references.id_contaminant` | `RHC-NNN` text | Registry | No | — | Yes, technical key |
| references `compound_name` | `references.refs_review_name` | text review label | References | No | — | No |
| references `source` | `references.refs_source` | text | References | No | — | Yes |
| references `link` | `references.refs_url` | absolute HTTP(S) URL | References | No | — | Yes |
| Footnotes `id` | `footnotes.source_notes_footnote_id` | footnote-ID text | Footnotes | No | — | Yes |
| Footnotes `text` | `footnotes.source_notes_footnote_text` | text | Footnotes | No | — | Yes |

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
