# TEAR NOT DEMON: the world layer (a design; 2026-11-22)

What exists: the generator (`games/tnd/world.py`, run when a cart is
built), the layers under it (docs/TND-PORT.md, P21-P37), and step 2 of
the order below as layer 5 (P38). The rest is design.

## The frame, in the player's words

- "the regular time is the fast pace exciting dmc style. the slow motion is
  to string high action together strategically. this combines resident
  evil, devil may cry, speed running and xcom."
- "the world ... like in classic resident evil, key puzzles opens routes,
  shortcuts for back tracking or hard optional shortcuts to move forward.
  the dmc, mission structure between sectors, multiple exits, the rank is
  for fighting realtime, but a ranking in full game traversal too based on
  time completion."
- "we start in a bunker." "starting bunker, some other scattered. the
  bunker is where you prep, setting your way marks planning routes,
  inventory packing, saving. as we grow the city size this becomes more of
  a part of the game. each game is a random map so the player solves the
  puzzle, almost like xcom feel like planning." A game is several sittings.

## A game

1. NEW GAME draws a world: a city nobody has seen, and its puzzle.
2. In the starting bunker: the map (what is known of it), waymarks, the
   pack, a save.
3. Out of the door the clock runs. Real time is the fight; slowed time
   strings it together, and is the only place the sight, the target and
   the spot are shown.
4. A bunker reached is a sitting ended: saved, the map filled in with what
   was walked, the plan made again, the pack remade.
5. The CORE reached is the game ended: the traversal rank, against the
   world's own par.

## The world (prototyped: `games/tnd/world.py`)

Over city.py's town (a tree of streets on a 16 x 16 grid, cut along its
route from START to the CORE into seven or eight sectors, a gate between
each two), from the same seed:

| | what | how it is placed |
|---|---|---|
| a key a gate | lies at a dead end | the far end of the gate's own sector; three times in six a sector or two BACK |
| bunkers | the start's dead end, and three more | a dead end well off the route in every second sector |
| back doors (2-3) | a street the tree lacks, bolted on its deep side | where opening it saves twelve blocks or more of the walk home to a bunker |
| hard ways (2) | a street the tree lacks that skips a gate and its key | forward across one or two gates, worth eight blocks or more; open to anyone, and HELD |
| par | blocks from START to the CORE | a search over where he is, the keys in hand and the bolts drawn: by the gates, and by the hard ways |

Three seeds (build/tiers/worlds.png): the route alone is 61 to 86 blocks;
the keys make it 123 to 168; the hard ways bring that down to 99 to 132.
So a hard way is worth about a fifth of a game's walking -- which is the
trade the two ranks are for. A block is sixteen units: at the run's pace a
game's par is three to five minutes of pure running before a single fight,
so sixteen-square cities are an evening, and "several sittings" is what a
larger city is for.

A sector has, then: the gate on (its key somewhere behind), sometimes a
hard way on, sometimes a back door home -- more than one way out.

**Random, and the same for everyone who is given its number.** A world is
its seed. One is about 256 words of map and forty of keys, bunkers and
doors, so a cart can carry hundreds made beforehand (the first cut), or
the console can grow one (the pure one: the generator is integer work on a
256-node tree). The seed is taken from the frame NEW GAME is pressed on,
which a tape repeats exactly.

## The bunker

The player (2026-11-22, of the first cut's hatch in the road): "the
bunkers were more of doors against a building, and an actual room you
enter, in there we can have training rooms with the items as objects you
can practice melee and gunplay. that will also help calibrate the game
play, those training rooms. the hub room hold a desk with the map and
inventory management. the prep table". BUILT so as layer 7 (TND-PORT P40):
a door on the dead end's wall; inside, real rooms walked with the street's
own controls -- the hub with the prep table (the map now; the pack and the
stash at step 5), a ring with the six bodies to fight, a range with items
to shoot and strike. One set of rooms serves every bunker.

- **MAP.** The city from above, drawn as geometry (the display list holds
  about 37 characters, so a map is shapes, not text). FOG: what he has
  walked, plus what this bunker's own survey gives -- its sector's streets,
  not what lies in them. Keys, gates and doors appear when seen.
- **WAYMARKS.** Up to four, in order, put on the map with the pad. In the
  street the arrow that already leads to the key and the gate leads to the
  next waymark, and reaching one moves it on.
- **PACK.** A few slots; rounds by the cylinder, medicine, keys (a key
  takes a slot), a charge (it opens a held way without the fight). The
  stash stays in the bunkers, one stash between them. Carried weight past
  a free allowance takes from his pace -- packing is a speed decision.
- **SAVE.** The world's seed, the clock, the map walked (a bit a node),
  keys, gates and bolts, pack and stash, waymarks, each sector's combat
  rank: about forty words, beside the save the card already keeps.
- **Down in the street**, he is back at the last bunker he saved in, with
  what he had then; the clock keeps what the lost sitting cost.

## The two ranks

- **Combat, a sector**: the style rank the game has, earned in real time
  (variety, the string, no blow taken). Time slowed neither adds to it nor
  bleeds it. Shown at the sector's gate.
- **Traversal, the game**: glass seconds in the street -- slowed time
  counts in full, bunkers do not -- over the whole game, against the
  world's par. Shown at the core, with the seed.

So slowed time buys combat rank and spends traversal rank; a hard way
spends combat risk and buys traversal time; a heavy pack buys safety and
spends pace.

## Who is in a sector, and what lies there

- A sector's danger (it rises along the route) sets its company from the
  sizes: the horde early, commons, elites later; a hard way is an elite's
  pack; the core is the rival, a second full player. (Zombies, demons and
  aliens are these bodies re-proportioned and re-coloured.) They must
  STRIKE, on a wind-up that slowed time shows.
- A cleared sector stays quiet; a light patrol is back once he has rested
  in a bunker, so the way home is not free and a back door is worth its
  bolt.
- Items lie at dead ends and in plazas: rounds, medicine, a charge. They
  are all but free to draw.

## What the machine has for it

| | have | this layer wants |
|---|---|---|
| program | 32,768 words a page; layer 4 is 20,588 | the street's code grows; each bunker screen is its own page |
| data memory | about 3,170 words free with bodies drawn from the cart | the map's geometry while in the bunker; the pack; the fog's 8 words |
| objects, vertices | 64 and 2,048 a frame | items a dozen; the company a sector by the head-count already measured |
| cart | about 1.5 M words of 4.06 M with 16-bit poses | a hundred worlds 30,000 words; a bunker picture 92,160 |
| text | about 37 characters | numbers and a cursor; everything else is picture |
| the card | a save of a few words, written and read back exactly | forty more |

## The order to build it in

1. **The world, on the desktop** -- done as a prototype here; next its
   rules tuned by looking at maps (how often a key lies back, how many
   doors), and a test that every world drawn can be finished.
2. **A world in the street**: the generator's keys, bunkers and doors in
   the city the layers already walk (one seed, baked) -- many keys, the
   bolts, the held ways; the arrow on a waymark. BUILT: TND_LAYER=5
   (docs/TND-PORT.md P38), in the emulator and the hardware's simulation;
   not yet on glass. The pack holds the first hard way but does not strike.
3. **The bunker's MAP and waymarks** (the map as geometry). BUILT:
   TND_LAYER=6 (docs/TND-PORT.md P39), in the emulator and the hardware's
   simulation; not yet on glass. A mode of the street's own program, not a
   page; the fog is by sector (the one he stands in, and from a hatch the
   next), not by node; the arrow's way is searched over the open streets.
4. **The clock, the par, the two ranks; the save across sittings.**
5. **The pack, the stash, items in the street; weight.**
6. **Random worlds**: a library in the cart, the seed from NEW GAME.
7. **Their company**: enemies by sector, striking; patrols; the rival.

## Decided here, to be overruled freely

- The map is fogged, and a bunker surveys its own sector.
- The clock runs in the street at glass speed, slowed time included; it
  does not run in a bunker.
- Going down costs the sitting's time and returns him to his last save.
- Weight slows him.
- A world is a seed, shown, so two people can play the same one.

## Every idea from the talk, and where it goes (2026-11-22)

The player: "we also need to incorporate all the other ideas from this
discussion." So that none is lost -- each with the step above that carries
it (or "new"), and whether he said it or it was offered and not refused.

| the idea | whose | where |
|---|---|---|
| real time is the fast, exciting fight (DMC); slowed time strings it together (XCOM) | his | the layers (P30-P37); step 7 makes real time press him |
| what slowed time shows, running time does not: the sight, the target, the spot | his (the sight); offered (the rest) | P35, P37; step 7 adds the enemies' wind-ups and a blow's reach to it |
| the enemies strike, on a wind-up he can read | offered | step 7 |
| the clock runs at glass speed in slowed time: thinking costs seconds | offered | step 4 |
| a combat rank a sector, for real-time fighting; a traversal rank for the whole game, by time | his | step 4 |
| slowed time neither earns nor bleeds the combat rank | offered | step 4 |
| a run is provable: a tape and a seed | offered | step 6 (the seed shown); the tape is the platform's |
| keys open routes; back doors for the way back; hard optional ways forward | his | step 2 |
| sectors as missions, more than one way out | his | steps 2 and 4 (the rank at each gate) |
| a hard way is held: a fight, or a charge spent, or the wall jump and the slide asked of him | offered | step 2 (open), 5 (the charge), 7 (the pack); the movement kind is new street pieces -- later |
| the bunker: prep, waymarks, routes, packing, saving; more of them as the city grows | his | steps 3-5 |
| the bunker as baked rooms seen from fixed lenses (the machine's plates) | offered | after step 5: first a screen, then rooms |
| the map fogged, a bunker surveying its sector | offered | step 3 |
| carried weight slows him | offered | step 5 |
| each game a random map; several sittings; cities that grow | his | step 6; the larger city is the generator's `size` and the map's words |
| the world's par, so a random map can be ranked | offered | step 1 (done), step 4 |
| the enemies are his own body, smaller -- zombies, demons, aliens; the hardest a second full player | his | P37 (the sizes); step 7: their looks (proportion, colour, posture, a horn or a crest), their fists, the rival |
| the rival's hands: a mind using his kit, or tapes of play | offered, undecided | step 7 |
| a cleared sector stays quiet; a patrol returns after a rest | offered | step 7 |
| more items; the city as it is | his | step 5; the town's own budget is kept (ZETA0-FRONTIER 20, the balance) |
| better menus: baked screens, the four scanout panels, 37 live characters; later a small blit for glyphs | his (the wish); offered (the means) | steps 3-5; the blit is a machine experiment of its own |
| limited rounds as a routing matter; the fists load the gun | mine, not yet judged | P34; step 5 makes rounds a thing packed |
| the vertex store doubled, for a larger company | offered | a machine experiment: nine M10K are left, it wants seventeen |
