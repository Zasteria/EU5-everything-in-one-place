# Community Fixes v1.3.0 - test guide (2026-08-19)

Nine new pillars, all built and file-verified, ZERO in-game tested.
Map modes deferred (needs a live probe, not in this build).

## Setup (do this first, game closed)

1. Junction the mod into the Paradox mod folder:
   ```
   cmd /c mklink /J "%USERPROFILE%\Documents\Paradox Interactive\Europa Universalis V\mod\community-fixes" "T:\responsive-universalis\submods\community-fixes"
   ```
2. Launch EU5 with `-tdebug` (Steam launch options).
3. Playset: enable Community Fixes v1.3.0 (check the version shows 1.3.0 -
   proves the junction, not the Workshop copy, is loading). Family load
   order as usual, CF after the main mod.
4. Start a FRESH campaign (any country with neighbors to fight; a small
   Ireland/Italy minor works well for the siege test).
5. Before playing: tell Claude "check error.log" - acceptance is ZERO
   mod-attributable distinct lines vs the 17-line vanilla baseline.
   Nothing below matters until this passes.

## Priority tests (concrete, in rough order of importance)

### 1. Garrison sortie (the big one)
- Declare war on a neighbor that has a fort. Siege it with a deliberately
  TINY army: 1-2 regiments against a garrison of 1000+ (hover the fort
  icon for the garrison number).
- EXPECTED: within ~14 game-days the garrison marches out and attacks
  your besiegers (a field battle starts, garrison side is the attacker).
- Then the control: siege the same fort with a proper army clearly bigger
  than 1.5x the garrison. EXPECTED: no sortie, siege proceeds normally.
- Watch for the failure direction: garrisons sortieing into battles they
  LOSE (fort falls instantly to the besieger). If you see that, say so -
  the threshold dial goes from 1.5 toward 2.0.

### 2. Parliament cooldown
- Call parliament, finish or dissolve it. Hover the call-parliament
  button. EXPECTED: available again in ~12 months, not ~5 years.

### 3. Inflation action
- Open cabinet actions, hover "Reduce Inflation".
- EXPECTED: tooltip shows -0.001 monthly inflation (vanilla -0.00025).

### 4. Estate loans (the insta-bankruptcy fix)
- Open the loans screen with no credit automation enabled.
- EXPECTED: estate loan offers roughly double what you are used to, and
  no offers below 5 ducats. If you can push a poor country toward
  deficit: the game should absorb a bad month with an estate loan
  instead of tipping straight into bankruptcy.

### 5. Peace costs
- In any war, open the peace screen and hover a province.
- EXPECTED: war score prices about a quarter lower than you are used to.

## Feel tests (no pass/fail, just report impressions)

- **AI peace**: does a losing AI (warscore around -35 to -40) offer or
  accept peace instead of dragging to -50? Do near-ideal deals get
  accepted without months of spam?
- **War exhaustion**: do lost battles visibly move exhaustion more?
  (Weakest-sourced pillar - if it feels wrong, it gets reverted first.)
- **Reinforcement/mercs**: units refill a bit faster after battles; merc
  pools recover over months (long-horizon, low priority).
- **Carpet sieges**: AI wars should show fewer, larger siege stacks
  (max 6 armies per carpet operation, was 10).

## Optional: fort garrison inflator for sortie testing

If no convenient big-garrison fort exists, put this in
`Documents/Paradox Interactive/Europa Universalis V/run/garrison_test.txt`
(replace the location key), then console: `run garrison_test.txt`:

```
location:corbeil = { set_garrison_size = 2000 }
```

(set_garrison_size is a proven engine effect, usage doc from the exe.)

## Teardown (after the session)

Remove the junction so the mod folder is empty again (MP checksum rule):

```
cmd /c rmdir "%USERPROFILE%\Documents\Paradox Interactive\Europa Universalis V\mod\community-fixes"
```

## After testing

Report per-pillar: pass / fail / feel. Claude greps error.log again,
fixes what needs fixing, regenerates, and only after your word does
v1.3.0 go to the Workshop (standing rule: no push without verification).
