# How the ULMG game works

The United League of Moderate Gamers spent decades as a Strat-O-Matic league. The website grew up beside that: rosters, drafts, trades, and the constitution, with the game itself played from cards and dice. The game now plays inside the site.

This is how a game is built, and where it parts from Strat-O-Matic. The constitution is still the rulebook. The change is that the rules which decide who may play, and for how long, are checked before the next pitch.

A manager can read straight through. The last section is a map of the code.

## Strat-O-Matic, and what changed

A Strat-O-Matic plate appearance is a dice roll read off a card. The batter's card and the pitcher's card are charts. Which card you read depends on the roll and on the version of the game. Left and right splits are separate cards or separate columns. Fielding is a grade, and it changes particular results. Steals, bunts, the hit-and-run, and the intentional walk are manager decisions resolved on their own charts. The cards are Strat-O-Matic's translation of a real season into that system.

Nothing in those dice knows the constitution. A manager can send a batter up past his plate appearances, or leave a starter in past his innings. The league catches that in the bookkeeping, or trusts the manager to have caught it himself.

The ULMG game keeps the part that mattered: each player is a card from a real season, the manager makes the strategic calls, and the constitution still limits how that card may be used. It drops the dice chart. A plate appearance is a draw from the two players' actual outcome rates. And the usage limits are no longer bookkeeping around the game. They are a condition of the plate appearance being played.

## Two programs

A game is two programs with a hard line between them.

The **engine** is a small Rust program in `engine/`. It plays one baseball game. It knows innings, outs, the bases, a lineup, a pitcher, and how to draw one plate appearance. It does not know a roster cap, a series, a draft, or which human is sitting in the seat. It stores nothing. Django sends it the whole state of the game, a call, and a seed. It sends back one plate appearance and the next state. The same state, call, seed, and runner ratings always produce the same plate appearance, so a game can be replayed from its log.

The **league** is the Django site. It builds the cards, holds the half plans, checks the roster and the usage ledger, renders the page, and writes the log. `ulmg/engine_client.py` is the only code that talks to the engine.

One pitch, from the manager's click to the play-by-play line:

1. The page submits the log position it was showing, and a call if the manager made one.
2. Django refuses the click if that log position is stale, if the manager does not hold the seat, if the game is paused, or if a substitution is still required.
3. Django checks the batter and the pitcher against the usage ledger.
4. Django sends the engine the state, with this plate appearance's platoon rates written onto the two cards.
5. The engine draws the plate appearance and returns the new state.
6. Django appends the play to the log and counts it on the ledger, in the same database transaction. If the count would cross a cap, the play is refused and nothing is written.

The log is the game. The box score, the win and the loss, and a replay are all computed by folding that log. The engine can be restarted at any time; it has nothing to remember.

## The card

A card is the player's previous MLB season. A ULMG season uses the FanGraphs line from the year before. A player who appeared in the majors that year is carded, and only a carded player can sit on the MLB or AAA roster.

The engine is handed finished numbers. It does not compute a rating from raw stats. `ulmg/cards.py` does that work.

**Hitting.** Eight rates per plate appearance, and they sum to 1: strikeout, walk, hit by pitch, single, double, triple, home run, and a ball in play that is out. The pitcher's card has the same events per batter faced, except that his non-home-run hits are a single rate. The single, double, and triple *shares* of those hits stay the hitter's.

**Platoon.** Each hitter has a line against left-handed and right-handed pitching, and each pitcher has a line against left-handed and right-handed batters. A thin split is pulled toward the overall card: 400 plate appearances, or 400 batters faced, of the overall line are mixed in, and the result is scaled back to 1. A split with no sample is the overall card. A switch-hitter bats from the side opposite the pitcher's arm. When a hand is unknown, the overall card is used. The game writes the matching split onto the cards for that one plate appearance, so the rest of the game keeps the overall card.

**Batted balls.** Ground-ball, fly-ball, and line-drive shares, from the FanGraphs counts. A card with none of them plays at the league mix: 43 percent ground balls, 36 percent fly balls, 21 percent line drives. The mix decides what kind of out a ball in play is. It does not change the chance of a hit.

**Running.** Steal success is his stolen bases and caught stealings, regressed toward a 72 percent success rate over 10 attempts. His attempt rate is attempts per time he reached first base on a single, a walk, or a hit by pitch. His speed is FanGraphs Spd.

**Defense.** One number per position, in fielding runs, regressed toward average with 600 innings of regression and scaled to a 1,300-inning season. Catcher is rated only from innings actually caught; a player who never caught has no catcher rating and cannot be filed at catcher. Everywhere else, the rating starts from his primary position and slides along a spectrum with shortstop as the baseline. Second base is credited 12 runs from there, center field 13, third base 15, right field 16, left field 17, and first base 18. Innings he did play at another position pull that slot toward what he actually did there. The engine wants a smaller unit, so the site divides those runs by 10 before sending them. The pitcher's own fielding number is sent as zero.

**Fatigue sample.** For a pitcher, the card also carries his age, whether he started at least half his appearances, his pitches per appearance that season and in his career, and how many appearances the season sample is. That sample is what the engine draws a fatigue line from. It is not an outcome rating, and it does not change his strikeouts or his hits. The usage ledger classifies pitchers separately, from starts and relief appearances. A pitcher can be a starter for fatigue and a swingman for usage.

**Park.** The home club's field. Singles, doubles, triples and home runs each have a score, and 100 is average, so 115 is a factor of 1.15. An event with no score uses the park's overall factor, the wOBA index, or the runs index when that is all the park has. A club with no field plays at 100. A high set of scores, Coors Field, produces more hits and more home runs than a low set, Tropicana Field. The dimensions, the ground rules and the field plate are stored on the same field for the art. Until a plate has been written, the page draws a generic park.

## One plate appearance

The draw is an odds-ratio matchup, the log5 method. For each event, the batter's rate and the pitcher's rate are combined against a league line. A pitcher who matches the league line gives the batter his own card back. The league line, per plate appearance, is a strikeout 22.6 percent of the time, a walk 8.4, a hit by pitch 1.1, a home run 3.1, and a non-home-run hit 19.2. Whatever is left is a ball in play that is out.

The park multiplies singles, doubles, triples and home runs by their own factors. Every rate, including the strikeouts and walks, is then scaled so the eight still sum to 1. Factors of 1 leave the matchup where it was.

Defense moves probability between non-home-run hits and balls in play that are out. The eight fielders and the pitcher are summed — the designated hitter does not field — and each point of that sum moves 0.002 of a plate appearance. Four fifths of that movement is hits and outs. One fifth is reached-on-error and outs. A good defense turns hits and errors into outs. A bad one does the reverse. Home runs are not touched. wRC+ is not an input to this draw.

The engine then rolls one number and reads the outcome off those eight probabilities.

A ball in play that is out is then called a ground out, a fly out, or a line out, from the matchup's batted-ball mix. At a league-average defense, 0.7 percent of plate appearances are a reached-on-error instead of that out: about one every four games for a team, which is the major-league rate of a batter reaching on an error. Seven of ten of those are ground balls. The fielder charged is usually an infielder on a ground ball and an outfielder on a fly, and his own rating tilts it: a poor glove is charged more often than a good one at the same position. The batter is safe at first and runners advance only when forced. It is an at-bat and not a hit. The run he scores is unearned, and so is every run that scores on the play, and every run after the error would have been the third out.

The runners then move from the out that remains:

- With a runner on first and fewer than two outs, a ground out is a double play 52 percent of the time. That constant is set so a league-average game turns two on about 10 percent of its double-play chances.
- An unforced runner on third scores on a ground out half the time, and an unforced runner on second takes third half the time.
- A fly out with a runner on third and fewer than two outs is a sacrifice fly 60 percent of the time. The runner on second tags to third 20 percent of the time.
- With two outs, the out ends the half inning and nobody moves.

On a single or a double, the runner on first takes one extra base 25 percent of the time at league speed. His chance scales with his Spd against the league's, and it is kept between 5 and 60 percent. With no speed on the card, he runs at 25 percent.

A league-average lineup against league-average pitching, in a neutral park, scores between 4.2 and 4.9 runs a team. That band is the check the engine's distribution test holds the whole model to.

### Calls

A human plays it straight, or makes one call. The batting seat can bunt, steal, or hit and run. The fielding seat can call an intentional walk or pitch around.

- A **bunt** is a single 15 percent of the time, a sacrifice 60 percent of the time when a runner is on and there are fewer than two outs, and an out the rest of the time.
- A **steal** sends the lead runner when a base ahead of him is open. He makes it at his card's success rate, or at 75 percent with no rate. Caught with the third out, the plate appearance ends before the batter finishes it: no at-bat, and the out counts for the pitcher.
- A **hit-and-run** cuts the strikeout rate in half and moves that probability onto hits and outs in play, in the proportion the matchup already had. On a single, the runner from first always takes the extra base.
- An **intentional walk** is four balls. It is not drawn.
- **Pitch around** doubles the hitter's walk rate for this plate appearance, up to a ceiling of 1, and shrinks his other rates so they still sum to 1. The probabilities printed on the page are the straight matchup. The doubled walk rate is what gets drawn.
- **Infield in** exists in the engine. With a runner on third and fewer than two outs, the runner holds on a ground out, and about 10 percent of those ground outs get through as singles. The game page does not offer this call.

When the batting side is the computer, and the plate appearance was not sent in as a steal, a bunt, or a hit-and-run, the engine itself calls a bunt on about 0.8 percent of plate appearances, with no look at the situation, and otherwise plays it straight. Steals are a different decision, made by the league before the pitch is sent. That one reads the card and the situation, and it is described with the computer manager below. A human seat never gets the flat bunt. The human bunts by choosing it.

### The count

The outcome is drawn first. The engine then builds a legal pitch sequence that ends in that outcome: a random count, up to two foul balls with two strikes, and a final pitch of the kind the outcome needs. An intentional walk is four balls. A caught stealing is one pitch.

Those pitches are what the log prints, what fatigue charges, and what the usage ledger stores as the pitch count. They are a telling of a result that has already been decided. The count does not cause the out or the hit.

Four things arrive with every plate appearance and do not change the draw. The pitcher's fatigue and his ceiling decide whether he is allowed to still be on the mound. The hitter's wRC+ prices how hard each pitch was. Weather is accepted and ignored. The postseason flag only changes whether extra innings place a runner on second.

## The game on the field

The engine keeps the inning, the half, the outs, the bases, the score, and each club's three groups of players: in the game, available, and already used. A player who leaves cannot come back. Four outs are rejected. The half inning ends at three outs. The home team does not bat in the ninth or later with a lead. A home run or a hit that wins it in the bottom of the ninth or later ends the game on that pitch.

From the tenth inning on, the batter immediately before that half's leadoff man starts on second. The engine does this for a regular-season game. A game marked postseason starts every extra half with the bases empty. The league sim opens every game as a regular-season game, so the runner is placed. When he scores, the box score charges the run to the pitcher who started the half and scores it unearned.

Pitchers do not hit. The designated hitter does not field. He cannot be moved to a position, and nobody else can be moved onto his spot. A pinch hitter or a pinch runner for anyone but the designated hitter has no position yet, and his club cannot throw a pitch until he is given one or replaced. Replacing the designated hitter makes the new man the designated hitter, and he needs no position.

The box score is computed from the log alone: the line score, the batting and pitching lines, runners left on base, errors, and the notation for a pinch hitter or a pinch runner. The E column counts reached-on-error charged to that club, and the note under the batting line names the fielders. The win, the loss, and the save follow MLB rules 9.17 and 9.19.

## Fatigue

Fatigue is the engine's own reason to empty the mound. It is separate from the constitution's innings limits, and it does not make the pitcher worse. His rates on the hundredth pitch are his rates on the first.

When a pitcher enters, the engine draws the line he can pitch to. The draw blends three numbers: a prior (95 pitches for a starter, 18 for a reliever), his pitches per appearance that season, and his career pitches per appearance. A season with fewer than 10 appearances leans on the prior. The blend is two thirds the regressed season and one third the career, then multiplied by 1.18 for a starter and 1.10 for a reliever. When the season and the career are both 102 pitches an appearance, the line is 120.

Age sets the window around that line. Through age 30 the window is 6 pitches either way. From 38 on it runs from 14 percent under the line to 4 percent over it. Ages 31 through 37 sit on a straight line between those two windows.

Each pitch then costs effort. An ordinary pitch costs 1, so the line is in pitch units. The cost depends on a leverage number the engine computes from the inning, the score, the outs, and how many runners are on:

| Situation | Effort per pitch |
| --- | --- |
| Leverage under 0.7, hitter under 85 wRC+ | 0.90 |
| Ordinary | 1.00 |
| Leverage 1.5 or more | 1.15 |
| Leverage 2.0 or more | 1.30 |
| Hitter 115 wRC+ or better, added on top of the row above | +0.10 |

The weak-hitter discount replaces the other rows. It is the mop-up price.

When the effort spent reaches the line, the engine pulls him and the mound is empty. He cannot be sent back out. The league then has to bring somebody in, and that somebody still has to pass the usage rules.

On top of the line, a computer-managed starter has a hook from the half plan. A quick hook pulls him at 85 percent of his line or at 4 runs. A normal hook pulls him at 95 percent or at 5 runs. A slow hook pulls him at 6 runs; at 100 percent of the line the engine has already emptied the mound on its own. If the hook wants him out and no legal reliever is available, he stays, and the log says so. A human starter stays until the manager, the fatigue line, or a usage limit takes him out. The hook is the computer's opinion. The line and the usage limit are rules.

## The constitution, during the game

The draft, the protection list, the V, A, and B levels, and the 75-man organization limit live in the rest of the site. They decide who a club owns. They do not change the odds of a pitch, and they are not re-checked between innings.

What the game itself enforces is who may be on the field today, and how much of his card he has left.

### The roster a game is played from

The active roster is the 30-man. Each half has two copies of it.

Home games use the 30-man the half opened with. That roster is frozen, so a call-up cannot be planned into a home game, and a player sent down can still play the home games he was on the opening roster for.

Road games use the 30-man as it stands. A club may make 10 roster moves in a half. A move is one player up and one player down, as a pair. The call-up stays on the 30-man for 15 road games or the rest of the half, whichever comes first. A move made while a road game is being played is available on the next pitch. That is also how a paused game gets a pitcher: call someone up who is still legal, or get an override.

A lineup is nine batters, each position filed once, no pitcher among them, and a catcher rating required at catcher. The plan files two of them, one against left-handed pitching and one against right-handed pitching. The day's lineup is the card that matches the opposing starter's throwing hand. An unknown starter, or a right-hander, uses the card against right-handers.

### The half plan

Before the half, each club files a plan: a rotation, the two lineup cards, a bench in order, a closer, single-inning relief (SIRP), multi-inning relief (MIRP), a bullpen usage, and a starter hook. Any day can be overridden until that day's game is opened: a spot starter, or a lineup for that day alone. Opening the game freezes both clubs' sheets for that game. Later edits to the plan do not reach it. Before the first pitch, the manager holding the seat can still set the lineup for this game from the game's roster. That change does not rewrite the plan.

A batter on the filed lineup who cannot play — he is past a cap, or he is not on this game's roster — is replaced from the bench, in bench order, when the game opens. The log records the reason. A computer starter who cannot start is replaced by the next legal pitcher in the rotation. A human starter who cannot start stops the opening. The manager spot-starts someone else on that day of the plan, then opens the game.

The computer manager does not have opinions beyond the plan. Every choice walks a list and takes the first player a legality check accepts. The players it skips, and the reason each was skipped, are written into the log.

- The starter is the one planned for the day. If he is illegal, the computer takes the next legal pitcher in rotation order after him, wrapping around.
- A reliever is chosen by the situation and by the bullpen usage on the plan. Traditional closer is the default. The closer works the 9th or later in a save situation as MLB rule 9.19 describes it (a lead of three or fewer with a full inning left to pitch, or the tying run on base, at bat, or on deck). SIRP works one inning from the 6th on when the game is within three runs either way. MIRP works before the 6th, or later when the game is not that close. Highest leverage, fireman, protect the lead, and save the pen move those same three columns earlier or later. The computer tries the group the situation calls for, then any group it has not tried yet, in the order multi-inning, single-inning, the closer, then any other pitcher on the game roster.
- At the start of a half inning, a reliever whose role no longer fits the inning gives way to an available arm who fits it.
- A bench replacement is the first legal player in bench order.
- A steal is attempted with a runner on first, second base open, and fewer than two outs. The runner is rolled once per stay on first, with probability equal to his card's attempt rate. The roll and the rate are in the log either way, sent or held.

A seat with a human in it makes these choices on the page. The computer runs the seats nobody took, and any seat a manager leaves.

### The usage ledger

Every plate appearance is counted, for the batter and the pitcher, in the same transaction that appends it to the log. The batter is checked before he is seated and before each of his plate appearances. The pitcher is checked before he enters and before each batter he faces. The check locks his season counter, so two live games cannot both spend the last of a cap.

The caps come from the card season, the same year the card's rates come from.

**Hitters.** His cap is his plate appearances from that season. At 500 at-bats or 550 plate appearances, he has no cap.

**Starts.** A pitcher with no starts on the card cannot start. One with starts gets the larger of his real starts and the row he qualifies for:

| At least this many card innings | Starts |
| --- | --- |
| 175 | 34 |
| 155 | 30 |
| 130 | 26 |
| 110 | 23 |
| 75 | 19 |
| 50 | 14 |
| under 50 | his real starts only |

**Season innings.** A pitcher who only started has no season innings cap. Each start still has a per-game limit. A pitcher who only relieved has an innings cap of his card innings, 1.25 times those innings at 60 or more, or 1.5 times at 70 or more, rounded down to an out. A pitcher who did both is a swingman, and his season cap is his actual card innings. The half plan names him rotation or bullpen. While he is bullpen only, and before he has started, he pitches against that reliever cap instead of his actual innings. His first start ends that. He cannot make that start once he has already pitched his actual innings.

**One outing.** The limit is 1.25 times his card-season innings per appearance, rounded up, and then clamped. A start is clamped between 4 and 9 innings. A relief outing is clamped between 1 and 3. A pitcher with five or more starts on his card keeps his starter's outing limit when he relieves. A card with no appearances of that kind gets the floor, 4 or 1.

**Rest, inside the series.** A season is 162 games. Each half is eight 4-game series against the other conference, eight 3-game series against the other division, and six 4-game division series, then one extra division game. Rest is counted in games of the series. A starter cannot start within three games of another start: in a four-game series, game 1 blocks games 2, 3, and 4. A reliever cannot pitch three games of the series in a row, and he cannot pitch the game before or the game after an outing of 30 or more pitches in that series.

A play that starts with room for one more out may record two or three, as a double play does. The extra outs count, and they are kept on the appearance as allowance. The next batter is where the limit stops him.

The page shows what is left on the card in front of the manager: plate appearances left, or starts left, season innings left, and innings left in this outing. A player who cannot be brought in is listed and disabled, with the reason beside his name.

When the pitcher on the mound reaches a limit, he has to come out. When nobody on the roster can legally face the next batter, the game pauses. The page shows why every arm was refused. Play resumes when a roster move provides a legal pitcher, or when the commissioner grants an override. An owner can request one from the paused game. The commissioner grants it for one player, one cap, one game, with a reason, and the grant is logged. The override makes that action legal. It does not erase the innings.

### The penalty lines

The ledger keeps a running measure of how far each player is past a season cap. The measure is the worst of his plate appearances, his starts, and his season innings.

More than 10 percent over, the player is ineligible for the playoffs, and the club loses its first-round AA pick. A second player over that line costs the club both of its first-round picks. More than 20 percent over, the player is a free agent at the next open draft, and the club is ineligible for the playoffs.

Per-game limits and rest are not these lines. They stop an outing unless an override covers that game. The penalty lines are the season caps, and an override that carries a player past one of them is how a club gets there. The game will allow the pitch. The standings carry the consequence.

## Playing one

A club plays its season from the half plan. The plan is who comes in when a person is not in the seat.

A manager opens his club's next unplayed road game, and only that game, and he sits the visiting side. Games go in schedule order. The home side is the home club's computer, playing the home club's frozen plan, so a manager's home games are played by the visitor. He can leave the visiting seat and the computer will finish from his own plan, and he can take that seat back. He can hand the game, or the rest of the series, to the computer. A series plays in schedule order and stops if a side runs out of legal pitchers.

The commissioner can autoplay any game that is not final. A sim tester can open any unplayed game and sit the visitor, the home side, or both. Everyone else plays the road.

The page is one column, meant to be played from a phone as well as a desk.

Before the game is open, it shows both clubs' planned starter and lineup, with a link to change that day in the plan. The form offers the seats that person may take. For a manager, that is the visiting side. Opening freezes both clubs' sheets for this game. Autoplay uses the same computer paths the seat does, and every handoff is a line in the log.

Once the game is open, the page shows who holds each seat. The scoreboard has the score, the half inning, the outs, and the runners. Under it are the two cards in the matchup. Each card shows the overall line and the platoon lines — plate appearances or batters faced, average, on-base, slugging for a hitter, and the strikeout, walk, and home-run rates — and the usage he has left. Under the cards are the eight probabilities of a straight plate appearance.

The manager holding a seat plays the next plate appearance with one button, and may set a call from the menu first. Between pitches he can change pitchers, pinch hit, pinch run, replace a fielder, or set positions. The designated hitter's position is fixed on that form. Before the first pitch he can rewrite the lineup. On a road game he can make the paired roster move.

Every form carries the log position it was drawn from. A second click, or a click from a tab that has fallen behind, changes nothing. If the engine is not answering, the page says so and writes nothing; the log is where it was.

The play-by-play under the forms is the log: the starters, each call, each computer decision and the players it skipped, each plate appearance with its count, each substitution, and the final. At the end, the box score replaces the buttons.

## Where the code is

| What | Where |
| --- | --- |
| The draw, the baserunning, the count | `engine/src/sim.rs` |
| Innings, substitutions, the fatigue pull, the extra-inning runner | `engine/src/game.rs` |
| The fatigue line and the effort table | `engine/src/fatigue.rs` |
| The engine's flat bunt | `engine/src/manager.rs` |
| The stateless HTTP routes | `engine/src/service.rs`, `engine/src/http.rs` |
| Django's client for those routes | `ulmg/engine_client.py` |
| Building a card from FanGraphs | `ulmg/cards.py` |
| The home field: scores, dimensions, the plate | `ulmg/park.py` |
| Caps, rest, overrides, penalties | `ulmg/usage.py` |
| The half plan and the frozen game sheet | `ulmg/plans.py` |
| The computer's starter, bullpen, hook, and steal | `ulmg/computer_manager.py` |
| Playing, checking, and logging one game | `ulmg/sim_game.py` |
| The 30-man, the freeze, and roster moves | `ulmg/roster_moves.py` |
| The box score, the win, the loss, the save | `ulmg/box_score.py` |
| The page | `ulmg/templates/game.html` |

`engine/src/governance.rs` is a review step a drawn result passes through. No rule is defined there, so it never redraws. The league rules are applied earlier, by refusing the plate appearance, or later, by the penalty lines.
