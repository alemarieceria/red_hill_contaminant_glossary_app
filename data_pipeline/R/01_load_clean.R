# data_pipeline/R/01_load_clean.R
# Load and Clean
# Reads glossary + references, validates against schema, exports clean CSVs

library(here)
library(readxl)
library(dplyr)
library(tidyr)
library(readr)

# 1. Define schema (source of truth) ----
schema <- tribble(
  ~source_file, ~col_name, ~standardized_col_name, ~data_type, ~owner, ~nullable, ~notes,
  "glossary", "Compound name given in datasets", "compound_name", "text", "Eamonn", FALSE, "Primary identifier",
  "glossary", "Compound name for sorting", "compound_name_sorted", "text", "Eamonn", FALSE, "Used for alphabetic order",
  "glossary", "a.k.a.s", "compound_name_akas", "text", "Alemarie", TRUE, "Pipe-separated synonyms",
  "glossary", "CG ID #", "cg_id", "integer", "Eamonn", FALSE, "Unique ID in this glossary",
  "glossary", "CASRN", "casrn", "text", "Alemarie", TRUE, "Chemical Abstracts Service Registry Number",
  "glossary", "InChIKey", "inchikey", "text", "Alemarie", TRUE, "IUPAC chemical identifier",
  "glossary", "Primary", "classification_primary", "text", "Eamonn", TRUE, "Main chemical classification",
  "glossary", "Secondary", "classification_secondary", "text", "Eamonn", TRUE, "Secondary classification",
  "glossary", "Tertiary", "classification_tertiary", "text", "Eamonn", TRUE, "Tertiary classification",
  "glossary", "Aromatic", "is_aromatic", "boolean", "Alemarie", TRUE, "Has aromatic ring?",
  "glossary", "BTEXMN", "is_btexmn", "boolean", "Eamonn", TRUE, "Benzene/Toluene/Ethylbenzene/Xylene/Methane/Naphthalene",
  "glossary", "DBP", "is_dbp", "boolean", "Eamonn", TRUE, "Disinfection byproduct",
  "glossary", "Known JP-5 component", "is_jp5_component", "boolean", "Eamonn", TRUE, "Found in jet fuel",
  "glossary", "PAH", "is_pah", "boolean", "Eamonn", TRUE, "Polycyclic aromatic hydrocarbon",
  "glossary", "Pesticide", "pesticide_flag", "text", "Alemarie", TRUE, "Pesticide classification (not boolean!)",
  "glossary", "Herbicide", "is_herbicide", "boolean", "Alemarie", TRUE, "Herbicide flag",
  "glossary", "C", "atom_count_c", "integer", "Alemarie", TRUE, "Carbon atom count",
  "glossary", "N", "atom_count_n", "integer", "Alemarie", TRUE, "Nitrogen atom count",
  "glossary", "F", "atom_count_f", "integer", "Alemarie", TRUE, "Fluorine atom count",
  "glossary", "Cl", "atom_count_cl", "integer", "Alemarie", TRUE, "Chlorine atom count",
  "glossary", "Br", "atom_count_br", "integer", "Alemarie", TRUE, "Bromine atom count",
  "glossary", "1° alcohols", "functional_group_primary_alcohol", "integer", "Eamonn", TRUE, "Primary alcohol group count",
  "glossary", "2° alcohols", "functional_group_secondary_alcohol", "integer", "Eamonn", TRUE, "Secondary alcohol group count",
  "glossary", "3° alcohols", "functional_group_tertiary_alcohol", "integer", "Eamonn", TRUE, "Tertiary alcohol group count",
  "glossary", "Ethers", "functional_group_ether", "integer", "Eamonn", TRUE, "Ether group count",
  "glossary", "Ketones", "functional_group_ketone", "integer", "Eamonn", TRUE, "Ketone group count",
  "glossary", "Aldehydes", "functional_group_aldehyde", "integer", "Eamonn", TRUE, "Aldehyde group count",
  "glossary", "Esters", "functional_group_ester", "integer", "Eamonn", TRUE, "Ester group count",
  "glossary", "Epoxides", "functional_group_epoxide", "integer", "Eamonn", TRUE, "Epoxide group count",
  "glossary", "Amines", "functional_group_amine", "integer", "Eamonn", TRUE, "Amine group count",
  "glossary", "Halogenated", "is_halogenated", "boolean", "Eamonn", TRUE, "Contains halogen (F/Cl/Br)?",
  "glossary", "Saturated", "is_saturated", "boolean", "Eamonn", TRUE, "Saturated hydrocarbon?",
  "glossary", "NPDWR", "has_npdwr", "boolean", "Eamonn", TRUE, "Regulated by EPA NPDWR?",
  "glossary", "NPDWR MCLG (mg/L)", "npdwr_mclg", "number", "Alemarie", TRUE, "Max contaminant level goal",
  "glossary", "NPDWR MCL (mg/L)", "npdwr_mcl", "number", "Alemarie", TRUE, "Max contaminant level",
  "glossary", "NPDWR notes", "npdwr_notes", "text", "Eamonn", TRUE, "Regulatory notes",
  "glossary", "SMCL (mg/L)", "smcl", "text", "Eamonn", TRUE, "Secondary max contaminant level",
  "glossary", "CCL5", "is_ccl5", "boolean", "Eamonn", TRUE, "Candidate contaminant list 5",
  "glossary", "HDOH", "has_hdoh", "boolean", "Eamonn", TRUE, "Regulated by Hawaii DOH?",
  "glossary", "HDOH MCL (mg/L)", "hdoh_mcl", "text", "Eamonn", TRUE, "Hawaii MCL value",
  "glossary", "HDOH more stringent", "hdoh_more_stringent", "boolean", "Eamonn", TRUE, "Stricter than EPA?",
  "glossary", "Montreal Protocol", "is_montreal_protocol", "boolean", "Alemarie", TRUE, "Ozone-depleting substance?",
  "glossary", "Stockholm Convention", "stockholm_convention_status", "text", "Eamonn", TRUE, "Persistent organic pollutant status",
  "glossary", "Sources", "sources", "text", "Dilsiich", TRUE, "Will be replaced by reference join",
  "glossary", "Notes", "notes", "text", "Eamonn", TRUE, "Public-facing compound description",
  "glossary", "Footnotes", "footnote_refs", "text", "Eamonn", TRUE, "Comma-separated footnote IDs (A, B, C)",
  "glossary", "Immediate", "in_immediate", "boolean", "Eamonn", TRUE, "Found in immediate dataset?",
  "glossary", "Flushing reports", "in_flushing_reports", "boolean", "Eamonn", TRUE, "Found in flushing reports?",
  "glossary", "LTM plan", "in_ltm_plan", "boolean", "Eamonn", TRUE, "Part of long-term monitoring?",
  "glossary", "EDWM plan", "in_edwm_plan", "boolean", "Eamonn", TRUE, "Part of extended drinking water monitoring?",
  "glossary", "SafeWaters data (old scrape)", "in_safewaters_old", "boolean", "Eamonn", TRUE, "Historical SafeWaters presence",
  "glossary", "SafeWaters data (checking 2026-06-22)", "safewaters_checking", "text", "Eamonn", TRUE, "Latest SafeWaters status",
  "reference", "compound", "compound_name", "text", "Eamonn", FALSE, "Compound name (joins to glossary)",
  "reference", "source", "source_type", "text", "Dilsiich", FALSE, "Source type (NPI, Wikipedia, Pubchem, etc.)",
  "reference", "link", "source_url", "text", "Dilsiich", FALSE, "Full URL to source",
)

cat("Schema loaded:", nrow(schema), "rows\n\n")

# 2. Load raw files ----
cat("Loading glossary...\n")
glossary_raw <- read_excel(
  here("data", "01_raw", "20260702_contaminant_glossary.xlsx"),
  sheet = "Glossary"
)

cat("Loading reference info...\n")
reference_raw <- read_excel(
  here("data", "01_raw", "20260701_ref_info.xlsx"),
  sheet = "Sheet1"
)

cat("Loading footnotes...\n")
footnotes_raw <- read_excel(
  here("data", "01_raw", "20260702_contaminant_glossary.xlsx"),
  sheet = "Footnotes"
)

# 3. Validation ----
cat("\n--- VALIDATION ---\n")
cat("Glossary:", nrow(glossary_raw), "rows,", ncol(glossary_raw), "columns\n")
cat("Reference:", nrow(reference_raw), "rows,", ncol(reference_raw), "columns\n")
cat("Footnotes:", nrow(footnotes_raw), "rows\n")

glossary_cols <- schema %>% filter(source_file == "glossary") %>% pull(col_name)
missing_cols <- setdiff(glossary_cols, names(glossary_raw))
if (length(missing_cols) > 0) {
  stop("Missing columns in glossary: ", paste(missing_cols, collapse = ", "))
}

reference_cols <- schema %>% filter(source_file == "reference") %>% pull(col_name)
missing_cols <- setdiff(reference_cols, names(reference_raw))
if (length(missing_cols) > 0) {
  stop("Missing columns in reference: ", paste(missing_cols, collapse = ", "))
}

cat("All expected columns present\n")

# 4. Rename columns ----
cat("\n--- RENAMING COLUMNS ---\n")

glossary_schema_map <- schema %>%
  filter(source_file == "glossary") %>%
  select(col_name, standardized_col_name, data_type)  

glossary_renamed <- glossary_raw %>%
  rename(all_of(setNames(glossary_schema_map$col_name, glossary_schema_map$standardized_col_name)))

reference_schema_map <- schema %>%
  filter(source_file == "reference") %>%
  select(col_name, standardized_col_name, data_type) 

reference_renamed <- reference_raw %>%
  rename(all_of(setNames(reference_schema_map$col_name, reference_schema_map$standardized_col_name)))

cat("Columns renamed\n")

# 5. Convert data types ----
cat("\n--- CONVERTING DATA TYPES ---\n")

convert_types <- function(df, schema_map) {
  for (i in seq_len(nrow(schema_map))) {
    col <- schema_map$standardized_col_name[i]
    type <- schema_map$data_type[i]

    if (col %in% names(df)) {
      if (type == "integer") {
        df[[col]] <- as.integer(df[[col]])
      } else if (type == "number") {
        df[[col]] <- as.numeric(df[[col]])
      } else if (type == "boolean") {
        df[[col]] <- as.logical(df[[col]])
      } else if (type == "text") {
        df[[col]] <- as.character(df[[col]])
      }
    }
  }
  df
}

glossary_clean <- convert_types(glossary_renamed, glossary_schema_map)
reference_clean <- convert_types(reference_renamed, reference_schema_map)
footnotes_clean <- footnotes_raw

cat("Data types converted\n")

# 6. Export clean CSVs ----
cat("\n--- EXPORTING ---\n")

write_csv(glossary_clean, here("data", "02_interim", "glossary_clean.csv"))
cat("Wrote glossary_clean.csv\n")

write_csv(reference_clean, here("data", "02_interim", "references_clean.csv"))
cat("Wrote references_clean.csv\n")

write_csv(footnotes_clean, here("data", "02_interim", "footnotes_clean.csv"))
cat("Wrote footnotes_clean.csv\n")

cat("\nLoad and clean complete.\n")
