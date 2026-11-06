# Machine-specific wallpapers

- **mini-mecha:** original `backgrounds/.config/backgrounds/tolkien/mordor.jpg`.
  It still uses `hyprland-common/.config/hypr/hyprpaper.conf`; the image is unchanged.
- **oki-mecha:** `backgrounds/.config/backgrounds/tolkien/mordor-atelier-5k.png`,
  selected by `hyprland-oki-mecha/.config/hypr/hyprpaper-oki-mecha.conf`.

The new image is a text-free, dark Lord of the Rings-inspired Mordor landscape
with two hobbits, Barad-dûr and Mount Doom. Neutral graphite/charcoal with localized
amber/burnt-orange firelight complements Atelier Amber without purple/pink lighting.
It is an AI-generated **5120×2880 PNG export**, upscaled with Lanczos from the
generator's **1672×941** output and cropped very slightly to exact 16:9. It is not
native 5K detail. The original generated file is not required at runtime.

Each machine's Hyprland profile sets `ATELIER_WALLPAPER_CONFIG`. The shared startup
uses it to start Hyprpaper, falling back to the original shared config if unset.
This avoids changing the shared default or moving existing Stow-owned files.
`fit_mode = cover` applies to every output on the chosen machine.

For a new machine / after pulling these changes:

```sh
HYPR_MACHINE=oki-mecha ./setup.sh backgrounds hyprland
# Or HYPR_MACHINE=mini-mecha for the unchanged original wallpaper.
./check-setup.sh --machine oki-mecha backgrounds hyprland
```

The profile package includes its wallpaper config, and the backgrounds package
includes the asset. Changing a profile is persistent at the next session start;
reloading Hyprland alone does not restart an already-running Hyprpaper process.
Only Hyprpaper was restarted to apply the new wallpaper in the current oki session.
Hyprlock's Balrog background and the root-owned ReGreet wallpaper are unchanged.
