# Text vs structured owner list: National Gallery of Art test set (100 objects)

Read with `run_P3.json`. These are two descriptions by the same museum, not independent sources.
Every row is a candidate for an expert to check, not a confirmed error in either description:
the extraction itself can be wrong (e.g. an end date read as a start date).

| Kind | Count | Objects affected |
|---|---|---|
| Owner in the text, missing from the owner list | 148 | 61 |
| Owner in the list, not found in the text extraction | 59 | 34 |
| Same owner, acquisition years 3+ years apart | 38 | 29 |
| (left out: the 'year' is a lifespan in the quote, an extraction error) | 20 | |

## Date conflicts

- NGA 73852 · German military: text 1945 ("in the possession of the German military until 1945, mainly at the Reich Chancellery") vs list 1941
- NGA 73852 · Dr. and Mrs. Vitale Bloch: text 1962 ("Dr. and Mrs. Vitale Bloch (sale, London, Sotheby's, 28 June 1962, lot 87)") vs list 1954
- NGA 53128 · W. Averell Harriman Foundation: text 1972 ("W. Averell Harriman Foundation; gift 1972 to NGA.") vs list 1943
- NGA 73851 · Baron Etienne Martin de Beurnonville: text 1885 ("purchased by Baron Etienne Martin de Beurnonville (sale, Paris, Hôtel Drouot, 16-19 February 1885, no. 51, to Philippe)") vs list 1877
- NGA 73851 · Ian Woodner: text 1983 ("purchased by Ian Woodner, New York, 21 July 1983") vs list 1986
- NGA 46246 · Samuel H. Kress Foundation: text 1950 ("gift 27 September 1950 to the Samuel H. Kress Foundation, New York;") vs list 1935
- NGA 46286 · Samuel H. Kress Foundation: text 1950 ("gift 27 September 1950 to the Samuel H. Kress Foundation, New York;") vs list 1937
- NGA 46090 · Alexandre Berthier: text 1906 ("sold probably 1906 to Alexandre Berthier [1883-1918], 4th Prince de Wagram, Paris;") vs list 1900
- NGA 46224 · Samuel H. Kress Foundation: text 1950 ("gift 27 September 1950 to the Samuel H. Kress Foundation, New York;") vs list 1935
- NGA 46488 · M. Knoedler & Co.: text 1930 ("sold May 1930 to (M. Knoedler & Co., London, New York, and Paris);[5]") vs list 1927
- NGA 46258 · Samuel H. Kress Foundation: text 1950 ("gift 27 September 1950 to the Samuel H. Kress Foundation, New York;") vs list 1935
- NGA 61248 · John Hay Whitney Charitable Trust: text 1982 ("deeded 1982 to the John Hay Whitney Charitable Trust, New York;") vs list 1950
- NGA 46081 · Benoit Oppenheim [1842-1931]: text 1927 ("Benoit Oppenheim [1842-1931], Berlin, until at least 1927;") vs list 1901
- NGA 46285 · Count Alessandro Contini Bonacossi: text 1922 ("(Count Alessandro Contini Bonacossi, Rome and Florence);") vs list 1935
- NGA 46285 · Samuel H. Kress Foundation: text 1950 ("gift 27 February 1950 to the Samuel H. Kress Foundation, New York;") vs list 1935

## Owners named in the text but missing from the owner list (first 20)

- NGA 229508 · Louis Alexander Ricard-Abenheimer (other): "(Louis Alexander Ricard-Abenheimer, Frankfurt am Main)"
- NGA 229508 · Henry A. and his wife Elinor Ullin (heir): "by descent to their son Henry A. and his wife Elinor Ullin, Melbourne"
- NGA 229508 · L. Scott (dealer): "L. Scott"
- NGA 229508 · Belgian private collection (other): "Belgian private collection"
- NGA 52199 · the artist [1830-1903] (collector): "By inheritance from the artist [1830-1903] to his wife, Mme. Camille [Julie] Pissarro"
- NGA 52199 · Van Riel (collector): "purchased by Van Riel"
- NGA 52199 · Jeume de Paume (collecting point): "transferred to the Jeu de Paume"
- NGA 52199 · Gustave Rochlitz (collector): "remained with Rochlitz, in whose possession it was found after the war"
- NGA 52199 · France (heir): "restituted to France on 27 March 1946"
- NGA 143662 · Wilhelm Koenig (collector): "Wilhelm Koenig [1881-1941], Vienna (Lugt 2653b)"
- NGA 73852 · People's Commissars of the Ukrainian Soviet Socialist Republic (confiscating agency): "on 2 January 1940, by decree of the People's Commissars of the Ukranian Soviet Socialist Republic, the Ossolinski Librar"
- NGA 73852 · German troops (other): "German troops took L'vov in June 1941, and in July K. Muhlmann, the German special representative for works of art, took"
- NGA 73852 · K. Muhlmann (dealer): "German troops took L'vov in June 1941, and in July K. Muhlmann, the German special representative for works of art, took"
- NGA 73852 · salt mine near Salzburg, Austria (collecting point): "discovered in a salt mine near Salzburg, Austria, and taken to the Munich Central Collecting Point, April 1945"
- NGA 73852 · private collection (other): "private collection, Nuremberg"
- NGA 53128 · Marie N. Harriman (collector): "by exchange 1943 to Marie N. Harriman [1903-1970] and W. Averell Harriman [1891-1986], New York;"
- NGA 139276 · Possibly Baron von Bernus (collector): "Possibly Baron von Bernus, Heidelberg."
- NGA 139276 · Museum Folkwang and the city of Essen (confiscating agency): "In 1939 the Museum Folkwang and the city of Essen raised the funds to purchase the collection"
- NGA 139276 · Allied forces (collecting point): "Eleven Hirschland paintings were evacuated, with other paintings from the Folkwang, to a mine near Siegen, where they we"
- NGA 139276 · Collecting Point at Wiesbaden (collecting point): "The 11 paintings in Marburg were transferred by September 1946 to the Collecting Point in Wiesbaden"

## In the owner list, not found in the text extraction (first 15)

Either the extraction missed them or the list holds information the text does not show.
- NGA 229508 · Private Collection (NGA Former Owner) (?–?)
- NGA 52199 · Rochlitz, Gustav (1941–1945)
- NGA 52199 · Munich Central Collecting Point (1945–1946)
- NGA 143662 · Koenigs, Franz Wilhelm (?–?)
- NGA 73852 · Library of the Ukrainian Academy of Sciences (1940–1941)
- NGA 73852 · Hitler, Adolf (1941–1941)
- NGA 73852 · Mühlmann, Kajetan (1941–1941)
- NGA 139276 · Triest, Fred (?–?)
- NGA 139276 · Stiftung Ratjen (?–2007)
- NGA 3199 · Burlet, Charles A. de (?–?)
- NGA 51136 · La Tour d'Auvergne-Lauraguais, Elisabeth Marguerite, Princesse de (1918–1936)
- NGA 51136 · Frink, Angelika Wertheim, Mrs. (1941–1969)
- NGA 51136 · Canadeesche Hypothek Bank (?–?)
- NGA 51136 · Kapferer, Marcel (?–?)
- NGA 277 · Giovanelli, Giuseppe Prince (?–?)
