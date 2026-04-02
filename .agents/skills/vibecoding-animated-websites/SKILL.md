---
name: vibecoding-animated-websites
description: Builds high-end, animated websites with a focus on aesthetics, semantic HTML, and accessibility. Use when the user wants to "vibecode", create an "animated website", or use the "Noir Luxe" style workflow.
---

# Vibecoding Animated Websites

## When to use this skill
- When the user asks to "vibecode" or build an "animated website".
- When the user wants a high-end, luxury, or purely aesthetic-driven web experience.
- When the user references "Antigravity", "Google Whisk", or "Google Flow" in the context of web design.

## Workflow
- [ ] **Step 1: Research & Mood Boarding**
    - [ ] Ask for or specify the business, aesthetic, and specific colors if not provided.
    - [ ] Acquire reference images (screenshots of 3-5 high-end websites).
- [ ] **Step 2: Project Setup & Custom Rules**
    - [ ] Initialize project with semantic HTML5, 8px grid, preferred-reduced-motion, and CSS variable colors.
- [ ] **Step 3: Initial Build**
    - [ ] Execute the Initial Build Prompt with user's specific details.
- [ ] **Step 4: Hero Asset Creation**
    - [ ] Generate "Starting State" image.
    - [ ] Generate "End State" image (same subject, chaotic/dynamic).
- [ ] **Step 5: Animation Generation**
    - [ ] Create transition animation between states.
- [ ] **Step 6: Asset Conversion**
    - [ ] Convert video to image sequence.
- [ ] **Step 7: Implementation**
    - [ ] Implement scroll-controlled animation using image sequence.
- [ ] **Step 8: Refinement**
    - [ ] Add Dark/Light mode toggle.
    - [ ] Polish features, testimonials, and typography.

## Instructions

### 1. Research & Inputs
**CRITICAL**: If the user has NOT provided the following, you MUST ask for them before proceeding:
1.  **Business Name/Type**
2.  **Desired Aesthetic** (e.g., Luxury, Minimalist, Cyberpunk)
3.  **Color Palette**

*Action*: Study reference images or search for "luxury website design trends" to inform the "vibe".

### 2. Custom Rules (Apply to all prompts)
Apply these rules to all generation steps:
1.  **Semantic HTML5**: Use `<header>`, `<main>`, `<section>`, `<article>`, `<footer>`.
2.  **8px Grid**: All margins/paddings must be multiples of 8px (e.g., `16px`, `32px`, `64px`).
3.  **Accessibility**:
    *   `@media (prefers-reduced-motion: reduce)` must be respected.
    *   Use high contrast for text.
4.  **Theming**: Use CSS variables (`--color-bg`, `--color-text`, `--color-accent`) for all colors.

### 3. Prompts & Templates

#### Initial Build Prompt
Use this template for the first code generation:
```text
Create a landing page for [Business Name]. [Aesthetic] aesthetic.
Colors: [Specific Colors].
Rules: Semantic HTML, 8px grid, CSS vars.
Sections:
- Hero (Headline + CTA)
- Features (Craftsmanship/Details)
- Testimonials
- Final CTA
Typography: [Elegant/Bold/Modern]
```

#### Hero Image Generation (Google Whisk / Image Gen Tool)
*State 1 (Static)*:
```text
[Product/Object] wrapped/still, [Background Color] background, studio lighting, high definition, [Aesthetic] style.
```

*State 2 (Dynamic)*:
```text
[Product/Object] exploding/unwrapping/in-motion, particles flying, [Background Color] background, dramatic, chaotic, beautiful.
```

#### Animation Prompt (Google Flow / Video Gen Tool)
```text
Smooth, cinematic transition showing [Product] changing from [State 1] to [State 2].
```

### 4. Implementation Details
- **Image Sequence**: Do not use large video files for scroll effects. Use a sequence of JPEGs loaded into a `<canvas>` or cycled via `<img>` src based on scroll position.
- **Dark/Light Mode**:
    *   Add a toggle button.
    *   Use JS to toggle a `dark-mode` class on `<body>`.
    *   Update CSS variables based on the class.

### 5. Final Polish
- Slow down animations if they feel frantic.
- Ensure type hierarchies are distinct (H1 vs H2 vs Body).
- Add "social proof" elements to the Testimonials section.
