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
