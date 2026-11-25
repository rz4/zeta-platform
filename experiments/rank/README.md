# rank -- his sessions, read through the game's own meter (2026-11-25)

The player, of the yard: "the goal lf the game is to keep a high combat rank, and like DMC you have to be stylish
and not stick with one way of dealing with enemies. think like in bJJ you are thinking ok, from here what is my
next move" -- and of the tank, the boxer and the run: "they are supposed to feel like they can be interchangable
in importance".

The full game has that meter (TND-PORT P5: the archive's `combat.Style`). In the yard nothing paid it: on his
tapes it never moved. This is a first reading of it there (TND-PORT P94, branch `exp/rank`), and what three of his
sessions look like through it. Nothing here is part of the game he plays until he says so.

## The instrument

A tape replays exactly only on the build it was played on, and the yard's rules changed between his sessions. So
the meter is put on each tape's OWN commit as an observer -- it pays the meter and draws nothing -- and the replay
is checked against the build kept with the tape, every frame (his place, his height, his health, his style, every
body's place and health). All three sessions below, under both rules: the same, every frame.

    git show COMMIT:games/tnd/gen_tnd.py > OLD.py
    python3 experiments/rank/observe.py OLD.py games/tnd/_gen_obs_tmp.py
    TND_LAYER=13 TND_OUT=OBS.zol python3 games/tnd/_gen_obs_tmp.py && rm games/tnd/_gen_obs_tmp.py
    python3 experiments/rank/read.py OBS.zol TAPE.yard.zol TAPE.ztp OUT.npz     # the meter, and the motion check
    python3 experiments/rank/links.py OUT.npz                                   # what followed what

(Tapes and their builds are in `build/tapes`, which is not in the repository. Sessions: 20261124-234539 on P83,
80d29b9; 20261125-010354 on P84, 1334d04; 20261125-024126 on P89, 5022d21.)

## A way

What the meter remembers is not the move but the WAY he dealt with a body:

- a fist's: his style (tank, boxer), the part it met (head, body, legs), the move;
- the run's body blows, each its own: the dive, the slide, the handspring, the slam, the lance;
- a round's: his style, the part, charged or not, from the air or not.

A blow that strikes several bodies pays for each and is remembered once.

## Two rules, both measured

**The archive's (P5), with the way in place of the move.** A landed blow pays its worth x 1, 0.6, 0.4, 0.25 as
its way recurs in his last five x the combo (+5% a hit, to twenty). A blow taken keeps 45%. Nothing landing for a
second, it cools a quarter-point a frame; for two, three quarters. D, C, B, A, S, SS, SSS at 0, 60, 150, 300,
520, 800, 1200.

**As built (P94).** The same, but: 1, 0.6, 0.2 -- and a way already three times in his last five is SPENT: it
pays nothing and holds nothing up (no combo, the meter still cooling), and is remembered. And the LINK: a blow from
another style than the last paid blow's pays half as much again.

Why the second: under the first, on his 47 minutes of P83, the meter reached SSS (1,455 points, 97 seconds at S or
above) on a climb of 131 blows of which 116 were one way -- the run's round into a body's middle. And again
(1,355) on 73 blows of which 52 were the tank's jab to a head. A floor of a quarter, doubled by the combo, is
half a blow's worth for ever: volume reaches the top. That is the opposite of what he said the game is for.

| session | rule | D | C | B | A | S | SS | SSS | most points |
|---|---|---|---|---|---|---|---|---|---|
| P83, 46.8 min, 1,924 blows landed | the archive's | 39.6% | 15.5% | 17.2% | 13.2% | 8.8% | 3.3% | 2.5% | 1,455 |
| | as built | 77.9% | 15.6% | 5.5% | 1.1% | | | | 377 |
| P84, 12.7 min, 220 | the archive's | 33.1% | 11.6% | 29.5% | 24.5% | 1.4% | | | 534 |
| | as built | 53.9% | 17.8% | 19.3% | 8.5% | 0.5% | | | 524 |
| P89, 7.1 min, 257 | the archive's | 67.1% | 12.6% | 10.1% | 9.5% | 0.7% | | | 537 |
| | as built | 85.0% | 8.5% | 6.4% | | | | | 278 |

## What he did (observed; the same under either rule)

| session | time in tank / run / boxer | blows landed by tank / run / boxer | by gun / fist / the run's body |
|---|---|---|---|
| P83 | 24 / 64 / 11% | 27 / 54 / 19% | 74 / 17 / 9% |
| P84 | 4 / 83 / 13% | 3 / 73 / 24% | 31 / 21 / 48% |
| P89 | 8 / 51 / 41% | 6 / 25 / 69% | 72 / 26 / 1% |

| session | the next blow: the same way | the same kind | the same style | its way three times in the last five already | any five blows: one style only | all three | frames past 2 s since a blow landed |
|---|---|---|---|---|---|---|---|
| P83 | 77% | 94% | 98% | 68% | 93% | 1% | 50% |
| P84 | 58% | 97% | 96% | 44% | 88% | 2% | 66% |
| P89 | 73% | 95% | 95% | 61% | 82% | 2% | 59% |

- **He does not link.** Nineteen times in twenty the next blow he lands is of the same kind (gun, fist, the run's
  body) and the same style as the last. Changes of style-and-kind inside three seconds: 79 in the 47 minutes (22
  of them the run's round into a body blow of the run's, 24 the boxer's round and fist either way; 19 were a
  change of STYLE), 5 in the 12.7 (4 of style), 10 in the 7.1 (4 of style).
- **One way at a time.** The commonest state a blow of his lands in is "this way, three times in the last five
  already": 44 to 68% of all his blows. The longest unbroken run of one way: 114 blows.
- **Most of a session is between fights.** Half to two thirds of his frames are more than two seconds past a
  landed blow -- where the meter cools at 45 points a second. Time at D is first that, then the lack of variety.
- **The three are not equal in his hands yet.** The run has most of every session's time; the tank had a quarter
  of one and under a tenth of the others. The session with the most ways in it is P84's -- the night the run got
  its handspring, slam and lance: it is the only one that reads S as built.

## A scripted string, for scale (not play: a standing body, nothing missed, 19 to 26 seconds each, as built)

| the string | at its end |
|---|---|
| one way: the tank's round, again | D, 0 points (22 at its best) |
| two ways: jab, round | B, 182 |
| three ways in one style: jab, hook, round | S, 635 |
| six ways: three of the tank's, then three of the boxer's | SS, 1,040 |
| eight ways, the style changed at every blow | SSS, 1,331 |

## Supposed

- He does not link because nothing has asked him to: no rank was on the glass, and one way worked.
- The cooling was set for a street of demons that come to him. In the yard he crosses forty units between
  bodies; as it stands the meter reads D on arrival however he fought a moment ago. That is a knob, and his.
- A fist's part is hardly a choice (a jab meets a head, a cross a body), where the gun has the spot: fists have
  fewer ways than the gun. If the three are to be equal, the fists and the run may want choices of their own.

## Not known

What a linked session of HIS reaches, and whether the spent rule feels like a goal or a scold. No tape has one.
