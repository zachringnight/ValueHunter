#!/usr/bin/env Rscript

suppressPackageStartupMessages({
  library(cfbfastR)
  library(arrow)
})

# --- Helper: fail fast if API key missing ---
key <- Sys.getenv("CFBD_API_KEY", unset = NA)
if (is.na(key) || nchar(key) == 0) {
  message("[cfbfastR] Missing CFBD_API_KEY environment variable.\n",
          "Set it in your environment locally or as a GitHub Actions repository secret named CFBD_API_KEY.")
  quit(status = 1)
}

# --- Simple CLI arg parsing ---
args <- commandArgs(trailingOnly = TRUE)
season <- NA
season_type <- "regular"

if (length(args) > 0) {
  for (i in seq(1, length(args), by = 2)) {
    flag <- args[i]
    val <- ifelse(i + 1 <= length(args), args[i + 1], NA)
    if (flag %in% c("--season", "-s")) season <- as.integer(val)
    if (flag %in% c("--season_type", "-t")) season_type <- as.character(val)
  }
}

if (is.na(season)) {
  season <- as.integer(format(Sys.Date(), "%Y"))
}
if (!season_type %in% c("regular", "postseason")) {
  season_type <- "regular"
}

# --- Create output dir ---
out_dir <- file.path("data", "cfbd")
if (!dir.exists(out_dir)) dir.create(out_dir, recursive = TRUE, showWarnings = FALSE)

message(sprintf("[cfbfastR] Fetching data for season=%s, season_type=%s", season, season_type))

# --- Fetch games ---
# Using cfbd_ functions which wrap CollegeFootballData API
# Reference: https://cfbfastR.sportsdataverse.org/

games <- tryCatch({
  cfbd_games(year = season, season_type = season_type)
}, error = function(e) {
  message("[cfbfastR] Error fetching games: ", conditionMessage(e))
  quit(status = 2)
})

# --- Fetch team info (reference table) ---
team_info <- tryCatch({
  cfbd_team_info()
}, error = function(e) {
  message("[cfbfastR] Warning: could not fetch team info: ", conditionMessage(e))
  NULL
})

# --- Write outputs ---
prefix <- file.path(out_dir, sprintf("%s_%s", season, season_type))

# Parquet
arrow::write_parquet(games, paste0(prefix, "_games.parquet"))
if (!is.null(team_info)) arrow::write_parquet(team_info, file.path(out_dir, "team_info.parquet"))

# CSV (optional, larger) — helpful for Python workflows
utils::write.csv(games, paste0(prefix, "_games.csv"), row.names = FALSE)
if (!is.null(team_info)) utils::write.csv(team_info, file.path(out_dir, "team_info.csv"), row.names = FALSE)

message("[cfbfastR] Done. Files written to ", normalizePath(out_dir))
