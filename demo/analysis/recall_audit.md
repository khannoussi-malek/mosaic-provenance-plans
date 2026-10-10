# Recall audit: Red Flag names the matcher never surfaced

Question: of the 46 NGA test objects that are not in `demo/data/label_cases.json` (the 54 cases the matcher surfaced, 31 flagged and 23 near), how many name a Red Flag person or firm in a way that should have produced a `flagged` label?

## Method

1. Selected the 46 objects in `demo/data/testset_nga.json` whose id is not in `label_cases.json`.
2. **Code search over the full text (provenance and footnotes) plus the gold owners**, against all 1,100 rows of `phase0/data/red_flag_names.csv`:
   - capitalised tokens (hyphen parts split) folded two ways (ü→ue and ü→u, accents stripped), matched exactly against the folded `match_key` and the surname part of `name`;
   - `difflib.get_close_matches` at cutoff 0.84 on the same tokens, and at 0.75 on gold-owner surnames;
   - a case-insensitive `grep` of the CSV (name and notes) for about 120 owner, dealer and auction-house names in the 46 texts (Aufhäuser, Weiss, Seligmann, Duveen, Weil, Nebehay, Schab, Ketterer, Stuttgart, Sklarz, Strölin, Scheyer, Kantor, Kleemann, Colnaghi, Durlacher, Agnew, Ackermann, Drouot, Christie, Sotheby, and others).
3. I judged each candidate by hand: is it the same person or firm, does the text name them as owner, dealer, agent or intermediary of this object, and does their holding touch 1933-45?
4. To explain the misses I read `demo/make_labelpage.py`. The matcher runs only on `d["gold_owners"]` names (`s.match(s.forward(g["name"]), ...)`) and never on the provenance text. I did not open `demo/out/` or any other label file.

## Real hits (same person or firm, named in the chain of this object)

| Object | Name in text | List entry | In 1933-45? | Quote |
|---|---|---|---|---|
| 6611 *Three Genii* | M Knoedler and co., NY | `Knoedler et Cie` (Paris; "Schenker documents indicate sales to German buyers") | yes | "(M Knoedler and co., NY); purchased by Lessing J. Rosenwald [1891-1979] ... 1940" |

Caveat: the list entry names the Paris branch, and the text names the New York house. It is the same firm, but the list's evidence concerns Paris. Following the skill's guidance, Knoedler is a mainstream firm on the list, so a match marks the object for review, not as looted.

## Real name matches that are not owners or intermediaries (correctly not flagged)

| Object | Name in text | List entry | In 1933-45? | Why it does not count |
|---|---|---|---|---|
| 95 | "August L. Mayer, _Francisco de Goya_, Munich, 1923" (note 4) | `Mayer, August L` (Goya expert) | no (1923) | Same person, but cited as an author, not an owner |
| 95 | "Frederik Muller et Cie, Amsterdam, 25-26 October 1927" (note 3) | `Mueller & Co, Frederick` (Amsterdam auction firm) | no (1927) | Same firm, but this is the publisher of the James Simon sale catalogue cited as a reference. The object was with Sklarz by 1923 and Duveen sold it to Mellon in 1930 |
| 34047, many prints | "Fritz Lugt, _Les Marques..._", "(Lugt 1185)" | `Lugt, Fritz` | n/a | Collector-mark reference numbers and an author citation, not ownership |
| 73851, 1609, 47120 | Hôtel Drouot sales of 1877, 1885 and 1898 | `Drouot, Hotel` | no | Same auction house, but every sale is pre-1933 |
| 52183 | "Hôtel Drouot, Paris, 23 November 1910"; note: "misidentified with the 9 July 1942 sale at Drouot, but that sale did not include this picture" | `Drouot, Hotel` | no | The only wartime Drouot link is explicitly refuted by the text |

## Rejected near-matches (different person or firm)

- Gutmann, Rudolf (34659, Viennese collector whose collection was confiscated in 1938) vs `Guetmann, Prof Dr` (ERR member, Brussels): different person. This object is a genuine Nazi-era case, but the owner is not on the list.
- Oettingen-Wallerstein Collection (3783) vs `Wallerstein, Dr Victor`: a princely collection, not the Florence refugee dealer.
- Stuttgarter Kunstkabinett (139202) vs `Valentin, F` (Stuttgart dealer): different firm. Heumann, Carl vs `Hermann, Dr Kurt`: different name.
- Valentiner, Wilhelm R. (1609, author) vs `Valentin, F`.
- Hirschl & Adler (126155) vs `Hirsch, Alfredo`.
- Simon, Dr James (95) vs `Simon, O` / `Simon, Dr Victor`.
- Schiff, Mortimer L. (41708) vs `Schiff-Giorgini, Dr` / `Schiffman, Erich`. Kress Foundation vs `Kress, Karl` (ERR photographer). Matthews vs `Matthiesen, Galerie`.
- Phillips, de Pury & Luxembourg (119837) vs `Phillips Company` (Eindhoven electronics).
- Seligmann (41708, 136751): appears in the list only inside the notes of `Botton, Mlle Lucie`, with no entry of its own.
- Galerie André Weil (46517): appears only in notes ("David-Weill" collection), with no entry.
- Given-name collisions: Martin (Aufhäuser, Beurnonville) vs `Martin, Dr Kurt`; Hermann Marx vs `Hermann, Dr Kurt`; Otto Kahn / Otto von der Malsburg vs `Otto, Prof Georg`, `Abetz Otto`; Hans Naef vs `Wendland Hans`; John, Friedrich, Franz, David, Ernst.
- Spelling collisions: Wellner/`Fellner, Galerie`, Bernard Montague/`Bernard, Jacques`, Barnard/`Bernard`, Boerner/`Bernier`, Walter/`Walther`, Chandler/`Haendler`, Rosenwald/`Rosenthal`, Widener/`Winter`.
- Not on the list at all: Aufhäuser, Weiss & Co., Duveen, Nebehay, Schab, Sklarz, Paalen, Strölin, Scheyer, Kantor, Kleemann, Ketterer, Petiet, Molyneux, Druet, Colnaghi, Durlacher, Sedelmeyer, Fischhof, Rothschild.

## Count

**1 object should have been `flagged` but was never surfaced: 6611 (Knoedler, sold 1940).**

Why it was missed: `make_labelpage.py` matches only `gold_owners`, and the gold list for 6611 contains only "Rosenwald, Lessing Julius". The parenthesised dealer `(M Knoedler and co., NY)` is in the text but not in the gold owners, so the matcher never saw the name. If Knoedler had been passed in, the `match_key` "Knoedler" would match. The other real name matches (Mayer, Frederik Muller, Lugt, Drouot) are authors, references or pre-1933 sales, so not surfacing them is correct.
