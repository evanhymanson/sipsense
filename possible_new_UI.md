# SipSense UI Review - Issues & Suggestions

Full audit of the frontend for things that would feel weird, broken, or confusing to a real user.

---

## Critical UX Issues (Users Will Notice Immediately)

### 1. Silent Failures Everywhere
Multiple actions fail without telling the user anything happened:
- **Toast/cheers reactions** (`CheckInCard.jsx:51`) - if the API call fails, the button just does nothing
- **Follow/unfollow** (`UserProfile.jsx:45`) - same silent failure pattern
- **Chat localStorage full** (`ChatSidebar.jsx:304`) - chat history silently stops saving
- **Alert mark-as-read** (`Alerts.jsx:12,17,22`) - errors caught and ignored with `.catch(() => {})`
- **User search in feed** (`Feed.jsx:20`) - search errors silently swallowed

**Suggestion:** Add toast notifications or inline error messages so users know when something goes wrong.

### 2. "Can't Toast Your Own" Is Invisible
`CheckInCard.jsx:90` - The message that you can't react to your own check-in is hidden behind a `title` attribute (hover-only). On mobile, users will just think the button is broken.

**Suggestion:** Either hide the toast button entirely on your own posts, or show a brief tooltip/snackbar when tapped.

### 3. No Retry Mechanisms
When API calls fail, users are stuck:
- **TasteQuiz** (`TasteQuiz.jsx:139`) - quiz submission fails with no way to retry; user has to refresh
- **WhiskeyDetail** - 8+ API calls fire on load; any failure shows a generic message with no retry
- **Browse page** (`Browse.jsx:306`) - generic error, no retry button

**Suggestion:** Add retry buttons on error states, or auto-retry with exponential backoff.

### 4. ScanBottle Drop Zone Not Keyboard Accessible
`ScanBottle.jsx:144-157` - The image upload area has no `role="button"` and no keyboard support. Users navigating with keyboard or assistive tech can't use the scanner at all.

**Suggestion:** Add `role="button"`, `tabIndex={0}`, and `onKeyDown` handler for Enter/Space.

### 5. No File Size Validation on Uploads
`ScanBottle.jsx` and `WhiskeyDetail.jsx` (rating photo upload) - Users can try to upload a 50MB photo with no warning. The request will just hang or fail.

**Suggestion:** Check file size before upload (e.g., max 10MB) and show a clear message.

---

## Navigation & Flow Issues

### 6. Navigation Dead-ends
- **UserProfile** - No back button or breadcrumb. User has to use browser back.
- **JourneyDetail** (`JourneyDetail.jsx:73`) - Back link goes to `/discover` but journeys aren't prominently on Discover.
- **After login** - Goes to `/` (Browse), but **after registration** goes to `/quiz`. If someone registers and then navigates away mid-quiz, there's no prompt to finish it.

**Suggestion:** Add consistent back navigation. Consider a "Finish your quiz" banner for users who skipped it.

### 7. Browse Filters Don't Persist in URL
`Browse.jsx:73-85` - Filters and search are state-only, not reflected in the URL. If a user shares a link or refreshes, all filters reset.

**Suggestion:** Sync filter state to URL query params so links are shareable and refresh-safe.

### 8. Category Tabs Overflow Without Scroll Indicator
`Browse.jsx:231-241` - On mobile, the category tab bar can overflow. There's no visual cue that more tabs exist off-screen.

**Suggestion:** Add a horizontal scroll fade/arrow indicator on the tab bar.

---

## Confusing UI Patterns

### 9. Compare Mode Is Discoverable But Confusing
- Max 3 bottles enforced silently (`Browse.jsx:167`) - user taps a 4th bottle and nothing happens
- The compare drawer header says "Compare (N/3)" but doesn't explain the limit
- No "clear all" button in the compare drawer

**Suggestion:** Show a brief "Max 3 bottles" message when limit reached. Add a "Clear all" button.

### 10. Flavor Filter Accepts Comma-separated Values But UI Doesn't Show This
`Browse.jsx:156` - The flavor filter input supports comma-separated terms, but there's no placeholder or hint explaining this.

**Suggestion:** Add placeholder text like `"e.g. vanilla, caramel"` or convert to a tag-based input.

### 11. Star Rating Uses Clickable Spans, Not a Real Input
`WhiskeyDetail.jsx:527-534` - Stars are `<span>` elements with `onClick`. Not focusable, not keyboard navigable, no ARIA role.

**Suggestion:** Use `<button>` elements with `aria-label="Rate N stars"` and proper focus styles.

### 12. Trending Sections Disappear Without Explanation
`Browse.jsx:281` - Trending and new arrivals sections auto-hide when they have no data, but users who saw them before won't understand why they vanished.

**Suggestion:** Show a "No trending whiskeys right now" message instead of hiding the section entirely.

---

## Visual & Styling Issues

### 13. Hardcoded Colors Instead of CSS Variables
Multiple components use hardcoded hex values instead of the design system variables defined in App.css:
- `ChatSidebar.css:46` - `#d19a82` instead of `var(--amber)`
- `ChatSidebar.css:96` - `#4ade80` (green) not from the palette
- `ChatSidebar.css:101,131` - `#f87171` (red) not from the palette
- `StoreLocator.css:63` - `#e05050` for error text
- `CheckInCard.css:68` - `rgba(200, 154, 43, 0.12)` instead of `var(--amber-dim)`
- `StoreMap.jsx:33` - `#c8872a` for user location circle

**Suggestion:** Replace with CSS custom properties for consistent theming and future dark/light mode support.

### 14. Badge Grid Too Wide on Small Screens
`BadgeGrid.css:3` - Uses `minmax(200px, 1fr)` which forces horizontal scroll on screens under ~450px.

**Suggestion:** Use `minmax(140px, 1fr)` or add a responsive breakpoint.

### 15. Skeleton Loading Card Has No Animation
`SkeletonCard.jsx` - Shows gray placeholder boxes but no shimmer/pulse animation, so it looks like a broken render rather than a loading state.

**Suggestion:** Add a CSS shimmer animation (`@keyframes shimmer`) to the skeleton elements.

---

## Data Consistency Issues

### 16. Category Emoji Maps Duplicated and Incomplete
The same emoji-to-category mapping is hardcoded in at least 4 files:
- `WhiskeyCard.jsx:3-14`
- `ChatSidebar.jsx:25-29`
- `Feed.jsx:7`
- `ScanBottle.jsx`

Missing categories include: "Bottled in Bond", "Grain Whiskey", "Blended Malt", etc. Any new category added to the database will show a generic fallback emoji.

**Suggestion:** Extract to a shared `constants.js` file and ensure all DB categories are covered.

### 17. Food Pairing Emoji Chain Is Fragile
`WhiskeyDetail.jsx:169-186` - A massive if/else chain maps food names to emojis. Any new pairing type from the backend will show no emoji.

**Suggestion:** Move to a lookup object or have the backend return emoji data.

### 18. Inconsistent API Field Names
Components expect different field name formats:
- `ChatSidebar.jsx` expects `rating_avg`, `price_usd` (snake_case)
- Other components sometimes use camelCase equivalents
- `BadgeGrid.jsx` handles both `b.awarded_at` and `b.awardedAt`

**Suggestion:** Standardize on one naming convention (snake_case from API, transform in the client if needed).

---

## Accessibility Issues

### 19. Modals Missing Dialog Semantics
`ReportModal.jsx`, `CompareDrawer.jsx` - No `role="dialog"`, no `aria-labelledby`, no focus trapping. Users with screen readers won't know a modal opened, and keyboard users can tab behind the modal.

**Suggestion:** Add proper ARIA dialog attributes and implement focus trapping.

### 20. Tab Components Missing Tab Semantics
`Profile.jsx:382-390`, `Feed.jsx:114-125` - Tab-like navigation uses plain `<button>` elements without `role="tablist"`, `role="tab"`, or `aria-selected`.

**Suggestion:** Add proper ARIA tab roles and manage keyboard navigation (arrow keys).

### 21. Images Missing Alt Text
- `ScanBottle.jsx:210` - Recent scan images use category emoji as alt text (not descriptive)
- `Profile.jsx:264` - Journal entry images have no alt text
- `WhiskeyCard.jsx:54` - SVG placeholder has no text alternative

**Suggestion:** Use descriptive alt text like `"Bottle of [whiskey name]"`.

### 22. Progress Dots on Quiz Are Visual-Only
`TasteQuiz.jsx:207-214` - Quiz progress shown as dots with no text or ARIA label. Screen reader users have no idea what step they're on.

**Suggestion:** Add `aria-label="Step N of 6"` or a visually hidden text label.

---

## Performance Concerns

### 23. WhiskeyDetail Fires 8+ Parallel API Calls
`WhiskeyDetail.jsx:50-70` - On page load, the component fires requests for: whiskey details, similar, blurb, ratings, pairings, price context, buy links, and watch status. On slow connections this hammers the backend.

**Suggestion:** Consolidate into fewer API calls, or lazy-load below-the-fold sections.

### 24. Journal Tab Loads Everything At Once
`Profile.jsx` - The journal tab has no pagination or virtualization. A power user with hundreds of entries will see a long load time and janky scroll.

**Suggestion:** Add pagination or virtual scrolling.

### 25. Potential Memory Leaks in ScanBottle
`ScanBottle.jsx:55,117,179` - Multiple `URL.createObjectURL()` calls. Not all paths guarantee cleanup via `URL.revokeObjectURL()`, especially on errors.

**Suggestion:** Always revoke object URLs in cleanup/finally blocks.

---

## Missing Features That Users Would Expect

### 26. No Confirmation Before Destructive Actions
- Removing from collection (`Profile.jsx:209`) - instant removal, no "Are you sure?"
- Unfollowing a user (`UserProfile.jsx`) - instant, no confirmation

**Suggestion:** Add a confirmation dialog or undo toast for destructive actions.

### 27. No Password Visibility Toggle
`Onboarding.jsx:100-101` - Password input has no show/hide toggle. Users can't verify what they typed.

**Suggestion:** Add an eye icon toggle to reveal/hide password.

### 28. No Offline/Network Error State
None of the pages handle being offline. If the user loses connection, everything just silently fails.

**Suggestion:** Add a global network status indicator and queue actions for retry.

### 29. No Pull-to-Refresh on Feed
`Feed.jsx` - The social feed has no way to refresh without scrolling to top and reloading. Mobile users expect pull-to-refresh.

**Suggestion:** Implement pull-to-refresh or an auto-refresh indicator for new posts.

### 30. Search Has No Recent/Suggested Searches
`Browse.jsx` - The search input has no history, no autocomplete, and no suggestions. Users typing partial names get no help.

**Suggestion:** Add search suggestions or recent search history from localStorage.

---

## Quick Wins (Low Effort, High Impact)

| # | Issue | Fix |
|---|-------|-----|
| 1 | Add loading spinners to buttons during API calls | Prevents double-clicks and shows progress |
| 2 | Add `cursor: pointer` to badge cards on hover | `BadgeGrid.css` - makes it clear they're interactive |
| 3 | Add placeholder text to barcode input | `ScanBottle.jsx:184` - e.g. "Enter UPC code" |
| 4 | Show password requirements below field | `Onboarding.jsx` - "Minimum 6 characters" |
| 5 | Add empty state illustrations | Replace text-only "No results" messages with friendly illustrations |
| 6 | Fix console.error leaks | Remove from production: `WhiskeyDetail.jsx:65,96,110,137,257,615`, `TasteQuiz.jsx:138`, `JourneyDetail.jsx:26,39` |
