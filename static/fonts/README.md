# Font Download Instructions

This application requires the following fonts for local/air-gapped use.

## Required Font Files

### 1. Pretendard (Korean Variable Font)
**Download from:** https://github.com/orioncactus/pretendard/releases

1. Download `Pretendard-1.3.9.zip` (or latest version)
2. Extract the ZIP file
3. Navigate to `public/variable/` folder
4. Copy `PretendardVariable.ttf` to `static/fonts/pretendard/`

**Place as:** `static/fonts/pretendard/PretendardVariable.ttf`

---

### 3. Bricolage Grotesque (Variable Font)
**Download from:** https://fonts.google.com/specimen/Bricolage+Grotesque

1. Click "Download family" button
2. Extract the ZIP file
3. Copy `BricolageGrotesque-VariableFont_opsz,wght.ttf` to `static/fonts/bricolage-grotesque/`
4. Convert to WOFF2 format (see conversion instructions below) OR rename to `.woff2`

**Direct variable font file:**
- Place as: `static/fonts/bricolage-grotesque/BricolageGrotesque-VariableFont_opsz,wght.woff2`

### 4. Plus Jakarta Sans (Variable Font)
**Download from:** https://fonts.google.com/specimen/Plus+Jakarta+Sans

1. Click "Download family" button
2. Extract the ZIP file
3. Copy from the `variable` folder:
   - `PlusJakartaSans-VariableFont_wght.ttf`
   - `PlusJakartaSans-Italic-VariableFont_wght.ttf`
4. Convert to WOFF2 format

**Place as:**
- `static/fonts/plus-jakarta-sans/PlusJakartaSans-VariableFont_wght.woff2`
- `static/fonts/plus-jakarta-sans/PlusJakartaSans-Italic-VariableFont_wght.woff2`

### 5. IBM Plex Mono
**Download from:** https://fonts.google.com/specimen/IBM+Plex+Mono

1. Click "Download family" button
2. Extract the ZIP file
3. Copy these files:
   - `IBMPlexMono-Regular.ttf`
   - `IBMPlexMono-Medium.ttf`
   - `IBMPlexMono-SemiBold.ttf`
4. Convert to WOFF2 format

**Place as:**
- `static/fonts/ibm-plex-mono/IBMPlexMono-Regular.woff2`
- `static/fonts/ibm-plex-mono/IBMPlexMono-Medium.woff2`
- `static/fonts/ibm-plex-mono/IBMPlexMono-SemiBold.woff2`

---

## TTF to WOFF2 Conversion

If you downloaded TTF files, convert them to WOFF2 for better compression:

### Option 1: Online Converter (requires internet)
- https://cloudconvert.com/ttf-to-woff2
- https://www.fontsquirrel.com/tools/webfont-generator

### Option 2: Command Line (requires woff2 tool)
```bash
# Install woff2 tools (on Ubuntu/Debian)
sudo apt install woff2

# Convert TTF to WOFF2
woff2_compress font.ttf
```

### Option 3: Use TTF directly
If WOFF2 conversion is not available, you can modify `fonts.css` to use TTF:

Change:
```css
src: url('./bricolage-grotesque/BricolageGrotesque-VariableFont_opsz,wght.woff2') format('woff2');
```

To:
```css
src: url('./bricolage-grotesque/BricolageGrotesque-VariableFont_opsz,wght.ttf') format('truetype');
```

---

## Directory Structure After Setup

```
static/fonts/
├── fonts.css
├── README.md
├── pretendard/
│   └── PretendardVariable.ttf
├── bricolage-grotesque/
│   └── BricolageGrotesque-VariableFont_opsz,wdth,wght.ttf
├── plus-jakarta-sans/
│   ├── PlusJakartaSans-VariableFont_wght.ttf
│   └── PlusJakartaSans-Italic-VariableFont_wght.ttf
└── ibm-plex-mono/
    ├── IBMPlexMono-Regular.ttf
    ├── IBMPlexMono-Medium.ttf
    └── IBMPlexMono-SemiBold.ttf
```

---

## Verification

After placing the font files, start the application and check the browser's Developer Tools (F12) → Network tab to ensure fonts are loading without errors.
