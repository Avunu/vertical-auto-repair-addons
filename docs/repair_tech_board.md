# Repair Job Board

The shop's TV: open repair jobs as color-coded cards, one column per technician plus an
Unassigned column. React 19 (with the React Compiler) and TypeScript 7, compiled by Vite
into `static/dist/`, at `/repair-tech/board/`.

## What it shows

Each card has the work order number, the customer, the vehicle's year and model, and its
appointment type's icon. A card's color is its stage's **Job Board Status**
(`repair.order.stage.board_status`, from `repair_tech_api`):

| Color         | Status                    | Default stage             |
| ------------- | ------------------------- | ------------------------- |
| Orange        | Waiting for diagnostics   | Waiting for Diagnostics   |
| Blue          | Waiting for PA inspection | Waiting for PA Inspection |
| Red           | Waiting on customer       | Waiting for Customer      |
| Yellow        | Waiting on parts          | Waiting for Parts         |
| Green         | Ready for repair          | Ready for Repair          |
| Chrome/silver | Under repair              | Under Repair              |

Stages without a board status (New, Confirmed) keep their orders off the board. Ready
for repair sorts to the top of a column, then the oldest order first.

## Job types

A card's icon comes from the order's **Appointment Type**. Set it up under the
appointment type: **Job Board Icon** (Car or Heavy truck) and **Job Board Label**, the
name the board's key gives the type (the type's name when empty). Types without an icon
leave their cards unmarked and stay out of the key. The upgrade to 18.0.1.1.0 sets
"Truck Repair" to Heavy truck and "Auto Repair" to Car.

Only today's work shows. A job scheduled for today or an earlier day stays on the board
until it is done, a job with no date yet (not booked) shows too, and a job booked for a
later day appears on its day. "Today" is the day in the time zone of the user the board
runs as, so set the TV's user to the shop's time zone.

Columns are the technicians with an open order that shows. Up to five fit in a row; more
wrap into further rows, and a column with more cards than fit pages itself every ten
seconds. The board refreshes every 30 seconds and keeps the last board on screen if a
refresh fails.

## Setting up the TV

Sign the TV's browser in as a user who can read every repair order and its stages:
member of **Inventory / User** (`stock.group_stock_user`), as a technician is. Without
it the board says "This user is not allowed to see the board" instead of showing jobs.
Open `/repair-tech/board/` and make the window full screen. The page is a stage at least
1920x1080 with the screen's shape, scaled to fill it: a 16:9 TV gets exactly 1920x1080,
and a taller screen gets a taller stage with room for more cards, so there are no empty
bars.

## Installing on an iPad

The board is an installable web app. It needs HTTPS, as any service worker does.

1. Open `/repair-tech/board/` in Safari and sign in.
2. Tap Share, then Add to Home Screen, and leave Open as Web App on.
3. Open it from the new icon. It runs in its own window, with a dark status bar and no
   Safari controls. If it asks you to sign in again, do it there: an installed app can
   keep its own session.
4. Stop the iPad from sleeping: Settings, Display & Brightness, Auto-Lock, Never. The
   board also asks to keep the screen on, which iOS honors in recent versions, but the
   setting is the dependable one. Guided Access (Settings, Accessibility) also keeps the
   board from being closed by a stray swipe.

The board is the same on a TV and an iPad. Only the stage's shape differs.

## Working on it

The data comes from `repair.order.board_jobs` ([`repair_tech_api`](repair_tech_api.md));
`frontend/api/` is generated from it.

```sh
cd repair_tech_board
pnpm install
pnpm run generate           # after changing board_jobs or its schema
pnpm run check              # tsc, and the generated files up to date
pnpm run build              # tsc, then vite build
```
