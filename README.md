# LuigiCasinoBot

A Discord bot for Luigi's Casino games, with Mario cards, a Luigi dealer, and the stacked DS screens.

## Games

The original games are Memory Match (`/casino_memorymatch`), Pair-a-Gone (`/casino_pairagone`), Picture Poker (`/casino_picturepoker`), Lucky Stars (`/casino_luckystars`), Mushroom Roulette (`/casino_roulette`), and Super Mario Slot (`/casino_slots`).

In Roulette, place your wager across up to five chips, then spin. Pictures pay x12, colors x2, splits x6, and corners x3. Undo and Clear let you move chips before spinning.

In Slots, stop each of the three reels. Superstars are wild. Three Superstars pay x20; stars x15; mushrooms or flowers x10; feathers or eggs x5. Two Superstars pay x4 and one pays x2 when there is no better match. Payouts include the original wager. Spins and reel stops are random; button timing doesn't affect the result.

### Challenges and new tables

| Command | How it plays | Coins |
|---|---|---|
| `/casino_memorymaster` | Memory Match with larger boards, opening hints, and a Known cards notebook. Clear boards to earn Stars; five mistakes end a board. | Free |
| `/casino_pairagone_endless` | Remove matching neighbors, including diagonals. Cards slide together and refill until you're stuck or finish the run. Each pair scores two points. | Free |
| `/casino_blackjack wager:20` | Hit, stand, double, or split after confirming an even wager. Six decks, dealer stands on soft 17, and blackjack pays 3:2. One same-rank split; split Aces get one card each. | Community wallet |
| `/casino_thrilling` | Two to four players see everyone else's card but their own. Bet, call, raise, or fold across five hands. | 75 practice chips each |
| `/casino_fortune_tower` | Bank the current offer or risk another row. Matching parent cards threaten the tower; Heroes and the Gate can save it. | Practice points |

Memory Master starts each run at zero Stars. Stars carry between boards and through pauses. Endless Pair-a-Gone expands its card pool every 50 removed cards. Blackjack allows doubling after a split, but has no insurance or surrender. Thrilling Cards caps each player's commitment at 15 chips per hand.

### Practice card games

| Command | How it plays |
|---|---|
| `/casino_tripletriad` | Place cards on a 3x3 board and capture neighbors with stronger edges. Open hands and equal starting sets. |
| `/casino_red7` | Play a card, change the winning rule, or do both. You must finish your turn ahead. Uses the seven Basic rules. |
| `/casino_scopa` | Capture matching values or sums from a 40-card deck. Score cards, coins, settebello, primiera, and sweeps. |
| `/casino_cuttle` | Play cards for points, attack your opponent's cards, or use their effects. Includes counter windows. |
| `/casino_platoon` | Split ten cards into five nonempty formations, predict a winner, and choose which formation to challenge. |
| `/casino_pazaak` | Build toward 20 with a ten-card side deck. Four modifiers last the whole match; first to three sets wins. |
| `/casino_war` | Higher card wins. A tie lets you surrender half the stake or double it and go to War. |

These seven games use practice points, not community coins. Omit `opponent` to play Luigi. All except Casino War also support a human opponent in a configured public channel. They must accept before the deal.

Use **My hand / play** for private controls, then **Confirm move** to submit your choice. **Rules** explains each game's variant; **Details** shows the full readable state.

## Playing and resuming

Use `/casino` to configure public game channels. Thrilling Cards requires a public channel; hand views and betting controls stay private. The `animations` option overrides your saved animation preference for that table.

Saved games resume through the same command. For Thrilling Cards and the seven practice tables, pass `table:<saved-id>`. Moves are saved before images are sent, so a failed upload or repeated click won't replay a move or payout.

After eight idle minutes, Memory Master and endless Pair-a-Gone pause, Blackjack stands, and Fortune Tower banks. The seven practice tables also pause after eight minutes. Invitations expire after two minutes. In Thrilling Cards, an idle turn folds after 90 seconds. Rules, Details, and Refresh don't extend these timers.

## Saved data

Blackjack rounds and balances live in MongoDB. Challenges and practice matches use SQLite at `CASINO_SESSION_DB`, which defaults to `data/casino_sessions.sqlite3`.

Keep that database when updating the bot. Docker Compose gives dev, stage, and prod separate data volumes mounted at `/app/data`. Deleting a volume deletes its saved sessions. Run one bot process per environment.

## Tests

```sh
python -m pytest tests -q
```

The suite uses mocked Discord and Mongo calls, real SQLite storage, and rendered images. The separate `src/economy/test_mongo.py` script requires a running database.
