# Shop Scheduling

Ties repair orders to `resource_booking` appointments so the shop schedules
against the aggregate availability of every technician, then commits the job
to one of them.

## What it does

- **Openings come from the whole shop.** `resource_booking` computes free
  slots as *shop hours ∩ (union of every bookable technician)*, so a slot is
  offered when **any** qualified technician is free. Their working schedule,
  time off, and any busy meeting on their calendar all subtract.
- **Assignment happens when the slot is taken.** The booking's resource
  combination is picked from whoever is actually free in that window
  (`sorted` by sequence or `random`, per appointment type), and lands on the
  repair order as its **Technician**.
- **The appointment owns the schedule.** Booking start, duration and
  technician flow onto `repair.order.schedule_date`, `planned_duration` and
  `technician_id` — including when the meeting is dragged in any calendar,
  which never passes through `resource.booking.write`.
- **A job has one appointment.** Scheduling it again moves that appointment
  instead of adding another, and placing it on the calendar again replaces
  its meeting rather than leaving the old one behind. Canceled appointments
  are archived and don't count.
- **Rescheduling from the job works too.** Changing those three fields on an
  already-scheduled repair order pushes back to the appointment, where the
  `resource_booking` constraints re-check that nobody is double-booked.
  Pending appointments are left alone: those get booked through the wizard or
  the portal, where the openings are actually offered.
- **Duration defaults to what was sold.** `book_hours` sums the flat-rate
  hours on the job's service lines, so a technician's day is consumed for as
  long as the customer was quoted. It survives placement on the calendar,
  which otherwise hands the meeting whatever the click was worth — and the
  booking takes its duration from its meeting.
- **Openings are listed in the backend, not just the portal.** "Find
  Openings" on the wizard and "Show Openings" on an appointment run the same
  computation the portal page renders — same slot grid, same modifications
  deadline — and list each opening with everyone still free for it, in the
  shop's own timezone. Taking one books it, so the answer and the booking
  cannot drift apart. The stock calendar view has no availability layer of
  its own, and nothing in Odoo Community lets one be painted on it.
- **A refused slot says why.** Upstream only explains an unbookable slot to
  the portal; everywhere else the empty resource combination surfaces as the
  `combination_required_if_event` check constraint ("The operation cannot be
  completed: Missing resource booking combination."). Here the backend answers
  like the portal does: what was asked for, and the next openings that are
  actually free.
- **Placement is refused before the database can be.** The check constraint
  is not reachable from the compute that would explain it: the availability
  search reads `calendar.event`, which flushes the booking with its meeting
  already set and no combination chosen yet, so Postgres rejects the
  half-written row from *inside* `_get_best_combination()` and the readable
  refusal never runs. Meetings are therefore checked against the openings
  before anything is written.
- **Placement happens on a week grid.** The stock meetings calendar declares
  no scale, so it opens in whatever scale the browser session last used, and a
  click in month scale creates an all-day event that fits no work interval and
  books nobody. Appointments are placed on a pinned `day,week` view with no
  all-day row.

## Models

| Model | Added |
|---|---|
| `repair.order` | `booking_ids`, `booking_id`, `booking_count`, `book_hours`, `action_shop_schedule`, `action_view_bookings` |
| `resource.booking` | `repair_id`, `vehicle_id`, `technician_id`, `action_shop_create_repair`, `action_shop_show_openings`, `_shop_openings`, `_shop_fitting_combinations`; readable refusal on `_get_best_combination`, pinned grid on `action_schedule` |
| `resource.booking.type` | `shop_repair_ok` |
| `calendar.event` | sync hook on create/write; duration forced from the booking on create; placement checked against the openings before write |
| `shop.appointment.wizard` | transient — appointment type, duration, preferred technician, look-ahead, listed openings |
| `shop.appointment.slot` | transient — one listed opening: when, and who is free for it |

## Configuration

1. One `resource.calendar` per shift pattern, in the shop's own timezone.
2. Each technician as an `hr.employee` **with a linked user**, on their shift
   calendar. Without the user link, only bookings mark them busy — their own
   meetings will not.
3. One `resource.booking.combination` per technician.
4. A `resource.booking.type` per appointment kind ("Intake / Diagnostic",
   "State Inspection", …), ticked **Shop Appointment Type**, with the
   qualified technicians' combinations attached and the shop calendar as its
   own working schedule.
5. Give shop staff the **Resource Booking / User** group — creating and
   reading appointments requires it.

Two settings decide what is offered, and neither is obvious:

- **Every technician's own calendar is intersected with the shop's**, so a
  technician left on a calendar in another timezone is bookable only where
  the two overlap. Two calendars that both read "8–12, 13–17" can share as
  little as three hours.
- **`Modifications deadline` on the appointment type is also a lead time.**
  Openings start at `now + deadline` (24 hours by default), so with a
  deadline of 24 the rest of tomorrow morning is never offered. It filters
  what is *offered*; it does not stop a manager placing an appointment inside
  it by hand.

## Known limits

- A technician is busy for the appointment window only. A job stalled waiting
  on parts does not re-block them, and a multi-day job needs either a long
  appointment or one appointment per day.
- Assignment is `sorted` or `random`, not least-loaded: neither looks at who
  already has the most hours booked that week.
- Community has no Gantt view; the shop board is the calendar view coloured
  by technician.
