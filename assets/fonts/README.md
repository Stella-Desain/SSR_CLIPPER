# Bundled caption fonts

`PodcastBlack.ttf` is the weight-900 static instance of Montserrat from the
[Google Fonts source](https://github.com/google/fonts/tree/main/ofl/montserrat).
Its SIL Open Font License is included as `Montserrat-OFL.txt`.

The renderer scales the glyphs to the measured reference caption proportions.
Bundling the font avoids platform-dependent system-font substitutions. The font
is a close visual match, not a verified identification of the reference font.

`RobotoVariable.ttf` is the unmodified Roboto variable font from the
[Google Fonts source](https://github.com/google/fonts/tree/main/ofl/roboto).
The SIL Open Font License is included as `Roboto-OFL.txt`.
SHA-256: `d7598e12c5dbef095ff8272cfc55da0250bd07fbdecbac8a530b9b277872a134`.
Tegas 4:3 uses its regular weight; Sinematik 16:9 uses Montserrat Black.
Both render captions as bitmaps, without requiring installed system fonts.
