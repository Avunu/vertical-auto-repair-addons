# Copyright 2026 Avunu LLC (avu.nu)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
"""The scenario itself, kept apart from the code that loads it.

Prices are rough 2026 US independent-shop numbers: parts marked up roughly
2x cost, labor billed flat rate. They are meant to look plausible on a printed
estimate, not to be a price book.
"""

# key, name, sell price / hour, cost / hour
LABOR = [
    ("labor_auto", "Shop Labor — Auto", 145.0, 42.0),
    ("labor_truck", "Labor — Heavy Truck", 165.0, 55.0),
    ("labor_diag", "Diagnostic Labor", 165.0, 48.0),
    ("diag_fee", "Diagnostic Fee", 165.0, 48.0),
    ("sublet", "Sublet Repair", 1.0, 1.0),
    ("shop_supplies", "Shop Supplies", 1.0, 0.35),
    ("disposal", "Tire / Fluid Disposal Fee", 6.0, 2.0),
]

VENDORS = [
    ("napa", "NAPA Auto Parts — Springfield"),
    ("worldpac", "WorldPac Distribution"),
    ("hdparts", "Heavy Duty Parts Warehouse"),
]

# key, name, sell, cost, vendor, lead days
PARTS = [
    ("oil_5w30", "Motor Oil 5W-30 Full Synthetic (qt)", 9.50, 4.10, "napa", 1),
    ("oil_15w40", "Motor Oil 15W-40 Diesel (gal)", 28.00, 13.50, "hdparts", 2),
    ("filter_oil", "Oil Filter — Standard", 12.75, 4.90, "napa", 1),
    ("filter_oil_hd", "Oil Filter — Heavy Duty", 38.00, 17.20, "hdparts", 3),
    ("filter_air", "Engine Air Filter", 27.50, 10.80, "napa", 1),
    ("filter_cabin", "Cabin Air Filter", 24.00, 9.20, "napa", 1),
    ("filter_fuel_hd", "Fuel Filter Kit — Diesel", 82.00, 39.00, "hdparts", 3),
    ("pads_front", "Brake Pads — Front Ceramic Set", 78.00, 31.00, "worldpac", 1),
    ("pads_rear", "Brake Pads — Rear Ceramic Set", 71.00, 28.50, "worldpac", 1),
    ("rotor_front", "Brake Rotor — Front (each)", 64.00, 26.00, "worldpac", 1),
    ("rotor_rear", "Brake Rotor — Rear (each)", 58.00, 23.50, "worldpac", 1),
    ("brake_fluid", "Brake Fluid DOT 3 (12oz)", 8.25, 3.10, "napa", 1),
    ("battery_grp24", "Battery — Group 24F 700CCA", 189.00, 96.00, "napa", 1),
    (
        "battery_grp31",
        "Battery — Group 31 950CCA (truck)",
        289.00,
        152.00,
        "hdparts",
        2,
    ),
    ("alternator", "Alternator — Remanufactured", 285.00, 141.00, "worldpac", 2),
    ("starter", "Starter — Remanufactured", 236.00, 118.00, "worldpac", 2),
    ("serp_belt", "Serpentine Belt", 42.00, 16.50, "napa", 1),
    ("tensioner", "Belt Tensioner Assembly", 96.00, 44.00, "worldpac", 2),
    ("coolant", "Coolant 50/50 Premix (gal)", 22.00, 9.40, "napa", 1),
    ("thermostat", "Thermostat & Gasket", 34.00, 13.00, "worldpac", 2),
    ("water_pump", "Water Pump", 148.00, 68.00, "worldpac", 2),
    ("spark_plug", "Spark Plug — Iridium (each)", 14.50, 5.60, "napa", 1),
    ("wiper_pair", "Wiper Blade Pair", 34.00, 13.20, "napa", 1),
    ("tire_ltx", "Tire — 265/70R17 All-Terrain", 218.00, 132.00, "worldpac", 2),
    ("tire_hd", "Tire — 295/75R22.5 Drive (truck)", 545.00, 372.00, "hdparts", 4),
    ("shock_front", "Shock Absorber — Front (each)", 92.00, 41.00, "worldpac", 2),
    ("cv_axle", "CV Axle Assembly", 158.00, 74.00, "worldpac", 2),
    ("o2_sensor", "Oxygen Sensor — Upstream", 118.00, 52.00, "worldpac", 2),
    ("air_dryer", "Air Dryer Cartridge (truck)", 132.00, 61.00, "hdparts", 3),
    ("brake_shoe_hd", "Brake Shoe Set — Truck Axle", 318.00, 168.00, "hdparts", 3),
]

# Deliberately uneven: the unstocked parts are what make a special-order
# purchase show up on a job.
ON_HAND = {
    "oil_5w30": 96,
    "oil_15w40": 24,
    "filter_oil": 40,
    "filter_oil_hd": 8,
    "filter_air": 18,
    "filter_cabin": 16,
    "pads_front": 12,
    "pads_rear": 9,
    "rotor_front": 10,
    "rotor_rear": 6,
    "brake_fluid": 24,
    "battery_grp24": 6,
    "serp_belt": 7,
    "coolant": 15,
    "spark_plug": 48,
    "wiper_pair": 20,
    "shock_front": 4,
    "filter_fuel_hd": 5,
    "battery_grp31": 2,
    # Not stocked at all -- ordered per job: alternator, starter, water_pump,
    # tensioner, thermostat, tires, cv_axle, o2_sensor, air_dryer, brake_shoe_hd
}

# Canned jobs. `actions` are the inspection recommended-actions that price
# themselves through this job in the estimate builder.
SERVICE_JOBS = [
    {
        "key": "lof_synthetic",
        "name": "Full Synthetic Oil & Filter Service",
        "description": "Up to 6 qt full synthetic, new filter, "
        "multi-point inspection, fluids topped off.",
        "pricing": "fixed",
        "price": 99.95,
        "labor": "labor_auto",
        "hours": 0.5,
        "parts": [("oil_5w30", 6), ("filter_oil", 1)],
        "actions": ["Change oil and filter"],
    },
    {
        "key": "brakes_front",
        "name": "Front Brake Service — Pads & Rotors",
        "description": "Replace front pads and rotors, clean and lubricate "
        "hardware, road test.",
        "pricing": "fixed",
        "price": 549.00,
        "labor": "labor_auto",
        "hours": 1.8,
        "parts": [("pads_front", 1), ("rotor_front", 2), ("brake_fluid", 1)],
        "actions": ["Replace front brake pads and rotors"],
    },
    {
        "key": "brakes_rear",
        "name": "Rear Brake Service — Pads & Rotors",
        "pricing": "fixed",
        "price": 498.00,
        "labor": "labor_auto",
        "hours": 1.6,
        "parts": [("pads_rear", 1), ("rotor_rear", 2)],
        "actions": ["Replace rear brake pads and rotors"],
    },
    {
        "key": "battery",
        "name": "Battery Replacement & Charging System Test",
        "pricing": "fixed",
        "price": 289.00,
        "labor": "labor_auto",
        "hours": 0.5,
        "parts": [("battery_grp24", 1)],
        "actions": ["Replace battery"],
    },
    {
        "key": "alternator",
        "name": "Alternator Replacement",
        "pricing": "computed",
        "labor": "labor_auto",
        "hours": 2.2,
        "parts": [("alternator", 1), ("serp_belt", 1)],
        "actions": ["Replace alternator"],
    },
    {
        "key": "cooling",
        "name": "Cooling System Service — Pump & Thermostat",
        "pricing": "computed",
        "labor": "labor_auto",
        "hours": 3.0,
        "parts": [("water_pump", 1), ("thermostat", 1), ("coolant", 2)],
        "actions": ["Replace water pump", "Coolant service"],
    },
    {
        "key": "serp_belt",
        "name": "Serpentine Belt & Tensioner",
        "pricing": "fixed",
        "price": 329.00,
        "labor": "labor_auto",
        "hours": 1.2,
        "parts": [("serp_belt", 1), ("tensioner", 1)],
        "actions": ["Replace serpentine belt"],
    },
    {
        "key": "air_cabin_filters",
        "name": "Engine & Cabin Air Filter Replacement",
        "pricing": "fixed",
        "price": 129.00,
        "labor": "labor_auto",
        "hours": 0.4,
        "parts": [("filter_air", 1), ("filter_cabin", 1)],
        "actions": ["Replace engine air filter", "Replace cabin air filter"],
    },
    {
        "key": "tires_at",
        "name": "Four Tire Replacement & Alignment — Light Truck",
        "pricing": "computed",
        "labor": "labor_auto",
        "hours": 2.5,
        # The disposal fee is a service, not a part, so it rides on the labor
        # side of the job rather than in the parts list.
        "parts": [("tire_ltx", 4)],
        "actions": ["Replace tires"],
    },
    {
        "key": "pm_a_truck",
        "name": "PM Service A — Class 8 Tractor",
        "description": "Full-synthetic-blend oil and filters, chassis lube, "
        "annual DOT inspection items, air dryer check.",
        "pricing": "computed",
        "labor": "labor_truck",
        "hours": 3.5,
        "parts": [("oil_15w40", 11), ("filter_oil_hd", 1), ("filter_fuel_hd", 1)],
        "actions": ["Perform PM service"],
    },
    {
        "key": "brakes_truck",
        "name": "Truck Brake Service — One Axle",
        "pricing": "computed",
        "labor": "labor_truck",
        "hours": 4.5,
        "parts": [("brake_shoe_hd", 1), ("air_dryer", 1)],
        "actions": ["Replace truck brake shoes"],
    },
    # The next three exist mostly so that "future" and "needs attention"
    # findings have something to price with. Without a job behind the
    # recommended action, a finding cannot become an optional line on the
    # quote, and the customer has nothing to opt into from the portal.
    {
        "key": "wipers",
        "name": "Wiper Blade Replacement",
        "pricing": "fixed",
        "price": 59.00,
        "labor": "labor_auto",
        "hours": 0.2,
        "parts": [("wiper_pair", 1)],
        "actions": ["Replace wiper blades"],
    },
    {
        "key": "shocks_front",
        "name": "Front Shock Replacement — Pair",
        "pricing": "computed",
        "labor": "labor_auto",
        "hours": 1.5,
        "parts": [("shock_front", 2)],
        "actions": ["Replace front shocks"],
    },
    {
        "key": "bulb",
        "name": "Exterior Bulb Replacement",
        "pricing": "fixed",
        "price": 45.00,
        "labor": "labor_auto",
        "hours": 0.3,
        "actions": ["Replace exterior bulb"],
    },
    {
        "key": "diag_driveability",
        "name": "Driveability Diagnosis (1 hour)",
        "description": "Scan, verify concern, targeted testing, written findings.",
        "pricing": "fixed",
        "price": 165.00,
        "labor": "labor_diag",
        "hours": 1.0,
        "actions": ["Diagnose check engine light"],
    },
]

# key, name, login, is_service_advisor
STAFF = [
    ("tech_ramirez", "Luis Ramirez", "luis.ramirez@usademo.example.com", False),
    ("tech_okafor", "Grace Okafor", "grace.okafor@usademo.example.com", False),
    ("tech_bell", "Travis Bell", "travis.bell@usademo.example.com", False),
    ("advisor_shaw", "Dana Shaw", "dana.shaw@usademo.example.com", True),
]

# key, name, duration in hours
BOOKING_TYPES = [
    ("intake_diag", "Intake / Diagnostic", 1.0),
    ("light_repair", "Light Repair", 2.0),
    ("heavy_repair", "Heavy Repair", 6.0),
    ("pm_service", "PM Service — Fleet", 4.0),
]

CUSTOMERS = [
    {
        "key": "hartley",
        "name": "Megan Hartley",
        "phone": "+1 417 555 0142",
        "email": "megan.hartley@example.com",
        "street": "418 W Elm St",
    },
    {
        "key": "doyle",
        "name": "Sean Doyle",
        "phone": "+1 417 555 0187",
        "email": "sean.doyle@example.com",
        "street": "2210 S Kimbrough Ave",
    },
    {
        "key": "whitfield",
        "name": "Alice Whitfield",
        "phone": "+1 417 555 0119",
        "email": "alice.whitfield@example.com",
        "street": "77 Cherry Hill Rd",
    },
    {
        "key": "nakamura",
        "name": "Kenji Nakamura",
        "phone": "+1 417 555 0164",
        "email": "kenji.nakamura@example.com",
        "street": "905 E Battlefield Rd",
    },
    {
        "key": "obrien",
        "name": "Patricia O'Brien",
        "phone": "+1 417 555 0173",
        "email": "patricia.obrien@example.com",
        "street": "1544 N Glenstone Ave",
    },
    {
        "key": "vasquez",
        "name": "Hector Vasquez",
        "phone": "+1 417 555 0198",
        "email": "hector.vasquez@example.com",
        "street": "63 Sunset St",
    },
    {
        "key": "ferreira",
        "name": "Bianca Ferreira",
        "phone": "+1 417 555 0155",
        "email": "bianca.ferreira@example.com",
        "street": "3320 S Campbell Ave",
    },
    {
        "key": "kowalski",
        "name": "Ed Kowalski",
        "phone": "+1 417 555 0126",
        "email": "ed.kowalski@example.com",
        "street": "812 W Chestnut Expy",
    },
    {
        "key": "greenlawn",
        "name": "Greenlawn Landscaping LLC",
        "is_company": True,
        "phone": "+1 417 555 0210",
        "email": "fleet@greenlawn.example.com",
        "street": "4100 W Kearney St",
    },
    {
        "key": "ozark",
        "name": "Ozark Freight Lines",
        "is_company": True,
        "phone": "+1 417 555 0233",
        "email": "maintenance@ozarkfreight.example.com",
        "street": "5500 E Division St",
    },
    {
        "key": "bluecreek",
        "name": "Blue Creek Plumbing & Heating",
        "is_company": True,
        "phone": "+1 417 555 0245",
        "email": "shop@bluecreek.example.com",
        "street": "1207 N Boonville Ave",
    },
    {
        "key": "cityparks",
        "name": "Example City — Parks Dept",
        "is_company": True,
        "phone": "+1 417 555 0266",
        "email": "fleet@cityparks.example.com",
        "street": "100 Example Park Rd",
    },
]

# key, catalog model xml id, year, plate, VIN (real check digit, decodes on vPIC),
# odometer, owner, colour
VEHICLES = [
    (
        "accord_hartley",
        "model_honda_accord",
        2015,
        "MO 7HX-421",
        "1HGCR2F39FA801742",
        118_450,
        "hartley",
        "Silver",
    ),
    (
        "camry_doyle",
        "model_toyota_camry",
        2018,
        "MO 4CN-909",
        "4T1B11HK2JU512883",
        74_920,
        "doyle",
        "White",
    ),
    (
        "civic_whitfield",
        "model_honda_civic",
        2012,
        "MO 2LP-338",
        "2HGFB2F59CH534196",
        164_300,
        "whitfield",
        "Blue",
    ),
    (
        "outback_nakamura",
        "model_subaru_outback",
        2019,
        "MO 9RT-118",
        "4S4BSANC0K3288451",
        61_740,
        "nakamura",
        "Green",
    ),
    (
        "escape_obrien",
        "model_ford_escape",
        2016,
        "MO 5DK-702",
        "1FMCU9GXXGUB21447",
        98_615,
        "obrien",
        "Red",
    ),
    (
        "rav4_vasquez",
        "model_toyota_rav4",
        2020,
        "MO 8WQ-556",
        "2T3P1RFV9LW063312",
        42_880,
        "vasquez",
        "Grey",
    ),
    (
        "altima_ferreira",
        "model_nissan_altima",
        2014,
        "MO 3BM-274",
        "1N4AL3AP1EC119275",
        141_020,
        "ferreira",
        "Black",
    ),
    (
        "silverado_kowalski",
        "model_chevrolet_silverado",
        2017,
        "MO 6TF-863",
        "3GCUKREC3HG214880",
        112_305,
        "kowalski",
        "Black",
    ),
    (
        "wrangler_hartley",
        "model_jeep_wrangler",
        2013,
        "MO 1JW-445",
        "1C4AJWAG4DL616093",
        132_770,
        "hartley",
        "Orange",
    ),
    (
        "elantra_doyle",
        "model_hyundai_elantra",
        2021,
        "MO 7EL-201",
        "5NPLL4AG5MH037724",
        31_240,
        "doyle",
        "White",
    ),
    (
        "model3_nakamura",
        "model_tesla_model_3",
        2018,
        "MO 0EV-333",
        "5YJ3E1EA8JF000000",
        68_990,
        "nakamura",
        "Blue",
    ),
    (
        "prius_whitfield",
        "model_toyota_prius",
        2010,
        "MO 2HY-887",
        "JTDKN3DU5A0142208",
        208_460,
        "whitfield",
        "Silver",
    ),
    (
        "f250_bluecreek",
        "model_ford_f_250",
        2019,
        "MO BC-1140",
        "1FT7W2BT4KEC55031",
        87_330,
        "bluecreek",
        "White",
    ),
    (
        "ram2500_greenlawn",
        "model_ram_2500",
        2017,
        "MO GL-2201",
        "3C6UR5CL2HG712664",
        103_775,
        "greenlawn",
        "White",
    ),
    (
        "transit_greenlawn",
        "model_ford_transit",
        2020,
        "MO GL-2202",
        "1FTYE1YM3LKA33018",
        58_410,
        "greenlawn",
        "White",
    ),
    (
        "f350_cityparks",
        "model_ford_f_350",
        2014,
        "MO CP-0087",
        "1FT8W3BT0EEA88276",
        149_620,
        "cityparks",
        "Green",
    ),
    (
        "cascadia_ozark",
        "model_freightliner_cascadia",
        2016,
        "MO OZ-4410",
        "3AKJGLD53GSHF9902",
        612_400,
        "ozark",
        "Red",
    ),
    (
        "t680_ozark",
        "model_kenworth_t680",
        2015,
        "MO OZ-4411",
        "1XKYDP9X0FJ445667",
        738_155,
        "ozark",
        "Blue",
    ),
    (
        "anthem_ozark",
        "model_mack_anthem",
        2019,
        "MO OZ-4412",
        "1M1AN4GY1KKM01234",
        402_880,
        "ozark",
        "Black",
    ),
    (
        "intl_ozark",
        "model_international_ma025",
        2018,
        "MO OZ-4413",
        "1HTMMAAL5JH445120",
        288_310,
        "ozark",
        "White",
    ),
    (
        "hino_bluecreek",
        "model_hino_conventional_type_truck",
        2018,
        "MO BC-1141",
        "5PVNJ8JTXJJ8S5002",
        174_905,
        "bluecreek",
        "White",
    ),
]

VEHICLES = [
    {
        "key": key,
        "model": model,
        "year": year,
        "plate": plate,
        "vin": vin,
        "odometer": odo,
        "owner": owner,
        "color": color,
    }
    for key, model, year, plate, vin, odo, owner, color in VEHICLES
]


# ---------------------------------------------------------------------------
# The job lifecycle. One entry per repair order, spread across every stage a
# shop actually has work sitting in on any given day.
#
# stage:  booked        -> written up and on the calendar, nothing committed
#         quoted        -> inspected, estimate out, waiting on the customer
#         waiting_parts -> approved and confirmed, part on order
#         in_bay        -> work under way, hours logged, some parts consumed
#         invoiced      -> finished, invoiced, (usually) paid
#         declined      -> customer said no; they still owe the diagnostic fee
#
# findings map an inspection item name to (severity, recommended action, note).
# Anything not listed grades "good", which is what a real checklist looks like.
# ---------------------------------------------------------------------------

SCENARIOS = [
    # -- finished and paid ---------------------------------------------------
    {
        "booking": "light_repair",
        "hour": 9,
        "key": "accord_brakes",
        "vehicle": "accord_hartley",
        "stage": "invoiced",
        "day_offset": -47,
        "miles_since": 1_240,
        "concern": "Grinding noise from the front when braking, and the pedal "
        "pulses at highway speed.",
        "inspection": {
            "template": "Courtesy Inspection",
            "findings": [
                (
                    "Tires & Wheels",
                    ("future", "Replace tires", '5/32" front, 6/32" rear.'),
                ),
                ("Brake Fluid", ("attention", None, "Dark, due for a flush.")),
            ],
        },
        "parts": [("pads_front", 1), ("rotor_front", 2), ("brake_fluid", 1)],
        "labor": [("labor_auto", 1.8, "Front brake service — pads and rotors")],
        "timesheets": [
            (-47, 1.5, "R&R front pads and rotors"),
            (-47, 0.4, "Road test"),
        ],
    },
    {
        "booking": "light_repair",
        "hour": 8,
        "key": "camry_lof",
        "vehicle": "camry_doyle",
        "stage": "invoiced",
        "day_offset": -31,
        "miles_since": 890,
        "concern": "Due for an oil change; also asked us to look at a slow "
        "leak in the right front tire.",
        "inspection": {
            "template": "Courtesy Inspection",
            "findings": [
                (
                    "Engine Air Filter",
                    ("future", "Replace engine air filter", "Dirty but serviceable."),
                ),
            ],
        },
        "parts": [("oil_5w30", 6), ("filter_oil", 1)],
        "labor": [("labor_auto", 0.5, "Full synthetic oil and filter service")],
        "timesheets": [(-31, 0.4, "LOF and multi-point")],
    },
    {
        "booking": "pm_service",
        "hour": 7,
        "key": "cascadia_pm",
        "vehicle": "cascadia_ozark",
        "stage": "invoiced",
        "day_offset": -22,
        "miles_since": 4_100,
        "concern": "Scheduled PM service. Driver reports air dryer purging "
        "more often than usual.",
        "inspection": {
            "template": "State Safety Inspection",
            "findings": [
                (
                    "Brake Lining - Rotors / Drums",
                    ("future", None, 'Drive axle linings at 8/32".'),
                ),
            ],
        },
        "parts": [
            ("oil_15w40", 11),
            ("filter_oil_hd", 1),
            ("filter_fuel_hd", 1),
            ("air_dryer", 1),
        ],
        "labor": [
            ("labor_truck", 3.5, "PM Service A — Class 8 tractor"),
            ("labor_truck", 0.8, "Air dryer cartridge replacement"),
        ],
        "timesheets": [(-22, 3.2, "PM A service"), (-22, 0.9, "Air dryer cartridge")],
    },
    {
        "booking": "light_repair",
        "hour": 10,
        "key": "escape_battery",
        "vehicle": "escape_obrien",
        "stage": "invoiced",
        "day_offset": -14,
        "miles_since": 310,
        "concern": "Wouldn't start Tuesday morning; had to get a jump.",
        "inspection": {
            "template": "Courtesy Inspection",
            "findings": [
                (
                    "Battery",
                    (
                        "today",
                        "Replace battery",
                        "Tested 312 CCA against 700 rated. Failed.",
                    ),
                ),
                (
                    "Belts",
                    (
                        "future",
                        "Replace serpentine belt",
                        "Fine cracking on the ribbed side.",
                    ),
                ),
            ],
        },
        "parts": [("battery_grp24", 1)],
        "labor": [("labor_auto", 0.5, "Battery replacement and charging system test")],
        "timesheets": [(-14, 0.6, "Battery test and replacement")],
    },
    {
        "booking": "light_repair",
        "hour": 13,
        "key": "f250_tires",
        "vehicle": "f250_bluecreek",
        "stage": "invoiced",
        "day_offset": -9,
        "miles_since": 640,
        "concern": "Fleet request — four tires and an alignment before winter.",
        "parts": [("tire_ltx", 4), ("disposal", 4)],
        "labor": [("labor_auto", 2.5, "Mount, balance four tires and align")],
        "timesheets": [(-9, 2.3, "Four tires mounted and balanced, alignment")],
    },
    {
        "booking": "heavy_repair",
        "hour": 8,
        "key": "prius_coolant",
        "vehicle": "prius_whitfield",
        "stage": "invoiced",
        "day_offset": -5,
        "miles_since": 120,
        "paid": False,
        "concern": "Temperature gauge climbing in stop-and-go traffic, and "
        "there's a sweet smell after parking.",
        "inspection": {
            "template": "Courtesy Inspection",
            "findings": [
                (
                    "Antifreeze / Coolant",
                    ("today", "Replace water pump", "Weeping from the pump seal."),
                ),
                (
                    "Fluid Leak(s)",
                    ("today", None, "Coolant residue on the block below the pump."),
                ),
            ],
        },
        "parts": [("water_pump", 1), ("thermostat", 1), ("coolant", 2)],
        "labor": [("labor_auto", 3.0, "Water pump and thermostat replacement")],
        "timesheets": [
            (-6, 2.0, "Pump R&R"),
            (-5, 1.2, "Refill, bleed, pressure test"),
        ],
    },
    # -- in the bay right now ------------------------------------------------
    {
        "booking": "light_repair",
        "hour": 9,
        "key": "silverado_alt",
        "vehicle": "silverado_kowalski",
        "stage": "in_bay",
        "day_offset": 0,
        "concern": "Battery light flickers at idle and the headlights dim when "
        "the A/C kicks on.",
        "inspection": {
            "template": "Courtesy Inspection",
            "findings": [
                (
                    "Battery",
                    (
                        "attention",
                        None,
                        "Battery tests good; charging system is the fault.",
                    ),
                ),
                ("Belts", ("today", "Replace serpentine belt", "Glazed and slipping.")),
            ],
        },
        "parts": [("alternator", 1), ("serp_belt", 1)],
        "labor": [("labor_auto", 2.2, "Alternator replacement")],
        "timesheets": [(0, 1.5, "Alternator R&R, belt")],
    },
    {
        "booking": "heavy_repair",
        "hour": 7,
        "key": "t680_brakes",
        "vehicle": "t680_ozark",
        "stage": "in_bay",
        "day_offset": 0,
        "concern": "Pulls right under hard braking. Due for annual DOT "
        "inspection while it's here.",
        "inspection": {
            "template": "State Safety Inspection",
            "findings": [
                (
                    "Brake Lining - Rotors / Drums",
                    (
                        "fail_state",
                        "Replace truck brake shoes",
                        'Steer axle linings at 2/32". Out of service.',
                    ),
                ),
                (
                    "Steering & Suspension",
                    ("future", None, "Drag link has slight play; monitor."),
                ),
            ],
        },
        "parts": [("brake_shoe_hd", 1)],
        "labor": [
            ("labor_truck", 4.5, "Steer axle brake service"),
            ("labor_truck", 1.0, "Annual DOT inspection"),
        ],
        "timesheets": [(0, 3.0, "Steer axle shoes and drums")],
    },
    # -- approved, waiting on a part ----------------------------------------
    {
        "booking": "light_repair",
        "hour": 10,
        "key": "altima_cv",
        "vehicle": "altima_ferreira",
        "stage": "waiting_parts",
        "day_offset": 1,
        "concern": "Clicking on tight left turns, getting worse over the last month.",
        "inspection": {
            "template": "Courtesy Inspection",
            "findings": [
                (
                    "Fluid Leak(s)",
                    (
                        "today",
                        None,
                        "Torn outer CV boot, grease slung inside the wheel.",
                    ),
                ),
                (
                    "Strut(s) / Shock(s)",
                    ("future", None, "Front struts weeping lightly."),
                ),
            ],
        },
        "parts": [("cv_axle", 1)],
        "labor": [("labor_auto", 1.8, "Front CV axle replacement")],
        "notes": "Axle on order from WorldPac, ETA tomorrow AM. Customer knows.",
    },
    # -- estimate out, waiting on the customer -------------------------------
    {
        "booking": "intake_diag",
        "hour": 11,
        "key": "wrangler_estimate",
        "vehicle": "wrangler_hartley",
        "stage": "quoted",
        "day_offset": 0,
        "estimate": "sent",
        "concern": "Check engine light came on last week. Running rough at idle.",
        "inspection": {
            "template": "Courtesy Inspection",
            "findings": [
                (
                    "Engine Oil",
                    (
                        "today",
                        "Change oil and filter",
                        "5,800 miles over the interval.",
                    ),
                ),
                (
                    "Engine Air Filter",
                    ("today", "Replace engine air filter", "Packed with dust."),
                ),
                (
                    "Windshield Wipers",
                    (
                        "future",
                        "Replace wiper blades",
                        "Streaking, chattering on the return.",
                    ),
                ),
                (
                    "Strut(s) / Shock(s)",
                    ("attention", "Replace front shocks", "Right front shock leaking."),
                ),
            ],
        },
        "labor": [("diag_fee", 1.0, "Diagnostic — check engine light")],
        "timesheets": [(0, 1.0, "Scan, verify, targeted testing")],
    },
    {
        "booking": "intake_diag",
        "hour": 13,
        "key": "outback_estimate",
        "vehicle": "outback_nakamura",
        "stage": "quoted",
        "day_offset": 0,
        "estimate": "sent",
        "concern": "Here for a state safety inspection and whatever it needs to pass.",
        "inspection": {
            "template": "State Safety Inspection",
            "findings": [
                (
                    "Brake Lining - Rotors / Drums",
                    (
                        "fail_state",
                        "Replace rear brake pads and rotors",
                        "Rear pads at 2mm, rotors below discard.",
                    ),
                ),
                (
                    "Exterior Lights",
                    ("today", "Replace exterior bulb", "Left rear turn signal out."),
                ),
                (
                    "Windows - Glazing - Mirrors",
                    ("future", None, "Chip in the windshield, out of the sweep."),
                ),
                (
                    "Body - Doors - Latches - Seat Belts",
                    (
                        "future",
                        "Replace wiper blades",
                        "Wipers hardened, will not pass next year.",
                    ),
                ),
            ],
        },
        "labor": [("labor_auto", 0.5, "State safety inspection")],
    },
    # -- inspection done, estimate not built yet -----------------------------
    {
        "booking": "intake_diag",
        "hour": 15,
        "key": "rav4_inspection",
        "vehicle": "rav4_vasquez",
        "stage": "quoted",
        "day_offset": 0,
        "concern": "Routine service before a road trip to Colorado. Please "
        "check everything over.",
        "inspection": {
            "template": "Courtesy Inspection",
            "findings": [
                (
                    "Tires & Wheels",
                    (
                        "future",
                        "Replace tires",
                        '4/32" all round, will not last the winter.',
                    ),
                ),
                ("Brake Fluid", ("future", None, "Moisture test at 2.8%.")),
                ("Windshield Wipers", ("today", None, "Torn on the driver's side.")),
            ],
        },
        "labor": [("labor_auto", 0.5, "Full synthetic oil and filter service")],
        "parts": [("oil_5w30", 5), ("filter_oil", 1)],
    },
    # -- written up and on the calendar --------------------------------------
    {
        "booking": "intake_diag",
        "hour": 9,
        "key": "civic_booked",
        "vehicle": "civic_whitfield",
        "stage": "booked",
        "day_offset": 1,
        "concern": "A/C blows warm once the car has been sitting in the sun.",
    },
    {
        "booking": "light_repair",
        "hour": 11,
        "key": "elantra_booked",
        "vehicle": "elantra_doyle",
        "stage": "booked",
        "day_offset": 2,
        "concern": "First service — oil change and tire rotation.",
    },
    {
        "booking": "pm_service",
        "hour": 8,
        "key": "transit_booked",
        "vehicle": "transit_greenlawn",
        "stage": "booked",
        "day_offset": 2,
        "concern": "Fleet PM. Driver notes the sliding door sticks in the cold.",
    },
    {
        "booking": "pm_service",
        "hour": 7,
        "key": "anthem_booked",
        "vehicle": "anthem_ozark",
        "stage": "booked",
        "day_offset": 3,
        "concern": "PM service and DOT annual. Also check the APU — driver "
        "says it shuts down overnight.",
    },
    {
        "booking": "heavy_repair",
        "hour": 8,
        "key": "f350_booked",
        "vehicle": "f350_cityparks",
        "stage": "booked",
        "day_offset": 4,
        "concern": "Plow truck prep before the season. Full going-over.",
    },
    # -- customer declined; diagnostic fee still owed -------------------------
    {
        # Left at "quoted" rather than "declined" on purpose. The decline path
        # calls repair.order.action_repair_cancel, which OCA
        # repair_quality_control overrides to read `inspection_ids` as
        # qc.inspection records -- but shop_inspection redefines that same
        # field as fleet.vehicle.inspection and wins the override. The result
        # is AttributeError on every cancel (the method does not exist on the
        # model at all, so even an empty recordset raises), and any draft DVI
        # gets unlinked on the way. Seeding a cancelled order would mean
        # writing the state by hand, which would hide a broken workflow rather
        # than show it. Flip this back to "declined" once the collision is
        # resolved -- the seeder already handles that stage.
        "booking": "intake_diag",
        "hour": 14,
        "key": "intl_declined",
        "vehicle": "intl_ozark",
        "stage": "quoted",
        "day_offset": -3,
        "estimate": "sent",
        "concern": "Low power under load and black smoke on a grade.",
        "inspection": {
            "template": "State Safety Inspection",
            "findings": [
                (
                    "Road Test",
                    (
                        "today",
                        "Diagnose check engine light",
                        "Derate active, boost pressure low.",
                    ),
                ),
                (
                    "Engine / Transmission Mounts",
                    (
                        "future",
                        "Replace front shocks",
                        "Front mount collapsing; quoting mount work as optional.",
                    ),
                ),
            ],
        },
        "labor": [("diag_fee", 2.0, "Diagnostic — low power / derate")],
        "notes": "Customer is moving the unit to the dealer under warranty and "
        "intends to decline. Diagnostic time still billable.",
        "timesheets": [(-3, 2.0, "Diagnostic — derate and boost testing")],
    },
]
