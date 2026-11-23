# TEAR NOT DEMON: imprints

What has been found with the player and kept in the game, each with
where it came from and where it is held. (`docs/EXPERIENCE-IMPRINTING.md`
says what an imprint is. What was turned down is
`experiments/tnd/REJECTED.md`.)

Status: **validated** -- he judged it on the Pocket and said so;
**adopted** -- he specified it and plays with it, no verdict in words;
**candidate** -- built, not yet played.

| id | The imprint | Status | From | Held in |
|---|---|---|---|---|
| tnd-001 | **Two headings.** His steering (the tank's, the lens's) is never turned by a blow; his BODY turns whole to throw one the way the pad points, and he stands as it left him. | validated: settled on the Pocket 2026-11-22, on the fourth try | TND-PORT P28-P31 | `gen_tnd.py` (YAW, HEAD); `tests/test_tnd_layer2.py` |
| tnd-002 | **X counts, Y ends by the count.** No timing windows: "a player could just button mash fast and still get combos". | validated with tnd-001 | P30-P31 | the count (`f_c3`); `test_tnd_layer2.py` |
| tnd-003 | **A button held slows time, and slowed time is the stage**: the blow is the way in, the hold is where he moves. Nothing may restrict him while a button is held. | adopted; his tapes are 35-53% slowed | P30, P32 (his 26-minute tape) | SLOWON; the dilation scripts in `test_tnd_layer2.py` |
| tnd-004 | **What slowed time shows, running time does not**: "the targeting should really only show in slow motion". | adopted | P35 | the sight's draw |
| tnd-005 | **The gun**: B held draws and aims -- the pad turns him finely and the shot goes where he faces; let go, it fires; a way with a fresh B is a snap shot. | played: "feels a bit better", then "starting to feel alot better" | P34-P35 | `test_tnd_layer2.py` (the gun's 14) |
| tnd-006 | **The locked run is on the tangent**: he circles the target, shoots one-handed off the run, and weaves in for a superman punch. | adopted; the run is a tenth to a fifth of his tapes | P36 | `tests/test_tnd_layer3.py` |
| tnd-007 | **R alone chooses**: the nearest target, Left and Right the next, Up and Down the spot (high, mid, low; it stays); the pad never moves him. | adopted; the spot is used (high 43%, mid 41%, low 14%) | P37 | `tests/test_tnd_layer4.py` |
| tnd-008 | **A bunker is a door and rooms**: a hub with the prep table (the map; later the pack), a ring to fight in, a range of items. | adopted: his own design, and "pretty cool" | P40 | `tests/test_tnd_layer7.py` |
| tnd-009 | **The lab**: a white room where who stands there and what a blow does to a body are knobs. | validated as a tool: "wow this is getting fucking cool" | P42; `experiments/tnd/tnd-lab-0001.json` | `tests/test_tnd_lab.py` |
| tnd-010 | **Four jabs and a miss.** The fourth is the right jab and sends the body out of a fifth's reach; Y past the third is a jab that steps in and begins a new string. | candidate | P43; `tnd-lab-0001` | `test_tnd_lab.py` (the string's 14) |
| tnd-011 | **The gun is held ready while B is down**, over whatever his legs do. | candidate | P43; `tnd-lab-0001` | `test_tnd_lab.py` |
| tnd-012 | **The lens looks up with a body thrown.** | candidate | P43; `tnd-lab-0001` | `test_tnd_lab.py` |
| tnd-016 | **Where it lands**: head, body and legs by the height a fist or a round meets a body at; the spot a height on the target; his waist bending to it; the round on the line from his hand; a gun in his hand. His direction; every particular the agent's. | candidate | P46 | `test_tnd_aim.py` |
| tnd-015 | **The reactor**: a room whose check is his body's width; his double in the corner doing what he does; a landed blow sends him as it sends a body. His proposal; the mirror of moves (not steps) and the recoil are the agent's readings. | candidate | P45 | `test_tnd_reactor.py` |
| tnd-014 | **The pass by stance** (Y with the gun up: the boxer's stun, the run's tackle), **the close-quarters shot**, **a held jab choosing the special**, **the aimed run down the sights**. The agent's readings of his words. | candidate | P44 | `test_tnd_lab.py` (P44's five) |
| tnd-013 | **The world persists**: a pack's place is a function of the clock, who is left of it is remembered, a rest gives one back; seen packs are on the map. | candidate (layer 8 has not come back on a tape) | P41 | `tests/test_tnd_layer8.py` |

To add one: the experiment's record gets `"verdict": "kept"` and the
imprint's id; the imprint gets a row here naming the record. To change
one that is validated, ask him first -- it was his verdict.
