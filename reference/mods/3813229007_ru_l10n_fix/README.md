# Russian Localization Fix (Community Mod Scaffold)

This directory (`ru-l10n-fix/`) contains the mod package that overrides broken localization strings and data bindings in the official Europa Universalis V Russian localization.

---

## 1. Directory Structure

Per the official [Europa Universalis V Modding Documentation](https://eu5.paradoxwikis.com/Mod_structure), EU5 uses a 3-stage modular loading architecture (`loading_screen`, `main_menu`, and `in_game`).

To override specific localization keys without shadowing or wiping out the 100,000+ vanilla lines, all `.yml` override files **must** reside in the `replace/` subfolder with unique filenames:

```
ru-l10n-fix/
├── .metadata/
│   ├── metadata.json                                   # Required EU5 mod metadata descriptor
│   └── thumbnail.png                                   # Mod preview thumbnail (512x512)
├── main_menu/
│   └── localization/
│       └── russian/
│           └── replace/                                # Key override folder (avoids PhysFS file-shadowing)
│               ├── ru_l10n_fix_interfaces_l_russian.yml  # Fixes SOCVAL_ONE_SIDE ($NAME|Y$), loan repayment, UI scopes
│               ├── ru_l10n_fix_effects_l_russian.yml     # Fixes societal values effect macros
│               ├── ru_l10n_fix_government_l_russian.yml  # Fixes societal values government actions & parliament
│               ├── ru_l10n_fix_parliament_l_russian.yml  # Fixes parliament agenda & debate localization
│               ├── ru_l10n_fix_economy_l_russian.yml     # Fixes unclosed bracket syntax errors
│               ├── ru_l10n_fix_messages_l_russian.yml    # Fixes [[ double-bracket crash
│               └── ru_l10n_fix_international_organizations_l_russian.yml # Fixes VOTE_OF_COUNTRY and IO parliament scopes
└── in_game/
    └── common/
        └── customizable_localization/
            └── ru_l10n_fix_custom_loc.txt              # Scripted custom loc fix for end_predlog_sso
```

---

## 2. In-Game Mod Architecture & Activation

Unlike older Paradox titles, **Europa Universalis V does not have an external Paradox Launcher (`dowser.exe`)**. Mod and DLC management is built directly into the game's engine:

1. **Local Mod Discovery**:
   - The game scans `%USERPROFILE%\Documents\Paradox Interactive\Europa Universalis V\mod\<mod_name>\`.
   - The engine validates `.metadata/metadata.json`. If missing or invalid, the game will error or ignore the mod.
   - Discovered mods appear automatically in the in-game **Local Mods** catalog.

2. **In-Game Playset Management**:
   - In the EU5 Main Menu, open **"Модификации и дополнения"** (`MAIN_MENU_MODS_AND_DLCS`).
   - Select or create a playset (e.g., "Initial playset").
   - Find **"Russian Localization Fix"** under Local Mods and enable its toggle checkbox.
   - When prompted that the mod modifies the checksum, confirm/continue (standard Paradox behavior).
   - Click Save/Apply. The engine saves the playset state directly to:
     `C:\Users\<user>\Documents\Paradox Interactive\Europa Universalis V\playsets.json`.

---

## 3. Automated Validation & Deployment

From the WSL workspace repository:

- **Validate files and structure**:
  ```bash
  npm run validate
  ```
  *Verifies top-level 3-stage directories, `.metadata/metadata.json` schema, `replace/` directory placement, UTF-8 BOM (`\ufeff`), and bracket balance across all localization files.*

- **Deploy to Windows User Documents**:
  ```bash
  npm run deploy
  ```
  *Performs a clean sync of the mod tree to `C:\Users\irksa\Documents\Paradox Interactive\Europa Universalis V\mod\ru-l10n-fix`.*
