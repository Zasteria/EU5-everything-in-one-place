HRE fix 1.0.1 - Europa Universalis V 1.4

Removes the starting AI-only requirement to already have a CB against another
HRE member from the organization's war-legality trigger. This tests whether
that early check prevents AI war planning from reaching CB acquisition.

No replacement restriction is added early. Golden Bull retains its native
no-CB restriction when enacted. Native war costs, antagonism, internal-peace
policies, attack-desire rules and Parliament CBs remain unchanged.

Demand Unlawful Territory is disabled for both AI and player Emperors.
The action is hidden, its requirements always fail, and its AI checks are
disabled. Existing pending demands are invalidated without running acceptance
or rejection effects. Other HRE interactions remain native.

Enable HRE fix in the game's launcher mod list, then restart EU5 and load your
campaign. Community Mod Framework is not required. For an isolated test, use
this standalone mod without Playmaker Cabinet Queue, which includes the same
CB change and has its own HRE interaction override. This update changes only
the standalone HRE fix mod.

Source checks pass. AI war planning and pending-demand cancellation need
in-game testing.
