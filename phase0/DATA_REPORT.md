# Phase 0 data report: Nazi-era provenance (NGA + AIC + ALIU Red Flag list)

Spike done 2026-10-07, about 90 minutes. Scripts are in `phase0/scripts/`, outputs in `phase0/data/`. Full console output: `data/analyze_output.txt`.

## Numbers

| | NGA | AIC |
|---|---|---|
| Objects in source | 146,099 (`objects.csv`) | 133,120 (API, all artworks) |
| With non-empty provenance | 81,540 | 35,124 (all fetched via API) |
| Provenance mentions a year 1933–1945 (`\b19(3[3-9]\|4[0-5])\b`) | **11,180** | **12,656** |
| ...distinct texts (many prints and portfolios share boilerplate) | 4,324 | 2,590 |
| Median length, all / distinct (chars) | 258 / 330 | 148 / 270 |
| Texts with ≥1 Red Flag surname, **naive** (case-insensitive, whole word) | 8,383 (75%) | 4,576 (36%) |
| ...**cased** (capitalised surname, minus about 70 stop-keys) | 3,855 (34%) | 1,057 (8.4%) |
| ...**fullname** (list forename or initial within 2 tokens before surname) | **565 (5.1%)**, 472 distinct | **218 (1.7%)**, 149 distinct |
| Eyeballed precision on 20 random matches: correct entity / actual 1933–45 event | cased ≈ 9/19 / 1/19; fullname ≈ 19/20 / 8/20 | cased ≈ 5–8/20 / 2/20; fullname ≈ 19/20 / 5/20 |

**Top 15 names in the naive tier.** These are mostly noise.
- NGA: may 3012, kress 2407, lugt 2069, hermann 1908, dreyfus 1906, john 588, knoedler 525, thomas 377, martin 278, baron 224, goldschmidt 216, contini bonacossi 213, drouot 186, herbert 145, wildenstein 134.
- AIC: martin 1672, may 1332, john 483, frank 337, lugt 317, nathan 290, baron 190, drouot 154, durand-ruel 97, wildenstein 84, thomas 79, knoedler 64, bernard 61, simon 50, jacquin 49.

**Top names in the fullname tier.**
- NGA: Contini Bonacossi 208, Drouot 185, Bignou 37, Graupe 36, Cassirer 17, Friedlaender 16, Buchholz 15, Boehler 14, Mayer 9, Charpentier 9, Carlhian 8, Matthiesen 4, Morandotti 4, Wendland 4, Sambon 4.
- AIC: Drouot 151, Boehler 13, Cassirer 10, Mayer 7, Wendland 6, Nathan 5, Friedlaender 4, Goudstikker 4, Dubourg 4, Schoeller 3, Fabiani 3, Bignou 2, Haberstock 2, Sambon 2, de Boer 2.

**Red Flag names found in both collections:** 143 naive, 110 cased, **22 fullname**: Drouot, Bignou, Graupe, Boehler, Cassirer, Friedlaender, Mayer, Charpentier, Wendland, Nathan, Schoeller, Sambon, Dubourg, Goudstikker, Rochlitz, Fabiani, Planiscig, Haberstock, Trévise, Reber, Goldschmidt, Boehmer.

**The same work in both collections:** none found. The 71 title+artist candidates are generic titles ("Cup", "The Nativity") or different impressions of the same print. Dealers do link the collections, though: Wendland, Rochlitz, Haberstock and Boehler all appear in both, and so does the Paul Rosenberg / ERR / Jeu de Paume chain.

**Red Flag list**
- 1,100 entries after dropping verbatim duplicates. That gives 1,019 distinct match keys across 10 countries (DE 501, FR 330, NL 113, CH 61, IT 34, BE 28, ES 17, PT 9, SE 4, LU 3). Firms and auction houses are included.
- Most machine-readable copy: the **HTML text** transcription at lootedart.com/MVI3RM469661 (457 KB page). It cites NARA as its source. I parsed it with `red_flag_parse.py` into `data/red_flag_names.csv` (name, match_key, country, notes, how_obtained).
- The same site has a **text PDF** of the ALIU *Names Index* (`aliu_index_0712.pdf`, 374 KB, OpenOffice-generated, `pdftotext` works). The openartdata.org mirror is also plain HTML.
- The originals are **scanned microfilm** (NARA M1782 roll 1 / M1944 roll 22, also on Fold3). Wikipedia says dfs.ny.gov has photocopy PDFs. I did not download those.

**Licences**
- NGA: CC0 (README).
- AIC: CC0 for all fields except `description`, which is CC-BY (stated in the API response; we don't use `description`).
- ALIU 1946 report: a US federal government work, so public domain in the US.
- The lootedart.com transcription is under "© website copyright Central Registry". The facts are not copyrightable, but we should cite it, or re-derive from the NARA scan.

## Defects that matter for the demo
- **Surname matching is nearly worthless on its own.** The list contains months and given names ("May", "Martin", "John", "Thomas", "Hermann"). It contains homonyms: Samuel H. Kress vs ERR photographer Karl Kress, Gustave Dreyfus vs a Zurich dealer, Philip Hofer vs W. A. Hofer, Nathan Cummings vs Fritz Nathan. Lugt is cited as a catalogue ("Lugt 1375"), not as an owner.
- **The list is "persons of interest", not perpetrators.** It also names victims (Goudstikker, Bernheim-Jeune, Wildenstein) and mainstream firms (Knoedler, Durand-Ruel, Hôtel Drouot). A hit is a lead, not a verdict.
- **Right person, wrong time or role.** About 60% of correct-entity full-name hits are events outside 1933–45 (a Drouot sale in 1868, Carlhian in 1922), or citations of an author (Max J. Friedländer, August L. Mayer as art historians). The text also mentions a 1933–45 year somewhere else.
- **Spelling variants.**
  - Muhlmann / Mühlmann / Muehlmann: NGA writes "K. Muhlmann", which the list key does not match.
  - Böhler 49 / Boehler 8 / Bohler 2.
  - Göring / Goering.
  - "E.R.R." / "ERR" / "Einsatzstab".
  - Umlaut folding adds only about 2% more hits, because the list is already ASCII (ue/oe).
- **Key events hide in footnotes.** NGA puts them in footnotes (3,641 of 11,180 texts have `[n]` notes). In NGA 52157 the ERR confiscation and the Göring selection are only in note [1], not in the ownership chain. AIC puts sources inline in `[...]`.
- **Missing or uncertain dates and principals.**
  - 552 NGA / 2,449 AIC texts carry by/c./before/after/? qualifiers.
  - The year regex misses ranges like "1930s" (31 / 3 texts) and "1932–1946".
  - Heinrich Hoffmann (subject of DIR 1) is **not** in the transcribed Red Flag list, and Göring and Hitler are not either. The list is intermediaries only. Check it against the scan.
- **Language.** English dominates. There are some German/French/Dutch fragments and archival titles (63 / 22 / 5 NGA texts), for example the German title of the Göring list. No OCR problems in the museum data (0 mojibake). The list transcription has parsing seams: entries split across HTML paragraphs, a duplicated entry, stray script tags. I fixed these heuristically.
- **AIC API quirk.** `from + limit` must be ≤ 1000. I worked around it by bisecting `id` ranges (about 420 requests at 1/s). The bulk dump (130 MB `.tar.bz2`) is the alternative.

## Bonus: ground truth exists
Every one of NGA's 11,180 texts from 1933–45 also has structured `previous owner` rows in `objects_constituents.csv`. 10,292 of them have an owner interval that overlaps 1933–45. That is ready-made gold data for scoring an LLM's ownership-chain extraction.

## Demo test questions (IDs are real)
1. **NGA 52157**, Boudin, *On the Jetty*. The main chain looks clean (Lévy de Benzion → Drouot 1949 → … → NGA). Note [1]: "confiscated by the Nazi Einsatzstab Reichsleiter Rosenberg (ERR) from the Levy de Benzion collection … selected by Hermann Goering on 25 November 1942 from the Jeu de Paume (OSS Consolidated Interrogation Report #2…)". *Q: Was this work in Nazi hands, and which ALIU report documents it?* This tests footnote reading and linking to the ALIU reports.
2. **AIC 191565**, Matisse, *Girl in Yellow and Blue with Guitar*. "Paul Rosenberg… confiscated by the ERR… transferred to Jeu de Paume, Sept. 5, 1941; exchanged with Gustav Rochlitz… on behalf of Hermann Göring… from Nov. 27, 1942 [ALIU CIR No. 1, p. 43]". *Q: Which Red Flag dealer handled it and in what kind of transaction?* Rochlitz has a Red Flag entry and his own DIR No. 4.
3. **NGA 73852**, Dürer, *Male Nude Holding a Mirror*. "German troops took L'vov in June 1941, and in July K. Muhlmann, the German special representative for works of art, took the Lubomirski Dürer drawings to Adolf Hitler in Berlin… discovered in a salt mine near Salzburg". *Q: Who removed it, and is he on the Red Flag list?* This tests the variant "Muhlmann" vs list "Muehlmann, Kajetan" and resolving the initial "K.".
4. Reserve: **NGA 53141**, Teniers. The chain goes Goudstikker firm (1941) → "Professor Hoffmann, Munich". This needs the resolution "Professor Hoffmann" = Heinrich Hoffmann, who is absent from the list.

## Verdict: **GO WITH CHANGES**
The data is sufficient, openly licensed, and has rich test cases. There are about 6.9k distinct texts from 1933–45, and NGA's structured owners give us ground truth. But "Red Flag surname overlap" must **not** be the headline metric. Naive matching hits 75% of NGA texts, mostly noise. Even full-name matching gives only about 25–40% real 1933–45 Red Flag events. Changes:
1. Deduplicate texts.
2. Split each text into dated events, including footnotes, and match only events dated 1933–45.
3. Build an alias table with forenames, ue/ö folding, and variants like Muhlmann / Bohler.
4. Carry each Red Flag entry's role note, so we can tell victims and mainstream firms from agents.
5. Evaluate against NGA's structured owners.

Plain string matching makes a good baseline for showing that the LLM pipeline adds value.

**Missing / not done:** no download of the NARA or dfs.ny.gov scans (so no multimodal sample yet); precision is from 20-sample eyeballing, not a labelled set; the cross-collection work match is crude.
