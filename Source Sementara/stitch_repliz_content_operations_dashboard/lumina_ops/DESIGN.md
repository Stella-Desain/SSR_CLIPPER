---
name: Lumina Ops
colors:
  surface: '#FFFFFF'
  surface-dim: '#dadad7'
  surface-bright: '#faf9f6'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#f4f4f0'
  surface-container: '#efeeea'
  surface-container-high: '#e9e8e5'
  surface-container-highest: '#e3e2df'
  on-surface: '#1a1c1a'
  on-surface-variant: '#424843'
  inverse-surface: '#2f312f'
  inverse-on-surface: '#f1f1ed'
  outline: '#737972'
  outline-variant: '#c2c8c0'
  surface-tint: '#4a6550'
  primary: '#000b03'
  on-primary: '#ffffff'
  primary-container: '#0b2515'
  on-primary-container: '#728e78'
  inverse-primary: '#b0ceb5'
  secondary: '#416900'
  on-secondary: '#ffffff'
  secondary-container: '#a9f93b'
  on-secondary-container: '#457000'
  tertiary: '#170208'
  on-tertiary: '#ffffff'
  tertiary-container: '#341720'
  on-tertiary-container: '#a77c87'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#ccead1'
  primary-fixed-dim: '#b0ceb5'
  on-primary-fixed: '#062011'
  on-primary-fixed-variant: '#324d3a'
  secondary-fixed: '#a9f93b'
  secondary-fixed-dim: '#8fdb17'
  on-secondary-fixed: '#102000'
  on-secondary-fixed-variant: '#304f00'
  tertiary-fixed: '#ffd9e1'
  tertiary-fixed-dim: '#eabac5'
  on-tertiary-fixed: '#2f131b'
  on-tertiary-fixed-variant: '#603d46'
  background: '#F8F9FA'
  on-background: '#1a1c1a'
  surface-variant: '#e3e2df'
  text-main: '#111827'
  text-muted: '#6B7280'
  border-subtle: '#E5E7EB'
  status-success: '#10B981'
  status-error: '#EF4444'
  status-warning: '#F59E0B'
typography:
  display-kpi:
    fontFamily: Inter
    fontSize: 32px
    fontWeight: '700'
    lineHeight: 40px
    letterSpacing: -0.02em
  headline-lg:
    fontFamily: Inter
    fontSize: 24px
    fontWeight: '600'
    lineHeight: 32px
    letterSpacing: -0.01em
  headline-md:
    fontFamily: Inter
    fontSize: 18px
    fontWeight: '600'
    lineHeight: 28px
  body-md:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 20px
  label-caps:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: '600'
    lineHeight: 16px
    letterSpacing: 0.05em
  label-sm:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: '500'
    lineHeight: 16px
  headline-lg-mobile:
    fontFamily: Inter
    fontSize: 20px
    fontWeight: '600'
    lineHeight: 28px
rounded:
  sm: 0.25rem
  DEFAULT: 0.5rem
  md: 0.75rem
  lg: 1rem
  xl: 1.5rem
  full: 9999px
spacing:
  base: 8px
  gap-bento: 16px
  margin-page: 24px
  padding-card: 24px
  sidebar-width: 260px
---

## Brand & Style

This design system is built for high-stakes B2B content operations, blending a "Premium Technical" aesthetic with the organizational clarity of a Bento Grid layout. It targets content directors and AI pipeline operators who require a tool that feels like a high-performance instrument—authoritative, precise, and sophisticated.

The visual direction follows a **Minimalist Bento** style:
- **Modular Precision:** Information is compartmentalized into clear, rounded containers that suggest a cohesive but multifaceted system.
- **Technical Sophistication:** A heavy emphasis on typography and white space over decorative elements, ensuring the data is the primary visual driver.
- **Intentional Contrast:** The pairing of deep, obsidian-like greens with surgical, high-visibility lime creates a hierarchy where action is never questioned and status is immediately understood.

## Colors

The palette is anchored by a high-contrast relationship between deep environmental tones and electric accents.

- **Primary Deep Green:** Reserved for high-level navigation and grounding elements. It provides a "dark mode" anchor even within a light-mode interface, lending a sense of stability and luxury.
- **Vibrant Lime:** This is the "functional" color. It is used exclusively for primary calls-to-action (CTAs), progress indicators, and active states. Its high luminance ensures it cuts through dense data.
- **Functional Neutrals:** We use a cool-toned background (`#F8F9FA`) to separate the pure white Bento cards, creating a subtle layered depth without relying on heavy shadows.

## Typography

The typographic system utilizes **Inter** for its neutral, highly legible character. 

The most critical rule for this design system is the application of **Tabular Figures** (`tabular-nums`) for all KPI values and data tables. This prevents "jitter" when numbers update in real-time, maintaining the structural integrity of the Bento Grid. 

Vertical hierarchy is established through a strict contrast in weights. Headlines are semi-bold to bold, while body text remains regular for maximum breathability. Labels use a slightly heavier weight at a smaller scale to remain distinct from body copy.

## Layout & Spacing

The layout is built on a **12-column Bento Grid** system with a fixed 8px baseline rhythm.

- **The Bento Grid:** Content is organized into discrete rectangular modules. Use a 16px gap between all modules. For desktop, the layout utilizes a fixed-width left sidebar for navigation and a fluid main content area.
- **Grid Density:** Cards should span 3, 4, 6, or 12 columns depending on content complexity. 
- **Responsive Behavior:** 
  - **Desktop (>1024px):** 12-column grid, 260px sidebar.
  - **Tablet (768px - 1023px):** 6-column grid, sidebar collapses to icons.
  - **Mobile (<768px):** Single column stack, 16px margins, headlines scale down to `-mobile` variants.

## Elevation & Depth

This design system favors **Tonal Layers** and **Low-Contrast Outlines** over heavy shadows to maintain a clean, technical feel.

- **Planes:** The base layer is the background color (`#F8F9FA`). The second layer consists of the white surface cards.
- **Shadows:** Use a single, highly diffused "Ambient Shadow" for cards: `0px 1px 3px rgba(0, 0, 0, 0.05)`. This creates just enough separation to suggest the cards are resting on the surface.
- **Borders:** Every Bento module must have a 1px solid border (`#E5E7EB`).
- **Interactive Depth:** On hover, a card may transition to a slightly deeper shadow or a subtle border color change to the Primary color at 10% opacity.

## Shapes

The shape language is defined by the **16px container radius**.

- **Large Containers (Bento Cards):** Use the `rounded-lg` (16px) setting to create the signature soft-but-structured Bento look.
- **Standard Components:** Buttons and input fields use the `rounded-full` or `rounded-md` (8px) setting depending on the context. Primary action buttons should always be pill-shaped (full) to distinguish them from the rectangular grid.
- **Media/Video Clips:** Thumbnails within the pipeline should follow the 8px radius to feel nested correctly within the 16px parent cards.

## Components

### Buttons
- **Primary:** Pill-shaped, Vibrant Lime background, Primary Green text. No border.
- **Secondary:** Pill-shaped, transparent background, 1px Primary Green border.
- **Icon Buttons:** Circular with subtle light gray backgrounds for secondary actions like "Edit" or "More."

### Bento Cards
- Every card must have a title in `headline-md`.
- Content should be padded by 24px on all sides.
- Use "Empty State" buttons within cards to ensure the interface is always actionable.

### KPI Modules
- Large tabular numbers in `display-kpi`.
- Include a "trend indicator" (up/down arrow) in the top right using `status-success` or `status-error`.

### Pipeline Progress
- Progress bars must use the Vibrant Lime for the fill and the subtle Border color for the track. 
- Use "Pulse" animations on the lime fill for active "Generating" states.

### Data Visualization
- **Strict Rule:** No pie charts for distribution data. Use horizontal bar charts with rounded caps to show distribution across social accounts.
- Use the Primary Green for the background of dark-themed components (like the Sidebar) to create a "Premium" anchor.