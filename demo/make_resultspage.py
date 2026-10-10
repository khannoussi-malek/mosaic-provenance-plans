"""Fill docs/results-page.template.html with out/results.json and three worked examples -> docs/results-page.html."""
import json
from datetime import date

import score as s

DOCS = s.HERE.parent / "docs"
NAMES = {"P0": "P0 name match", "P1": "P1 small model", "P1r": "P1r small + retry", "P2": "P2 large model",
         "P3": "P3 cascade", "P4": "P4 small + verifier", "P5": "P5 cascade + adjudicator"}
WHAT = {"P0": "Red Flag full-name string match on the raw text; no model.",
        "P1": "qwen3:8b extracts ownership events (owner, role, date, place, exact quote).",
        "P1r": "P1, and on a parse error or truncation the same model is asked again with more room.",
        "P2": "qwen2.5:14b, same task as P1.",
        "P3": "P1 first; a document goes to P2 only when a free check fails.",
        "P4": "P1, then a second pass by the same model fixes, drops or adds events.",
        "P5": "P3, then an adjudicator reads each flagged match with the list entry's note."}
ORDER = ["P0", "P1", "P1r", "P2", "P3", "P4", "P5"]

EXAMPLES = [
    {"id": "73398", "title": "A Flagellator of Christ", "artist": "Alessandro Algardi",
     "verdicts": [{"kind": "flag", "text": "P0 flagged"}, {"kind": "flag", "text": "P3 flagged"},
                  {"kind": "", "text": "reference: flagged"}],
     "quotes": [{"text": "This object was sold in 1942 with the Gutmann collection of 225 silver, jewelry and Renaissance objects "
                         "to the dealers Karl Haberstock and Julius Boehler",
                 "mark": "sold in 1942 with the Gutmann collection of 225 silver, jewelry and Renaissance objects to the dealers "
                         "Karl Haberstock and Julius Boehler"}],
     "why": "The 1942 sale appears only in a footnote, after the main ownership chain. The extraction found it, dated it and "
            "linked both dealers to their list entries; string matching agreed. The answer is a pointer for an expert, with the "
            "footnote as its source."},
    {"id": "172", "title": "Portrait of a Young Woman", "artist": "Giuliano Bugiardini",
     "verdicts": [{"kind": "flag", "text": "P0 flagged"}, {"kind": "ok", "text": "P3 not flagged"},
                  {"kind": "", "text": "reference: not flagged"}],
     "quotes": [{"text": "(Count Alessandro Contini Bonacossi [1878-1955], Rome);[2] sold 1929 to the Samuel H. Kress Foundation, New York",
                 "mark": "sold 1929"}],
     "why": "Contini Bonacossi is on the list, so string matching raises an alarm. The extraction reads the holding period: he "
            "sold the painting in 1929, before 1933. This is the kind of false alarm that halves string matching's precision."},
    {"id": "66424", "title": "Still Life with Sleeping Woman", "artist": "Henri Matisse",
     "verdicts": [{"kind": "flag", "text": "P0 flagged"}, {"kind": "flag", "text": "P3 flagged"},
                  {"kind": "", "text": "reference: flagged"}],
     "quotes": [{"text": "This painting was confiscated by the ERR in 1941 with others from the Rosenberg collection in France",
                 "mark": "confiscated by the ERR in 1941"},
                {"text": "Goering is documented as having traded the painting to Gustav Rochlitz, who claimed to have sold it to Hans Wendland",
                 "mark": "who claimed to have sold it to Hans Wendland"}],
     "why": "The footnote names Hans Wendland, a dealer on the Red Flag list, but the museum's own structured owner list does not "
            "include him. A system that trusted the structured list alone would miss him; one that reads the text can show the "
            "gap to a curator."},
]


def main():
    res = json.loads((s.HERE / "out" / "results.json").read_text())
    p = res["plans"]
    have = lambda n: n in p
    findings = [
        {"label": "Name matching vs small model", "value": f"{p['P0']['screen']['F1']:.2f} → {p['P1']['screen']['F1']:.2f}",
         "text": "Screening F1. Reading dates and context removes most false alarms; precision rises from "
                 f"{p['P0']['screen']['P']:.2f} to {p['P1']['screen']['P']:.2f}."},
        {"label": "Bigger model alone", "value": f"+{(p['P2']['seconds'] / p['P1']['seconds'] - 1) * 100:.0f}% compute",
         "text": "The 14b model is not reliably better than the 8b model on either task, and has the lowest recall at both museums."},
        {"label": "Cascade (P3)", "value": f"{p['P3']['owners']['F1']:.3f} owner F1",
         "text": "Beats the small model and its retry on owners, but not the large model. It is cheaper than the large "
                 "model only when cost ratio plus escalation share is below 1: just held on the test set, failed on the dev split."},
    ]
    if have("P1r"):
        findings.append({"label": "Same model, retried", "value": f"{p['P1r']['owners']['F1']:.3f} owner F1",
                         "text": "Retrying the small model fixes an answer that ran out of room (+4.5% compute), "
                                 "but not a malformed one: at temperature 0 the same model repeats it."})
    dq = ("Comparing each National Gallery text with the museum's own structured owner list, up to 148 owners named in the "
          "texts are missing from the list (61 of 100 objects), among them the Red Flag dealer Hans Wendland, and up to 38 "
          "acquisition dates differ by three years or more. These are upper bounds and candidates for curators, not measured "
          "errors: the name matching between the two is approximate (it links the Kress Foundation to Samuel H. Kress), some "
          "date pairs compare an end date with a start date, and 20 apparent conflicts were lifespans read as acquisition years.")
    data = {"results": res, "order": ORDER, "names": NAMES, "what": WHAT, "findings": findings, "examples": EXAMPLES, "dq": dq}
    html = (DOCS / "results-page.template.html").read_text()
    html = (html.replace("__DATA__", json.dumps(data, ensure_ascii=False).replace("</", "<\\/"))
                .replace("__DATE__", date.today().strftime("%-d %B %Y"))
                .replace("__SCREEN_N__", str(res["n_docs"] - res["labels"]["left_out"]))
                .replace("__AGREE__", f"{res['labels']['agreement'] * 100:.0f}")
                .replace("__KAPPA__", f"{res['labels']['kappa']:.2f}"))
    (DOCS / "results-page.html").write_text(html)
    print(f"-> {DOCS / 'results-page.html'} ({len([n for n in ORDER if n in p])} plans)")


if __name__ == "__main__":
    main()
