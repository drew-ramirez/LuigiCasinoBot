# LuigiCasinoBot

A Discord bot that recreates Luigi’s Casino games from Mario 64 DS.

## Roulette, slots, and DS artwork

- `/casino_roulette`: place up to five coins from your fixed wager on pictures/colors/splits/corners, then Spin. Menus name the pictures; the board has no added numbers. Undo and Clear move existing coins without charging again. Gross returns are x12/x2/x6/x3 respectively.
- `/casino_slots`: Super Mario Slot, with three independently stopped reels. Wild Superstars substitute for matching symbols; the best matching payout wins. Three Superstars return x20, stars x15, mushrooms/flowers x10, feathers/eggs x5; two Superstars return x4, otherwise one Superstar returns x2. Returns include the wager.
- Both games honor animation preferences, private/public game mappings, the wallet and metrics. A wager is deducted once; idle sessions forfeit it. Use Play again for a new wager.
- This is a Discord adaptation with uniformly random pockets/symbols and random reel stops (button timing is not a skill input). Original DS reel frequencies were not established. Roulette now uses five coin placements, two stacked native DS screens, alternating-color reference wheel textures, an overhead-to-tilted camera cut, a ball tied to the actual payout pocket, and a Luigi result scene. The fixed total wager is divided among five chips (or fewer for wagers under five); all chips must be placed before spinning. The reference video was inspected in-browser at the betting, spin, dealer/payout and slot phases. The wheel animation uses cropped reference textures and projected geometry, not the original 3D engine.
- Shared felt boards, Picture Poker HOLD/HIT markers and result/rank labels use extracted DS sprites. The artwork and extraction atlas are in `src/assets/casino`.
- Reference rules: https://www.mariowiki.com/Mushroom_Roulette and https://www.mariowiki.com/Super_Mario_Slot . The supplied sheet contains the slot payout chart.
- Restart the bot to load and sync the new slash commands. No live bot restart or command sync is performed by the offline tests.

Card-game visuals use the stacked DS presentation for Memory Match, Pair-A-Gone, Picture Poker and Lucky Stars. Animation-enabled starts include the moving casino room; event GIFs play once.

## Saved challenges and new tables

| Command | Decisions and progression | Currency |
|---|---|---|
| `/casino_memorymaster` | Advanced Memory Match: 16/18/20 cards, 4/6/8 opening hints at 0/5/10 Stars; five mistakes end a board. Clear adds one Star, failure removes one with a zero floor. Next board, Known cards, Pause, Resume and Finish. | Free; personal score only |
| `/casino_pairagone_endless` | Pair-a-Gone and On: 20 face-up cards, immediate matching neighbours including diagonals, survivor compaction and endless refill. Pause preserves the draw order; stuck or voluntary finish saves the score once. | Two points per removed pair; no coins |
| `/casino_blackjack wager:20` | Confirm an even wager, then hit, stand, double or split. Six fresh decks, dealer stands on soft 17, natural pays 3:2 profit, one same-rank split, double after split, one card per split Ace. No insurance or surrender. | Existing community wallet |
| `/casino_thrilling` | Public 2–4-human lobby. Join and Ready, then five rotating hands. Each private view hides its owner's card and shows the others. Open 1–5, call, fold or raise 1–5; at most two raises. | 75 practice chips per seat; maximum 15 per hand; conserved pot |
| `/casino_fortune_tower` | Diamond practice: bank the current offer or risk another row. Touching-parent matches threaten the tower; Heroes protect rows and the Gate can rescue a hazard. New offers may fall. | Virtual practice points only |

The existing six games remain available. New solo commands honor configured public/private channels and the player's animation preference; their optional `animations` parameter overrides that preference for the current view. Use the existing `/casino` configuration commands to map each new game. Thrilling Cards requires a configured public channel; its card inspection and action controls are ephemeral, never unsolicited DMs.

Memory hints and later revealed cards remain knowable through the Known cards notebook and saved media. These are assistance-tolerant personal records, not an enforced unaided-memory competition. New Memory Master runs start at zero Stars; Stars persist across boards and pauses within a run.

Endless Pair-a-Gone uses an explicitly labelled bot progression: expand the refill pool every 50 removed cards, consuming the current saved batch before introducing the expanded four-of-each batch. Original symbol thresholds, distribution and exact movement ordering remain unverified. No rescue shuffle preserves a stuck run. Its score counts removed cards, not successful clicks.

Thrilling Cards uses bounded Discord house rules for ante, raises and five-hand sessions. Cards rank 2 through Ace, with clubs < diamonds < hearts < spades breaking equal ranks. Only eligible showdown cards become public; a fold win reveals none. Friends can share private screenshots, so it is trust-based practice play. Every result conserves chips; there is no separate winner bonus.

Fortune's Tower uses the 60-card Diamond deck (eight each of 1–7, four Heroes), with a 30-point practice stake. Exceptional cases are declared house conventions: resolve hazards left-to-right, a Hero Gate protects its replacement row, retain the highest set multiplier, and include an unused Gate in the final jackpot. Gross points are `stake / 15 × value × multiplier`; net subtracts the stake. These are not verified original payout/RTP claims, and the mode never touches the wallet.

### Recovery and timeouts

Accepted states are saved before rendering. Duplicate/stale controls cannot repeat a draw, payout or final score. Failed images fall back to the same saved text state; rerun the command after an unavailable Discord response to recover. Public media receives only the information allowed for that viewer.

Solo controls expire after eight minutes of inactivity: Memory Master and endless Pair-a-Gone pause, Blackjack stands all unresolved hands, and Tower banks the current offer. Reopen the command to recover the same table. A new Blackjack deal always requires an explicit wager confirmation or Play again; split/double funding is checked atomically, and all displayed returns include any returned stake.

Thrilling lobbies expire after two minutes; an inactive turn folds after 90 seconds. Rules/Refresh do not extend that clock. After a restart or failed public publication, run `/casino_thrilling table:<saved-id>` to resume the same hand. Completed hands remain settled; departures forfeit committed chips. Timers begin only after a usable public table is delivered. Process downtime pauses deadlines rather than simulating unattended turns.

### Durable storage and offline checks

Blackjack rounds and wallet changes are stored atomically together in the existing Mongo user document. Challenge sessions, finalized personal records and practice matches use `CASINO_SESSION_DB`, defaulting to `data/casino_sessions.sqlite3`. Keep that database when updating the bot. Compose mounts separate `casino-dev-data`, `casino-stage-data` and `casino-prod-data` volumes at `/app/data`; removing those volumes deletes saved practice/challenge sessions. Use one running bot process per environment for message/timer coordination.

Run the offline suite with `python -m pytest tests -q`. On machines with an inaccessible system pytest temporary directory, first create `data`, then pass a fresh `--basetemp=data/test-run` path. The tests mock Discord and Mongo writes, exercise real SQLite recovery/concurrency, and inspect actual Pillow output. They do not log in, sync slash commands, restart the live bot or perform a live Mongo integration test. The separate `src/economy/test_mongo.py` diagnostic requires a database and is outside this offline suite.


## Seven more practice card games

| Command | Complete game and selected rules |
|---|---|
| `/casino_tripletriad` | Basic/Open three-by-three capture game. Both players receive the same five original cards; stronger facing edges capture, without Same/Plus/combo rules. Unplayed cards count in the final score. |
| `/casino_red7` | Red7 Basic v1.2, one round: play a palette card, change the rule, or do both. Seven scoring rules and number/color tie breaks; menus offer complete winning turns. No advanced action cards or multi-round scoring. |
| `/casino_scopa` | One full forty-card deal, using French suits with diamonds as coins. Equal-card capture takes priority over sums; score cards, coins, settebello, primiera and sweeps. No sweep on the final play. |
| `/casino_cuttle` | Classic card combat with points, scuttles, permanents, one-off effects and explicit counter windows. Queens protect, Kings lower the victory threshold, and three consecutive passes end a stalemate. The rules follow the classic FAQ/Pagat variant. |
| `/casino_platoon` | Arrange ten cards into five formations, lock them, predict a winning slot and select battles. King/Bishop/Wizard effects and three battle credits decide one campaign. Declared practice conventions: standard 52 plus two Wizards, one Wizard per formation, tied opener redraw, drawn battles count against the challenger. Predictions measure accuracy; no original chip ladder. |
| `/casino_pazaak` | Configure ten side cards, draw four modifiers for the entire match, then win three sets closest to 20. One modifier per turn, including negative-card bust rescues. Declared practice conventions: free ±1–6 catalogue with two copies per kind, uniform replacement draws from 1–10, random first opener/alternating later openers, and immediate safe-nine-card win. |
| `/casino_war` | Six-deck dealer game with a fixed 20-point practice stake. Initial win returns 40 gross; tie offers surrender (10 returned) or War (40 total committed, burn three cards). War win returns 60, repeated tie 80, loss zero. Returns include the returned stake. |

All seven use personal practice results and never charge or credit community coins. Liar's Dice is not included. The existing dealer artwork remains unobstructed; game names and status appear in Discord text rather than added image banners.

Omit `opponent` to play against Luigi. The first six commands also accept a human `opponent` in a configured public casino channel; the opponent must explicitly accept before any cards are dealt. Public messages expose only legal shared information. My hand / play opens an ephemeral view, with grouped and paginated choices followed by **Confirm move**. Triple Triad deliberately uses open hands; Cuttle's Eight can reveal an opponent's hand under its rules. Private screenshots can be shared, so these remain trust-based practice games.

Use Rules for the exact selected variant and Details for the complete readable state. `animations` overrides the existing preference. Map the games through the existing `/casino` configuration commands. An image or attachment failure falls back to the same saved text without replaying a move.

Both players can pause, resume or confirm a concession. Invitations expire after two minutes; eight minutes of inactivity pauses a dealt match without forfeiting it. Reopen the original command with `table:<saved-id>` after a restart, pause or failed delivery. Rules, Details and Refresh do not extend the deadline. A saved confirmed move includes Luigi's reply; stale or duplicate controls cannot repeat either. Existing SQLite persistence and the single-bot-process requirement apply to these tables too.


### Card artwork and visual sources

All twelve expansion modes share the existing Mario card frames and portrait proportions. `src/casinogames/mario_cards.py` crops the original frame and character/power-up sprites from the existing `src/assets/cardart/cards.gif`; memory faces and backs retain their existing loaders. Red7 uses seven saturated fields with redundant letter/number identifiers, Pazaak uses signed values, and standard cards retain their true ranks and suits alongside decorative Mario portraits. Red Kings use Mario and black Kings use Bowser; this does not change suit or rank rules. Crowded hands and formations fan or stack complete cards instead of stretching them. No new external card-art pack was installed.

For additional artwork, [Kenney's CC0 pixel playing-card pack](https://kenney.nl/assets/playing-cards-pack) and [Adrian Kennard's CC0 SVG/PDF decks](https://www.me.uk/cards/) are practical reusable sources. [The original Luigi sprite sheet](https://www.spriters-resource.com/ds_dsi/supermario64ds/asset/6853/) and [FFVIII Triple Triad card atlas](https://www.spriters-resource.com/playstation/finalfantasy8/asset/35819/) are obtainable game-art references, not open-license packs. [Asmadi's Red7 rulebook](https://asmadigames.com/rules/Red7_Rules.pdf) and [the official KOTOR manual](https://store.steampowered.com/manual/32370) guide each game's visual identity. These references do not replace the implemented rules or establish blanket redistribution rights. No verified ready-to-use White Witch Platoon card atlas was found in this research pass.
