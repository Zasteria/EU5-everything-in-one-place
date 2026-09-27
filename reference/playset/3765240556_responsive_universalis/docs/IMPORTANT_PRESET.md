# "Important Only" preset - exact contents

Applied by the **Important Only** button in the message settings screen (Message Presets mod).
Matching is by the settings-row label (`<KEY>_SETUP` localization); lists live in
[`tools/build_message_presets_gui.py`](../tools/build_message_presets_gui.py) - edit there and re-run the script to change the preset.

## Popup + log + map icon (22 types)

| Key | Meaning |
|---|---|
| DECLWAR | War declared on us |
| DECLWAR_ON_SUBJECT / DECLWAR_ON_UNION | War declared on our subject / union partner |
| DECLWAR_WE_JOIN / DECLWAR_AS_SUBJECT / DECLWAR_AS_UNION / DECLWAR_WE_AID | We are pulled into a war |
| WEDECLWAR | We declare war |
| COUNTRY_JOINED_WAR_AGAINST_US | A country joins the war against us |
| PEACEACCEPT / PEACEWEACCEPT | Peace offer accepted (ours / we accept) |
| PEACEACCEPTOTHER_ALLY | Our ally makes peace |
| WHITEPEACEWE | We white-peace |
| UNCONDITIONALSURRENDER_WE_SURRENDERED / …_THEY_SURRENDERED | Unconditional surrender (us / them) |
| MILALLHONOR / MILALLDISHONOR | Ally honors / dishonors the call to arms |
| CIVILWAR_STARTS / CIVILWAR_WON / CIVILWAR_WON_REBELS | Civil war in our country starts / is won / rebels win |
| REGENCY | Regency begins (succession-critical) |
| IMPORTANT_CHAR_DEATH | Important character dies |

## Log only - no popup (16 types)

Your battles and sieges: SIEGEUS, SIEGEOVER_WON, SIEGEOVER_LOST, OCCUPATION_START_US, ATTACKUS, NAVALATTACKUS, ARMYDEAD, SHIPSUNK.
Context awareness: DECLWAROTHER (wars between others), PEACEACCEPTOTHER, PEACEREJECT, PEACEWEREJECT, CIVILWAR_STARTS_OTHER, WE_ABANDON_CIVIL_WAR, THEY_ABANDON_CIVIL_WAR, OUR_SUBJECT_IS_GETTING_ATTACKED.

## Everything else

All other ~800 configurable message types: log, popup, pause and map icon **off** (diplomat movements, foreign actions, trade/construction noise, etc.).

## Notes

- Bankruptcy and our-country disasters are **not message types** in EU5 - they arrive as events/alerts and are unaffected (they always show).
- Pause-on-message is turned off by every preset; re-enable per-type manually if wanted.
- Presets only stage the checkboxes - click **Save & Close** to persist, or Cancel to abort. Vanilla **Reset to Default** restores factory settings.
- Clear the search filter before applying a preset (a filtered list only applies to visible types).
