# experiments -- sessions on the Pocket, as records

One file an experiment (`zeta-xp-1`), named by game. The design is
`docs/EXPERIENCE-IMPRINTING.md`.

    python3 -m zeta.experience ingest build/tapes/<tape>.ztp \
        --game <the .zbin it was played on> --symbols <that build's .zol> \
        --axes games/tnd/axes.json --observer games/tnd/observe.py \
        --card <the save it began with> --built-at <commit> --recipe "<how>" \
        --id <id> --out experiments/tnd/<id>.json
    python3 -m zeta.experience compare experiments/tnd/A.json experiments/tnd/B.json

`ingest` writes `machine`, `evidence`, `knobs` and `observed`, and leaves
any other key in the file alone. The rest is written by hand:

    "human":  {"said": ["his words, verbatim"], "said_on": "date",
               "knobs_chosen": [{"axis": "...", "signed_notches": -1}]}
    "agent":  {"observations": [{"what": "...", "frames": [a, b]}],
               "readings": [{"supposes": "...", "or": ["..."], "confidence": "low|medium|high"}],
               "proposed": ["..."]}
    "result": {"commits": ["..."], "proved": ["..."], "cost": "...",
               "next_record": null, "verdict": "pending|kept|revised|rejected",
               "imprints": ["tnd-..."]}

Rules:

- **The cart a tape was played on must be the cart it is replayed on.**
  Keep the `.zbin` from the card before pushing over it, and build the
  symbols from the same commit and recipe. `ingest` refuses a tape whose
  sum is not the cart's.
- A record's `evidence.end_state_sha256` is the check that a later
  replay is the same session.
- Tapes stay in `build/tapes/` (not in git); a record carries the tape's
  SHA-256. The song the layers are played with is a local asset, so the
  exact card build is reproducible only where that asset is.
- What the player said goes in verbatim. What a tape shows goes in as
  numbers and frames. What anyone supposes is labelled as that.
- A turned-down experiment is not deleted: its verdict is `rejected`,
  and it gets a line in `tnd/REJECTED.md`.
