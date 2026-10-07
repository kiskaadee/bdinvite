# Digital Invitation — Frontend Specification

## 1. Purpose

A responsive, mobile-first digital birthday invitation that reproduces the visual character of a physical invitation while adding an interactive RSVP flow.

The application has two distinct experiences:

### Guest Experience
A highly designed invitation served publicly at `/birthday/`, consisting of:
1. **Invitation hero**: Fixed-aspect-ratio vertical composition with animated golden bokeh particles, title, honoree, date/time, and RSVP call-to-action
2. **RSVP form**: Name, phone, and optional email fields matching the invitation's visual world
3. **Submission feedback**: Explicit semantic feedback (Success, Duplicate, Error)
4. **Event reminder & logistics**: Countdown timer to the event, circular map preview, venue details, and navigation link

### Admin Experience
A simple dashboard served at `/birthday/admin` (Authelia-protected) allowing the event organizer to:
1. View invitee responses in a searchable table
2. Monitor response count
3. Export responses as CSV
4. Edit invitation copy and event logistics via a form with live text preview

The guest experience is the primary design focus. The admin dashboard deliberately does **not** use the invitation's visual effects.

---

## 2. Design Principles

### 2.1 The Invitation is a Physical Object (Section-Based Composition)
The invitation hero maintains a fixed vertical aspect ratio (9:16) regardless of viewport width. The browser provides a responsive **stage** around it on wider screens.

The page itself is a scrollable viewport composed of discrete sections:
```text
PAGE (Scrollable Viewport)
│
├── Invitation Hero Section (Fixed vertical aspect ratio, desktop stage)
│
├── RSVP Section (Revealed via CTA click, matching visual world)
│
└── Confirmation Section (Replaces RSVP on success; countdown + logistics)
```

The invitation hero itself is **not** an overflow-scrolling container. The page scrolls smoothly across these visual sections, maintaining balanced compositions within each viewport.

```text
Desktop Stage
┌────────────────────────────────────────────┐
│                                            │
│          ┌──────────────────┐              │
│          │                  │              │
│          │   INVITATION     │  (9:16 card) │
│          │      HERO        │              │
│          │                  │              │
│          └──────────────────┘              │
│                                            │
└────────────────────────────────────────────┘
```

On mobile, the section expands to occupy the available width while preserving vertical proportions.

---

### 2.2 One Visual Composition
There are not separate mobile and desktop invitation designs. The visual card scales responsively within the viewport. Desktop provides surrounding staging; mobile provides full viewport width to the invitation.

---

### 2.3 Decoration Must Not Interfere with Information
The animated particle background is subordinate to content:
- Particles concentrate toward upper-left and lower-right corners
- The central content area remains substantially darker and sparse
- Movement is extremely slow (ambient life, not spectacle)
- Particles vary in radius, opacity, and soft golden blur
- Never compromises text readability

---

### 2.4 The RSVP Interaction is Part of the Invitation
The RSVP form and confirmation states inherit the invitation's visual identity:
- Dark background (`#0a0a0a`)
- Golden accents (`#d4a843`, `#f0d68a`)
- Typography system
- Ambient particle canvas spanning the entire page behind all sections

---

### 2.5 Content is Configuration, Not Code
Event-specific copy is never hardcoded in presentation components:
- Fetched on load from `GET /birthday/api/config`
- Admin can modify event details dynamically without rebuilding the frontend

---

### 2.6 Explicit Configuration Loading & Error States
Before rendering the invitation, the frontend manages configuration lifecycle explicitly:

```text
CONFIG_LOADING
      │
      ├── success ──────→ INVITATION
      │
      └── failure/error ─→ CONFIG_ERROR
```

If the API fails to load or returns invalid data:
- Renders a graceful fallback:
  > **No pudimos cargar la invitación.**  
  > Inténtalo nuevamente.
- Includes a retry button
- Never exposes broken components or undefined text values to the guest

---

### 2.7 Typography System (Self-Hosted)
The design contrasts an organic handwritten script with a clean geometric sans-serif:
- **Display Script**: Configurable script font (candidates: Great Vibes, Alex Brush, Sacramento, Allison, Whisper) used for "Birthday Party" and the honoree name
- **Body & Metadata**: Montserrat (weights 300, 400, 500, 600, 700) with generous letter-spacing for dates, labels, and copy
- **Self-Hosted Invariant**: All web fonts are bundled and served from `/birthday/fonts/` (WOFF2 format) to ensure deterministic rendering and zero third-party CDN dependencies

---

## 3. Guest Experience Lifecycle

```text
               PAGE LOAD
                   │
                   ▼
            CONFIG_LOADING
              │          │
         fail │          │ success
              ▼          ▼
        CONFIG_ERROR   INVITATION HERO
                             │
                      CTA click (smooth scroll)
                             │
                             ▼
                         RSVP FORM
                             │
                           submit
                             │
                             ▼
                         SUBMITTING
                             │
             ┌───────────────┼───────────────┐
             │               │               │
             ▼               ▼               ▼
          SUCCESS        DUPLICATE         ERROR
             │               │               │
             ▼               ▼               ▼
       CONFIRMATION       "¡UPS!"      "ALGO SALIÓ
        & COUNTDOWN     (duplicate)       MAL"
             │                             │
             ▼                             ▼
       MAP & LOGISTICS                  (retry)
```

---

## 4. State 1 — Invitation Hero

Displays the invitation cover in a centered 9:16 stage:

```text
┌─────────────────────────────┐
│                             │
│       Birthday Party        │  ← Display Script
│                             │
│    YOU'RE INVITED TO THE    │  ← Montserrat, tracked
│    BIRTHDAY PARTY HONORING  │
│                             │
│        Isabelle Snow        │  ← Display Script
│                             │
│       OCT      7:00 PM      │  ← Montserrat, 500
│    28 FRIDAY                │
│                             │
│                             │
│   CONFIRMA TU ASISTENCIA    │  ← CTA Button
│              ↓              │
│                             │
└─────────────────────────────┘
```

The address is intentionally omitted from the hero to focus attention on the RSVP action.

---

## 5. RSVP Call-To-Action (CTA)

Default copy:
> **CONFIRMA TU ASISTENCIA**  
> ↓

Interaction:
- Click or keyboard activation smoothly scrolls the viewport to the RSVP section
- Focus is moved to the first input field
- Fully keyboard accessible (`<button>` with visible `:focus-visible` gold ring)
- Supports `prefers-reduced-motion` (instant jump instead of smooth scroll)

---

## 6. State 2 — RSVP Form

Appears below the invitation hero section:

```text
┌─────────────────────────────┐
│                             │
│        ¿NOS VEMOS?          │
│                             │
│   NOMBRE COMPLETO           │
│   [_______________________] │
│                             │
│   TELÉFONO (MÓVIL)          │
│   [_______________________] │
│                             │
│   CORREO · OPCIONAL         │
│   [_______________________] │
│                             │
│        TE VEO AHÍ           │
│                             │
└─────────────────────────────┘
```

### Form Fields & Validation

1. **Full Name (`name`)**:
   - Required, trimmed, max 100 characters
   - Inline error: *"Por favor, ingresa tu nombre completo."*

2. **Phone Number (`phone`)**:
   - Required
   - Validated against Colombian mobile format: 10 digits starting with `3` (e.g. `300 123 4567` or `+57 300 123 4567`)
   - Normalization removes non-digits and leading `57` country code before submission
   - Inline error: *"Ingresa un número móvil válido (10 dígitos)."*

3. **Email (`email`)**:
   - Optional
   - If provided, validated against standard email format
   - Inline error: *"Ingresa un correo electrónico válido."*

4. **Submit Button (`submit_label`)**:
   - Default: *"TE VEO AHÍ"* (configurable)
   - Disables during submission to prevent double submits

---

## 7. Submission State

When submitted:
1. Inputs are disabled
2. Submit button shows loading spinner or text: *"ENVIANDO..."*
3. Form dispatches `POST /birthday/api/rsvp`
4. Evaluates the semantic response discriminator

---

## 8. State 3 — Submission Responses

### 8.1 Successful Submission & Confirmation
When backend returns `{ "result": "SUCCESS", "name": "..." }`:
- Viewport smoothly transitions into the **Confirmation Section**
- Saves a session marker in browser storage:
  ```ts
  sessionStorage.setItem('bdinvite:rsvp-submitted', JSON.stringify({
    name: data.name,
    timestamp: Date.now()
  }));
  ```
- If the guest refreshes the page during the session, the confirmation section is displayed immediately, avoiding duplicate prompt friction.

#### Visual Hierarchy & Layout:
```text
┌─────────────────────────────┐
│                             │
│                             │
│          ¡PERFECTO!         │
│                             │
│   Tu asistencia ha sido     │
│        confirmada.          │
│                             │
│       Gracias, Andrés.      │
│                             │
│            ·                │
│            ·                │
│       NOS VEMOS EN          │
│     12 : 04 : 37 : 22      │
│                             │
│            ·                │
│                             │
│          ╭──────╮           │
│        ╭─┤      ├─╮         │
│       │  │  MAP │  │        │
│        ╰─┤      ├─╯         │
│          ╰──────╯           │
│                             │
│      FRESCO RISTORANTE      │
│       514 S Brand Blvd      │
│      Glendale, CA 91204     │
│                             │
│       VER UBICACIÓN ↗       │
│                             │
└─────────────────────────────┘
```

---

## 9. Countdown Component

The countdown calculates remaining time against the event's **absolute instant** using its configured IANA timezone (`America/Bogota`):

```ts
interface EventTimeConfig {
  event_date: string;       // "2026-10-28"
  event_time: string;       // "19:00"
  event_timezone: string;   // "America/Bogota"
}
```

The countdown does **not** assume hardcoded UTC offsets. It computes the target instant in UTC using browser timezone utilities (`Intl.DateTimeFormat`):

```text
targetInstant = parseInTimezone(event_date, event_time, event_timezone)
remainingMs   = targetInstant - Date.now()
```

### Countdown Display States:
1. **Before Event** (`remainingMs > 0`):
   ```text
   NOS VEMOS EN
   12 : 04 : 37 : 22
   (Días : Horas : Min : Seg)
   ```
2. **Event Day / In Progress** (within event duration window):
   ```text
   EVENTO EN CURSO
   ```
3. **Event Concluded**:
   ```text
   EVENTO FINALIZADO
   ```

---

## 10. Map Preview & Location Details

The map is rendered as a clean, circular preview widget linked to the external navigation destination:
- **Treatment**: Circular crop (~140px diameter), subtle golden border `1px solid rgba(212, 168, 67, 0.3)`
- **Hover/Active**: Scales smoothly (`transform: scale(1.05)`), border brightens
- **Venue Copy**: Clean text block listing venue name and address
- **External Link**: Text link `VER UBICACIÓN ↗` opening `map_url` in a new tab (`target="_blank" rel="noopener noreferrer"`)
- **Asset**: Served via `map_preview_url` (pointing to `/birthday/api/map-preview.png`), dynamically generated on the backend from OpenStreetMap stitched tiles with a cache-busting timestamp `?t=...`

---

## 11. Duplicate Submission State

When backend returns `{ "result": "DUPLICATE" }`:
- Form presents the duplicate feedback message:
  > **¡UPS!**  
  > Parece que ya tenemos tus datos registrados.  
  > Si necesitas modificar tu información, ponte en contacto con nosotros.
- Does not expose existing database records or personal details
- Offers a button to return to the invitation or edit fields

---

## 12. Unexpected Error & Network Failure

When backend returns `{ "result": "ERROR" }` or fetch throws a network exception:
- Message:
  > **ALGO SALIÓ MAL**  
  > No pudimos registrar tu asistencia. Inténtalo nuevamente.
- Button: **INTENTAR DE NUEVO**
- Preserves user input values so the user does not have to retype their details

---

## 13. Particle Background Engine

Implemented on an HTML5 `<canvas>` element:
- Positioned fixed behind all page sections (`z-index: 0`, `pointer-events: none`)
- Canvas dimensions dynamically track `window.innerWidth` and `window.innerHeight`

### Particle Attributes
```ts
interface Particle {
  x: number;
  y: number;
  radius: number;          // 2px - 10px
  opacity: number;         // 0.15 - 0.7
  blur: number;            // 2px - 12px
  goldHue: number;         // Warm gold to soft amber
  vx: number;              // -0.15 to +0.15 px/frame
  vy: number;              // -0.15 to +0.15 px/frame
  twinkleSpeed: number;    // 0.005 - 0.02
  twinklePhase: number;    // 0 to 2π
}
```

### Spatial Distribution
- Weighted random distribution:
  - 40% probability: Upper-left quadrant
  - 40% probability: Lower-right quadrant
  - 20% probability: Uniformly sparse across center
- Particle density: ~120 on viewport > 768px; ~80 on mobile viewports

### Accessibility / Reduced Motion
- If `@media (prefers-reduced-motion: reduce)` is detected:
  - Renders a single static frame of particles
  - Animation loop is halted immediately
  - Smooth scroll behavior reverts to immediate jump

---

## 14. Admin Experience

Served under route `/birthday/admin` and protected at the reverse-proxy level by Authelia ForwardAuth.

### 14.1 RSVP Management Table
- **Total Count**: Live tally of confirmed invitees
- **Search Bar**: Debounced substring filtering by name, phone, or email
- **Table Columns & Interactions**:
  - **Name**: Displayed as text; converted to inline `<input>` during edit mode
  - **Phone**: Formatted as Colombian mobile (`300 123 4567`); validates 10-digit format during inline editing
  - **Email**: Displayed as text (or em-dash if omitted); validates email format during edit
  - **Submission Date/Time**: Converted from stored UTC to the event's configured timezone (`event_timezone`, e.g., `America/Bogota`) using Colombian Spanish locale (`es-CO`)
  - **Actions**:
    - **Editar**: Triggers row edit mode with Save / Cancel controls; displays inline conflict errors if the phone number is already registered
    - **Eliminar**: Opens a confirmation dialog and permanently removes the record via `DELETE /birthday/api/admin/rsvps/{id}`
- **CSV Export**: *"Descargar CSV"* button triggering `GET /birthday/api/admin/export`

### 14.2 Configuration Editor
A flat form allowing the host to edit dynamic invitation data:
- Honoree Name
- Event Date, Event Time, Event Timezone (validated against IANA database)
- Invitation Title & Intro Copy
- Venue Name & Address Lines
- Map Preview URL & External Map URL
- RSVP Button Copy & Feedback Messages

**Special Features:**
- **On-Demand Map Generation**: Button to trigger `POST /birthday/api/admin/map-preview/generate`, resolving coordinates, writing a freshly stitched OpenStreetMap tile preview to disk, and reporting resolved coordinates with timestamp cache-busting.
- **Hierarchical Text Preview**: Real-time structured preview of the invitation typographic hierarchy before saving.

---

## 15. Routing & URL Structure

The application operates with base path `/birthday/` via React Router:
- `/birthday/` → Guest experience (Invitation hero, RSVP flow, Confirmation)
- `/birthday/admin` → Admin dashboard (RSVP table, CSV export)
- `/birthday/admin/config` → Invitation configuration editor
- `*` → Redirects to `/birthday/`
